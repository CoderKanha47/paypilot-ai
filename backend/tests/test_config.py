"""Configuration safety interlocks and missing-credential behaviour."""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from app.config import Settings, reset_settings_cache
from app.services.ai import build_provider


def _settings(**overrides) -> Settings:
    base = {
        "paypal_client_id": "",
        "paypal_client_secret": "",
        "paypal_base_url": "https://api-m.sandbox.paypal.com",
        "paypal_currency": "USD",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


class TestSafetyInterlocks:
    def test_default_is_sandbox(self):
        settings = _settings()
        assert settings.paypal_mode == "sandbox"
        assert settings.paypal_is_sandbox is True
        assert settings.paypal_configured is False

    def test_live_mode_is_blocked_by_default(self):
        with pytest.raises(ValidationError) as excinfo:
            _settings(
                paypal_mode="live",
                paypal_base_url="https://api-m.paypal.com",
                allow_live_payments=False,
            )
        assert "ALLOW_LIVE_PAYMENTS" in str(excinfo.value)

    def test_live_mode_requires_a_live_base_url(self):
        with pytest.raises(ValidationError) as excinfo:
            _settings(
                paypal_mode="live",
                paypal_base_url="https://api-m.sandbox.paypal.com",
                allow_live_payments=True,
            )
        assert "Sandbox endpoint" in str(excinfo.value)

    def test_sandbox_mode_rejects_a_production_base_url(self):
        with pytest.raises(ValidationError) as excinfo:
            _settings(
                paypal_mode="sandbox",
                paypal_base_url="https://api-m.paypal.com",
            )
        assert "Sandbox base URL" in str(excinfo.value)

    def test_credentials_must_both_be_present(self):
        assert _settings(paypal_client_id="only-id").paypal_configured is False
        assert _settings(paypal_client_secret="only-secret").paypal_configured is False
        assert _settings(paypal_client_id="a", paypal_client_secret="b").paypal_configured is True

    def test_production_disables_demo_seeding(self):
        settings = _settings(app_env="production", seed_demo_data=True)
        assert settings.seed_demo_data is False

    def test_currency_is_uppercased_and_validated(self):
        assert _settings(paypal_currency="eur").paypal_currency == "EUR"
        with pytest.raises(ValidationError):
            _settings(paypal_currency="XYZ")

    def test_cors_origins_are_split(self):
        settings = _settings(cors_origins="http://a.test, http://b.test")
        assert settings.cors_origin_list == ["http://a.test", "http://b.test"]


class TestAIProviderSelection:
    def test_demo_is_the_default(self):
        settings = _settings(ai_provider="demo")
        provider = build_provider(settings)
        assert provider.name == "demo"
        assert provider.live is False
        assert provider.is_configured() is True

    def test_openai_without_a_key_falls_back_to_labelled_demo(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "openai")
        monkeypatch.setenv("AI_API_KEY", "")
        monkeypatch.setenv("OPENAI_API_KEY", "")
        reset_settings_cache()
        try:
            settings = Settings(_env_file=None)
            if settings.ai_provider != "openai":
                pytest.skip("environment override not applied")
            provider = build_provider(settings)
            assert provider.name == "demo", "must fall back, never fail silently as live"
            assert provider.live is False
        finally:
            reset_settings_cache()

    def test_openai_with_a_key_is_live(self):
        settings = _settings(ai_provider="openai", ai_api_key="sk-test")
        provider = build_provider(settings)
        assert provider.name == "openai"
        assert provider.live is True
        assert provider.model  # a default model is always configured

    def test_anthropic_with_a_key_is_live(self):
        settings = _settings(ai_provider="anthropic", anthropic_api_key="ant-test")
        provider = build_provider(settings)
        assert provider.name == "anthropic"
        assert provider.live is True

    def test_openai_compatible_needs_no_key(self):
        settings = _settings(
            ai_provider="openai_compatible",
            ai_base_url="http://localhost:11434/v1",
            ai_model="llama3.1",
        )
        provider = build_provider(settings)
        assert provider.name == "openai_compatible"
        assert provider.is_configured() is True


def test_settings_cache_roundtrip(monkeypatch):
    monkeypatch.setenv("PAYPAL_CURRENCY", "JPY")
    reset_settings_cache()
    try:
        from app.config import get_settings

        assert get_settings().paypal_currency == "JPY"
        assert get_settings() is get_settings()  # cached
    finally:
        reset_settings_cache()


def test_env_example_documents_every_secret():
    from pathlib import Path

    from app.config import PROJECT_ROOT

    example = PROJECT_ROOT / ".env.example"
    assert example.exists(), ".env.example must be committed"
    text = example.read_text(encoding="utf-8")
    for key in (
        "PAYPAL_CLIENT_ID",
        "PAYPAL_CLIENT_SECRET",
        "PAYPAL_BASE_URL",
        "PAYPAL_CURRENCY",
        "AI_PROVIDER",
        "AI_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        assert key in text, f"{key} missing from .env.example"
    # No real-looking secret may be present.
    assert "sk-" not in text
    assert "EAAG" not in text


def test_gitignore_excludes_secrets_and_databases():
    from pathlib import Path

    from app.config import PROJECT_ROOT

    text = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in (".env", "*.db", "__pycache__", "node_modules", "dist", ".venv"):
        assert pattern in text, f"{pattern} missing from .gitignore"
