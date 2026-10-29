"""Interchangeable AI provider layer.

Three live providers (``openai``, ``anthropic``, ``openai_compatible`` for any
OpenAI-style endpoint such as Ollama, LM Studio, Groq or Together) plus an
explicitly labelled **demo** provider.

Important
---------
The demo provider never claims to be a language model. Its answers are derived
deterministically from the exact figures the backend computed, and every
response carries ``mode="demo"`` so the UI can label it.

No provider is given a tool, a URL, or any ability to move money: the model can
only read the small, PII-minimised context it is handed and return text.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx

from ..config import Settings
from ..errors import AIProviderError
from ..logging_config import log_extra

logger = logging.getLogger("paypilot.ai")

CONTEXT_START = "<transaction_context>"
CONTEXT_END = "</transaction_context>"


class AIProvider(ABC):
    """Common interface for every backend we support."""

    name: str = "base"
    live: bool = False

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    def is_configured(self) -> bool:
        """True when the provider has everything it needs to answer."""

    @abstractmethod
    async def complete(self, *, system: str, user: str, timeout: float) -> str:
        """Return the raw model text for a system/user prompt pair."""


# --------------------------------------------------------------------- demo
class DemoAIProvider(AIProvider):
    """Deterministic, data-driven answers — clearly labelled as demo mode.

    It parses the same JSON context a real model would receive and turns the
    pre-computed facts into natural language. Arithmetic is never performed
    here: every number comes from the backend's integer-minor-unit totals.
    """

    name = "demo"
    live = False

    def is_configured(self) -> bool:
        return True

    async def complete(self, *, system: str, user: str, timeout: float) -> str:
        context = _extract_context(user)
        intent = context.get("intent", "general")
        facts: dict[str, Any] = context.get("facts", {})
        currency = context.get("primary_currency", "USD")
        amount = facts.get("totals", {}).get("all_time_completed", "0.00")

        lines: list[str] = []
        recommendations: list[str] = []
        references: list[str] = []

        if intent == "weekly_total":
            totals = facts.get("totals", {})
            lines.append(
                f"This week ({totals.get('week_start', '')} onward) you collected "
                f"{totals.get('week_completed', '0.00')} {currency} across "
                f"{totals.get('week_count', 0)} captured payment(s)."
            )
            lines.append(
                f"Month to date: {totals.get('month_completed', '0.00')} {currency} "
                f"from {totals.get('month_count', 0)} payment(s)."
            )
            lines.append(
                f"All time: {amount} {currency} captured from "
                f"{facts.get('status_counts', {}).get('completed', 0)} successful payment(s)."
            )
            recommendations.append(
                "Compare this week with your monthly average in Overview → Collection trend."
            )
        elif intent == "pending":
            pending = facts.get("pending", [])
            totals = facts.get("totals", {})
            lines.append(
                f"You have {len(pending)} payment request(s) awaiting completion totalling "
                f"{totals.get('pending_amount', '0.00')} {currency}."
            )
            for item in pending[:5]:
                lines.append(
                    f"- {item.get('amount', '0.00')} {currency} — {item.get('description', '')} "
                    f"(created {item.get('created', '')}, ref {item.get('reference') or 'n/a'})"
                )
                references.extend(item.get("id") and [item["id"]] or [])
            if not pending:
                lines.append("Nothing is waiting on a payer right now.")
            recommendations.append(
                "Send a reminder for anything older than 7 days; PayPal orders expire if left too long."
            )
        elif intent == "summary":
            status_counts = facts.get("status_counts", {})
            totals = facts.get("totals", {})
            lines.append(
                f"You have {context.get('record_count', 0)} recorded payment(s). "
                f"{status_counts.get('completed', 0)} completed for "
                f"{totals.get('all_time_completed', '0.00')} {currency}; "
                f"{status_counts.get('pending', 0)} still pending; "
                f"{status_counts.get('failed', 0) + status_counts.get('declined', 0)} failed or declined; "
                f"{status_counts.get('cancelled', 0) + status_counts.get('expired', 0)} cancelled or expired."
            )
            for item in facts.get("recent", [])[:4]:
                lines.append(
                    f"- {item.get('amount', '0.00')} {currency} · {item.get('status', '')} · "
                    f"{item.get('description', '')} ({item.get('created', '')})"
                )
                if item.get("id"):
                    references.append(item["id"])
        elif intent == "attention":
            items = facts.get("needs_attention", [])
            if items:
                lines.append(f"{len(items)} record(s) need attention today:")
                for item in items[:6]:
                    status_text = item.get("status", "")
                    reason = item.get("reason") or (
                        "no approval after 7+ days"
                        if status_text == "pending"
                        else "no reason recorded"
                    )
                    lines.append(
                        f"- {item.get('amount', '0.00')} {currency} · {status_text} · "
                        f"{item.get('description', '')} · {reason}"
                    )
                    if item.get("id"):
                        references.append(item["id"])
            else:
                lines.append("Nothing needs attention: no failed, declined or stalled requests are on record.")
            recommendations.append(
                "Retry failed requests with a fresh order, and re-issue anything older than 30 days."
            )
        elif intent == "trends":
            monthly = facts.get("monthly", [])
            series = " → ".join(f"{m.get('label')} {m.get('amount')}" for m in monthly)
            lines.append(f"Monthly collections ({currency}): {series or 'no completed payments yet'}.")
            peak = (
                max(monthly, key=lambda m: int(m.get("amount_minor") or 0))
                if monthly
                else None
            )
            if peak:
                lines.append(
                    f"Your strongest month in this window was {peak.get('label')} at "
                    f"{peak.get('amount')} {currency} across {peak.get('count')} payment(s)."
                )
            recommendations.append("Check whether your strongest month lines up with a campaign or retainer cycle.")
        elif intent == "failure_explain":
            failures = facts.get("failures", [])
            if failures:
                lines.append(
                    f"There are {len(failures)} failed/declined/expired record(s). "
                    "PayPal declines do not expose the payer's card details to merchants, so the "
                    "recorded API reason is the full extent of what is known."
                )
                for item in failures[:4]:
                    lines.append(
                        f"- {item.get('description', '')}: {item.get('reason', 'no reason recorded')} "
                        f"(PayPal status {item.get('paypal_status', 'unknown')}, order {item.get('order_id', '')})"
                    )
                    if item.get("id"):
                        references.append(item["id"])
                recommendations.append(
                    "Create a new order for declined payments and confirm the payer's billing address matches."
                )
            else:
                lines.append("No failed, declined or expired payments are recorded.")
        elif intent == "follow_up_today":
            pending = facts.get("pending", [])
            failures = facts.get("failures", [])
            lines.append(
                f"Today: {len(pending)} pending request(s) worth "
                f"{facts.get('totals', {}).get('pending_amount', '0.00')} {currency} "
                f"and {len(failures)} failed/expired record(s) to re-issue."
            )
            for item in (pending + failures)[:5]:
                lines.append(
                    f"- {item.get('amount', '0.00')} {currency} · {item.get('description', '')} · "
                    f"{item.get('status', '')}"
                )
                if item.get("id"):
                    references.append(item["id"])
            recommendations.append("Follow up on the oldest pending request first — it has the highest chance of expiring.")
        else:
            totals = facts.get("totals", {})
            lines.append(
                f"Across {context.get('record_count', 0)} record(s) you have captured "
                f"{totals.get('all_time_completed', '0.00')} {currency}, with "
                f"{totals.get('pending_amount', '0.00')} {currency} still pending across "
                f"{facts.get('status_counts', {}).get('pending', 0)} request(s)."
            )
            lines.append(
                "Ask about weekly totals, pending payments, trends, failures, or what to follow up on today."
            )

        response = {
            "answer": "\n".join(lines),
            "facts": context.get("facts", {}).get("key_facts", [])[:6] or [
                f"Records analysed: {facts.get('record_count', 0)}"
            ],
            "recommendations": recommendations[:4],
            "references": list(dict.fromkeys(references))[:6],
            "confidence": "high",
            "disclaimer": (
                "Demo mode: this answer was generated by a deterministic rule engine from your "
                "recorded data, not by an AI model. Recommendations are suggestions, not financial advice."
            ),
        }
        return json.dumps(response)


# -------------------------------------------------------------------- openai
class OpenAIProvider(AIProvider):
    """OpenAI Chat Completions with structured JSON output."""

    name = "openai"
    live = True

    def __init__(self, settings: Settings, *, base_url: str | None = None, model: str | None = None):
        super().__init__(settings)
        self.base_url = (base_url or settings.ai_base_url or "https://api.openai.com/v1").rstrip("/")
        self.model = model or settings.ai_model or settings.openai_model or "gpt-4o-mini"
        self.api_key = settings.resolved_ai_key
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(settings.ai_timeout_seconds, connect=8.0))

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def complete(self, *, system: str, user: str, timeout: float) -> str:
        if not self.is_configured():
            raise AIProviderError(
                f"{self.name} is selected but no API key is configured.",
                provider=self.name,
                retryable=False,
            )
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.1,
            "max_tokens": self.settings.ai_max_tokens,
            "response_format": {"type": "json_object"},
        }
        try:
            response = await self._client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            raise AIProviderError(
                f"The {self.name} request timed out after {timeout:.0f}s.",
                provider=self.name,
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(
                f"Could not reach {self.name}: {type(exc).__name__}.",
                provider=self.name,
                retryable=True,
            ) from exc

        if response.status_code >= 400:
            message, retryable = _http_error(response, self.name)
            raise AIProviderError(message, provider=self.name, retryable=retryable)

        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AIProviderError(
                f"{self.name} returned a malformed completion payload.",
                provider=self.name,
                retryable=True,
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise AIProviderError(
                f"{self.name} returned an empty completion.", provider=self.name
            )
        return content


class OpenAICompatibleProvider(OpenAIProvider):
    """Any OpenAI-shaped endpoint (Ollama, LM Studio, Groq, Together, ...)."""

    name = "openai_compatible"

    def __init__(self, settings: Settings) -> None:
        base = (settings.ai_base_url or "http://localhost:11434/v1").rstrip("/")
        model = settings.ai_model or "llama3.1"
        super().__init__(settings, base_url=base, model=model)

    def is_configured(self) -> bool:
        # Local servers often need no key at all.
        return bool(self.base_url)


# ----------------------------------------------------------------- anthropic
class AnthropicProvider(AIProvider):
    """Anthropic Messages API."""

    name = "anthropic"
    live = True

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.base_url = (settings.ai_base_url or "https://api.anthropic.com").rstrip("/")
        self.model = settings.ai_model or settings.anthropic_model or "claude-3-5-haiku-latest"
        self.api_key = settings.resolved_ai_key or settings.anthropic_api_key
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(settings.ai_timeout_seconds, connect=8.0))

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def complete(self, *, system: str, user: str, timeout: float) -> str:
        if not self.is_configured():
            raise AIProviderError(
                "anthropic is selected but ANTHROPIC_API_KEY is not configured.",
                provider=self.name,
                retryable=False,
            )
        body = {
            "model": self.model,
            "max_tokens": self.settings.ai_max_tokens,
            "temperature": 0.1,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        try:
            response = await self._client.post(
                f"{self.base_url}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            raise AIProviderError(
                f"The anthropic request timed out after {timeout:.0f}s.",
                provider=self.name,
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(
                f"Could not reach anthropic: {type(exc).__name__}.",
                provider=self.name,
                retryable=True,
            ) from exc

        if response.status_code >= 400:
            message, retryable = _http_error(response, self.name)
            raise AIProviderError(message, provider=self.name, retryable=retryable)

        try:
            payload = response.json()
            blocks = payload["content"]
            content = "".join(
                block.get("text", "") for block in blocks if isinstance(block, dict)
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise AIProviderError(
                f"{self.name} returned a malformed completion payload.",
                provider=self.name,
                retryable=True,
            ) from exc
        if not content.strip():
            raise AIProviderError(f"{self.name} returned an empty completion.", provider=self.name)
        return content


def _http_error(response: httpx.Response, provider: str) -> tuple[str, bool]:
    status = response.status_code
    try:
        body = response.json()
        message = (
            body.get("error", {}).get("message")
            if isinstance(body.get("error"), dict)
            else body.get("error")
        ) or body.get("message") or f"{provider} returned HTTP {status}"
    except ValueError:
        message = f"{provider} returned HTTP {status}"
    if status in {401, 403}:
        return f"{provider} rejected the API key (HTTP {status}).", False
    if status == 404:
        return f"{provider} model or endpoint not found (HTTP 404): {message}", False
    if status == 429:
        return f"{provider} rate limit reached (HTTP 429). Try again shortly.", True
    if status >= 500:
        return f"{provider} is unavailable (HTTP {status}).", True
    return str(message), False


def _extract_context(prompt: str) -> dict[str, Any]:
    """Pull the JSON context block back out of the rendered prompt."""
    start = prompt.find(CONTEXT_START)
    end = prompt.find(CONTEXT_END)
    if start == -1 or end == -1 or end <= start:
        return {}
    raw = prompt[start + len(CONTEXT_START) : end].strip()
    try:
        parsed = json.loads(raw)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def build_provider(settings: Settings) -> AIProvider:
    """Factory: choose the configured provider, falling back to the labelled demo."""
    choice = settings.ai_provider
    if choice == "openai":
        provider: AIProvider = OpenAIProvider(settings)
    elif choice == "anthropic":
        provider = AnthropicProvider(settings)
    elif choice == "openai_compatible":
        provider = OpenAICompatibleProvider(settings)
    else:
        provider = DemoAIProvider(settings)

    if provider.live and not provider.is_configured():
        logger.warning(
            "AI provider '%s' is not configured — falling back to the labelled demo engine.",
            choice,
            extra=log_extra(requested_provider=choice),
        )
        return DemoAIProvider(settings)
    return provider


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def strip_code_fences(text: str) -> str:
    match = _FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort extraction of the first JSON object in a model response."""
    cleaned = strip_code_fences(text)
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except ValueError:
        pass

    decoder = json.JSONDecoder()
    index = cleaned.find("{")
    while index != -1:
        try:
            candidate, _ = decoder.raw_decode(cleaned, index)
        except ValueError:
            index = cleaned.find("{", index + 1)
            continue
        if isinstance(candidate, dict):
            return candidate
        index = cleaned.find("{", index + 1)
    return None
