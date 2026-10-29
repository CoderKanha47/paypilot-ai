"""Shared pytest fixtures.

The suite runs fully offline: PayPal and the AI provider are mocked or run in
the labelled demo engine. No test spends real money or needs network access.

Environment is pinned *before* the application modules are imported.
"""

from __future__ import annotations

import os
import tempfile
from datetime import timedelta
from pathlib import Path

import httpx
import pytest

# ---------------------------------------------------------------- env setup
_TMP_DIR = Path(tempfile.mkdtemp(prefix="paypilot-tests-"))
os.environ["PAYPILOT_DATABASE_URL"] = f"sqlite:///{_TMP_DIR / 'test.db'}"
os.environ["APP_ENV"] = "test"
os.environ["SEED_DEMO_DATA"] = "false"
os.environ["AI_PROVIDER"] = "demo"
os.environ["PAYPAL_CLIENT_ID"] = ""
os.environ["PAYPAL_CLIENT_SECRET"] = ""
os.environ["LOG_LEVEL"] = "ERROR"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"

from app.config import Settings, get_settings, reset_settings_cache  # noqa: E402

reset_settings_cache()

from app.database import dispose_engine, init_db, session_scope  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.models import AppMeta, Transaction, utcnow  # noqa: E402
from app.money import to_minor  # noqa: E402
from app.rate_limit import SlidingWindowLimiter  # noqa: E402

dispose_engine()
init_db()

from fastapi.testclient import TestClient  # noqa: E402

from app.routers import assistant as assistant_router  # noqa: E402
from app.routers import payments as payments_router  # noqa: E402


@pytest.fixture(scope="session")
def app():
    return fastapi_app


@pytest.fixture(scope="session")
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_db():
    """Every test starts with an empty database and fresh rate limits."""
    with session_scope() as session:
        session.query(Transaction).delete()
        session.query(AppMeta).delete()
    payments_router._create_limiter.reset()
    payments_router._capture_limiter.reset()
    assistant_router._chat_limiter.reset()
    yield


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture
def session():
    with session_scope() as db:
        yield db


def make_transaction(
    session,
    *,
    amount: str = "100.00",
    currency: str = "USD",
    status: str = "completed",
    description: str = "Design retainer",
    reference: str | None = "REF-1",
    days_ago: int = 0,
    is_demo_record: bool = False,
    mode: str = "sandbox",
    paypal_order_id: str | None = None,
    paypal_capture_id: str | None = None,
    failure_reason: str | None = None,
) -> Transaction:
    """Insert a transaction row with exact integer minor units."""
    import uuid

    created = utcnow() - timedelta(days=days_ago)
    row = Transaction(
        paypal_order_id=paypal_order_id or f"ORDER{uuid.uuid4().hex[:20].upper()}",
        paypal_capture_id=paypal_capture_id
        or (f"CAP{uuid.uuid4().hex[:20].upper()}" if status == "completed" else None),
        paypal_intent="CAPTURE",
        status=status,
        paypal_status={"completed": "COMPLETED", "pending": "CREATED"}.get(status, status.upper()),
        amount_minor=to_minor(amount, currency),
        currency=currency,
        description=description,
        customer_reference=reference,
        mode=mode,
        is_demo_record=is_demo_record,
        amount_captured_minor=to_minor(amount, currency) if status == "completed" else None,
        failure_reason=failure_reason,
        created_at=created,
        updated_at=created,
        completed_at=created if status == "completed" else None,
    )
    session.add(row)
    session.flush()
    return row


