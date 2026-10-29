"""CSV / JSON / printable-summary exports."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ..config import Settings
from ..deps import get_db, get_settings
from ..errors import bad_request
from ..money import from_minor
from ..schemas import ReportSummaryResponse
from ..services import repository as repo
from ..services.analytics import build_dashboard

router = APIRouter(prefix="/reports", tags=["reports"])

CSV_COLUMNS = [
    "id",
    "created_at",
    "completed_at",
    "status",
    "paypal_status",
    "amount",
    "currency",
    "amount_captured",
    "description",
    "customer_reference",
    "paypal_order_id",
    "paypal_capture_id",
    "failure_reason",
    "mode",
    "is_demo_record",
]


def _rows(session: Session, include_demo: bool = True) -> list:
    return list(repo.all_transactions(session, include_demo=include_demo))


def _amount(minor: int | None, currency: str) -> str:
    if minor is None:
        return ""
    exponent = 0 if currency in {"JPY", "KRW", "VND", "CLP", "ISK", "HUF", "TWD"} else 2
    return f"{from_minor(minor, currency):.{exponent}f}"


def _iso(value: datetime | None) -> str:
    return value.isoformat(sep=" ", timespec="seconds") if value else ""


def _records(session: Session) -> list[dict]:
    records: list[dict] = []
    for row in _rows(session):
        records.append(
            {
                "id": row.id,
                "created_at": _iso(row.created_at),
                "completed_at": _iso(row.completed_at),
                "status": row.status,
                "paypal_status": row.paypal_status or "",
                "amount": _amount(row.amount_minor, row.currency),
                "currency": row.currency,
                "amount_captured": _amount(row.amount_captured_minor, row.currency),
                "description": row.description,
                "customer_reference": row.customer_reference or "",
                "paypal_order_id": row.paypal_order_id,
                "paypal_capture_id": row.paypal_capture_id or "",
                "failure_reason": row.failure_reason or "",
                "mode": row.mode,
                "is_demo_record": str(row.is_demo_record).lower(),
            }
        )
    return records


def _filename(extension: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"paypilot-transactions-{stamp}.{extension}"


@router.get("/transactions.csv", summary="Download transactions as CSV")
def transactions_csv(
    session: Session = Depends(get_db),
    include_demo: bool = Query(default=True, description="Include rows labelled DEMO"),
) -> Response:
    records = _records(session)
    if not include_demo:
        records = [r for r in records if r["is_demo_record"] == "false"]

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    try:
        writer.writeheader()
        writer.writerows(records)
    except csv.Error as exc:  # pragma: no cover - defensive
        raise bad_request(f"Could not build the CSV report: {exc}", code="report_failed") from exc

    content = buffer.getvalue()
    if not content:
        raise bad_request("The CSV report could not be generated.", code="report_failed")

    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{_filename("csv")}"',
            "X-Report-Rows": str(len(records)),
        },
    )


@router.get("/transactions.json", summary="Download transactions as JSON")
def transactions_json(
    session: Session = Depends(get_db),
    include_demo: bool = Query(default=True),
) -> Response:
    records = _records(session)
    if not include_demo:
        records = [r for r in records if r["is_demo_record"] == "false"]

    payload = {
        "report": "paypilot-transactions",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "row_count": len(records),
        "contains_demo_rows": any(r["is_demo_record"] == "true" for r in records),
        "currency_note": "Amounts are decimal strings; sum only within a single currency.",
        "transactions": records,
    }
    try:
        content = json.dumps(payload, indent=2, ensure_ascii=False)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise bad_request(f"Could not build the JSON report: {exc}", code="report_failed") from exc

    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{_filename("json")}"'},
    )


@router.get(
    "/summary", response_model=ReportSummaryResponse, summary="Printable transaction summary"
)
def summary(
    session: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> ReportSummaryResponse:
    data = build_dashboard(session, settings, recent_limit=1, months=12)
    records = _records(session)
    notes = list(data.notes) or ["Figures are computed from the transactions stored in this app."]
    notes.append("PayPilot AI is not financial, legal or tax advice.")
    return ReportSummaryResponse(
        generated_at=data.generated_at,
        currency=data.metrics["primary_currency"],
        total_captured=data.metrics["total_captured"],  # type: ignore[arg-type]
        total_pending=data.metrics["total_pending"],  # type: ignore[arg-type]
        transaction_count=data.metrics["total_transactions"],
        status_breakdown=data.status_distribution,  # type: ignore[arg-type]
        monthly=data.monthly,  # type: ignore[arg-type]
        notes=notes,
    )
