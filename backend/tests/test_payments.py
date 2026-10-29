"""Payment endpoints — validation, ownership, idempotency and capture rules."""

from __future__ import annotations

import pytest


def _create(client, **overrides):
    payload = {"amount": "149.99", "currency": "USD", "description": "Invoice #7"}
    payload.update(overrides)
    return client.post("/api/payments/create-order", json=payload)


# ------------------------------------------------------------ invalid input
@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": "-5.00"},
        {"amount": "0"},
        {"amount": "0.00"},
        {"amount": "not-a-number"},
        {"amount": ""},
        {"amount": "10000000000"},
        {"currency": "XYZ"},
        {"currency": "usdx"},
        {"description": ""},
        {"description": "   "},
        {"description": "x" * 400},
        {"customer_reference": "x" * 300},
        {"amount": None},
    ],
)
def test_invalid_create_requests_are_rejected(client, overrides):
    response = _create(client, **overrides)
    assert response.status_code == 422, f"expected 422 for {overrides}, got {response.text}"
    detail = response.json()["detail"]
    assert detail["code"] in {"validation_error", "invalid_amount"}
    assert detail["errors"]


def test_missing_body_fields_rejected(client):
    response = client.post(
        "/api/payments/create-order", json={"currency": "USD", "description": "x"}
    )
    assert response.status_code == 422
    assert "amount" in " ".join(response.json()["detail"]["errors"])


def test_missing_body_rejected(client):
    assert client.post("/api/payments/create-order").status_code == 422


