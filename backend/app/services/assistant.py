"""Grounded payment assistant.

Pipeline
--------
1. Read the relevant rows from SQLite.
2. Compute **all** arithmetic in Python using integer minor units.
3. Hand the model a small, PII-minimised JSON context.
4. Ask for a single JSON object and validate it before returning.
5. Tag every response with ``facts`` / ``recommendations`` / ``references`` so the
   UI can visually separate recorded data from suggestions.

The model has no tools and no ability to create or capture payments.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..errors import AIProviderError
from ..logging_config import log_extra
from ..money import from_minor, normalize_currency, sum_minor
from ..models import Transaction, utcnow
from .ai import AIProvider, CONTEXT_END, CONTEXT_START, extract_json_object
from .analytics import _month_key, _month_label

logger = logging.getLogger("paypilot.assistant")

MAX_FACTS = 8
MAX_RECOMMENDATIONS = 6
MAX_REFERENCES = 8

SUGGESTIONS = [
    "How much did I collect this week?",
    "Which payments are still pending?",
    "Summarize my recent transactions.",
    "Which payment requests need attention?",
    "Show my monthly payment trends.",
    "Explain why these orders failed.",
    "What should I follow up on today?",
]

DISCLAIMER = (
    "Recommendations are AI-generated suggestions based on your recorded payment data. "
    "They are not financial, legal or tax advice."
)

SYSTEM_PROMPT = """You are PayPilot, the payment operations assistant inside a small-business \
PayPal dashboard.

You are given a JSON <transaction_context> block containing figures the application already \
computed. Treat every number in that block as ground truth.

Rules:
- Answer only from the provided context. If the context does not contain the answer, say so \
plainly instead of guessing.
- Never perform arithmetic. The totals are pre-computed for you; quote them exactly as given.
- Never claim you created, captured, refunded, cancelled or approved a payment. You cannot \
execute actions; the user must click buttons in the app.
- Separate what is recorded (facts) from what you suggest (recommendations).
- Keep the answer under 140 words, concrete and skimmable.
- Do not invent transaction ids, dates, customers or amounts.

