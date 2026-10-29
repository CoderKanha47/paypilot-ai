"""Transaction history and detail endpoints."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from ..deps import get_db
from ..errors import not_found
from ..schemas import TransactionListResponse, TransactionOut
from ..services import repository as repo
from ..services.serializers import to_transaction_out

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _parse_day(value: str | None, *, end_of_day: bool = False) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.strptime(value.strip(), "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_date",
                "message": "Dates must be formatted as YYYY-MM-DD.",
            },
        ) from exc
    parsed = parsed.replace(tzinfo=timezone.utc).replace(tzinfo=None)
    if end_of_day:
        return parsed + timedelta(days=1)
    return parsed.replace(hour=0, minute=0, second=0, microsecond=0) if not end_of_day else parsed


@router.get("", response_model=TransactionListResponse, summary="List transactions with filters")
def list_transactions(
    session: Session = Depends(get_db),
    search: str | None = Query(default=None, max_length=120, description="Free-text search"),
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="pending|completed|declined|failed|cancelled|expired|refunded|failed_or_cancelled|all",
    ),
    date_from: str | None = Query(default=None, description="YYYY-MM-DD (inclusive)"),
    date_to: str | None = Query(default=None, description="YYYY-MM-DD (inclusive)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TransactionListResponse:
    start = _parse_day(date_from)
    end = _parse_day(date_to, end_of_day=True)

    if status_filter and status_filter not in (
        "all",
        "failed_or_cancelled",
        *repo.VALID_STATUSES,
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_status",
                "message": f"Unknown status filter '{status_filter}'.",
            },
        )

    items, total = repo.list_transactions(
        session,
        search=search,
        status=status_filter,
        date_from=start,
        date_to=end,
        limit=limit,
        offset=offset,
    )
    counts = repo.count_by_status(session, search=search, date_from=start, date_to=end)

    return TransactionListResponse(
        items=[to_transaction_out(row) for row in items],
        total=total,
        limit=limit,
        offset=offset,
        counts_by_status=counts,
    )


@router.get("/{transaction_id}", response_model=TransactionOut, summary="Transaction detail")
def get_transaction(
    transaction_id: str = Path(..., min_length=3, max_length=64),
    session: Session = Depends(get_db),
) -> TransactionOut:
    row = repo.get_by_id(session, transaction_id)
    if row is None:
        row = repo.get_by_order_id(session, transaction_id)
    if row is None:
        raise not_found(
            f"No transaction with id '{transaction_id}' exists in this application.",
            code="transaction_not_found",
        )
    return to_transaction_out(row)  # type: ignore[return-value]
