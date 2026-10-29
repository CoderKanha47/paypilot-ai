"""Monetary arithmetic — the foundation every financial figure rests on."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.money import (
    MIN_AMOUNT_MINOR,
    MoneyError,
    allocate_minor,
    format_amount,
    from_minor,
    minor_exponent,
    normalize_currency,
    parse_amount_to_minor,
    sum_minor,
    to_minor,
)


class TestExponent:
    @pytest.mark.parametrize(
        "currency,expected",
        [("USD", 2), ("eur", 2), ("GBP", 2), ("JPY", 0), ("KRW", 0), (" CLP ", 0)],
    )
    def test_minor_exponent(self, currency, expected):
        assert minor_exponent(currency) == expected

    @pytest.mark.parametrize("bad", ["", "US", "USDD", "12A", "dollars"])
    def test_invalid_currency_rejected(self, bad):
        with pytest.raises(MoneyError):
            minor_exponent(bad)

    def test_normalize_currency_uppercases(self):
        assert normalize_currency(" usd ") == "USD"


class TestConversion:
    def test_decimal_to_minor_is_exact(self):
        assert to_minor(Decimal("12.34"), "USD") == 1234
        assert to_minor("0.01", "USD") == 1
        assert to_minor("1000000.00", "USD") == 100_000_000

    def test_rounding_is_half_up_not_float(self):
        # 1.005 is not representable exactly in binary floating point; the
        # string path must still round half-up to 101.
        assert to_minor("1.005", "USD") == 101
        assert to_minor(Decimal("1.005"), "USD") == 101

    def test_jpy_has_no_minor_unit(self):
        assert to_minor("1500", "JPY") == 1500
        assert from_minor(1500, "JPY") == Decimal("1500")

    def test_round_trip(self):
        assert from_minor(123456, "USD") == Decimal("1234.56")
        assert to_minor(from_minor(123456, "USD"), "USD") == 123456

    def test_format_matches_paypal(self):
        assert format_amount(123456, "USD") == "1234.56"
        assert format_amount(5, "USD") == "0.05"
        assert format_amount(1500, "JPY") == "1500"

    def test_large_values_stay_exact(self):
        # Strings keep every digit — no float rounding anywhere in the path.
        assert to_minor("1234567.89", "USD") == 123456789
        assert to_minor("10000000.00", "USD") == 1_000_000_000  # exactly at the ceiling
        assert to_minor("1234567", "JPY") == 1234567

    def test_values_above_the_ceiling_are_rejected(self):
        with pytest.raises(MoneyError):
            to_minor("10000000.01", "USD")
        with pytest.raises(MoneyError):
            to_minor("1e9999", "USD")


class TestParsing:
    @pytest.mark.parametrize(
        "raw,currency,expected",
        [
            ("10.00", "USD", 1000),
            ("0.01", "USD", 1),
            ("1,250.00", "USD", 125000),
            (" 42 ", "USD", 4200),
            ("75.25", "USD", 7525),
            ("1000", "JPY", 1000),
            (10, "USD", 1000),
            (10.5, "USD", 1050),
        ],
    )
    def test_valid_amounts(self, raw, currency, expected):
        assert parse_amount_to_minor(raw, currency) == expected

    @pytest.mark.parametrize(
        "raw",
        ["0", "0.00", "-1", "-10.50", "abc", "", "NaN", "Infinity", "1e9999", None, True],
    )
    def test_invalid_amounts_rejected(self, raw):
        with pytest.raises(MoneyError):
            parse_amount_to_minor(raw, "USD")

    def test_ceiling_enforced(self):
        assert parse_amount_to_minor("10000000", "USD") == 1_000_000_000
        with pytest.raises(MoneyError):
            parse_amount_to_minor("10000000.01", "USD")

    def test_minimum_enforced(self):
        assert parse_amount_to_minor("0.01", "USD") == MIN_AMOUNT_MINOR

    def test_bool_is_not_a_number(self):
        with pytest.raises(MoneyError):
            parse_amount_to_minor(True, "USD")


class TestAggregation:
    def test_sum_minor_is_exact(self):
        values = [123456, 654321, 1, 999999999]
        assert sum_minor(values) == 123456 + 654321 + 1 + 999999999

    def test_sum_rejects_floats(self):
        with pytest.raises(MoneyError):
            sum_minor([1, 2.5])  # type: ignore[list-item]

    def test_sum_rejects_bools(self):
        with pytest.raises(MoneyError):
            sum_minor([True])  # type: ignore[list-item]

    def test_sum_of_empty_is_zero(self):
        assert sum_minor([]) == 0

    def test_allocate_preserves_total(self):
        parts = allocate_minor(1000, [1, 1, 1])
        assert sum(parts) == 1000
        assert sorted(parts) == [333, 333, 334]

    def test_allocate_is_deterministic(self):
        assert allocate_minor(100, [50, 30, 20]) == [50, 30, 20]

    def test_allocate_rejects_zero_weights(self):
        with pytest.raises(MoneyError):
            allocate_minor(100, [0, 0])


def test_authoritative_values_never_use_float():
    """The money module must not route totals through binary floats."""
    import app.money as money_module
    import inspect

    source = inspect.getsource(money_module)
    # float() may appear in docs/type hints, but never as an arithmetic tool.
    assert "float(" not in source.replace("float:", "").replace("| float", "")
