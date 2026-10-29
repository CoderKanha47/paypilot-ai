"""Cross-cutting error types and HTTP error helpers."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status


class PayPalError(Exception):
    """Any failure while talking to the PayPal REST API."""

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        name: str | None = None,
        details: Any = None,
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.http_status = http_status
        self.name = name
        self.details = details
        self.correlation_id = correlation_id

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"message": self.message}
        if self.name:
            payload["name"] = self.name
        if self.http_status:
            payload["paypal_status"] = self.http_status
        if self.correlation_id:
            payload["correlation_id"] = self.correlation_id
        if self.details:
            payload["details"] = self.details
        return payload


class AIProviderError(Exception):
    """Raised when the configured AI provider cannot produce a usable answer."""

    def __init__(self, message: str, *, provider: str = "unknown", retryable: bool = True):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.retryable = retryable


class DomainError(Exception):
    """Business-rule violation (e.g. capturing an unknown order)."""

    def __init__(self, message: str, *, code: str = "domain_error", **extra) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        for key, value in extra.items():
            setattr(self, key, value)


def http_error(
    status_code: int, message: str, *, code: str, **extra: Any
) -> HTTPException:
    detail: dict[str, Any] = {"code": code, "message": message}
    detail.update(extra)
    return HTTPException(status_code=status_code, detail=detail)


def bad_request(message: str, *, code: str = "bad_request", **extra: Any) -> HTTPException:
    return http_error(status.HTTP_400_BAD_REQUEST, message, code=code, **extra)


def not_found(message: str, *, code: str = "not_found", **extra: Any) -> HTTPException:
    return http_error(status.HTTP_404_NOT_FOUND, message, code=code, **extra)


def conflict(message: str, *, code: str = "conflict", **extra: Any) -> HTTPException:
    return http_error(status.HTTP_409_CONFLICT, message, code=code, **extra)


def upstream_error(message: str, *, code: str = "upstream_error", **extra: Any) -> HTTPException:
    return http_error(status.HTTP_502_BAD_GATEWAY, message, code=code, **extra)


def service_unavailable(message: str, *, code: str = "service_unavailable", **extra: Any) -> HTTPException:
    return http_error(status.HTTP_503_SERVICE_UNAVAILABLE, message, code=code, **extra)
