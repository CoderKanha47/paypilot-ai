"""FastAPI application factory.

Run locally::

    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles

from . import __version__
from .config import PROJECT_ROOT, Settings, get_settings
from .database import init_db, session_scope
from .errors import AIProviderError, DomainError, PayPalError
from .logging_config import configure_logging, log_extra
from .money import MoneyError
from .routers import assistant, dashboard, health, payments, reports, transactions
from .seed import seed_demo_data
from .services.ai import build_provider
from .services.payments import build_checkout

logger = logging.getLogger("paypilot.api")

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

DESCRIPTION = """
PayPilot AI — an AI-powered payment operations dashboard built on the PayPal
Sandbox.

* **PayPal**: server-created orders, payer approval, server-side capture and
  verification (Orders v2, OAuth 2.0 client credentials).
* **AI**: a grounded assistant that answers questions from your recorded
  transactions. Swappable providers (OpenAI, Anthropic, any OpenAI-compatible
  endpoint) plus an explicitly labelled demo engine.
* **Reports**: CSV / JSON exports and a printable summary.
"""


def _error_response(status_code: int, code: str, message: str, **extra) -> JSONResponse:
    detail = {"code": code, "message": message}
    detail.update(extra)
    return JSONResponse(status_code=status_code, content={"detail": detail})


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(
        settings.log_level, json_output=settings.app_env == "production"
    )
    logger.info(
        "Starting %s v%s (%s)",
        settings.app_name,
        __version__,
        settings.app_env,
        extra=log_extra(environment=settings.app_env),
    )

    init_db()
    if settings.seed_demo_data:
        with session_scope() as session:
            seeded = seed_demo_data(session, settings)
            if seeded:
                logger.info("Seeded %s labelled demo rows", seeded)

    app.state.checkout = build_checkout(settings)
    app.state.ai_provider = build_provider(settings)
    app.state.settings = settings

    logger.info(
        "PayPal mode: %s | AI provider: %s",
        "sandbox" if settings.paypal_configured else "DEMO (no credentials)",
        app.state.ai_provider.name,
        extra=log_extra(
            paypal_configured=settings.paypal_configured,
            ai_provider=app.state.ai_provider.name,
        ),
    )

    yield

    checkout = getattr(app.state, "checkout", None)
    if checkout is not None:
        await checkout.aclose()
    provider = getattr(app.state, "ai_provider", None)
    closer = getattr(provider, "aclose", None)
    if callable(closer):
        await closer()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(
        title="PayPilot AI",
        version=__version__,
        description=DESCRIPTION,
        openapi_url="/api/openapi.json",
        docs_url="/api/docs" if settings.app_env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # ------------------------------------------------------------- middleware
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Requested-With"],
        max_age=600,
    )

    @app.middleware("http")
    async def guard(request: Request, call_next):
        # Request size limit — cheap protection against oversized payloads.
        if request.method in {"POST", "PUT", "PATCH"}:
            length = request.headers.get("content-length")
            if length and length.isdigit() and int(length) > settings.max_request_bytes:
                return _error_response(
                    413, "payload_too_large", "Request body is too large."
                )
        try:
            response: Response = await call_next(request)
        except Exception:
            logger.exception("Unhandled error on %s %s", request.method, request.url.path)
            return _error_response(
                500, "internal_error", "An unexpected error occurred. Check the server logs."
            )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Cache-Control", "no-store" if request.url.path.startswith("/api") else "no-cache"
        )
        return response

    # -------------------------------------------------------- error handlers
    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError) -> JSONResponse:
        mapping = {
            "order_not_owned": 404,
            "reference_mismatch": 400,
            "order_not_approved": 409,
            "order_mismatch": 409,
            "amount_mismatch": 409,
            "currency_mismatch": 409,
            "already_captured": 409,
            "not_cancellable": 409,
            "duplicate_order": 409,
        }
        status_code = mapping.get(exc.code, 400)
        extra = {k: v for k, v in vars(exc).items() if k not in {"code", "message"}}
        return _error_response(status_code, exc.code, exc.message, **extra)

    @app.exception_handler(PayPalError)
    async def _paypal_error(request: Request, exc: PayPalError) -> JSONResponse:
        return _error_response(
            502 if exc.http_status else 503,
            "paypal_error",
            exc.message,
            paypal_error=exc.as_dict(),
        )

    @app.exception_handler(AIProviderError)
    async def _ai_error(request: Request, exc: AIProviderError) -> JSONResponse:
        return _error_response(
            503 if exc.retryable else 500, "ai_error", exc.message, provider=exc.provider
        )

    @app.exception_handler(MoneyError)
    async def _money_error(request: Request, exc: MoneyError) -> JSONResponse:
        return _error_response(422, "invalid_amount", str(exc))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        messages = []
        for error in exc.errors():
            loc = ".".join(str(part) for part in error.get("loc", []) if part != "body")
            messages.append(f"{loc}: {error.get('msg', 'invalid value')}")
        return _error_response(
            422,
            "validation_error",
            "The request failed validation.",
            errors=messages[:8],
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict):
            return JSONResponse(status_code=exc.status_code, content={"detail": detail}, headers=exc.headers)
        return _error_response(exc.status_code, "http_error", str(detail))

    # --------------------------------------------------------------- routers
    api = settings.api_prefix
    app.include_router(health.router, prefix=api)
    app.include_router(dashboard.router, prefix=api)
    app.include_router(transactions.router, prefix=api)
    app.include_router(payments.router, prefix=api)
    app.include_router(assistant.router, prefix=api)
    app.include_router(reports.router, prefix=api)

    @app.get(f"{api}/", include_in_schema=False)
    async def api_root() -> dict:
        return {"app": settings.app_name, "version": __version__, "docs": "/api/docs"}

    @app.api_route(
        f"{api}/{{full_path:path}}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    async def api_fallback(full_path: str) -> JSONResponse:
        """Structured 404 for any unknown API route."""
        return _error_response(404, "not_found", "Unknown API route.")

    # --------------------------------------------------- built frontend (SPA)
    if FRONTEND_DIST.is_dir():
        assets = FRONTEND_DIST / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets)), name="static-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str) -> Response:
            if full_path.startswith("api/"):
                return _error_response(404, "not_found", "Unknown API route.")
            candidate = (FRONTEND_DIST / full_path).resolve()
            if (
                full_path
                and candidate.is_file()
                and str(candidate).startswith(str(FRONTEND_DIST.resolve()))
            ):
                return FileResponse(candidate)
            index = FRONTEND_DIST / "index.html"
            if index.is_file():
                return FileResponse(index, headers={"Cache-Control": "no-cache"})
            return _error_response(404, "frontend_missing", "Frontend build not found.")

    return app


app = create_app()
