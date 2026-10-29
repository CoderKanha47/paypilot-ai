"""AI assistant endpoints.

DB reads happen in a worker thread; the provider HTTP call runs on the main
event loop. The model never receives a tool and can never move money.
"""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..config import Settings
from ..deps import get_ai_provider, get_db, get_settings
from ..errors import AIProviderError, service_unavailable
from ..logging_config import log_extra
from ..rate_limit import SlidingWindowLimiter, rate_limit
from ..schemas import AssistantSuggestionsResponse, ChatRequest, ChatResponse
from ..services.assistant import (
    SUGGESTIONS,
    build_context,
    build_prompt,
    validate_response,
)

logger = logging.getLogger("paypilot.api.assistant")

router = APIRouter(prefix="/assistant", tags=["assistant"])

_chat_limiter = SlidingWindowLimiter(max_requests=15, window_seconds=60)


@router.get(
    "/suggestions", response_model=AssistantSuggestionsResponse, summary="Example questions"
)
def suggestions() -> AssistantSuggestionsResponse:
    return AssistantSuggestionsResponse(suggestions=list(SUGGESTIONS))


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask the assistant a question about your payment data",
)
async def chat(
    request: Request,
    payload: ChatRequest,
    session: Session = Depends(get_db),
    provider=Depends(get_ai_provider),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    rate_limit(request, _chat_limiter)
    history = [{"role": m.role, "content": m.content} for m in payload.history]

    # 1. Read rows + compute every total outside the event loop.
    context = await asyncio.to_thread(build_context, session, settings, payload.message)
    prompt = build_prompt(context, history)

    # 2. Call the provider.
    started = time.perf_counter()
    try:
        raw = await provider.complete(
            system=_system_prompt(), user=prompt, timeout=settings.ai_timeout_seconds
        )
    except AIProviderError as exc:
        logger.warning(
            "Assistant provider call failed",
            extra=log_extra(provider=exc.provider, retryable=exc.retryable),
        )
        if exc.retryable:
            raise service_unavailable(
                f"The assistant could not complete the request: {exc.message}",
                code="ai_timeout",
                provider=exc.provider,
                retry_after=15,
            ) from exc
        raise service_unavailable(
            f"The assistant is misconfigured: {exc.message}",
            code="ai_not_configured",
            provider=exc.provider,
        ) from exc

    latency_ms = int((time.perf_counter() - started) * 1000)

    # 3. Validate, filtering references and checking for leaked secrets.
    try:
        result = validate_response(
            raw,
            context,
            provider=provider.name,
            mode="live" if provider.live else "demo",
            latency_ms=latency_ms,
        )
    except AIProviderError:
        if not provider.live:
            raise
        # One corrective retry, then surface a clear error.
        try:
            raw_retry = await provider.complete(
                system=_system_prompt() + "\nReturn ONLY the JSON object. No markdown.",
                user=prompt,
                timeout=settings.ai_timeout_seconds,
            )
            result = validate_response(
                raw_retry,
                context,
                provider=provider.name,
                mode="live",
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        except AIProviderError as exc:
            logger.warning("Assistant response validation failed twice",
                           extra=log_extra(provider=exc.provider))
            raise service_unavailable(
                f"The assistant returned an unusable response: {exc.message}",
                code="ai_invalid_response",
                provider=exc.provider,
                retry_after=10,
            ) from exc

    if not provider.live:
        result["notice"] = (
            "Demo mode: this answer came from a deterministic rule engine reading your "
            "recorded data — not from a language model. Set AI_PROVIDER and an API key to "
            "use a real model."
        )

    logger.info(
        "Assistant answered a question",
        extra=log_extra(
            provider=provider.name,
            mode=result["mode"],
            intent=context.intent,
            latency_ms=result["latency_ms"],
            records=context.payload["record_count"],
        ),
    )
    return ChatResponse(**result)


def _system_prompt() -> str:
    from ..services.assistant import SYSTEM_PROMPT

    return SYSTEM_PROMPT