def test_wrong_content_type_rejected(client):
    response = client.post(
        "/api/payments/create-order",
        content='{"amount":"10","currency":"USD","description":"x"}',
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 422


# --------------------------------------------------------------- demo create
def test_create_order_in_labelled_demo_mode(client):
    body = _create(client).json()
    assert body["mode"] == "demo"
    assert body["is_demo"] is True
    assert body["status"] == "pending"
    assert body["amount"] == "149.99"
    assert body["paypal_client_id"] == ""
    assert "DEMO" in body["order_id"]
    assert "DEMO MODE" in body["notice"]
    assert "NOT a Sandbox transaction" in body["notice"]


def test_created_order_is_persisted_with_demo_flag(client, session):
    from app.services.repository import get_by_order_id

    created = _create(client).json()
    session.expire_all()
    row = get_by_order_id(session, created["order_id"])
    assert row is not None
    assert row.is_demo_record is True
    assert row.mode == "demo"
    assert row.amount_minor == 14999


# -------------------------------------------------------------- demo capture
def test_capture_approve_completes_and_persists(client):
    created = _create(client).json()
    response = client.post(
        "/api/payments/capture-order",
        json={"order_id": created["order_id"], "transaction_id": created["transaction_id"],
              "demo_outcome": "approve"},
    )
    assert response.status_code == 200
    txn = response.json()["transaction"]
    assert txn["status"] == "completed"
    assert txn["paypal_status"] == "COMPLETED"
    assert txn["amount"] == "149.99"
    assert txn["paypal_capture_id"].startswith("DEMO-CAP-")
    assert txn["completed_at"] is not None
    assert "DEMO MODE" in response.json()["notice"]


def test_capture_is_idempotent(client):
    created = _create(client).json()
    capture = {"order_id": created["order_id"], "transaction_id": created["transaction_id"]}

    first = client.post("/api/payments/capture-order", json={**capture, "demo_outcome": "approve"})
    second = client.post("/api/payments/capture-order", json={**capture, "demo_outcome": "decline"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["already_captured"] is True
    # The second call must not downgrade a completed payment.
    assert second.json()["transaction"]["status"] == "completed"
    assert second.json()["transaction"]["paypal_capture_id"] == first.json()["transaction"]["paypal_capture_id"]


def test_capture_decline_records_failure_reason(client):
    created = _create(client).json()
    response = client.post(
        "/api/payments/capture-order",
        json={"order_id": created["order_id"], "demo_outcome": "decline"},
    )
    txn = response.json()["transaction"]
    assert txn["status"] == "declined"
    assert txn["failure_reason"]
    assert txn["completed_at"] is None


@pytest.mark.parametrize("outcome,expected", [
    ("fail", "failed"),
    ("pending", "pending"),
])
def test_capture_outcomes(client, outcome, expected):
    created = _create(client).json()
    response = client.post(
        "/api/payments/capture-order",
        json={"order_id": created["order_id"], "demo_outcome": outcome},
    )
    assert response.json()["transaction"]["status"] == expected


# ------------------------------------------------------------- ownership
def test_capturing_an_unknown_order_returns_404(client):
    response = client.post("/api/payments/capture-order", json={"order_id": "ORDERNOTOURS123"})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "order_not_owned"


def test_transaction_id_mismatch_rejected(client):
    created = _create(client).json()
    response = client.post(
        "/api/payments/capture-order",
        json={"order_id": created["order_id"], "transaction_id": "txn_wrong"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "reference_mismatch"


def test_malformed_order_id_rejected(client):
    response = client.post("/api/payments/capture-order", json={"order_id": "../../etc/passwd"})
    assert response.status_code == 422


def test_sync_unknown_order_returns_404(client):
    assert client.get("/api/payments/order/ORDERNOPE1").status_code == 404


# ------------------------------------------------------------- cancellation
def test_cancel_pending_order(client):
    created = _create(client).json()
    response = client.post(
        "/api/payments/cancel-order",
        json={"order_id": created["order_id"], "transaction_id": created["transaction_id"]},
    )
    assert response.status_code == 200
    assert response.json()["transaction"]["status"] == "cancelled"
    assert response.json()["transaction"]["failure_reason"]


def test_cannot_cancel_a_completed_payment(client):
    created = _create(client).json()
    client.post(
        "/api/payments/capture-order",
        json={"order_id": created["order_id"], "demo_outcome": "approve"},
    )
    response = client.post(
        "/api/payments/cancel-order", json={"order_id": created["order_id"]}
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "already_captured"


# ----------------------------------------------------------- sandbox (mocked)
def test_create_order_uses_real_paypal_service(client, sandbox_env, mock_paypal):
    body = _create(client).json()
    assert body["mode"] == "sandbox"
    assert body["is_demo"] is False
    assert body["order_id"].startswith("ORDER")
    assert "TEST-CLIENT-ID" in body["paypal_client_id"]
    assert "checkoutnow" in (body["approve_link"] or "")
    assert body["approval_url"].startswith("https://")
    assert body["notice"] is None
    assert mock_paypal.calls["create"] == 1
    assert mock_paypal.calls["token"] == 1


def test_create_order_sends_exact_amount(client, sandbox_env, mock_paypal):
    created = _create(client, amount="1234.56", customer_reference="INV-99").json()
    order = mock_paypal.orders[created["order_id"]]
    assert order["amount"] == {"value": "1234.56", "currency_code": "USD"}
    assert order["custom_id"] == "INV-99"


def test_capture_verifies_and_persists_sandbox_result(client, sandbox_env, mock_paypal, session):
    created = _create(client, amount="250.00").json()
    response = client.post(
        "/api/payments/capture-order",
        json={"order_id": created["order_id"], "transaction_id": created["transaction_id"]},
    )
    assert response.status_code == 200
    txn = response.json()["transaction"]
    assert txn["status"] == "completed"
    assert txn["paypal_status"] == "COMPLETED"
    assert txn["amount"] == "250.00"
    assert txn["paypal_capture_id"]
    assert txn["mode"] == "sandbox"
    assert response.json()["already_captured"] is False
    assert mock_paypal.calls["capture"] == 1


def test_capture_twice_is_idempotent_against_sandbox(client, sandbox_env, mock_paypal):
    created = _create(client).json()
    payload = {"order_id": created["order_id"], "transaction_id": created["transaction_id"]}

    first = client.post("/api/payments/capture-order", json=payload)
    second = client.post("/api/payments/capture-order", json=payload)

    assert first.status_code == second.status_code == 200
    assert second.json()["already_captured"] is True
    # Only one network capture was issued.
    assert mock_paypal.calls["capture"] == 1


def test_capture_before_approval_is_reported_clearly(client, sandbox_env, mock_paypal):
    mock_paypal.capture_not_approved = True
    created = _create(client).json()
    response = client.post(
        "/api/payments/capture-order", json={"order_id": created["order_id"]}
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "order_not_approved"
    assert "approved" in detail["message"].lower()


def test_tampered_amount_is_rejected(client, sandbox_env, mock_paypal):
    created = _create(client, amount="100.00").json()
    # Simulate a response that disagrees with what we charged for.
    mock_paypal.orders[created["order_id"]]["amount"]["value"] = "9999.99"

    response = client.post(
        "/api/payments/capture-order", json={"order_id": created["order_id"]}
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "amount_mismatch"


def test_tampered_currency_is_rejected(client, sandbox_env, mock_paypal):
    created = _create(client, amount="100.00").json()
    mock_paypal.orders[created["order_id"]]["amount"]["currency_code"] = "EUR"

    response = client.post(
        "/api/payments/capture-order", json={"order_id": created["order_id"]}
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "currency_mismatch"


def test_paypal_create_failure_surfaces_as_502(client, sandbox_env, mock_paypal):
    mock_paypal.fail_create = (
        422,
        {"name": "INVALID_REQUEST", "message": "The requested action is not valid.",
         "details": [{"field": "purchase_units[0].amount.value", "issue": "The value must be greater than 0"}]},
    )
    response = _create(client)
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["code"] == "paypal_create_failed"
    assert detail["paypal_error"]["name"] == "INVALID_REQUEST"
    assert detail["paypal_error"]["paypal_status"] == 422


def test_malformed_paypal_create_response(client, sandbox_env, mock_paypal):
    mock_paypal.return_html = True
    response = _create(client)
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "paypal_create_failed"
    assert response.json()["detail"]["paypal_error"]["name"] == "MALFORMED_RESPONSE"


def test_capture_failure_surfaces_as_502(client, sandbox_env, mock_paypal):
    created = _create(client).json()
    mock_paypal.fail_capture = (500, {"name": "INTERNAL_SERVICE_ERROR", "message": "boom"})
    response = client.post(
        "/api/payments/capture-order", json={"order_id": created["order_id"]}
    )
    assert response.status_code == 502
    assert response.json()["detail"]["paypal_error"]["name"] == "INTERNAL_SERVICE_ERROR"


def test_demo_outcome_is_rejected_when_sandbox_configured(client, sandbox_env, mock_paypal):
    created = _create(client).json()
    response = client.post(
        "/api/payments/capture-order",
        json={"order_id": created["order_id"], "demo_outcome": "approve"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "demo_outcome_forbidden"


def test_sync_pulls_authoritative_status(client, sandbox_env, mock_paypal):
    created = _create(client).json()
    response = client.get(f"/api/payments/order/{created['order_id']}")
    assert response.status_code == 200
    assert response.json()["paypal_status"] == "PAYER_ACTION_REQUIRED"
    assert response.json()["synced"] is False
