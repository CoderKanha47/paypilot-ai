"""Dashboard analytics.

Every figure returned here is computed from persisted rows. Integer minor units
are used for arithmetic and converted to :class:`decimal.Decimal` only at the
edge, so no financial number ever passes through a float.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Transaction, utcnow
from ..money import format_amount, from_minor, minor_exponent, normalize_currency, sum_minor

PRIMARY_STATUSES = ("completed", "pending", "failed", "cancelled", "declined", "expired", "refunded")


@dataclass
class DashboardData:
    metrics: dict
    monthly: list[dict]
    status_distribution: list[dict]
    recent: list[Transaction]
    generated_at: datetime
    notes: list[str] = field(default_factory=list)


def _decimal(minor: int, currency: str) -> Decimal:
    return from_minor(minor, currency)


def _month_key(value: datetime) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def _month_label(key: str) -> str:
    year, month = (int(part) for part in key.split("-"))
    return calendar.month_abbr[month]


def _success_rate(captured: int, attempted: int) -> float:
    """Percentage of attempted payments that completed (Decimal, never float math)."""
    if attempted <= 0:
        return 0.0
    ratio = (Decimal(captured) / Decimal(attempted) * 100).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )
    return float(ratio)


def build_dashboard(
    session: Session,
    settings: Settings,
    *,
    recent_limit: int = 8,
    months: int = 6,
) -> DashboardData:
    primary = normalize_currency(settings.paypal_currency)
    rows = list(session.scalars(select(Transaction).order_by(Transaction.created_at.desc())).all())

    generated_at = utcnow()
    any_demo = any(row.is_demo_record for row in rows)

    captured_minor = 0
    pending_minor = 0
    counts: dict[str, int] = defaultdict(int)
    currency_totals: dict[str, list[int]] = defaultdict(list)

    for row in rows:
        counts[row.status] += 1
        if row.currency == primary:
            if row.status == "completed":
                captured_minor += row.amount_minor
            elif row.status == "pending":
                pending_minor += row.amount_minor
        else:
            currency_totals[row.currency].append(row.amount_minor)

    captured_count = counts.get("completed", 0)
    pending_count = counts.get("pending", 0)
    failed_count = counts.get("failed", 0)
    declined_count = counts.get("declined", 0)
    cancelled_count = counts.get("cancelled", 0)
    expired_count = counts.get("expired", 0)
    refunded_count = counts.get("refunded", 0)

    attempted = captured_count + failed_count + declined_count + cancelled_count + expired_count
    # Decimal division on minor units, scaled back to major units — never a float.
    average = Decimal(0)
    if captured_count:
        average = (Decimal(captured_minor) / Decimal(captured_count)).scaleb(
            -minor_exponent(primary)
        )
        average = average.quantize(Decimal(1).scaleb(-minor_exponent(primary)), rounding=ROUND_HALF_UP)

    other_currencies = []
    for code, values in sorted(currency_totals.items()):
        other_currencies.append(
            {
                "currency": code,
                "amount": str(_decimal(sum_minor(values), code)),
                "count": len(values),
            }
        )

    # ------------------------------------------------------- monthly series
    window_start = generated_at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    for _ in range(months - 1):
        first_of_month = window_start.replace(day=1)
        window_start = (first_of_month - timedelta(days=1)).replace(day=1)

    buckets: dict[str, dict] = {}
    cursor = window_start
    for _ in range(months):
        key = _month_key(cursor)
        buckets[key] = {"month": key, "label": _month_label(key), "amount_minor": 0, "count": 0}
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)

    for row in rows:
        if row.status != "completed":
            continue
        if row.currency != primary:
            continue
        key = _month_key(row.created_at)
        if key in buckets:
            buckets[key]["amount_minor"] += row.amount_minor
            buckets[key]["count"] += 1

    monthly = [
        {
            "month": data["month"],
            "label": data["label"],
            "amount": str(_decimal(data["amount_minor"], primary)),
            "count": data["count"],
        }
        for data in buckets.values()
    ]

    # -------------------------------------------------- status distribution
    status_distribution = []
    for status in PRIMARY_STATUSES:
        if counts.get(status, 0) == 0 and status not in {"completed", "pending"}:
            continue
        amount = sum_minor(
            row.amount_minor for row in rows if row.status == status and row.currency == primary
        )
        status_distribution.append(
            {
                "status": status,
                "count": counts.get(status, 0),
                "amount": str(_decimal(amount, primary)),
                "currency": primary,
            }
        )

    metrics = {
        "primary_currency": primary,
        "total_captured": str(_decimal(captured_minor, primary)),
        "total_captured_minor": captured_minor,
        "total_pending": str(_decimal(pending_minor, primary)),
        "total_pending_minor": pending_minor,
        "captured_count": captured_count,
        "pending_count": pending_count,
        "failed_count": failed_count + declined_count,
        "cancelled_count": cancelled_count + expired_count,
        "refunded_count": refunded_count,
        "total_transactions": len(rows),
        "average_payment": str(average),
        "success_rate": _success_rate(captured_count, attempted),
        "period_days": 30,
        "other_currencies": other_currencies,
        "demo_data_included": any_demo,
    }

    notes: list[str] = []
    if other_currencies:
        notes.append(
            "Totals are shown per currency: amounts in different currencies are never added together."
        )
    if any_demo:
        notes.append("Includes records labelled DEMO. They are not real PayPal transactions.")

    return DashboardData(
        metrics=metrics,
        monthly=monthly,
        status_distribution=status_distribution,
        recent=list(rows[:recent_limit]),
        generated_at=generated_at,
        notes=notes,
    )


def compute_totals(
    rows: list[Transaction], *, currency: str, statuses: tuple[str, ...] = ("completed",)
) -> int:
    """Sum minor units for the given currency/status filter. Exact by construction."""
    code = normalize_currency(currency)
    return sum_minor(
        row.amount_minor for row in rows if row.currency == code and row.status in statuses
    )


def assert_exact(value: int, expected: int) -> None:  # pragma: no cover - debug helper
    assert value == expected, f"money mismatch: {value} != {expected} ({format_amount(value, 'USD')})"


def validate_amount_minor(row: Transaction) -> bool:
    """Guard against any row whose stored minor units are inconsistent."""
    return isinstance(row.amount_minor, int) and row.amount_minor >= 0 and minor_exponent(row.currency) >= 0
