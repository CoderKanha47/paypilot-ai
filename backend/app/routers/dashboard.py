"""Dashboard metrics — every figure computed from persisted rows."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..config import Settings
from ..deps import get_db, get_settings
from ..schemas import DashboardResponse
from ..services.analytics import build_dashboard
from ..services.serializers import to_transaction_out

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardResponse, summary="Aggregated dashboard metrics")
def dashboard(
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    months: int = Query(default=6, ge=1, le=24, description="Months in the collection chart"),
    recent: int = Query(default=8, ge=1, le=50, description="Number of recent rows to return"),
) -> DashboardResponse:
    data = build_dashboard(session, settings, recent_limit=recent, months=months)
    return DashboardResponse(
        metrics=data.metrics,  # type: ignore[arg-type]
        monthly=data.monthly,  # type: ignore[arg-type]
        status_distribution=data.status_distribution,  # type: ignore[arg-type]
        recent=[to_transaction_out(row) for row in data.recent],
        generated_at=data.generated_at,
    )
