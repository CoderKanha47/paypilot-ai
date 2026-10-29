"""ORM models.

Monetary values are persisted as **integer minor units** (``amount_minor``)
paired with an ISO-4217 ``currency``. This keeps SQLite storage exact and
avoids binary floating point for money.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utcnow() -> datetime:
    """Timezone-aware UTC now, stored naive (SQLite has no tz support)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


class Transaction(Base):
    """A payment request / payment captured through PayPal (or demo mode)."""

    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_status_created", "status", "created_at"),
        Index("ix_transactions_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("txn"))
    paypal_order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    paypal_capture_id: Mapped[str | None] = mapped_column(String(64), index=True)
    paypal_intent: Mapped[str] = mapped_column(String(16), default="CAPTURE")

    # Normalised application status: pending | completed | declined | failed |
    # cancelled | expired | refunded
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    # Raw status string returned by PayPal (CREATED, COMPLETED, DECLINED, ...).
    paypal_status: Mapped[str | None] = mapped_column(String(32))

    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    customer_reference: Mapped[str | None] = mapped_column(String(120))
    customer_note: Mapped[str | None] = mapped_column(Text)

    approval_url: Mapped[str | None] = mapped_column(Text)
    failure_reason: Mapped[str | None] = mapped_column(Text)

    # "sandbox" = created against the real PayPal Sandbox API.
    # "demo"    = simulated locally because no credentials were configured.
    mode: Mapped[str] = mapped_column(String(12), default="sandbox", index=True)
    is_demo_record: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    amount_captured_minor: Mapped[int | None] = mapped_column(BigInteger)
    fee_minor: Mapped[int | None] = mapped_column(BigInteger)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Transaction {self.id} {self.status} {self.amount_minor} {self.currency}>"


class AppMeta(Base):
    """Tiny key/value store for one-off bookkeeping (e.g. demo seed marker)."""

    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


def get_meta(session, key: str) -> str | None:
    row = session.get(AppMeta, key)
    return row.value if row else None


def set_meta(session, key: str, value: str) -> None:
    row = session.get(AppMeta, key)
    if row is None:
        row = AppMeta(key=key, value=value)
        session.add(row)
    else:
        row.value = value