@pytest.fixture
def seed_transactions(session):
    """A small, hand-checked dataset used by dashboard/report assertions.

    Totals: completed = 100.00 + 250.50 + 75.25 = 425.75 USD
    """
    rows = [
        make_transaction(session, amount="100.00", status="completed", days_ago=1,
                         description="Logo design", reference="A-1"),
        make_transaction(session, amount="250.50", status="completed", days_ago=40,
                         description="Website build", reference="A-2"),
        make_transaction(session, amount="75.25", status="completed", days_ago=120,
                         description="Consulting", reference="A-3"),
        make_transaction(session, amount="40.00", status="pending", days_ago=3,
                         description="Copywriting", reference="A-4"),
        make_transaction(session, amount="10.00", status="failed", days_ago=5,
                         description="Illustration", reference="A-5",
                         failure_reason="PayPal declined the funding source."),
        make_transaction(session, amount="20.00", status="cancelled", days_ago=7,
                         description="Photo shoot", reference="A-6"),
    ]
    session.flush()
    session.commit()  # visible to the API's separate connection during the test
    return rows


# --------------------------------------------------------------- mock PayPal
class MockPayPal:
    """Stateful fake of the PayPal Orders v2 API for httpx.MockTransport."""

    def __init__(self) -> None:
        self.orders: dict[str, dict] = {}
        self.calls = {"token": 0, "create": 0, "get": 0, "capture": 0}
        self.fail_token: int | None = None
        self.fail_create: tuple[int, dict] | None = None
        self.fail_capture: tuple[int, dict] | None = None
        self.malformed_create = False
        self.capture_not_approved = False
        self.capture_already_captured = False
        self.return_html = False
        self.unauthorized_once = False
        self.order_seq = 0

    # -- httpx transport -------------------------------------------------
    def __call__(self, request: httpx.Request) -> httpx.Response:  # type: ignore[name-defined]
        path = request.url.path
        if path.endswith("/v1/oauth2/token"):
            return self._token(request)
        if path.endswith("/v2/checkout/orders") and request.method == "POST":
            return self._create(request)
        if "/capture" in path and request.method == "POST":
            order_id = path.split("/orders/")[1].split("/")[0]
            return self._capture(order_id)
        if "/v2/checkout/orders/" in path and request.method == "GET":
            order_id = path.split("/orders/")[1]
            return self._get(order_id)
        return httpx.Response(404, json={"name": "NOT_FOUND", "message": "no route"})

    def _token(self, request: httpx.Request) -> httpx.Response:
        self.calls["token"] += 1
        if self.fail_token:
            return httpx.Response(
                self.fail_token,
                json={"error": "invalid_client", "error_description": "Client Authentication failed"},
            )
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Basic "):
            return httpx.Response(401, json={"error": "invalid_client"})
        return httpx.Response(
            200,
            json={
                "access_token": f"TEST-TOKEN-{self.calls['token']}",
                "expires_in": 32400,
                "token_type": "Bearer",
            },
        )

    def _create(self, request: httpx.Request) -> httpx.Response:
        self.calls["create"] += 1
        if self.fail_create:
            status, body = self.fail_create
            self.fail_create = None
            return httpx.Response(status, json=body)
        if self.malformed_create:
            return httpx.Response(200, text="<html>not json</html>")
        if self.return_html:
            return httpx.Response(200, text="<html>oops</html>", headers={"Content-Type": "text/html"})
        if not request.headers.get("authorization", "").startswith("Bearer "):
            return httpx.Response(401, json={"error": "unauthorized"})

        import json as _json

        body = _json.loads(request.content.decode())
        self.order_seq += 1
        order_id = f"ORDER{self.order_seq:06d}"
        unit = body["purchase_units"][0]
        order = {
            "id": order_id,
            "intent": body.get("intent", "CAPTURE"),
            "status": "PAYER_ACTION_REQUIRED",
            "amount": dict(unit["amount"]),
            "description": unit.get("description"),
            "custom_id": unit.get("custom_id"),
            "links": [
                {"rel": "approve", "href": f"https://www.sandbox.paypal.com/checkoutnow?token={order_id}"}
            ],
        }
        self.orders[order_id] = order
        return httpx.Response(201, json=order)

    def _get(self, order_id: str) -> httpx.Response:
        self.calls["get"] += 1
        if self.unauthorized_once:
            self.unauthorized_once = False
            return httpx.Response(401, json={"error": "invalid_token"})
        order = self.orders.get(order_id)
        if not order:
            return httpx.Response(404, json={"name": "ORDER_NOT_FOUND", "message": "Order not found"})
        return httpx.Response(200, json=order)

    def _capture(self, order_id: str) -> httpx.Response:
        self.calls["capture"] += 1
        order = self.orders.get(order_id)
        if not order:
            return httpx.Response(404, json={"name": "ORDER_NOT_FOUND", "message": "Order not found"})
        if self.capture_already_captured:
            return httpx.Response(
                422,
                json={
                    "name": "ORDER_ALREADY_CAPTURED",
                    "message": "Order is already captured",
                    "debug_id": "abc",
                },
            )
        if self.capture_not_approved:
            self.capture_not_approved = False
            return httpx.Response(
                422,
                json={
                    "name": "ORDER_NOT_APPROVED",
                    "message": "The requested order is not approved",
                    "details": [{"field": "intent", "issue": "ORDER_NOT_APPROVED"}],
                },
            )
        if self.fail_capture:
            status, body = self.fail_capture
            self.fail_capture = None
            return httpx.Response(status, json=body)

        captured = {
            **order,
            "status": "COMPLETED",
            "purchase_units": [
                {
                    "amount": dict(order["amount"]),
                    "payments": {
                        "captures": [
                            {
                                "id": f"CAPTURE{order_id[-6:]}",
                                "status": "COMPLETED",
                                "amount": dict(order["amount"]),
                                "seller_receivable_breakdown": {
                                    "gross_amount": dict(order["amount"]),
                                    "paypal_fee": {"value": "0.60", "currency_code": order["amount"]["currency_code"]},
                                },
                            }
                        ]
                    },
                }
            ],
        }
        self.orders[order_id] = captured
        return httpx.Response(201, json=captured)

    # -- helpers ---------------------------------------------------------
    def seed_order(self, order_id: str, *, amount: str, currency: str = "USD",
                   status: str = "PAYER_ACTION_REQUIRED") -> dict:
        order = {
            "id": order_id,
            "intent": "CAPTURE",
            "status": status,
            "amount": {"value": amount, "currency_code": currency},
            "links": [],
        }
        self.orders[order_id] = order
        return order


