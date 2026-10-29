"""Dashboard metrics must equal what the persisted rows actually add up to."""

from __future__ import annotations

from decimal import Decimal

from tests.conftest import make_transaction


def test_dashboard_zero_state(client):
    body = client.get("/api/dashboard").json()
    assert body["metrics"]["total_transactions"] == 0
    assert body["metrics"]["total_captured"] == "0.00"
    assert body["metrics"]["total_captured_minor"] == 0
    assert body["metrics"]["success_rate"] == 0.0
    assert body["recent"] == []
    assert body["metrics"]["demo_data_included"] is False


def test_dashboard_totals_from_persisted_rows(client, seed_transactions):
    body = client.get("/api/dashboard").json()
    metrics = body["metrics"]

    # 100.00 + 250.50 + 75.25 = 425.75
    assert metrics["total_captured"] == "425.75"
    assert metrics["total_captured_minor"] == 42575
    assert metrics["captured_count"] == 3
    assert metrics["total_pending"] == "40.00"
    assert metrics["pending_count"] == 1
    assert metrics["failed_count"] == 1  # failed + declined
    assert metrics["cancelled_count"] == 1  # cancelled + expired
    assert metrics["total_transactions"] == 6
    assert metrics["primary_currency"] == "USD"
    assert metrics["demo_data_included"] is False


def test_average_payment_is_decimal_not_binary_float(client, seed_transactions):
    metrics = client.get("/api/dashboard").json()["metrics"]
    # 425.75 / 3 = 141.91666... -> 141.92
    assert metrics["average_payment"] == "141.92"
    assert Decimal(metrics["average_payment"]) == Decimal("141.92")


def test_success_rate_computed_from_counts(client, seed_transactions):
    metrics = client.get("/api/dashboard").json()["metrics"]
    # completed 3, attempted = 3 completed + 1 failed + 1 cancelled = 5
    assert metrics["success_rate"] == 60.0


def test_monthly_chart_matches_total(client, seed_transactions):
    body = client.get("/api/dashboard").json()
    assert len(body["monthly"]) == 6
    chart_total = sum((Decimal(point["amount"]) for point in body["monthly"]), Decimal(0))
    assert chart_total == Decimal("425.75")
    for point in body["monthly"]:
        assert point["month"].count("-") == 1
        assert point["label"]
        assert isinstance(point["count"], int)


def test_status_distribution_adds_up(client, seed_transactions):
    body = client.get("/api/dashboard").json()
    distribution = body["status_distribution"]
    assert sum(entry["count"] for entry in distribution) == 6
    by_status = {entry["status"]: entry["count"] for entry in distribution}
    assert by_status["completed"] == 3
    assert by_status["pending"] == 1
    assert by_status["failed"] == 1
    assert by_status["cancelled"] == 1
    completed = next(e for e in distribution if e["status"] == "completed")
    assert completed["amount"] == "425.75"


def test_recent_transactions_ordered_newest_first(client, seed_transactions):
    recent = client.get("/api/dashboard").json()["recent"]
    assert len(recent) == 6
    timestamps = [row["created_at"] for row in recent]
    assert timestamps == sorted(timestamps, reverse=True)


def test_dashboard_respects_recent_limit(client, seed_transactions):
    recent = client.get("/api/dashboard?recent=2").json()["recent"]
    assert len(recent) == 2


def test_demo_rows_are_flagged(client, session):
    make_transaction(session, amount="50.00", is_demo_record=True, mode="demo")
    session.commit()

    body = client.get("/api/dashboard").json()
    assert body["metrics"]["demo_data_included"] is True
    flagged = [row for row in body["recent"] if row["is_demo_record"]]
    assert flagged and flagged[0]["mode"] == "demo"


def test_multi_currency_amounts_are_never_summed(client, session):
    make_transaction(session, amount="100.00", currency="USD", status="completed")
    make_transaction(session, amount="5000", currency="JPY", status="completed")
    session.commit()

    metrics = client.get("/api/dashboard").json()["metrics"]
    assert metrics["total_captured"] == "100.00"
    assert metrics["other_currencies"] == [
        {"currency": "JPY", "amount": "5000", "count": 1}
    ]


def test_dashboard_after_a_live_capture(client, session, sandbox_env, mock_paypal):
    """Metrics move when a payment is captured through the mocked Sandbox."""
    created = client.post(
        "/api/payments/create-order",
        json={"amount": "20.00", "currency": "USD", "description": "Metric test"},
    ).json()
    client.post(
        "/api/payments/capture-order",
        json={"order_id": created["order_id"], "transaction_id": created["transaction_id"]},
    )

    metrics = client.get("/api/dashboard").json()["metrics"]
    assert metrics["total_captured"] == "20.00"
    assert metrics["captured_count"] == 1
    assert metrics["demo_data_included"] is False
