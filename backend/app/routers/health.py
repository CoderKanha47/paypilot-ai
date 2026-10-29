"""Health and public configuration endpoints.

``/api/config`` is deliberately limited to *public* values: the PayPal
JavaScript SDK client id is public by design, the client secret never appears,
and the AI key is only reported as a boolean.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .. import __version__
from ..config import SUPPORTED_CURRENCIES, Settings
from ..deps import get_db, get_settings
from ..models import AppMeta, Transaction
from ..schemas import AIConfig, AppConfigResponse, HealthResponse, PaypalClientConfig
from ..services.ai import AIProvider
from ..services.paypal import sdk_url

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Liveness and dependency check")
def health(
    session: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> HealthResponse:
    db_state = "connected"
    try:
        session.execute(text("SELECT 1"))
    except Exception:  # pragma: no cover - only on a broken database
        db_state = "error"

    mode = "sandbox" if settings.paypal_configured else "disabled"
    if settings.paypal_configured and not settings.paypal_is_sandbox:
        mode = "live"

    return HealthResponse(
        status="ok" if db_state == "connected" else "degraded",
        app=settings.app_name,
        version=__version__,
        environment=settings.app_env,
        database=db_state,  # type: ignore[arg-type]
        paypal_configured=settings.paypal_configured,
        paypal_mode=mode,  # type: ignore[arg-type]
        ai_provider=settings.ai_provider,
        ai_configured=bool(settings.resolved_ai_key) or settings.ai_provider == "demo",
        time=datetime.now(timezone.utc),
    )


@router.get("/config", response_model=AppConfigResponse, summary="Public runtime configuration")
def config(
    request: Request,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AppConfigResponse:
    provider: AIProvider = request.app.state.ai_provider

    mode = "sandbox"
    if not settings.paypal_configured:
        mode = "disabled"
    elif not settings.paypal_is_sandbox:
        mode = "live"

    client_id = settings.paypal_client_id if settings.paypal_configured else ""
    seeded = session.get(AppMeta, "demo_seeded_at") is not None

    notice: str | None = None
    if not settings.paypal_configured:
        notice = (
            "PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET are not set. The app is running in "
            "clearly-labelled DEMO mode: checkout results are simulated locally and are NOT "
            "real PayPal Sandbox transactions."
        )
    elif settings.paypal_mode == "live":
        notice = "LIVE payments mode is enabled. Real money will move."

    return AppConfigResponse(
        app_name=settings.app_name,
        version=__version__,
        environment=settings.app_env,
        demo_data_seeded=seeded,
        demo_mode=not settings.paypal_configured,
        seed_allowed=settings.seed_demo_data,
        supported_currencies=list(SUPPORTED_CURRENCIES),
        paypal=PaypalClientConfig(
            configured=settings.paypal_configured,
            mode=mode,  # type: ignore[arg-type]
            sandbox=settings.paypal_is_sandbox,
            client_id=client_id,
            currency=settings.paypal_currency,
            sdk_url=sdk_url(client_id, settings.paypal_currency),
            brand_name=settings.paypal_brand_name,
        ),
        ai=AIConfig(
            provider=provider.name,
            configured=provider.is_configured(),
            model=getattr(provider, "model", "") or "",
            demo_fallback=True,
        ),
        notice=notice,
    )


@router.get("/health/db", include_in_schema=False)
def db_probe(session: Session = Depends(get_db)) -> dict:
    session.execute(text("SELECT 1"))
    count = session.scalar(select(Transaction.id).limit(1)) is not None
    return {"database": "connected", "has_transactions": count}
