"""Payment orchestration.

Single place where a payment moves state, so the rules are easy to audit:

* Orders are always created server-side.
* Capture only ever targets an order **we** created — the local record must
  exist first (``order ownership``), and the amount/currency PayPal returns are
  re-checked against our record before anything is persisted.
* A completed record is never captured twice: the second call returns the
  stored transaction with ``already_captured=True``.
* The browser's opinion of the payment status is ignored entirely.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import Settings
from ..errors import DomainError, PayPalError
from ..logging_config import log_extra
from ..models import Transaction, utcnow
from ..money import format_amount, parse_amount_to_minor
from ..schemas import CreateOrderRequest
from .demo_checkout import DemoCheckout
from .paypal import PayPalService, normalize_status

logger = logging.getLogger("paypilot.payments")

DemoOutcome = Literal["approve", "decline", "fail", "pending"]


class CheckoutBackend(Protocol):
    mode: str

    @property
    def configured(self) -> bool: ...

    async def aclose(self) -> None: ...

    async def create_order(
        self,
        *,
        amount_minor: int,
        currency: str,
        description: str,
        reference: str | None = None,
        note: str | None = None,
        return_url: str | None = None,
        cancel_url: str | None = None,
        intent: str = "CAPTURE",
    ) -> dict[str, Any]: ...

    async def capture_order(self, order_id: str, **kwargs: Any) -> dict[str, Any]: ...

    async def get_order(self, order_id: str) -> dict[str, Any]: ...


@dataclass
class PaymentResult:
    transaction: Transaction
    order: dict[str, Any]
    already_captured: bool = False
    mode: str = "sandbox"


def build_checkout(settings: Settings) -> CheckoutBackend:
    """Return the real PayPal client when configured, otherwise the demo engine."""
    if settings.paypal_configured:
        return PayPalService(settings)
    return DemoCheckout(settings)


async def create_payment(
    session: Session,
    settings: Settings,
    checkout: CheckoutBackend,
    payload: CreateOrderRequest,
) -> PaymentResult:
    amount_minor = payload.amount_minor()
    currency = payload.currency

    order = await checkout.create_order(
        amount_minor=amount_minor,
        currency=currency,
        description=payload.description,
        reference=payload.customer_reference,
        note=payload.customer_note,
    )

    _assert_amount_matches(order, amount_minor=amount_minor, currency=currency, context="create")

    row = Transaction(
        paypal_order_id=order["id"],
        paypal_intent=str(order.get("intent") or "CAPTURE"),
        status=normalize_status(order.get("status")),
        paypal_status=order.get("status"),
        amount_minor=amount_minor,
        currency=currency,
        description=payload.description,
        customer_reference=payload.customer_reference,
        customer_note=payload.customer_note,
        approval_url=order.get("approve_url"),
        mode=checkout.mode,
        is_demo_record=checkout.mode == "demo",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:  # pragma: no cover - duplicate order id
        session.rollback()
        raise DomainError(
            "A record for this PayPal order already exists.", code="duplicate_order"
        ) from exc

    logger.info(
        "Created payment request",
        extra=log_extra(
            transaction_id=row.id,
            order_id=row.paypal_order_id,
            amount_minor=amount_minor,
            currency=currency,
            mode=checkout.mode,
        ),
    )
    return PaymentResult(transaction=row, order=order, mode=checkout.mode)


async def capture_payment(
    session: Session,
    settings: Settings,
    checkout: CheckoutBackend,
    *,
    order_id: str,
    transaction_id: str | None = None,
    demo_outcome: DemoOutcome | None = None,
) -> PaymentResult:
    row = _find_owned_row(session, order_id, transaction_id=transaction_id)

    # Idempotency: never capture an order we already recorded as completed.
    if row.status == "completed":
        return PaymentResult(
            transaction=row,
            order={
                "id": row.paypal_order_id,
                "status": row.paypal_status or "COMPLETED",
                "capture_id": row.paypal_capture_id,
                "amount_minor": row.amount_minor,
                "currency": row.currency,
                "captured_minor": row.amount_captured_minor,
                "already_captured": True,
            },
            already_captured=True,
            mode=checkout.mode,
        )

    if checkout.mode == "demo":
        order = await checkout.capture_order(order_id, outcome=demo_outcome or "approve")
    else:
        order = await _capture_on_paypal(checkout, order_id)  # type: ignore[arg-type]

    # Verify PayPal's answer describes *this* order before persisting anything.
    if str(order.get("id")) != row.paypal_order_id:
        raise DomainError(
            "PayPal returned an order that does not match the requested payment.",
            code="order_mismatch",
        )
    _assert_amount_matches(
        order, amount_minor=row.amount_minor, currency=row.currency, context="capture"
    )

    status = normalize_status(order.get("status"))
    row.status = status
    row.paypal_status = order.get("status")
    row.paypal_capture_id = order.get("capture_id") or row.paypal_capture_id
    row.failure_reason = order.get("failure_reason")
    row.updated_at = utcnow()

    if status == "completed":
        captured = order.get("captured_minor")
        row.amount_captured_minor = (
            captured if isinstance(captured, int) else row.amount_minor
        )
        row.completed_at = utcnow()
        row.failure_reason = None

    session.flush()
    logger.info(
        "Payment capture resolved",
        extra=log_extra(
            transaction_id=row.id,
            order_id=row.paypal_order_id,
            status=status,
            paypal_status=row.paypal_status,
            mode=checkout.mode,
            already_captured=bool(order.get("already_captured")),
        ),
    )
    return PaymentResult(
        transaction=row,
        order=order,
        already_captured=bool(order.get("already_captured")),
        mode=checkout.mode,
    )


async def cancel_payment(
    session: Session,
    checkout: CheckoutBackend,
    *,
    order_id: str,
    transaction_id: str | None = None,
) -> PaymentResult:
    """Mark an un-approved request as cancelled after verifying with PayPal."""
    row = _find_owned_row(session, order_id, transaction_id=transaction_id)
    if row.status == "completed":
        raise DomainError("A captured payment cannot be cancelled here.", code="already_captured")

    remote_status: str | None = None
    if checkout.mode != "demo":
        try:
            remote = await checkout.get_order(order_id)
            remote_status = remote.get("status")
        except PayPalError as exc:
            if exc.name == "DEMO_NO_REMOTE_ORDER":
                remote_status = None
            else:
                raise
        if remote_status in {"COMPLETED", "PENDING"}:
            raise DomainError(
                f"PayPal reports this order as {remote_status}; it can no longer be cancelled.",
                code="not_cancellable",
            )

    row.status = "cancelled"
    row.paypal_status = remote_status or row.paypal_status or "CANCELLED"
    row.failure_reason = "Cancelled by the payer before approval."
    row.updated_at = utcnow()
    session.flush()
    return PaymentResult(transaction=row, order={"id": order_id, "status": row.paypal_status}, mode=checkout.mode)


async def sync_payment(
    session: Session, checkout: CheckoutBackend, *, order_id: str
) -> tuple[Transaction, bool]:
    """Refresh a local record from PayPal's authoritative state."""
    row = _find_owned_row(session, order_id, transaction_id=None)
    if checkout.mode == "demo":
        return row, False

    order = await checkout.get_order(order_id)
    status = normalize_status(order.get("status"))
    changed = status != row.status
    row.paypal_status = order.get("status")
    row.status = status
    if status == "completed" and not row.completed_at:
        captured = order.get("captured_minor")
        row.amount_captured_minor = captured if isinstance(captured, int) else row.amount_minor
        row.completed_at = utcnow()
        row.paypal_capture_id = order.get("capture_id") or row.paypal_capture_id
    row.updated_at = utcnow()
    session.flush()
    return row, changed


