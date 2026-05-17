"""
Unit tests for app/data/fundamentals.py.

All tests mock yfinance so no network calls are made.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.data.fundamentals import FundamentalDataFetchError, get_company_fundamentals
from app.models.fundamentals import CompanyFundamentals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_info(**overrides) -> dict:
    """Return a realistic yfinance .info dict with optional field overrides."""
    defaults: dict = {
        "longName": "Apple Inc.",
        "shortName": "Apple",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "marketCap": 3_000_000_000_000,
        "trailingPE": 28.5,
        "forwardPE": 26.0,
        "priceToBook": 45.0,
        "profitMargins": 0.25,
        "revenueGrowth": 0.05,
        "earningsGrowth": 0.08,
        "debtToEquity": 150.0,
        "freeCashflow": 90_000_000_000,
        "dividendYield": 0.005,
        "beta": 1.2,
    }
    defaults.update(overrides)
    return defaults


TICKER_PATH = "app.data.fundamentals.yf.Ticker"


def _mock_ticker(info: dict):
    """Return a patch context manager that makes yf.Ticker(...).info return info."""
    mock = MagicMock()
    mock.return_value.info = info
    return patch(TICKER_PATH, mock)


# ---------------------------------------------------------------------------
# Return type and provenance
# ---------------------------------------------------------------------------

class TestReturnType:
    def test_returns_company_fundamentals_instance(self):
        with _mock_ticker(_make_info()):
            result = get_company_fundamentals("AAPL")
        assert isinstance(result, CompanyFundamentals)

    def test_source_is_yfinance(self):
        with _mock_ticker(_make_info()):
            result = get_company_fundamentals("AAPL")
        assert result.source == "yfinance"

    def test_data_timestamp_is_populated(self):
        with _mock_ticker(_make_info()):
            result = get_company_fundamentals("AAPL")
        assert isinstance(result.data_timestamp, datetime)

    def test_data_timestamp_is_timezone_aware(self):
        with _mock_ticker(_make_info()):
            result = get_company_fundamentals("AAPL")
        assert result.data_timestamp.tzinfo is not None


# ---------------------------------------------------------------------------
# Ticker normalization
# ---------------------------------------------------------------------------

class TestTickerNormalization:
    def test_lowercase_ticker_normalized_to_uppercase(self):
        with _mock_ticker(_make_info()):
            result = get_company_fundamentals("aapl")
        assert result.ticker == "AAPL"

    def test_whitespace_stripped_and_uppercased(self):
        with _mock_ticker(_make_info()):
            result = get_company_fundamentals("  aapl  ")
        assert result.ticker == "AAPL"

    def test_uppercase_symbol_passed_to_yfinance(self):
        mock = MagicMock()
        mock.return_value.info = _make_info()
        with patch(TICKER_PATH, mock):
            get_company_fundamentals("aapl")
        mock.assert_called_once_with("AAPL")


# ---------------------------------------------------------------------------
# Successful fetch — full data
# ---------------------------------------------------------------------------

class TestSuccessfulFetch:
    def _fetch(self, **overrides) -> CompanyFundamentals:
        with _mock_ticker(_make_info(**overrides)):
            return get_company_fundamentals("AAPL")

    def test_company_name_populated(self):
        assert self._fetch().company_name == "Apple Inc."

    def test_sector_populated(self):
        assert self._fetch().sector == "Technology"

    def test_industry_populated(self):
        assert self._fetch().industry == "Consumer Electronics"

    def test_market_cap_populated(self):
        assert self._fetch().market_cap == pytest.approx(3_000_000_000_000)

    def test_trailing_pe_populated(self):
        assert self._fetch().trailing_pe == pytest.approx(28.5)

    def test_forward_pe_populated(self):
        assert self._fetch().forward_pe == pytest.approx(26.0)

    def test_price_to_book_populated(self):
        assert self._fetch().price_to_book == pytest.approx(45.0)

    def test_profit_margin_populated(self):
        assert self._fetch().profit_margin == pytest.approx(0.25)

    def test_revenue_growth_populated(self):
        assert self._fetch().revenue_growth == pytest.approx(0.05)

    def test_earnings_growth_populated(self):
        assert self._fetch().earnings_growth == pytest.approx(0.08)

    def test_debt_to_equity_populated(self):
        assert self._fetch().debt_to_equity == pytest.approx(150.0)

    def test_free_cash_flow_populated(self):
        assert self._fetch().free_cash_flow == pytest.approx(90_000_000_000)

    def test_dividend_yield_populated(self):
        assert self._fetch().dividend_yield == pytest.approx(0.005)

    def test_beta_populated(self):
        assert self._fetch().beta == pytest.approx(1.2)


# ---------------------------------------------------------------------------
# Successful fetch — missing optional fields
# ---------------------------------------------------------------------------

class TestMissingOptionalFields:
    def test_missing_trailing_pe_is_none(self):
        info = _make_info()
        del info["trailingPE"]
        with _mock_ticker(info):
            result = get_company_fundamentals("AAPL")
        assert result.trailing_pe is None

    def test_missing_dividend_yield_is_none(self):
        info = _make_info()
        del info["dividendYield"]
        with _mock_ticker(info):
            result = get_company_fundamentals("AAPL")
        assert result.dividend_yield is None

    def test_missing_beta_is_none(self):
        info = _make_info()
        del info["beta"]
        with _mock_ticker(info):
            result = get_company_fundamentals("AAPL")
        assert result.beta is None

    def test_none_value_for_metric_is_none(self):
        with _mock_ticker(_make_info(trailingPE=None)):
            result = get_company_fundamentals("AAPL")
        assert result.trailing_pe is None

    def test_all_optional_metrics_absent_still_returns_model(self):
        with _mock_ticker({"longName": "Some Corp"}):
            result = get_company_fundamentals("AAPL")
        assert isinstance(result, CompanyFundamentals)
        assert result.trailing_pe is None
        assert result.market_cap is None
        assert result.beta is None
        assert result.sector is None

    def test_empty_string_sector_becomes_none(self):
        with _mock_ticker(_make_info(sector="")):
            result = get_company_fundamentals("AAPL")
        assert result.sector is None

    def test_empty_string_industry_becomes_none(self):
        with _mock_ticker(_make_info(industry="")):
            result = get_company_fundamentals("AAPL")
        assert result.industry is None


# ---------------------------------------------------------------------------
# Company name extraction
# ---------------------------------------------------------------------------

class TestCompanyNameExtraction:
    def test_long_name_preferred_over_short_name(self):
        with _mock_ticker(_make_info(longName="Apple Inc.", shortName="Apple")):
            result = get_company_fundamentals("AAPL")
        assert result.company_name == "Apple Inc."

    def test_short_name_used_when_long_name_absent(self):
        info = _make_info()
        del info["longName"]
        with _mock_ticker(info):
            result = get_company_fundamentals("AAPL")
        assert result.company_name == "Apple"

    def test_short_name_used_when_long_name_is_none(self):
        with _mock_ticker(_make_info(longName=None, shortName="Apple")):
            result = get_company_fundamentals("AAPL")
        assert result.company_name == "Apple"


# ---------------------------------------------------------------------------
# Numeric conversion (_safe_float)
# ---------------------------------------------------------------------------

class TestNumericConversion:
    def test_integer_value_converted_to_float(self):
        with _mock_ticker(_make_info(trailingPE=28)):
            result = get_company_fundamentals("AAPL")
        assert isinstance(result.trailing_pe, float)
        assert result.trailing_pe == pytest.approx(28.0)

    def test_nan_value_becomes_none(self):
        with _mock_ticker(_make_info(trailingPE=float("nan"))):
            result = get_company_fundamentals("AAPL")
        assert result.trailing_pe is None

    def test_inf_value_becomes_none(self):
        with _mock_ticker(_make_info(trailingPE=float("inf"))):
            result = get_company_fundamentals("AAPL")
        assert result.trailing_pe is None

    def test_non_numeric_string_becomes_none(self):
        with _mock_ticker(_make_info(trailingPE="N/A")):
            result = get_company_fundamentals("AAPL")
        assert result.trailing_pe is None


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestTickerValidation:
    def test_empty_string_raises(self):
        with pytest.raises(FundamentalDataFetchError):
            get_company_fundamentals("")

    def test_whitespace_only_raises(self):
        with pytest.raises(FundamentalDataFetchError):
            get_company_fundamentals("   ")

    def test_non_string_int_raises(self):
        with pytest.raises(FundamentalDataFetchError):
            get_company_fundamentals(123)  # type: ignore[arg-type]

    def test_non_string_none_raises(self):
        with pytest.raises(FundamentalDataFetchError):
            get_company_fundamentals(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# yfinance error handling
# ---------------------------------------------------------------------------

class TestYfinanceErrors:
    def test_yfinance_exception_wrapped_in_fetch_error(self):
        with patch(TICKER_PATH, side_effect=Exception("network timeout")):
            with pytest.raises(FundamentalDataFetchError, match="yfinance raised an error"):
                get_company_fundamentals("AAPL")

    def test_empty_info_dict_raises(self):
        with _mock_ticker({}):
            with pytest.raises(FundamentalDataFetchError, match="No data returned"):
                get_company_fundamentals("AAPL")

    def test_none_info_raises(self):
        mock = MagicMock()
        mock.return_value.info = None
        with patch(TICKER_PATH, mock):
            with pytest.raises(FundamentalDataFetchError):
                get_company_fundamentals("AAPL")

    def test_info_with_no_company_name_raises(self):
        with _mock_ticker({"marketCap": 1_000_000, "trailingPE": 20.0}):
            with pytest.raises(FundamentalDataFetchError, match="could not identify the company"):
                get_company_fundamentals("INVALID")
