"""Payment endpoints: create -> (payer approves) -> capture -> verify -> persist."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..config import Settings
from ..deps import get_checkout, get_db, get_settings
from ..errors import PayPalError, bad_request, upstream_error
from ..logging_config import log_extra
from ..money import MoneyError
from ..rate_limit import SlidingWindowLimiter, rate_limit
from ..schemas import (
    CaptureOrderRequest,
    CaptureOrderResponse,
    CreateOrderRequest,
    CreateOrderResponse,
    OrderSyncResponse,
)
from ..services import payments as payment_service
from ..services import repository as repo
from ..services.serializers import to_transaction_out

logger = logging.getLogger("paypilot.api.payments")

router = APIRouter(prefix="/payments", tags=["payments"])

# Stricter limits for money-moving endpoints.
_create_limiter = SlidingWindowLimiter(max_requests=30, window_seconds=60)
_capture_limiter = SlidingWindowLimiter(max_requests=60, window_seconds=60)


@router.post(
    "/create-order",
    response_model=CreateOrderResponse,
    summary="Create a PayPal Sandbox order (server-side)",
)
async def create_order(
    request: Request,
    payload: CreateOrderRequest,
    session: Session = Depends(get_db),
    checkout=Depends(get_checkout),
    settings: Settings = Depends(get_settings),
) -> CreateOrderResponse:
    rate_limit(request, _create_limiter)
    try:
        result = await payment_service.create_payment(session, settings, checkout, payload)
    except MoneyError as exc:
        raise bad_request(str(exc), code="invalid_amount") from exc
    except PayPalError as exc:
        if exc.name == "CREDENTIALS_MISSING":
            raise bad_request(
                exc.message, code="paypal_not_configured", paypal_error=exc.as_dict()
            ) from exc
        if exc.name in {"INVALID_AMOUNT", "INVALID_ORDER_ID"}:
            raise bad_request(exc.message, code="invalid_payment_request") from exc
        logger.warning("PayPal create-order failed", extra=log_extra(error_name=exc.name))
        raise upstream_error(
            f"PayPal could not create the order: {exc.message}",
            code="paypal_create_failed",
            paypal_error=exc.as_dict(),
        ) from exc

    row = result.transaction
    notice = None
    if result.mode == "demo":
        notice = (
            "DEMO MODE: no PayPal order was created. Approving below simulates the payer "
            "locally — this is NOT a Sandbox transaction."
        )

    return CreateOrderResponse(
        transaction_id=row.id,
        order_id=row.paypal_order_id,
        status=row.status,  # type: ignore[arg-type]
        paypal_status=row.paypal_status,
        amount=payload.amount if isinstance(payload.amount, str) else str(payload.amount),
        currency=row.currency,
        description=row.description,
        approval_url=row.approval_url,
        approve_link=result.order.get("approve_url"),
        mode=result.mode,  # type: ignore[arg-type]
        is_demo=result.mode == "demo",
        paypal_client_id=settings.paypal_client_id if settings.paypal_configured else "",
        sdk_currency=row.currency,
        created_at=row.created_at,
        notice=notice,
    )


@router.post(
    "/capture-order",
    response_model=CaptureOrderResponse,
    summary="Capture an approved order (server-side, verified with PayPal)",
)
async def capture_order(
    request: Request,
    payload: CaptureOrderRequest,
    session: Session = Depends(get_db),
    checkout=Depends(get_checkout),
    settings: Settings = Depends(get_settings),
) -> CaptureOrderResponse:
    rate_limit(request, _capture_limiter)

    if payload.demo_outcome and settings.paypal_configured:
        raise bad_request(
            "demo_outcome is only accepted when PayPal credentials are absent.",
            code="demo_outcome_forbidden",
        )

    try:
        result = await payment_service.capture_payment(
            session,
            settings,
            checkout,
            order_id=payload.order_id,
            transaction_id=payload.transaction_id,
            demo_outcome=payload.demo_outcome,
        )
    except PayPalError as exc:
        logger.warning(
            "PayPal capture failed",
            extra=log_extra(order_id=payload.order_id, error_name=exc.name),
        )
        raise upstream_error(
            f"PayPal could not capture the order: {exc.message}",
            code="paypal_capture_failed",
            paypal_error=exc.as_dict(),
        ) from exc

    notice = None
    if result.mode == "demo":
        notice = "DEMO MODE: this result was simulated locally and is not a PayPal transaction."

    return CaptureOrderResponse(
        transaction=to_transaction_out(result.transaction),
        already_captured=result.already_captured,
        mode=result.mode,  # type: ignore[arg-type]
        notice=notice,
    )


@router.post(
    "/cancel-order",
    response_model=CaptureOrderResponse,
    summary="Record a payer cancellation (verified server-side)",
)
async def cancel_order(
    request: Request,
    payload: CaptureOrderRequest,
    session: Session = Depends(get_db),
    checkout=Depends(get_checkout),
) -> CaptureOrderResponse:
    rate_limit(request, _capture_limiter)
    try:
        result = await payment_service.cancel_payment(
            session, checkout, order_id=payload.order_id, transaction_id=payload.transaction_id
        )
    except PayPalError as exc:
        raise upstream_error(
            f"PayPal could not verify the order: {exc.message}",
            code="paypal_verify_failed",
            paypal_error=exc.as_dict(),
        ) from exc

    return CaptureOrderResponse(
        transaction=to_transaction_out(result.transaction),
        already_captured=False,
        mode=result.mode,  # type: ignore[arg-type]
        notice="Payment request marked as cancelled.",
    )


@router.get(
    "/order/{order_id}",
    response_model=OrderSyncResponse,
    summary="Refresh a local record from PayPal's authoritative state",
)
async def sync_order(
    order_id: str,
    session: Session = Depends(get_db),
    checkout=Depends(get_checkout),
) -> OrderSyncResponse:
    try:
        row, changed = await payment_service.sync_payment(
            session, checkout, order_id=order_id
        )
    except PayPalError as exc:
        raise upstream_error(
            f"PayPal could not return the order: {exc.message}",
            code="paypal_order_failed",
            paypal_error=exc.as_dict(),
        ) from exc

    return OrderSyncResponse(
        transaction=to_transaction_out(row),
        paypal_status=row.paypal_status or "UNKNOWN",
        synced=changed,
    )


@router.post("/reset-demo", include_in_schema=False, summary="Reset clearly-labelled demo data")
async def reset_demo(
    session: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict:
    if not settings.seed_demo_data:
        raise bad_request("Demo seeding is disabled for this deployment.", code="demo_disabled")
    from ..seed import clear_demo_data, seed_demo_data

    removed = await asyncio.to_thread(clear_demo_data, session)
    created = seed_demo_data(session, settings, force=True)
    session.commit()
    return {"removed": removed, "created": created, "notice": "Demo records only."}
