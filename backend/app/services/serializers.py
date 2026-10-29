"""ORM -> API serialization helpers (Decimal-safe)."""

from __future__ import annotations

from ..money import from_minor
from ..models import Transaction


def _dec(minor: int | None, currency: str) -> str | None:
    if minor is None:
        return None
    exponent = 2 if currency not in {"JPY", "KRW", "VND", "CLP", "ISK", "HUF", "TWD"} else 0
    return f"{from_minor(minor, currency):.{exponent}f}"


def to_transaction_out(row: Transaction) -> dict:
    return {
        "id": row.id,
        "paypal_order_id": row.paypal_order_id,
        "paypal_capture_id": row.paypal_capture_id,
        "status": row.status,
        "paypal_status": row.paypal_status,
        "amount": _dec(row.amount_minor, row.currency) or "0.00",
        "amount_minor": row.amount_minor,
        "amount_captured": _dec(row.amount_captured_minor, row.currency),
        "currency": row.currency,
        "description": row.description,
        "customer_reference": row.customer_reference,
        "failure_reason": row.failure_reason,
        "approval_url": row.approval_url,
        "mode": row.mode,
        "is_demo_record": row.is_demo_record,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "completed_at": row.completed_at,
    }