Respond with ONE JSON object and nothing else, using exactly this shape:
{
  "answer": "2-4 sentences of plain-language explanation",
  "facts": ["short recorded fact", "..."],
  "recommendations": ["short actionable suggestion", "..."],
  "references": ["transaction id from context"],
  "confidence": "high" | "medium" | "low"
}"""


def classify_intent(message: str) -> str:
    """Cheap, deterministic intent routing so demo mode and prompt share a label."""
    text = message.lower()
    if any(word in text for word in ("failed", "declined", "why did", "decline", "error", "expired")):
        return "failure_explain"
    if any(word in text for word in ("follow up", "today", "should i do", "next step", "to-do", "todo")):
        return "follow_up_today"
    if any(word in text for word in ("attention", "needs attention", "worried", "urgent", "remind")):
        return "attention"
    if any(word in text for word in ("trend", "monthly", "month over", "growth", "chart", "history")):
        return "trends"
    if any(word in text for word in ("pending", "unpaid", "awaiting", "outstanding", "owed", "owe", "owes", "chase")):
        return "pending"
    if any(word in text for word in ("week", "this week", "collected this")):
        return "weekly_total"
    if any(word in text for word in ("summar", "overview", "recent", "how am i doing", "status of my")):
        return "summary"
    return "general"


def _brief(value: str | None, limit: int = 64) -> str:
    """Truncate free text before it is handed to an external provider."""
    if not value:
        return ""
    cleaned = " ".join(value.split())
    return cleaned[:limit] + ("…" if len(cleaned) > limit else "")


def _row_ref(row: Transaction) -> dict[str, Any]:
    return {
        "id": row.id,
        "order_id": row.paypal_order_id,
        "capture_id": row.paypal_capture_id,
        "amount": f"{from_minor(row.amount_minor, row.currency):.2f}"
        if row.currency not in {"JPY", "KRW"}
        else str(from_minor(row.amount_minor, row.currency)),
        "amount_minor": row.amount_minor,
        "currency": row.currency,
        "status": row.status,
        "paypal_status": row.paypal_status,
        "description": _brief(row.description, 60),
        "reference": _brief(row.customer_reference, 40),
        "reason": _brief(row.failure_reason, 80),
        "created": row.created_at.strftime("%Y-%m-%d %H:%M"),
        "completed": row.completed_at.strftime("%Y-%m-%d %H:%M") if row.completed_at else None,
        "demo": row.is_demo_record,
    }


@dataclass
class ContextBundle:
    payload: dict[str, Any]
    known_references: set[str]

    @property
    def intent(self) -> str:
        return str(self.payload.get("intent", "general"))

    def to_json(self) -> str:
        return json.dumps(self.payload, ensure_ascii=False, separators=(",", ":"))


def build_context(
    session: Session,
    settings: Settings,
    message: str,
    *,
    now: datetime | None = None,
) -> ContextBundle:
    """Build the exact, pre-computed context handed to the model."""
    current = now or utcnow()
    primary = normalize_currency(settings.paypal_currency)
    intent = classify_intent(message)

    rows = list(session.scalars(select(Transaction).order_by(Transaction.created_at.desc())).all())
    known = {row.id for row in rows} | {row.paypal_order_id for row in rows}

    day_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = day_start - timedelta(days=day_start.weekday())  # ISO Monday
    month_start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def rows_matching(statuses: tuple[str, ...], since: datetime | None = None) -> list[Transaction]:
        return [
            row
            for row in rows
            if row.status in statuses and (since is None or row.created_at >= since)
        ]

    completed_primary = [r for r in rows_matching(("completed",)) if r.currency == primary]
    week_rows = [r for r in completed_primary if r.created_at >= week_start]
    month_rows = [r for r in completed_primary if r.created_at >= month_start]
    pending_rows = [r for r in rows_matching(("pending",)) if r.currency == primary]
    failure_rows = rows_matching(("failed", "declined", "expired"))
    cancelled_rows = rows_matching(("cancelled",))

    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row.status] = status_counts.get(row.status, 0) + 1

    totals = {
        "all_time_completed": f"{from_minor(sum_minor(r.amount_minor for r in completed_primary), primary)}",
        "all_time_completed_minor": sum_minor(r.amount_minor for r in completed_primary),
        "week_start": week_start.strftime("%Y-%m-%d"),
        "week_completed": f"{from_minor(sum_minor(r.amount_minor for r in week_rows), primary)}",
        "week_count": len(week_rows),
        "month_completed": f"{from_minor(sum_minor(r.amount_minor for r in month_rows), primary)}",
        "month_count": len(month_rows),
        "pending_amount": f"{from_minor(sum_minor(r.amount_minor for r in pending_rows), primary)}",
        "pending_count": len(pending_rows),
        "failed_count": len(failure_rows),
        "cancelled_count": len(cancelled_rows),
        "average_completed": f"{from_minor(sum_minor(r.amount_minor for r in completed_primary) // max(len(completed_primary), 1), primary)}",
    }

    # Monthly trend, computed here so the model never has to aggregate.
    monthly_map: dict[str, dict[str, Any]] = {}
    for row in completed_primary:
        key = _month_key(row.created_at)
        bucket = monthly_map.setdefault(
            key, {"month": key, "label": _month_label(key), "amount_minor": 0, "count": 0}
        )
        bucket["amount_minor"] += row.amount_minor
        bucket["count"] += 1
    monthly = [
        {
            **bucket,
            "amount": str(from_minor(bucket["amount_minor"], primary)),
        }
        for _, bucket in sorted(monthly_map.items())[-6:]
    ]

    stale_day = current.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7)
    needs_attention = [
        row
        for row in rows
        if row.status in {"failed", "declined", "expired"}
        or (row.status == "pending" and row.created_at < stale_day)
    ]

    payload: dict[str, Any] = {
        "generated_at": current.isoformat(timespec="seconds"),
        "primary_currency": primary,
        "intent": intent,
        "question": _brief(message, 200),
        "record_count": len(rows),
        "facts": {
            "status_counts": status_counts,
            "totals": totals,
            "monthly": monthly,
            "recent": [_row_ref(r) for r in rows[:8]],
            "pending": [_row_ref(r) for r in pending_rows[:8]],
            "failures": [_row_ref(r) for r in failure_rows[:8]],
            "needs_attention": [_row_ref(r) for r in needs_attention[:8]],
            "key_facts": [
                f"Captured all time ({primary}): {totals['all_time_completed']}",
                f"Captured this week: {totals['week_completed']} across {totals['week_count']} payment(s)",
                f"Captured this month: {totals['month_completed']} across {totals['month_count']} payment(s)",
                f"Pending: {totals['pending_amount']} across {totals['pending_count']} request(s)",
                f"Failed/declined/expired: {len(failure_rows)}",
                f"Records on file: {len(rows)}",
            ],
        },
        "allowed_references": sorted(known)[:80],
    }
    return ContextBundle(payload=payload, known_references=known)


def build_prompt(context: ContextBundle, history: list[dict[str, str]] | None = None) -> str:
    parts: list[str] = []
    for item in (history or [])[-6:]:
        role = item.get("role", "user")
        parts.append(f"{role}: {_brief(item.get('content', ''), 300)}")
    parts.append(f"user: {context.payload.get('question', '')}")
    parts.append(f"{CONTEXT_START}{context.to_json()}{CONTEXT_END}")
    return "\n".join(parts)


def validate_response(
    raw: str,
    context: ContextBundle,
    *,
    provider: str,
    mode: str,
    latency_ms: int,
    data_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Parse and harden the model output. Raises on unusable responses."""
    data = extract_json_object(raw)
    if data is None:
        raise AIProviderError(
            f"The {provider} response was not valid JSON.",
            provider=provider,
            retryable=True,
        )

    answer = data.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise AIProviderError(
            f"The {provider} response did not contain an answer.",
            provider=provider,
            retryable=True,
        )
    answer = answer.strip()[:2000]

    def clean_list(key: str, limit: int, max_len: int = 240) -> list[str]:
        value = data.get(key, [])
        if not isinstance(value, list):
            return []
        cleaned: list[str] = []
        for item in value[:limit]:
            if isinstance(item, str) and item.strip():
                cleaned.append(item.strip()[:max_len])
        return cleaned

    facts = clean_list("facts", MAX_FACTS)
    recommendations = clean_list("recommendations", MAX_RECOMMENDATIONS)

    references = clean_list("references", MAX_REFERENCES, max_len=64)
    # Only surface ids that actually exist in our database — the model cannot
    # mint references we have never seen.
    references = [ref for ref in references if ref in context.known_references][:MAX_REFERENCES]

    confidence = data.get("confidence")
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"

    secrets = _known_secrets()
    for needle in (answer, *facts, *recommendations):
        for secret in secrets:
            if secret and secret in needle:
                raise AIProviderError(
                    "The model response contained a value that looks like a secret and was discarded.",
                    provider=provider,
                    retryable=False,
                )

    facts_snapshot = {
        "totals": context.payload["facts"]["totals"],
        "status_counts": context.payload["facts"]["status_counts"],
        "record_count": context.payload["record_count"],
        "intent": context.intent,
    }
    if data_snapshot:
        facts_snapshot.update(data_snapshot)

    return {
        "answer": answer,
        "facts": facts,
        "recommendations": recommendations,
        "references": references,
        "confidence": confidence,
        "provider": provider,
        "mode": mode,
        "latency_ms": latency_ms,
        "data_snapshot": facts_snapshot,
        "disclaimer": DISCLAIMER,
        "notice": None,
        "suggestions": SUGGESTIONS,
    }


