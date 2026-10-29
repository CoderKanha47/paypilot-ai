"""Repository helpers for transaction records."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from ..models import Transaction, utcnow

VALID_STATUSES = (
    "pending",
    "completed",
    "declined",
    "failed",
    "cancelled",
    "expired",
    "refunded",
)


def get_by_order_id(session: Session, order_id: str) -> Transaction | None:
    return session.scalar(select(Transaction).where(Transaction.paypal_order_id == order_id))


def get_by_id(session: Session, transaction_id: str) -> Transaction | None:
    return session.get(Transaction, transaction_id)


def get_by_capture_id(session: Session, capture_id: str) -> Transaction | None:
    return session.scalar(select(Transaction).where(Transaction.paypal_capture_id == capture_id))


def _apply_filters(
    stmt: Select,
    *,
    search: str | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Select:
    if search:
        needle = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Transaction.description.ilike(needle),
                Transaction.customer_reference.ilike(needle),
                Transaction.paypal_order_id.ilike(needle),
                Transaction.paypal_capture_id.ilike(needle),
                Transaction.id.ilike(needle),
            )
        )
    if status:
        if status == "all":
            pass
        elif status == "failed_or_cancelled":
            stmt = stmt.where(Transaction.status.in_(("failed", "cancelled", "declined", "expired")))
        elif status in VALID_STATUSES:
            stmt = stmt.where(Transaction.status == status)
    if date_from:
        stmt = stmt.where(Transaction.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Transaction.created_at < date_to)
    return stmt


def list_transactions(
    session: Session,
    *,
    search: str | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
    order_desc: bool = True,
) -> tuple[Sequence[Transaction], int]:
    stmt = select(Transaction)
    stmt = _apply_filters(stmt, search=search, status=status, date_from=date_from, date_to=date_to)

    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(
        Transaction.created_at.desc() if order_desc else Transaction.created_at.asc()
    )
    stmt = stmt.limit(limit).offset(max(offset, 0))
    items = session.scalars(stmt).all()
    return items, int(total)


def count_by_status(
    session: Session,
    *,
    search: str | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, int]:
    filtered = _apply_filters(
        select(Transaction.id),
        search=search,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )
    stmt = (
        select(Transaction.status, func.count())
        .where(Transaction.id.in_(filtered))
        .group_by(Transaction.status)
    )
    rows = session.execute(stmt).all()
    return {str(status_value): int(count) for status_value, count in rows}


def recent_transactions(session: Session, limit: int = 8) -> Sequence[Transaction]:
    stmt = (
        select(Transaction)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
    )
    return session.scalars(stmt).all()


def all_transactions(session: Session, *, include_demo: bool = True) -> Sequence[Transaction]:
    stmt = select(Transaction).order_by(Transaction.created_at.desc())
    if not include_demo:
        stmt = stmt.where(Transaction.is_demo_record.is_(False))
    return session.scalars(stmt).all()


def transactions_in_window(session: Session, days: int) -> Sequence[Transaction]:
    since = utcnow() - timedelta(days=days)
    stmt = (
        select(Transaction)
        .where(Transaction.created_at >= since)
        .order_by(Transaction.created_at.desc())
    )
    return session.scalars(stmt).all()


def iso_week_start(now: datetime | None = None) -> datetime:
    """Monday 00:00 UTC of the current ISO week."""
    current = (now or utcnow()).replace(hour=0, minute=0, second=0, microsecond=0)
    return current - timedelta(days=current.weekday())


def month_start(now: datetime | None = None) -> datetime:
    current = now or utcnow()
    return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def days_ago(days: int, now: datetime | None = None) -> datetime:
    return (now or utcnow()) - timedelta(days=days)


def ensure_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def bulk_get(session: Session, ids: Iterable[str]) -> Sequence[Transaction]:
    id_list = [i for i in ids if i]
    if not id_list:
        return []
    return session.scalars(select(Transaction).where(Transaction.id.in_(id_list))).all()
