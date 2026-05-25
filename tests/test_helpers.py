"""Tests for app/utils/helpers.py — safe_float and normalize_ticker."""

import math

import pytest

from app.utils.helpers import normalize_ticker, safe_float


# ---------------------------------------------------------------------------
# safe_float
# ---------------------------------------------------------------------------

class TestSafeFloat:
    def test_int_converts_to_float(self):
        result = safe_float(42)
        assert result == 42.0
        assert isinstance(result, float)

    def test_float_passes_through(self):
        result = safe_float(3.14)
        assert result == pytest.approx(3.14)
        assert isinstance(result, float)

    def test_negative_int_converts(self):
        assert safe_float(-10) == -10.0

    def test_zero_converts(self):
        assert safe_float(0) == 0.0

    def test_numeric_string_converts(self):
        assert safe_float("3.14") == pytest.approx(3.14)

    def test_integer_string_converts(self):
        assert safe_float("100") == 100.0

    def test_none_returns_none(self):
        assert safe_float(None) is None

    def test_invalid_string_returns_none(self):
        assert safe_float("not-a-number") is None

    def test_empty_string_returns_none(self):
        assert safe_float("") is None

    def test_nan_returns_none(self):
        assert safe_float(float("nan")) is None

    def test_positive_infinity_returns_none(self):
        assert safe_float(float("inf")) is None

    def test_negative_infinity_returns_none(self):
        assert safe_float(float("-inf")) is None

    def test_list_returns_none(self):
        assert safe_float([1, 2]) is None

    def test_dict_returns_none(self):
        assert safe_float({"a": 1}) is None

    def test_large_finite_float_converts(self):
        assert safe_float(1e300) == 1e300

    def test_very_small_float_converts(self):
        result = safe_float(1e-300)
        assert result == pytest.approx(1e-300)


# ---------------------------------------------------------------------------
# normalize_ticker
# ---------------------------------------------------------------------------

class TestNormalizeTicker:
    def test_lowercase_uppercased(self):
        assert normalize_ticker("aapl") == "AAPL"

    def test_already_uppercase_unchanged(self):
        assert normalize_ticker("AAPL") == "AAPL"

    def test_leading_trailing_whitespace_stripped(self):
        assert normalize_ticker(" aapl ") == "AAPL"

    def test_hyphenated_ticker_preserved(self):
        assert normalize_ticker("BRK-B") == "BRK-B"

    def test_dot_ticker_preserved(self):
        assert normalize_ticker("BRK.B") == "BRK.B"

    def test_mixed_case_with_whitespace(self):
        assert normalize_ticker("  tsla  ") == "TSLA"

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="empty"):
            normalize_ticker("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="empty"):
            normalize_ticker("   ")

    def test_non_string_int_raises(self):
        with pytest.raises(ValueError, match="string"):
            normalize_ticker(123)  # type: ignore[arg-type]

    def test_non_string_none_raises(self):
        with pytest.raises(ValueError, match="string"):
            normalize_ticker(None)  # type: ignore[arg-type]

    def test_non_string_list_raises(self):
        with pytest.raises(ValueError, match="string"):
            normalize_ticker(["AAPL"])  # type: ignore[arg-type]

    def test_non_string_float_raises(self):
        with pytest.raises(ValueError, match="string"):
            normalize_ticker(1.5)  # type: ignore[arg-type]

    def test_returns_string(self):
        result = normalize_ticker("msft")
        assert isinstance(result, str)
