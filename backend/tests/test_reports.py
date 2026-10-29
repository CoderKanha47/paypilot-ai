"""CSV / JSON exports and the printable summary."""

from __future__ import annotations

import csv
import io
import json

from tests.conftest import make_transaction


def test_csv_has_header_and_rows(client, seed_transactions):
    response = client.get("/api/reports/transactions.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert "paypilot-transactions-" in response.headers["content-disposition"]

    reader = csv.DictReader(io.StringIO(response.text))
    rows = list(reader)
    assert reader.fieldnames is not None
    assert reader.fieldnames[0] == "id"
    assert "paypal_order_id" in reader.fieldnames
    assert len(rows) == 6


def test_csv_amounts_are_exact(client, seed_transactions):
    rows = list(csv.DictReader(io.StringIO(client.get("/api/reports/transactions.csv").text)))
    completed = {row["description"]: row for row in rows if row["status"] == "completed"}
    assert completed["Logo design"]["amount"] == "100.00"
    assert completed["Website build"]["amount"] == "250.50"
    assert completed["Consulting"]["amount"] == "75.25"
    assert completed["Logo design"]["amount_captured"] == "100.00"
    assert completed["Logo design"]["is_demo_record"] == "false"


def test_csv_includes_demo_rows_and_labels_them(client, session):
    make_transaction(session, amount="10.00", is_demo_record=True, mode="demo")
    session.commit()
    rows = list(csv.DictReader(io.StringIO(client.get("/api/reports/transactions.csv").text)))
    demo = [row for row in rows if row["is_demo_record"] == "true"]
    assert len(demo) == 1
    assert demo[0]["mode"] == "demo"


def test_csv_can_exclude_demo_rows(client, seed_transactions):
    rows = list(
        csv.DictReader(
            io.StringIO(client.get("/api/reports/transactions.csv?include_demo=false").text)
        )
    )
    assert all(row["is_demo_record"] == "false" for row in rows)


def test_csv_still_returns_a_header_when_empty(client):
    response = client.get("/api/reports/transactions.csv")
    assert response.status_code == 200
    assert response.text.splitlines()[0].startswith("id,created_at")
    assert response.headers["X-Report-Rows"] == "0"


def test_json_report_structure(client, seed_transactions):
    response = client.get("/api/reports/transactions.json")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    payload = response.json()
    assert payload["report"] == "paypilot-transactions"
    assert payload["row_count"] == 6
    assert payload["contains_demo_rows"] is False
    assert payload["generated_at"].endswith("+00:00")
    assert len(payload["transactions"]) == 6
    assert payload["currency_note"]


def test_json_report_amounts_are_strings_not_floats(client, seed_transactions):
    payload = client.get("/api/reports/transactions.json").json()
    row = next(t for t in payload["transactions"] if t["description"] == "Website build")
    assert row["amount"] == "250.50"
    assert isinstance(row["amount"], str)


def test_json_report_flags_demo_content(client, session):
    make_transaction(session, amount="5.00", is_demo_record=True, mode="demo")
    session.commit()
    payload = client.get("/api/reports/transactions.json").json()
    assert payload["contains_demo_rows"] is True


def test_json_report_can_exclude_demo_rows(client, session):
    make_transaction(session, amount="5.00", is_demo_record=True, mode="demo")
    make_transaction(session, amount="6.00")
    session.commit()
    payload = client.get("/api/reports/transactions.json?include_demo=false").json()
    assert payload["row_count"] == 1
    assert payload["contains_demo_rows"] is False


def test_printable_summary(client, seed_transactions):
    body = client.get("/api/reports/summary").json()
    assert body["currency"] == "USD"
    assert body["total_captured"] == "425.75"
    assert body["total_pending"] == "40.00"
    assert body["transaction_count"] == 6
    assert len(body["monthly"]) == 12
    assert body["status_breakdown"]
    assert any("not financial" in note for note in body["notes"])


def test_report_of_empty_database_is_not_an_error(client):
    assert client.get("/api/reports/summary").json()["transaction_count"] == 0
    assert json.loads(client.get("/api/reports/transactions.json").text)["row_count"] == 0
