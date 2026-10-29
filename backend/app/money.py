"""Money helpers.

Authoritative financial arithmetic is performed on **integer minor units**
(``12.34 USD`` -> ``1234``) and rendered through :class:`decimal.Decimal`.
Binary floating point is never used for money.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable

# Currencies whose smallest unit has no fractional part (ISO 4217 exponent 0).
ZERO_DECIMAL_CURRENCIES = frozenset(
    {"JPY", "KRW", "VND", "CLP", "ISK", "HUF", "TWD", "UGX", "XAF", "XOF", "XPF"}
)

MAX_AMOUNT_MINOR = 10_000_000_00  # 10,000,000.00 — a sane demo ceiling
MIN_AMOUNT_MINOR = 1  # PayPal rejects zero-value orders in this flow


class MoneyError(ValueError):
    """Raised when an amount or currency cannot be interpreted."""


def minor_exponent(currency: str) -> int:
    """Number of decimal places for ``currency`` (2 for USD, 0 for JPY...)."""
    code = (currency or "").strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise MoneyError(f"'{currency}' is not a valid ISO-4217 currency code.")
    return 0 if code in ZERO_DECIMAL_CURRENCIES else 2


def normalize_currency(currency: str) -> str:
    code = (currency or "").strip().upper()
    minor_exponent(code)  # validates
    return code


def to_minor(amount: Decimal | str | int, currency: str) -> int:
    """Convert a decimal amount into integer minor units (banker-free rounding)."""
    exponent = minor_exponent(currency)
    quantum = Decimal(1).scaleb(-exponent)
    try:
        value = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    except (InvalidOperation, ValueError) as exc:  # pragma: no cover - defensive
        raise MoneyError(f"Invalid monetary amount: {amount!r}") from exc
    if not value.is_finite():
        raise MoneyError("Monetary amount must be a finite number.")
    # Guard magnitude *before* quantising: quantize() raises InvalidOperation for
    # absurd exponents instead of the friendly error we want.
    ceiling = Decimal(MAX_AMOUNT_MINOR).scaleb(-exponent)
    if value > ceiling:
        raise MoneyError(f"Amount exceeds the maximum allowed for this demo ({ceiling}).")
    try:
        quantised = value.quantize(quantum, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise MoneyError(f"Amount '{amount}' cannot be represented exactly.") from exc
    return int(quantised.scaleb(exponent))


def from_minor(minor: int, currency: str) -> Decimal:
    """Convert integer minor units back into a :class:`~decimal.Decimal`."""
    if not isinstance(minor, int) or isinstance(minor, bool):
        raise MoneyError("Minor units must be an integer.")
    exponent = minor_exponent(currency)
    return Decimal(minor).scaleb(-exponent)


def format_amount(minor: int, currency: str) -> str:
    """Render minor units as the exact string PayPal expects, e.g. ``12.34``."""
    exponent = minor_exponent(currency)
    return f"{from_minor(minor, currency):.{exponent}f}"


def parse_amount_to_minor(raw: str | float | int, currency: str) -> int:
    """Validate-and-convert a user supplied amount.

    Accepts strings and numbers; rejects anything non-numeric, non-finite,
    negative, or above the configured ceiling.
    """
    if isinstance(raw, bool):
        raise MoneyError("Amount must be a number.")
    if isinstance(raw, (int, float)):
        # floats are only ever *converted*, never used for arithmetic.
        raw = repr(raw)
    if not isinstance(raw, str):
        raise MoneyError("Amount must be a number or numeric string.")

    text = raw.strip().replace(",", "")
    if not text:
        raise MoneyError("Amount is required.")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise MoneyError(f"'{raw}' is not a valid amount.") from exc
    if not value.is_finite():
        raise MoneyError("Amount must be a finite number.")
    if value <= 0:
        raise MoneyError("Amount must be greater than zero.")

    # Reject absurd magnitudes before conversion so we never hit decimal limits.
    exponent = minor_exponent(currency)
    if value * (Decimal(10) ** exponent) > Decimal(MAX_AMOUNT_MINOR):
        raise MoneyError(
            f"Amount exceeds the maximum allowed for this demo "
            f"({format_amount(MAX_AMOUNT_MINOR, currency)})."
        )

    minor = to_minor(value, currency)
    if minor < MIN_AMOUNT_MINOR:
        raise MoneyError("Amount is below the minimum chargeable value.")
    return minor


def sum_minor(values: Iterable[int]) -> int:
    """Sum minor units without ever touching a float."""
    total = 0
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise MoneyError("Minor unit values must be integers.")
        total += value
    return total


def allocate_minor(total: int, weights: Iterable[float]) -> list[int]:
    """Split ``total`` minor units proportionally (largest-remainder method)."""
    weight_list = list(weights)
    if not weight_list:
        return []
    weight_sum = sum(weight_list)
    if weight_sum <= 0:
        raise MoneyError("Weights must sum to a positive number.")
    exact = [Decimal(str(total)) * Decimal(str(w)) / Decimal(str(weight_sum)) for w in weight_list]
    floors = [int(e.to_integral_value(rounding=ROUND_HALF_UP)) for e in exact]
    remainder = total - sum(floors)
    order = sorted(range(len(exact)), key=lambda i: (exact[i] - floors[i]), reverse=True)
    for i in range(abs(remainder)):
        floors[order[i % len(order)]] += 1 if remainder > 0 else -1
    return floors
