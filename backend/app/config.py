"""Application settings.

All secrets are read from environment variables (optionally a local ``.env`` file
that is git-ignored). No secret is ever returned by an API endpoint.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent

SUPPORTED_CURRENCIES = (
    "USD",
    "EUR",
    "GBP",
    "CAD",
    "AUD",
    "NZD",
    "CHF",
    "SGD",
    "HKD",
    "JPY",
    "INR",
    "MXN",
    "BRL",
)


class Settings(BaseSettings):
    """Runtime configuration.

    Environment variable names are the upper-case versions of the field names,
    e.g. ``paypal_client_id`` -> ``PAYPAL_CLIENT_ID``.
    """

    model_config = SettingsConfigDict(
        env_file=[BACKEND_DIR / ".env", PROJECT_ROOT / ".env"],
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ app
    app_name: str = "PayPilot AI"
    app_version: str = "1.0.0"
    app_env: Literal["development", "test", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    api_prefix: str = "/api"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_request_bytes: int = 1_000_000

    database_url: str = "sqlite:///./paypilot.db"

    # --------------------------------------------------------------- paypal
    paypal_client_id: str = Field(default="")
    paypal_client_secret: str = Field(default="")
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"
    paypal_currency: str = "USD"
    paypal_brand_name: str = "PayPilot AI"
    paypal_return_url: str = "http://localhost:5173/payment/result?outcome=success"
    paypal_cancel_url: str = "http://localhost:5173/payment/result?outcome=cancelled"
    paypal_mode: Literal["sandbox", "live"] = "sandbox"
    # Safety interlock: live (real money) payments stay disabled unless explicitly
    # opted in. The hackathon demo always runs in Sandbox.
    allow_live_payments: bool = False
    paypal_timeout_seconds: float = 25.0

    # ------------------------------------------------------------------- ai
    ai_provider: Literal["demo", "openai", "anthropic", "openai_compatible"] = "demo"
    ai_api_key: str = ""
    ai_model: str = ""
    ai_base_url: str = ""
    ai_timeout_seconds: float = 30.0
    ai_max_tokens: int = 700
    # Convenience: allow using the vendor's own variable names.
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-haiku-latest"

    # ----------------------------------------------------------------- demo
    seed_demo_data: bool = True
    demo_seeded: bool = False  # internal marker, not meant to be set by hand

    # ------------------------------------------------------------- derived
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def paypal_configured(self) -> bool:
        return bool(self.paypal_client_id and self.paypal_client_secret)

    @property
    def paypal_is_sandbox(self) -> bool:
        return "sandbox" in self.paypal_base_url.lower() or self.paypal_mode == "sandbox"

    @property
    def resolved_ai_key(self) -> str:
        if self.ai_api_key:
            return self.ai_api_key
        if self.ai_provider == "openai":
            return self.openai_api_key
        if self.ai_provider == "anthropic":
            return self.anthropic_api_key
        return ""

    @field_validator("paypal_currency", "paypal_base_url", mode="before")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("paypal_currency")
    @classmethod
    def _currency_supported(cls, value: str) -> str:
        code = value.upper()
        if code not in SUPPORTED_CURRENCIES:
            raise ValueError(
                f"Unsupported currency '{code}'. Choose one of {', '.join(SUPPORTED_CURRENCIES)}."
            )
        return code

    @field_validator("log_level")
    @classmethod
    def _log_level(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def _safety_interlocks(self) -> "Settings":
        if self.paypal_mode == "live" and not self.allow_live_payments:
            raise ValueError(
                "PAYPAL_MODE=live is blocked. Set ALLOW_LIVE_PAYMENTS=true only if you "
                "genuinely intend to move real money. This project is built for Sandbox."
            )
        if self.paypal_mode == "sandbox" and "sandbox" not in self.paypal_base_url.lower():
            raise ValueError(
                "PAYPAL_MODE=sandbox requires a Sandbox base URL "
                "(https://api-m.sandbox.paypal.com)."
            )
        if self.paypal_mode == "live" and "sandbox" in self.paypal_base_url.lower():
            raise ValueError(
                "PAYPAL_MODE=live cannot point at the Sandbox endpoint. "
                "Set PAYPAL_BASE_URL=https://api-m.paypal.com if you really mean it."
            )
        if self.app_env == "production" and self.seed_demo_data:
            # Never fabricate financial records in production.
            object.__setattr__(self, "seed_demo_data", False)
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Used by tests that mutate environment variables."""
    get_settings.cache_clear()