def _find_owned_row(
    session: Session, order_id: str, *, transaction_id: str | None
) -> Transaction:
    from .repository import get_by_order_id

    row = get_by_order_id(session, order_id)
    if row is None:
        # Do not reveal whether the order exists remotely.
        raise DomainError(
            "This order was not created by this application, so it cannot be captured.",
            code="order_not_owned",
        )
    if transaction_id and row.id != transaction_id:
        raise DomainError(
            "transaction_id does not match the supplied order.", code="reference_mismatch"
        )
    return row


async def _capture_on_paypal(paypal: PayPalService, order_id: str) -> dict[str, Any]:
    try:
        return await paypal.capture_order(order_id)
    except PayPalError as exc:
        if exc.name in {"ORDER_NOT_APPROVED", "ORDER_VALIDATION_FAILED"} or (
            exc.http_status == 422 and "not approved" in exc.message.lower()
        ):
            raise DomainError(
                "PayPal has not approved this order yet. The payer must complete the "
                "checkout before it can be captured.",
                code="order_not_approved",
                paypal_message=exc.message,
            ) from exc
        if exc.name == "UNPROCESSABLE_ENTITY" and "already" in exc.message.lower():
            order = await paypal.get_order(order_id)
            order["already_captured"] = True
            return order
        raise


def _assert_amount_matches(
    order: dict[str, Any], *, amount_minor: int, currency: str, context: str
) -> None:
    remote_minor = order.get("amount_minor")
    remote_currency = order.get("currency")

    if remote_minor is None or remote_currency is None:
        # get_order on some payloads omits purchase_units for pending orders;
        # creation always includes them, so treat a missing value as tampering
        # only when the remote explicitly disagrees.
        return

    if str(remote_currency).upper() != currency.upper():
        raise DomainError(
            f"PayPal returned currency {remote_currency} but {currency} was requested.",
            code="currency_mismatch",
        )
    if int(remote_minor) != int(amount_minor):
        raise DomainError(
            f"PayPal returned amount {format_amount(int(remote_minor), currency)} "
            f"but {format_amount(amount_minor, currency)} was requested.",
            code="amount_mismatch",
        )


def amount_from_request(raw: str | int | float, currency: str) -> int:
    """Small helper used by tests and validation endpoints."""
    return parse_amount_to_minor(raw, currency)