import httpx  # noqa: I001  (re-exported for test modules that use the transport)


@pytest.fixture
def mock_paypal() -> MockPayPal:
    return MockPayPal()


_SANDBOX_KEYS = (
    "PAYPAL_CLIENT_ID",
    "PAYPAL_CLIENT_SECRET",
    "PAYPAL_BASE_URL",
)


@pytest.fixture
def sandbox_env(mock_paypal):
    """Configure fake Sandbox credentials and inject the mocked PayPal client.

    Exercises the **real** ``PayPalService`` code path — only the HTTP transport
    is faked. Environment variables are restored manually so the settings cache
    is never left pointing at test credentials.
    """
    previous = {key: os.environ.get(key) for key in _SANDBOX_KEYS}
    os.environ["PAYPAL_CLIENT_ID"] = "TEST-CLIENT-ID"
    os.environ["PAYPAL_CLIENT_SECRET"] = "TEST-CLIENT-SECRET"
    os.environ["PAYPAL_BASE_URL"] = "https://api-m.sandbox.paypal.com"
    reset_settings_cache()

    from app.services.paypal import PayPalService

    settings = get_settings()
    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(mock_paypal),
        base_url="https://api-m.sandbox.paypal.com",
    )
    service = PayPalService(settings, client=http_client)

    original = fastapi_app.state.checkout
    fastapi_app.state.checkout = service
    try:
        yield settings
    finally:
        fastapi_app.state.checkout = original
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        reset_settings_cache()


@pytest.fixture
def rest_client(client):
    """Alias kept for tests that only need HTTP access."""
    return client