def _known_secrets() -> list[str]:
    """Values that must never leak into an AI response or a log line."""
    from ..config import get_settings

    settings = get_settings()
    return [
        settings.paypal_client_secret,
        settings.resolved_ai_key,
        settings.openai_api_key,
        settings.anthropic_api_key,
    ]


async def answer_question(
    session: Session,
    settings: Settings,
    provider: AIProvider,
    message: str,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Full pipeline: gather -> compute -> prompt -> validate."""
    context = build_context(session, settings, message)
    prompt = build_prompt(context, history)
    started = time.perf_counter()

    raw = await provider.complete(
        system=SYSTEM_PROMPT, user=prompt, timeout=settings.ai_timeout_seconds
    )
    latency_ms = int((time.perf_counter() - started) * 1000)

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
        logger.warning(
            "Retrying AI response after validation failure",
            extra=log_extra(provider=provider.name, latency_ms=latency_ms),
        )
        raw_retry = await provider.complete(
            system=SYSTEM_PROMPT + "\nReturn ONLY the JSON object. No markdown, no prose.",
            user=prompt,
            timeout=settings.ai_timeout_seconds,
        )
        result = validate_response(
            raw_retry,
            context,
            provider=provider.name,
            mode="live" if provider.live else "demo",
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    if not provider.live:
        result["notice"] = (
            "Demo mode: this answer came from a deterministic rule engine reading your "
            "recorded data — not from an AI model. Configure AI_PROVIDER to use a real model."
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
    return result


def empty_snapshot(settings: Settings) -> dict[str, Any]:
    return {
        "primary_currency": normalize_currency(settings.paypal_currency),
        "totals": {},
        "status_counts": {},
        "record_count": 0,
        "intent": "general",
    }


def decimal_from_minor(minor: int, currency: str) -> Decimal:
    return from_minor(minor, currency)
