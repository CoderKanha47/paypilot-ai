"""Structured logging setup.

Secrets (client secret, API keys, access tokens) are never logged.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

_SENSITIVE_KEYS = {
    "authorization",
    "client_secret",
    "paypal_client_secret",
    "access_token",
    "api_key",
    "ai_api_key",
    "openai_api_key",
    "anthropic_api_key",
    "secret",
    "password",
    "token",
}


class JsonFormatter(logging.Formatter):
    """Minimal JSON-lines formatter so log aggregation tools can read output."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(self._redact(extra))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)

    @staticmethod
    def _redact(data: dict[str, Any]) -> dict[str, Any]:
        clean: dict[str, Any] = {}
        for key, value in data.items():
            if key.lower() in _SENSITIVE_KEYS:
                clean[key] = "[redacted]"
            elif isinstance(value, dict):
                clean[key] = JsonFormatter._redact(value)
            else:
                clean[key] = value
        return clean


def configure_logging(level: str = "INFO", *, json_output: bool = False) -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
    root.handlers.clear()
    root.addHandler(handler)
    # Quieten noisy third-party loggers.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def log_extra(**fields: Any) -> dict[str, Any]:
    """Build the ``extra`` payload used by ``logger.info(..., extra={"extra_fields": ...})``."""
    return {"extra_fields": fields}
