"""Local checkout simulator used **only** when PayPal credentials are absent.

It emits the same normalized shape as :class:`app.services.paypal.PayPalService`
so the payment router has a single code path. Every record it produces is
persisted with ``mode="demo"`` and ``is_demo_record=True`` and the API responses
carry an explicit notice — the app never presents a simulated result as a
Sandbox transaction.
"""

from __future__ import annotations

import uuid
from typing import Any

from ..config import Settings
from ..errors import PayPalError
from ..money import format_amount


def _demo_order_id() -> str:
    return f"DEMO-ORDER-{uuid.uuid4().hex[:20].upper()}"


def _demo_capture_id() -> str:
    return f"DEMO-CAP-{uuid.uuid4().hex[:20].upper()}"


class DemoCheckout:
    """Simulated PayPal orders for UI exploration without credentials."""

    mode = "demo"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def configured(self) -> bool:
        return False

    async def aclose(self) -> None:  # parity with PayPalService
        return None

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
    ) -> dict[str, Any]:
        return {
            "id": _demo_order_id(),
            "status": "CREATED",
            "intent": intent,
            "approve_url": None,
            "amount_minor": amount_minor,
            "currency": currency,
            "capture_id": None,
            "captured_minor": None,
            "fee_minor": None,
            "failure_reason": None,
            "already_captured": False,
            "payer_email": None,
            "description": description,
            "reference": reference,
            "note": note,
            "raw": {"demo": True, "amount": format_amount(amount_minor, currency)},
        }

    async def get_order(self, order_id: str) -> dict[str, Any]:
        raise PayPalError(
            "Demo orders are tracked locally; there is no remote order to fetch.",
            name="DEMO_NO_REMOTE_ORDER",
        )

    async def capture_order(
        self, order_id: str, *, outcome: str = "approve"
    ) -> dict[str, Any]:
        """Simulate the payer's decision.

        ``outcome`` is supplied explicitly by the demo UI and only honoured when
        no PayPal credentials are configured.
        """
        base: dict[str, Any] = {
            "id": order_id,
            "intent": "CAPTURE",
            "approve_url": None,
            "currency": self.settings.paypal_currency,
            "already_captured": False,
            "payer_email": None,
            "raw": {"demo": True, "outcome": outcome},
        }
        if outcome == "approve":
            base.update(
                status="COMPLETED",
                capture_id=_demo_capture_id(),
                failure_reason=None,
            )
        elif outcome == "decline":
            base.update(
                status="DECLINED",
                capture_id=None,
                failure_reason="Demo simulation: the payer's funding source declined the charge.",
            )
        elif outcome == "fail":
            base.update(
                status="FAILED",
                capture_id=None,
                failure_reason="Demo simulation: PayPal returned a FAILED capture status.",
            )
        elif outcome == "pending":
            base.update(
                status="PENDING",
                capture_id=None,
                failure_reason="Demo simulation: capture is pending an asynchronous review.",
            )
        else:
            raise PayPalError(
                f"Unknown demo outcome '{outcome}'.", name="INVALID_DEMO_OUTCOME"
            )
        base.setdefault("captured_minor", None)
        base.setdefault("fee_minor", None)
        return base
