"""Clearly-labelled demo data for UI exploration and the hackathon demo video.

Every row created here is stamped ``is_demo_record=True`` / ``mode="demo"`` and
is rendered with a DEMO badge throughout the product. Seeding happens only when
``SEED_DEMO_DATA=true`` **and** the table is empty **and** the app is not in
production mode — real records are never overwritten or mixed in silently.
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .logging_config import log_extra
from .models import AppMeta, Transaction, set_meta, utcnow
from .money import to_minor

logger = logging.getLogger("paypilot.seed")

SEED_KEY = "demo_seeded_at"

# (days_ago, amount, currency, description, reference, status)
DEMO_ROWS: Sequence[tuple[int, str, str, str, str, str]] = (
    (2, "1,250.00", "USD", "Brand identity package — Northwind Studio", "NW-2026-014", "completed"),
    (4, "480.00", "USD", "Monthly retainer — Harbor & Co.", "HARBOR-OCT", "completed"),
    (6, "2,100.00", "USD", "E-commerce build phase 2 — Lumen Goods", "LUMEN-P2", "completed"),
    (9, "350.00", "USD", "Landing page copywriting — Cedar Health", "CEDAR-COPY", "pending"),
    (11, "795.00", "USD", "SEO audit Q4 — Bluebird Travel", "BB-SEO-Q4", "pending"),
    (14, "1,500.00", "USD", "Photography half-day — Vireo Films", "VIR-PHOTO", "completed"),
    (17, "225.00", "USD", "Consulting call block — Aster Labs", "ASTER-H4", "failed"),
    (19, "640.00", "USD", "Newsletter templates — Juniper Coffee", "JUN-TPL", "declined"),
    (23, "980.00", "USD", "Shopify theme customization — Tern Outfitters", "TERN-THEME", "completed"),
    (27, "175.00", "USD", "Social media kit — Kestrel Fitness", "KESTREL-SM", "cancelled"),
    (34, "3,200.00", "USD", "Website redesign milestone 1 — Marlow Legal", "MARLOW-M1", "completed"),
    (41, "1,050.00", "USD", "Monthly retainer — Harbor & Co.", "HARBOR-SEP", "completed"),
    (52, "860.00", "USD", "Illustration set — Pinecone Books", "PINE-ILL", "completed"),
    (63, "410.00", "USD", "Analytics setup — Solstice Yoga", "SOL-ANALYTICS", "expired"),
    (74, "2,450.00", "USD", "Website redesign milestone 2 — Marlow Legal", "MARLOW-M2", "completed"),
    (88, "1,180.00", "USD", "Brand identity package — Northwind Studio", "NW-2026-009", "completed"),
    (101, "560.00", "USD", "Monthly retainer — Harbor & Co.", "HARBOR-AUG", "completed"),
    (118, "720.00", "USD", "Email flow design — Driftwood Travel Co.", "DRIFT-EMAIL", "completed"),
)

PAYPAL_STATUSES = {
    "completed": "COMPLETED",
    "pending": "CREATED",
    "declined": "DECLINED",
    "failed": "FAILED",
    "cancelled": "VOIDED",
    "expired": "EXPIRED",
}


def is_seeded(session: Session) -> bool:
    row = session.get(AppMeta, SEED_KEY)
    if row is not None:
        return True
    # Backstop: any existing row means we must not invent more.
    return bool(session.scalar(select(Transaction.id).limit(1)))


def seed_demo_data(session: Session, settings: Settings, *, force: bool = False) -> int:
    """Insert demo rows. Returns the number of rows created."""
    if not settings.seed_demo_data and not force:
        return 0
    if settings.app_env == "production" and not force:
        return 0
    if is_seeded(session) and not force:
        return 0

    now = utcnow()
    created = 0
    for days_ago, amount, currency, description, reference, status in DEMO_ROWS:
        order_id = f"DEMO{uuid.uuid4().hex[:22].upper()}"
        row = Transaction(
            paypal_order_id=order_id,
            paypal_capture_id=f"DEMO{uuid.uuid4().hex[:22].upper()}" if status == "completed" else None,
            paypal_intent="CAPTURE",
            status=status,
            paypal_status=PAYPAL_STATUSES.get(status, "CREATED"),
            amount_minor=to_minor(amount.replace(",", ""), currency),
            currency=currency,
            description=description,
            customer_reference=reference,
            approval_url=None,
            failure_reason=(
                "Demo row: PayPal declined the funding source."
                if status == "declined"
                else "Demo row: PayPal returned a FAILED capture status."
                if status == "failed"
                else "Demo row: payment request expired without approval."
                if status == "expired"
                else None
            ),
            mode="demo",
            is_demo_record=True,
            amount_captured_minor=(
                to_minor(amount.replace(",", ""), currency) if status == "completed" else None
            ),
            created_at=now - timedelta(days=days_ago),
            updated_at=now - timedelta(days=days_ago),
            completed_at=(now - timedelta(days=days_ago)) if status == "completed" else None,
        )
        session.add(row)
        created += 1

    set_meta(session, SEED_KEY, now.isoformat())
    session.flush()
    logger.info(
        "Seeded %s clearly-labelled demo transactions", created, extra=log_extra(count=created)
    )
    return created


def clear_demo_data(session: Session) -> int:
    """Remove demo rows only. Real Sandbox records are left untouched."""
    rows = list(session.scalars(select(Transaction).where(Transaction.is_demo_record.is_(True))))
    for row in rows:
        session.delete(row)
    session.flush()
    return len(rows)
