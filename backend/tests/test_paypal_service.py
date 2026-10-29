"""PayPalService unit tests — OAuth caching, validation and error handling.

Every test uses ``httpx.MockTransport``: no network, no credentials, no money.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.errors import PayPalError
from app.services.paypal import PayPalService, normalize_status, sdk_url
from tests.conftest import MockPayPal, get_settings


def make_service(handler, **settings_overrides) -> tuple[PayPalService, httpx.AsyncClient]:
    settings = get_settings().model_copy(update=settings_overrides)
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api-m.sandbox.paypal.com",
    )
    return PayPalService(settings, client=client), client


def configured() -> dict:
    return {"paypal_client_id": "CID", "paypal_client_secret": "CSEC"}


# ------------------------------------------------------------------- OAuth
@pytest.mark.asyncio
async def test_access_token_is_cached_until_expiry():
    mock = MockPayPal()
    service, client = make_service(mock, **configured())
    try:
        first = await service.get_access_token()
        second = await service.get_access_token()
        assert first == second
        assert mock.calls["token"] == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_forced_refresh_requests_a_new_token():
    mock = MockPayPal()
    service, client = make_service(mock, **configured())
    try:
        first = await service.get_access_token()
        second = await service.get_access_token(force_refresh=True)
        assert first != second
        assert mock.calls["token"] == 2
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_invalid_token_response_raises_paypal_error():
    mock = MockPayPal()
    mock.fail_token = 401
    service, client = make_service(mock, **configured())
    try:
        with pytest.raises(PayPalError) as excinfo:
            await service.get_access_token()
        assert excinfo.value.name == "invalid_client"
        assert excinfo.value.http_status == 401
        assert "authentication" in excinfo.value.message.lower()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_missing_credentials_raise_a_clear_error():
    settings = get_settings().model_copy(update={"paypal_client_id": "", "paypal_client_secret": ""})
    service = PayPalService(settings, client=httpx.AsyncClient(transport=httpx.MockTransport(MockPayPal())))
    with pytest.raises(PayPalError) as excinfo:
        await service.get_access_token()
    assert excinfo.value.name == "CREDENTIALS_MISSING"
    assert "PAYPAL_CLIENT_ID" in excinfo.value.message


@pytest.mark.asyncio
async def test_expired_token_is_reused_after_a_401_and_refreshed_once():
    mock = MockPayPal()
    mock.unauthorized_once = True
    service, client = make_service(mock, **configured())
    try:
        order = await service.create_order(
            amount_minor=1000, currency="USD", description="Test"
        )
        # 401 on GET -> invalidate -> new token -> retry succeeds.
        fetched = await service.get_order(order["id"])
        assert fetched["id"] == order["id"]
        assert mock.calls["token"] == 2
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_network_timeout_becomes_a_paypal_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("boom", request=request)

    service, client = make_service(handler, **configured())
    try:
        with pytest.raises(PayPalError) as excinfo:
            await service.get_access_token()
        assert excinfo.value.name == "PAYPAL_TIMEOUT"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_unreachable_host_becomes_a_paypal_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    service, client = make_service(handler, **configured())
    try:
        with pytest.raises(PayPalError) as excinfo:
            await service.get_access_token()
        assert excinfo.value.name == "PAYPAL_UNREACHABLE"
    finally:
        await client.aclose()


# ------------------------------------------------------------- create order
@pytest.mark.asyncio
async def test_create_order_sends_expected_body():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(200, json={"access_token": "T", "expires_in": 32400})
        captured.append(request)
        return httpx.Response(201, json={
            "id": "ORDERABC", "status": "PAYER_ACTION_REQUIRED",
            "links": [{"rel": "approve", "href": "https://paypal/checkoutnow?token=ORDERABC"}],
        })

    service, client = make_service(handler, **configured())
    try:
        order = await service.create_order(
            amount_minor=123456,
            currency="USD",
            description="Invoice for services",
            reference="INV-42",
        )
        assert order["id"] == "ORDERABC"
        assert order["approve_url"].startswith("https://paypal/")
        assert order["status"] == "PAYER_ACTION_REQUIRED"

        body = json.loads(captured[0].content)
        assert body["intent"] == "CAPTURE"
        assert body["purchase_units"][0]["amount"] == {"value": "1234.56", "currency_code": "USD"}
        assert body["purchase_units"][0]["custom_id"] == "INV-42"
        assert body["purchase_units"][0]["invoice_id"] == "INV-42"
        assert body["application_context"]["return_url"]
        assert body["application_context"]["cancel_url"]
        assert captured[0].headers["authorization"].startswith("Bearer ")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_create_order_rejects_an_unrepresentable_amount():
    service, client = make_service(MockPayPal(), **configured())
    try:
        with pytest.raises(PayPalError) as excinfo:
            await service.create_order(amount_minor=-1, currency="USD", description="x")
        assert excinfo.value.name == "INVALID_AMOUNT"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_create_order_rejects_missing_status_in_response():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(200, json={"access_token": "T", "expires_in": 32400})
        return httpx.Response(201, json={"id": "ORDERX"})

    service, client = make_service(handler, **configured())
    try:
        with pytest.raises(PayPalError) as excinfo:
            await service.create_order(amount_minor=100, currency="USD", description="x")
        assert excinfo.value.name == "MALFORMED_RESPONSE"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_create_order_rejects_non_json_response():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(200, json={"access_token": "T", "expires_in": 32400})
        return httpx.Response(200, text="<html>hello</html>")

    service, client = make_service(handler, **configured())
    try:
        with pytest.raises(PayPalError) as excinfo:
            await service.create_order(amount_minor=100, currency="USD", description="x")
        assert excinfo.value.name == "MALFORMED_RESPONSE"
    finally:
        await client.aclose()


# ------------------------------------------------------------------ capture
@pytest.mark.asyncio
async def test_capture_parses_capture_breakdown():
    mock = MockPayPal()
    service, client = make_service(mock, **configured())
    try:
        order = await service.create_order(
            amount_minor=5000, currency="USD", description="Widget"
        )
        result = await service.capture_order(order["id"])
        assert result["status"] == "COMPLETED"
        assert result["capture_id"].startswith("CAPTURE")
        assert result["captured_minor"] == 5000
        assert result["fee_minor"] == 60  # 0.60
        assert result["already_captured"] is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_capture_of_already_captured_order_refetches_instead_of_failing():
    mock = MockPayPal()
    mock.capture_already_captured = True
    mock.seed_order("ORDERDUP1", amount="10.00", status="COMPLETED")
    service, client = make_service(mock, **configured())
    try:
        result = await service.capture_order("ORDERDUP1")
        assert result["already_captured"] is True
        assert result["status"] == "COMPLETED"
        assert mock.calls["get"] == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_capture_error_carries_name_details_and_correlation_id():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth2/token"):
            return httpx.Response(200, json={"access_token": "T", "expires_in": 32400})
        return httpx.Response(
            422,
            json={"name": "ORDER_NOT_APPROVED", "message": "not approved yet",
                  "details": [{"field": "intent", "issue": "ORDER_NOT_APPROVED"}]},
            headers={"Paypal-Debug-Id": "debug-123"},
        )

    service, client = make_service(handler, **configured())
    try:
        with pytest.raises(PayPalError) as excinfo:
            await service.capture_order("ORDERX")
        error = excinfo.value
        assert error.http_status == 422
        assert error.name == "ORDER_NOT_APPROVED"
        assert error.correlation_id == "debug-123"
        assert error.details[0]["issue"] == "ORDER_NOT_APPROVED"
        assert error.as_dict()["name"] == "ORDER_NOT_APPROVED"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_malformed_order_id_is_rejected_before_the_network():
    mock = MockPayPal()
    service, client = make_service(mock, **configured())
    try:
        for bad in ("", "  ", "a" * 100, "order; DROP TABLE", "../orders"):
            with pytest.raises(PayPalError) as excinfo:
                await service.get_order(bad)
            assert excinfo.value.name in {"INVALID_ORDER_ID", "CREDENTIALS_MISSING"}
        assert mock.calls["token"] <= 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_get_order_missing_returns_404_error():
    mock = MockPayPal()
    service, client = make_service(mock, **configured())
    try:
        with pytest.raises(PayPalError) as excinfo:
            await service.get_order("ORDERNOPE")
        assert excinfo.value.http_status == 404
        assert excinfo.value.name == "ORDER_NOT_FOUND"
    finally:
        await client.aclose()


# ------------------------------------------------------------------ helpers
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("COMPLETED", "completed"),
        ("CREATED", "pending"),
        ("PAYER_ACTION_REQUIRED", "pending"),
        ("APPROVED", "pending"),
        ("PENDING", "pending"),
        ("DECLINED", "declined"),
        ("DENIED", "declined"),
        ("FAILED", "failed"),
        ("VOIDED", "cancelled"),
        ("CANCELLED", "cancelled"),
        ("EXPIRED", "expired"),
        ("REFUNDED", "refunded"),
        (None, "pending"),
        ("SOMETHING_NEW", "pending"),
    ],
)
def test_normalize_status_mapping(raw, expected):
    assert normalize_status(raw) == expected


def test_sdk_url_contains_public_client_id_and_currency():
    url = sdk_url("PUBLIC-ID", "EUR")
    assert "client-id=PUBLIC-ID" in url
    assert "currency=EUR" in url
    assert "intent=capture" in url
    assert "www.paypal.com/sdk/js" in url
    assert sdk_url("", "USD") == ""


def test_service_reports_disabled_mode_without_credentials():
    settings = get_settings().model_copy(
        update={"paypal_client_id": "", "paypal_client_secret": ""}
    )
    service = PayPalService(settings, client=httpx.AsyncClient(transport=httpx.MockTransport(MockPayPal())))
    assert service.configured is False
    assert service.mode == "disabled"


def test_service_reports_sandbox_mode_with_credentials():
    settings = get_settings().model_copy(
        update={"paypal_client_id": "a", "paypal_client_secret": "b"}
    )
    service = PayPalService(settings, client=httpx.AsyncClient(transport=httpx.MockTransport(MockPayPal())))
    assert service.configured is True
    assert service.mode == "sandbox"
