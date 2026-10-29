"""FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import get_db
from .services.ai import AIProvider
from .services.payments import CheckoutBackend

__all__ = ["get_db", "get_settings", "get_checkout", "get_ai_provider", "Settings"]


def get_checkout(request: Request) -> CheckoutBackend:
    """The PayPal client (or labelled demo engine) created at startup."""
    checkout: CheckoutBackend = request.app.state.checkout
    return checkout


def get_ai_provider(request: Request) -> AIProvider:
    provider: AIProvider = request.app.state.ai_provider
    return provider
