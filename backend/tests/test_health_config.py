"""Health, configuration and secret-exposure checks."""

from __future__ import annotations


def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert body["app"] == "PayPilot AI"
    assert body["paypal_configured"] is False
    assert body["paypal_mode"] == "disabled"
    assert body["ai_provider"] == "demo"


def test_health_reports_sandbox_when_configured(client, sandbox_env):
    body = client.get("/api/health").json()
    assert body["paypal_configured"] is True
    assert body["paypal_mode"] == "sandbox"


def test_config_exposes_only_public_values(client):
    body = client.get("/api/config").json()
    assert body["app_name"] == "PayPilot AI"
    assert body["demo_mode"] is True
    assert body["paypal"]["configured"] is False
    assert body["paypal"]["client_id"] == ""
    assert body["paypal"]["currency"] == "USD"
    assert "DEMO" in body["notice"]
    assert body["ai"]["provider"] == "demo"


def test_config_never_leaks_secrets(client, sandbox_env):
    text = client.get("/api/config").text
    assert "TEST-CLIENT-SECRET" not in text
    assert "client_secret" not in text.lower()
    # The public client id IS safe (and required) to expose for the JS SDK.
    assert "TEST-CLIENT-ID" in text


def test_all_endpoints_never_return_the_secret(client, sandbox_env):
    for path in ("/api/health", "/api/config", "/api/dashboard", "/api/transactions"):
        assert "TEST-CLIENT-SECRET" not in client.get(path).text


def test_unknown_api_route_returns_structured_404(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_found"


def test_cors_restricts_origin(client, sandbox_env):
    allowed = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"

    blocked = client.options(
        "/api/health",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert blocked.headers.get("access-control-allow-origin") is None


def test_security_headers_present(client):
    response = client.get("/api/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_oversized_payload_rejected(client):
    big = "x" * 2_000_000
    response = client.post(
        "/api/payments/create-order",
        json={"amount": "10", "currency": "USD", "description": big},
    )
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "payload_too_large"


def test_openapi_document_available(client):
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    for expected in (
        "/api/health",
        "/api/config",
        "/api/dashboard",
        "/api/transactions",
        "/api/payments/create-order",
        "/api/payments/capture-order",
        "/api/assistant/chat",
        "/api/reports/transactions.csv",
        "/api/reports/transactions.json",
    ):
        assert expected in paths, f"missing documented route {expected}"
