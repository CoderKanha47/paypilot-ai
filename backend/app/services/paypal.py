"""Official PayPal REST API client (Orders v2 + OAuth 2.0).

Design notes
------------
* All calls run **server side**. The browser never sees the client secret.
* The access token is cached until shortly before expiry and refreshed once on
  a 401 so a rotated/expired token never surfaces to the user.
* Every response is validated before it is trusted; malformed payloads raise
  :class:`~app.errors.PayPalError` rather than producing a half-parsed record.
* Capture is idempotent: PayPal answers ``ORDER_ALREADY_CAPTURED`` (HTTP 422),
  which we translate into "already captured" instead of an error.
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any

import httpx

from ..config import Settings
from ..errors import PayPalError
from ..logging_config import log_extra
from ..money import MoneyError, format_amount, parse_amount_to_minor

logger = logging.getLogger("paypilot.paypal")

# PayPal Orders v2 -> application status
PAYPAL_STATUS_MAP: dict[str, str] = {
    "CREATED": "pending",
    "SAVED": "pending",
    "APPROVED": "pending",
    "PAYER_ACTION_REQUIRED": "pending",
    "PENDING": "pending",
    "COMPLETED": "completed",
    "VOIDED": "cancelled",
    "CANCELLED": "cancelled",
    "CANCEL": "cancelled",
    "DECLINED": "declined",
    "DENIED": "declined",
    "FAILED": "failed",
    "EXPIRED": "expired",
    "REFUNDED": "refunded",
    "PARTIALLY_REFUNDED": "refunded",
    "REVOKED": "refunded",
}

TERMINAL_CAPTURE_STATUSES = {"COMPLETED", "PENDING", "FAILED", "DECLINED", "REFUNDED", "CANCELED"}


def normalize_status(paypal_status: str | None, *, fallback: str = "pending") -> str:
    """Map a raw PayPal status string onto the app's status vocabulary."""
    if not paypal_status:
        return fallback
    return PAYPAL_STATUS_MAP.get(paypal_status.strip().upper(), fallback)


def sdk_url(client_id: str, currency: str, *, intent: str = "capture") -> str:
    """Build the PayPal JavaScript SDK script URL (public client id only)."""
    from urllib.parse import urlencode

    if not client_id:
        return ""
    query = urlencode(
        {
            "client-id": client_id,
            "currency": currency,
            "intent": intent,
            "components": "buttons",
            "enable-funding": "card,venmo",
        }
    )
    return f"https://www.paypal.com/sdk/js?{query}"


