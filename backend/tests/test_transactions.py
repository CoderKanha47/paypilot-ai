"""Transaction persistence, search, filters and detail lookup."""

from __future__ import annotations

from datetime import timedelta

from app.models import utcnow
from app.money import to_minor
from tests.conftest import make_transaction


def test_transaction_persists_exactly(client, session):
    row = make_transaction(
        session,
        amount="99.99",
        description="Quarterly support",
        reference="Q3-2026",
        paypal_order_id="ORDERPERSIST1",
    )
    session.commit()

    body = client.get(f"/api/transactions/{row.id}").json()
    assert body["amount"] == "99.99"
    assert body["amount_minor"] == 9999
    assert body["currency"] == "USD"
    assert body["description"] == "Quarterly support"
    assert body["customer_reference"] == "Q3-2026"
    assert body["paypal_order_id"] == "ORDERPERSIST1"
    assert body["status"] == "completed"


def test_persisted_minor_units_survive_reload(session):
    row = make_transaction(session, amount="0.07")
    session.commit()
    session.expire_all()
    reloaded = session.get(type(row), row.id)
    assert reloaded is not None
    assert reloaded.amount_minor == 7
    assert reloaded.amount_minor == to_minor("0.07", "USD")


def test_list_returns_all_and_respects_limit(client, seed_transactions):
    body = client.get("/api/transactions").json()
    assert body["total"] == 6
    assert len(body["items"]) == 6

    page = client.get("/api/transactions?limit=2&offset=2").json()
    assert page["total"] == 6
    assert len(page["items"]) == 2
    assert page["offset"] == 2


def test_search_matches_description_reference_and_order_id(client, seed_transactions):
    assert client.get("/api/transactions?search=Website").json()["total"] == 1
    assert client.get("/api/transactions?search=A-3").json()["total"] == 1
    assert client.get("/api/transactions?search=logo").json()["total"] == 1
    assert client.get("/api/transactions?search=nothing-here").json()["total"] == 0


def test_status_filter(client, seed_transactions):
    assert client.get("/api/transactions?status=pending").json()["total"] == 1
    assert client.get("/api/transactions?status=completed").json()["total"] == 3
    assert client.get("/api/transactions?status=failed_or_cancelled").json()["total"] == 2
    assert client.get("/api/transactions?status=all").json()["total"] == 6


def test_counts_by_status_returned(client, seed_transactions):
    counts = client.get("/api/transactions").json()["counts_by_status"]
    assert counts["completed"] == 3
    assert counts["pending"] == 1


def test_date_range_filter(client, seed_transactions):
    recent = client.get("/api/transactions?date_from=2000-01-01").json()
    assert recent["total"] == 6

    narrow = client.get("/api/transactions?date_from=2999-01-01").json()
    assert narrow["total"] == 0


def test_date_filter_is_inclusive_of_end_day(client, session):
    today = utcnow()
    make_transaction(session, amount="10.00")
    session.commit()
    today_str = today.strftime("%Y-%m-%d")
    assert client.get(f"/api/transactions?date_to={today_str}").json()["total"] == 1


def test_invalid_status_filter_is_rejected(client):
    response = client.get("/api/transactions?status=banana")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_status"


def test_invalid_date_format_is_rejected(client):
    response = client.get("/api/transactions?date_from=31-12-2026")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_date"


def test_detail_by_order_id_also_works(client, seed_transactions):
    row_id = client.get("/api/transactions").json()["items"][0]["id"]
    by_id = client.get(f"/api/transactions/{row_id}")
    order_id = by_id.json()["paypal_order_id"]
    by_order = client.get(f"/api/transactions/{order_id}")
    assert by_order.status_code == 200
    assert by_order.json()["id"] == row_id


def test_missing_transaction_returns_structured_404(client):
    response = client.get("/api/transactions/txn_does_not_exist")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "transaction_not_found"


def test_customer_note_is_not_exposed(client, session):
    """Internal notes stay internal — only relevant fields reach the API."""
    row = make_transaction(session, amount="10.00")
    row.customer_note = "internal: net 15 terms"
    session.commit()
    body = client.get(f"/api/transactions/{row.id}").json()
    assert "customer_note" not in body


def test_ordering_is_newest_first(client, session):
    older = make_transaction(session, amount="10.00", description="Older")
    older.created_at = utcnow() - timedelta(days=10)
    make_transaction(session, amount="20.00", description="Newer")
    session.commit()

    items = client.get("/api/transactions").json()["items"]
    assert items[0]["description"] == "Newer"
