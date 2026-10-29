"""Typed request/response schemas for the public API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .money import MoneyError, normalize_currency, parse_amount_to_minor

StatusLiteral = Literal[
    "pending",
    "completed",
    "declined",
    "failed",
    "cancelled",
    "expired",
    "refunded",
]


class APIModel(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


# ----------------------------------------------------------------- health
class HealthResponse(APIModel):
    status: Literal["ok", "degraded"] = "ok"
    app: str
    version: str
    environment: str
    database: Literal["connected", "error"]
    paypal_configured: bool
    paypal_mode: Literal["sandbox", "live", "disabled"]
    ai_provider: str
    ai_configured: bool
    time: datetime


# ----------------------------------------------------------------- config
class PaypalClientConfig(APIModel):
    configured: bool
    mode: Literal["sandbox", "live", "disabled"]
    sandbox: bool
    client_id: str = ""
    currency: str = "USD"
    sdk_url: str = ""
    brand_name: str


class AIConfig(APIModel):
    provider: str
    configured: bool
    model: str = ""
    demo_fallback: bool = True


class AppConfigResponse(APIModel):
    app_name: str
    version: str
    environment: str
    demo_data_seeded: bool
    demo_mode: bool
    seed_allowed: bool
    supported_currencies: list[str]
    paypal: PaypalClientConfig
    ai: AIConfig
    notice: str | None = None


# ----------------------------------------------------------- transactions
class TransactionOut(APIModel):
    id: str
    paypal_order_id: str
    paypal_capture_id: str | None = None
    status: StatusLiteral
    paypal_status: str | None = None
    amount: Decimal
    amount_minor: int
    amount_captured: Decimal | None = None
    currency: str
    description: str
    customer_reference: str | None = None
    failure_reason: str | None = None
    approval_url: str | None = None
    mode: str
    is_demo_record: bool
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class TransactionListResponse(APIModel):
    items: list[TransactionOut]
    total: int
    limit: int
    offset: int
    counts_by_status: dict[str, int] = Field(default_factory=dict)


# --------------------------------------------------------------- dashboard
class StatusCount(APIModel):
    status: str
    count: int
    amount: Decimal
    currency: str


class CurrencyTotal(APIModel):
    currency: str
    amount: Decimal
    count: int


class MonthlyPoint(APIModel):
    month: str  # YYYY-MM
    label: str  # Jan, Feb...
    amount: Decimal
    count: int


class DashboardMetrics(APIModel):
    primary_currency: str
    total_captured: Decimal
    total_captured_minor: int
    total_pending: Decimal
    total_pending_minor: int
    captured_count: int
    pending_count: int
    failed_count: int
    cancelled_count: int
    refunded_count: int
    total_transactions: int
    average_payment: Decimal
    success_rate: float
    period_days: int = 30
    other_currencies: list[CurrencyTotal] = Field(default_factory=list)
    demo_data_included: bool = False


class DashboardResponse(APIModel):
    metrics: DashboardMetrics
    monthly: list[MonthlyPoint]
    status_distribution: list[StatusCount]
    recent: list[TransactionOut]
    generated_at: datetime


# ---------------------------------------------------------------- payments
class CreateOrderRequest(APIModel):
    amount: str | int | float = Field(..., description="Decimal amount, e.g. '129.50'")
    currency: str = "USD"
    description: str = Field(..., min_length=1, max_length=250)
    customer_reference: str | None = Field(default=None, max_length=120)
    customer_note: str | None = Field(default=None, max_length=500)

    @field_validator("currency")
    @classmethod
    def _valid_currency(cls, value: str) -> str:
        from .config import SUPPORTED_CURRENCIES

        try:
            code = normalize_currency(value)
        except MoneyError as exc:
            raise ValueError(str(exc)) from exc
        if code not in SUPPORTED_CURRENCIES:
            raise ValueError(
                f"Unsupported currency '{code}'. Choose one of {', '.join(SUPPORTED_CURRENCIES)}."
            )
        return code

    @field_validator("description")
    @classmethod
    def _valid_description(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Description is required.")
        return value.strip()

    @field_validator("customer_reference")
    @classmethod
    def _strip_reference(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None

    @model_validator(mode="after")
    def _validate_amount(self) -> "CreateOrderRequest":
        # Raises MoneyError (a ValueError) so FastAPI returns 422, not 500.
        parse_amount_to_minor(self.amount, self.currency)
        return self

    def amount_minor(self) -> int:
        return parse_amount_to_minor(self.amount, self.currency)


class CreateOrderResponse(APIModel):
    transaction_id: str
    order_id: str
    status: StatusLiteral
    paypal_status: str | None = None
    amount: Decimal
    currency: str
    description: str
    approval_url: str | None = None
    approve_link: str | None = None
    mode: Literal["sandbox", "demo"]
    is_demo: bool
    paypal_client_id: str = ""
    sdk_currency: str = ""
    created_at: datetime
    notice: str | None = None


class CaptureOrderRequest(APIModel):
    order_id: str = Field(..., min_length=3, max_length=64)
    transaction_id: str | None = Field(default=None, max_length=64)
    demo_outcome: Literal["approve", "decline", "fail", "pending"] | None = Field(
        default=None,
        description="Only honoured when PayPal credentials are absent (labelled demo mode).",
    )

    @field_validator("order_id")
    @classmethod
    def _valid_order_id(cls, value: str) -> str:
        if not value.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Malformed PayPal order id.")
        return value


class CaptureOrderResponse(APIModel):
    transaction: TransactionOut
    already_captured: bool = False
    mode: Literal["sandbox", "demo"]
    notice: str | None = None


class OrderSyncResponse(APIModel):
    transaction: TransactionOut
    paypal_status: str
    synced: bool


# --------------------------------------------------------------- assistant
class ChatMessage(APIModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=2000)


class ChatRequest(APIModel):
    message: str = Field(..., min_length=1, max_length=500)
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message cannot be empty.")
        return value.strip()


class AssistantAnswer(APIModel):
    answer: str
    facts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    disclaimer: str | None = None


class ChatResponse(APIModel):
    answer: str
    facts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    confidence: str = "medium"
    provider: str
    mode: Literal["live", "demo"]
    latency_ms: int
    data_snapshot: dict[str, Any] = Field(default_factory=dict)
    disclaimer: str | None = None
    notice: str | None = None
    suggestions: list[str] = Field(default_factory=list)


class AssistantSuggestionsResponse(APIModel):
    suggestions: list[str]


# ---------------------------------------------------------------- reports
class ReportSummaryResponse(APIModel):
    generated_at: datetime
    currency: str
    total_captured: Decimal
    total_pending: Decimal
    transaction_count: int
    status_breakdown: list[StatusCount]
    monthly: list[MonthlyPoint]
    notes: list[str] = Field(default_factory=list)


class ErrorResponse(APIModel):
    code: str
    message: str
    detail: Any = None