class PayPalService:
    """Thin, validated client for the PayPal Sandbox/production REST API."""

    TOKEN_REFRESH_MARGIN_SECONDS = 60.0

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=settings.paypal_base_url.rstrip("/"),
            timeout=httpx.Timeout(settings.paypal_timeout_seconds, connect=10.0),
            follow_redirects=False,
            headers={"Accept": "application/json", "Accept-Language": "en_US"},
        )
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self._token_refreshing = False

    # ------------------------------------------------------------ lifecycle
    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @property
    def configured(self) -> bool:
        return self.settings.paypal_configured

    @property
    def mode(self) -> str:
        if not self.configured:
            return "disabled"
        return "sandbox" if self.settings.paypal_is_sandbox else "live"

    # ----------------------------------------------------------------- auth
    def _basic_auth_header(self) -> str:
        raw = f"{self.settings.paypal_client_id}:{self.settings.paypal_client_secret}".encode()
        return "Basic " + base64.b64encode(raw).decode("ascii")

    async def get_access_token(self, *, force_refresh: bool = False) -> str:
        """Return a valid OAuth 2.0 access token, caching it until expiry."""
        now = time.monotonic()
        if (
            not force_refresh
            and self._access_token
            and now < self._token_expires_at - self.TOKEN_REFRESH_MARGIN_SECONDS
        ):
            return self._access_token

        if not self.settings.paypal_configured:
            raise PayPalError(
                "PayPal credentials are not configured. Set PAYPAL_CLIENT_ID and "
                "PAYPAL_CLIENT_SECRET in your .env file to use the Sandbox.",
                name="CREDENTIALS_MISSING",
            )

        try:
            response = await self._client.post(
                "/v1/oauth2/token",
                headers={
                    "Authorization": self._basic_auth_header(),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                content="grant_type=client_credentials",
            )
        except httpx.TimeoutException as exc:
            raise PayPalError(
                "Timed out contacting PayPal's OAuth endpoint.", name="PAYPAL_TIMEOUT"
            ) from exc
        except httpx.HTTPError as exc:
            raise PayPalError(
                f"Could not reach PayPal: {type(exc).__name__}", name="PAYPAL_UNREACHABLE"
            ) from exc

        if response.status_code != 200:
            raise self._error_from_response(response, context="OAuth token request")

        try:
            payload = response.json()
            token = payload["access_token"]
            expires_in = float(payload.get("expires_in", 32400))
        except (ValueError, KeyError, TypeError) as exc:
            raise PayPalError(
                "PayPal returned a malformed OAuth response.", name="MALFORMED_RESPONSE"
            ) from exc

        if not isinstance(token, str) or not token:
            raise PayPalError(
                "PayPal returned an empty access token.", name="MALFORMED_RESPONSE"
            )

        self._access_token = token
        self._token_expires_at = time.monotonic() + expires_in
        logger.info(
            "Obtained PayPal access token (expires in %.0fs, mode=%s)",
            expires_in,
            self.mode,
            extra=log_extra(mode=self.mode, expires_in=int(expires_in)),
        )
        return token

    def invalidate_token(self) -> None:
        self._access_token = None
        self._token_expires_at = 0.0

    # --------------------------------------------------------------- plumbing
    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        content: str | None = None,
        headers: dict[str, str] | None = None,
        retry_auth: bool = True,
    ) -> dict[str, Any]:
        token = await self.get_access_token()
        request_headers = {"Authorization": f"Bearer {token}"}
        if headers:
            request_headers.update(headers)

        try:
            response = await self._client.request(
                method, path, json=json_body, content=content, headers=request_headers
            )
        except httpx.TimeoutException as exc:
            raise PayPalError(
                f"Timed out calling PayPal {method} {path}.", name="PAYPAL_TIMEOUT"
            ) from exc
        except httpx.HTTPError as exc:
            raise PayPalError(
                f"Could not reach PayPal ({type(exc).__name__}).", name="PAYPAL_UNREACHABLE"
            ) from exc

        if response.status_code in (401, 403) and retry_auth:
            # Token may have been revoked/expired early: refresh once and retry.
            self.invalidate_token()
            return await self._request(
                method,
                path,
                json_body=json_body,
                content=content,
                headers=headers,
                retry_auth=False,
            )

        if response.status_code >= 400:
            raise self._error_from_response(response, context=f"{method} {path}")

        if not response.content:
            return {}
        try:
            payload = response.json()
        except ValueError as exc:
            raise PayPalError(
                f"PayPal returned a non-JSON body for {method} {path}.",
                http_status=response.status_code,
                name="MALFORMED_RESPONSE",
                correlation_id=response.headers.get("Paypal-Debug-Id"),
            ) from exc
        if not isinstance(payload, dict):
            raise PayPalError(
                f"PayPal returned an unexpected payload type for {method} {path}.",
                http_status=response.status_code,
                name="MALFORMED_RESPONSE",
            )
        return payload

    def _error_from_response(self, response: httpx.Response, *, context: str) -> PayPalError:
        name = None
        message = f"PayPal rejected the request ({context}) with HTTP {response.status_code}."
        details = None
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            name = body.get("name") or body.get("error")
            message = str(body.get("message") or body.get("error_description") or message)
            details = body.get("details")
        correlation_id = response.headers.get("Paypal-Debug-Id")
        logger.warning(
            "PayPal API error during %s: HTTP %s %s",
            context,
            response.status_code,
            name or "",
            extra=log_extra(
                context=context,
                http_status=response.status_code,
                error_name=name,
                correlation_id=correlation_id,
            ),
        )
        return PayPalError(
            message,
            http_status=response.status_code,
            name=name,
            details=details,
            correlation_id=correlation_id,
        )

    # ----------------------------------------------------------- public API
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
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Create a server-side order (``intent=CAPTURE``) on PayPal."""
        try:
            amount_value = format_amount(amount_minor, currency)
            # Validate before hitting the network.
            if parse_amount_to_minor(amount_value, currency) != amount_minor:
                raise MoneyError("Amount could not be represented exactly.")
        except MoneyError as exc:
            raise PayPalError(str(exc), name="INVALID_AMOUNT") from exc

        purchase_unit: dict[str, Any] = {
            "amount": {"currency_code": currency, "value": amount_value},
            "description": description[:120],
        }
        if reference:
            # custom_id/invoice_id let us reconcile PayPal rows with our records.
            purchase_unit["custom_id"] = reference[:127]
            purchase_unit["invoice_id"] = reference[:127]

        body: dict[str, Any] = {
            "intent": intent,
            "purchase_units": [purchase_unit],
            "application_context": {
                "brand_name": self.settings.paypal_brand_name[:127],
                "landing_page": "BILLING",
                "user_action": "PAY_NOW",
                "shipping_preference": "NO_SHIPPING",
                "return_url": return_url or self.settings.paypal_return_url,
                "cancel_url": cancel_url or self.settings.paypal_cancel_url,
            },
        }
        if note:
            body["purchase_units"][0]["custom_id"] = (reference or note)[:127]

        headers = {}
        if idempotency_key:
            headers["PayPal-Request-Id"] = idempotency_key

        payload = await self._request("POST", "/v2/checkout/orders", json_body=body, headers=headers)
        return self._validate_order(payload, context="create order")

    async def get_order(self, order_id: str) -> dict[str, Any]:
        payload = await self._request("GET", f"/v2/checkout/orders/{self._id(order_id)}")
        return self._validate_order(payload, context="get order")

    async def capture_order(
        self, order_id: str, *, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        """Capture an order the payer has approved. Idempotent where PayPal allows."""
        headers = {}
        if idempotency_key:
            headers["PayPal-Request-Id"] = idempotency_key

        try:
            payload = await self._request(
                "POST", f"/v2/checkout/orders/{self._id(order_id)}/capture", json_body={}, headers=headers
            )
        except PayPalError as exc:
            if exc.name in {"ORDER_ALREADY_CAPTURED", "CAPTURE_ORDER_ALREADY_CAPTURED"} or (
                exc.http_status == 422 and "already" in exc.message.lower()
            ):
                # Re-fetch so the caller still receives authoritative state.
                order = await self.get_order(order_id)
                order["already_captured"] = True
                return order
            raise
        result = self._validate_order(payload, context="capture order")
        result["already_captured"] = bool(payload.get("_already_captured"))
        return result

    async def verify_order(self, order_id: str) -> dict[str, Any]:
        """Alias kept for readability at call sites."""
        return await self.get_order(order_id)

    # ------------------------------------------------------------ validation
    @staticmethod
    def _id(order_id: str) -> str:
        cleaned = order_id.strip()
        if not cleaned or len(cleaned) > 64 or not cleaned.replace("-", "").replace("_", "").isalnum():
            raise PayPalError("Malformed PayPal order id.", name="INVALID_ORDER_ID")
        return cleaned

    def _validate_order(self, payload: dict[str, Any], *, context: str) -> dict[str, Any]:
        order_id = payload.get("id")
        status = payload.get("status")
        if not isinstance(order_id, str) or not order_id:
            raise PayPalError(
                f"PayPal response for {context} is missing an order id.",
                name="MALFORMED_RESPONSE",
            )
        if not isinstance(status, str) or not status:
            raise PayPalError(
                f"PayPal response for {context} is missing a status.",
                name="MALFORMED_RESPONSE",
            )

        links = payload.get("links")
        approve_url = None
        if isinstance(links, list):
            for link in links:
                if isinstance(link, dict) and link.get("rel") == "approve" and link.get("href"):
                    approve_url = str(link["href"])
                    break

        amount_minor: int | None = None
        currency: str | None = None
        capture_id: str | None = None
        captured_minor: int | None = None
        fee_minor: int | None = None
        failure_reason: str | None = None

        units = payload.get("purchase_units")
        if isinstance(units, list) and units and isinstance(units[0], dict):
            unit = units[0]
            amount = unit.get("amount")
            if isinstance(amount, dict):
                try:
                    currency = str(amount.get("currency_code") or "").upper() or None
                    raw_value = amount.get("value")
                    if raw_value is not None and currency:
                        amount_minor = parse_amount_to_minor(str(raw_value), currency)
                except MoneyError:
                    amount_minor = None

            payments = unit.get("payments") or {}
            captures = payments.get("captures") if isinstance(payments, dict) else None
            if isinstance(captures, list) and captures and isinstance(captures[0], dict):
                capture = captures[0]
                capture_id = capture.get("id")
                capture_status = capture.get("status")
                capture_amount = capture.get("amount")
                if isinstance(capture_amount, dict) and currency:
                    try:
                        captured_minor = parse_amount_to_minor(
                            str(capture_amount.get("value")), currency
                        )
                    except (MoneyError, TypeError):
                        captured_minor = None
                seller_receivable = capture.get("seller_receivable_breakdown")
                if isinstance(seller_receivable, dict):
                    gross = seller_receivable.get("gross_amount")
                    paypal_fee = seller_receivable.get("paypal_fee")
                    try:
                        if isinstance(gross, dict) and currency:
                            gross_minor = parse_amount_to_minor(
                                str(gross.get("value")), currency
                            )
                            if isinstance(paypal_fee, dict):
                                fee_minor = parse_amount_to_minor(
                                    str(paypal_fee.get("value")), currency
                                )
                                if amount_minor is None:
                                    amount_minor = gross_minor
                    except MoneyError:
                        fee_minor = None
                if capture_status in {"FAILED", "DECLINED", "DENIED"}:
                    failure_reason = f"Capture {str(capture_status).lower()} by PayPal"
                if not amount_minor and isinstance(capture_amount, dict) and currency:
                    amount_minor = captured_minor

        # A declined/failed order often carries a top-level reason.
        if status in {"FAILED", "DECLINED", "DENIED", "EXPIRED"} and not failure_reason:
            reason = payload.get("reason") or payload.get("message")
            failure_reason = str(reason) if reason else f"PayPal returned status {status}"

        return {
            "id": order_id,
            "status": status,
            "intent": str(payload.get("intent") or "CAPTURE"),
            "approve_url": approve_url,
            "amount_minor": amount_minor,
            "currency": currency,
            "capture_id": capture_id,
            "captured_minor": captured_minor,
            "fee_minor": fee_minor,
            "failure_reason": failure_reason,
            "already_captured": bool(payload.get("_already_captured")),
            "payer_email": _safe_payer_identifier(payload),
            "raw": payload,
        }


def _safe_payer_identifier(payload: dict[str, Any]) -> str | None:
    """Extract a non-PII payer label (account id) for audit purposes only.

    We deliberately do **not** keep the payer's email address or name: it is
    unnecessary for this product and must not be forwarded to the AI provider.
    """
    payer = payload.get("payer")
    if isinstance(payer, dict):
        for key in ("account_id", "payer_id"):
            value = payer.get(key)
            if isinstance(value, str) and value:
                return value
    return None
