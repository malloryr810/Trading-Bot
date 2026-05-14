"""
Unit tests for app/data/market_data.py.

All tests mock yfinance so no network calls are made.
"""

import pandas as pd
import pytest
from unittest.mock import patch

from app.data.market_data import DataFetchError, get_price_history


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(rows: int = 5) -> pd.DataFrame:
    """Return a minimal well-formed OHLCV DataFrame."""
    index = pd.date_range("2024-01-01", periods=rows, freq="D")
    return pd.DataFrame(
        {
            "Open": [100.0] * rows,
            "High": [105.0] * rows,
            "Low": [95.0] * rows,
            "Close": [102.0] * rows,
            "Volume": [1_000_000] * rows,
        },
        index=index,
    )


DOWNLOAD_PATH = "app.data.market_data.yf.download"


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestTickerValidation:
    def test_empty_string_raises(self):
        with pytest.raises(DataFetchError):
            get_price_history("")

    def test_whitespace_only_raises(self):
        with pytest.raises(DataFetchError):
            get_price_history("   ")

    def test_non_string_int_raises(self):
        with pytest.raises(DataFetchError):
            get_price_history(123)  # type: ignore[arg-type]

    def test_non_string_none_raises(self):
        with pytest.raises(DataFetchError):
            get_price_history(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Successful fetch
# ---------------------------------------------------------------------------

class TestSuccessfulFetch:
    def test_returns_dataframe(self):
        with patch(DOWNLOAD_PATH, return_value=_make_ohlcv()):
            result = get_price_history("AAPL")
        assert isinstance(result, pd.DataFrame)

    def test_column_names_are_lowercase(self):
        with patch(DOWNLOAD_PATH, return_value=_make_ohlcv()):
            result = get_price_history("aapl")
        assert all(col == col.lower() for col in result.columns)

    def test_required_columns_present(self):
        with patch(DOWNLOAD_PATH, return_value=_make_ohlcv()):
            result = get_price_history("AAPL")
        for col in ("open", "high", "low", "close", "volume"):
            assert col in result.columns

    def test_ticker_uppercased_before_fetch(self):
        with patch(DOWNLOAD_PATH, return_value=_make_ohlcv()) as mock_dl:
            get_price_history("aapl")
        mock_dl.assert_called_once_with(
            "AAPL", period="1y", interval="1d", progress=False
        )

    def test_whitespace_stripped_from_ticker(self):
        with patch(DOWNLOAD_PATH, return_value=_make_ohlcv()) as mock_dl:
            get_price_history("  AAPL  ")
        mock_dl.assert_called_once_with(
            "AAPL", period="1y", interval="1d", progress=False
        )

    def test_index_preserved(self):
        raw = _make_ohlcv(rows=10)
        with patch(DOWNLOAD_PATH, return_value=raw):
            result = get_price_history("AAPL")
        assert len(result) == 10


# ---------------------------------------------------------------------------
# Data validation
# ---------------------------------------------------------------------------

class TestDataValidation:
    def test_empty_dataframe_raises(self):
        with patch(DOWNLOAD_PATH, return_value=pd.DataFrame()):
            with pytest.raises(DataFetchError, match="No data returned"):
                get_price_history("INVALID")

    def test_missing_required_column_raises(self):
        incomplete = _make_ohlcv().drop(columns=["Volume"])
        with patch(DOWNLOAD_PATH, return_value=incomplete):
            with pytest.raises(DataFetchError, match="missing required columns"):
                get_price_history("AAPL")

    def test_all_nan_rows_dropped_and_raises_if_empty(self):
        raw = _make_ohlcv(rows=3)
        raw[["Open", "High", "Low", "Close", "Volume"]] = float("nan")
        with patch(DOWNLOAD_PATH, return_value=raw):
            with pytest.raises(DataFetchError, match="missing OHLCV values"):
                get_price_history("AAPL")

    def test_partial_nan_rows_dropped_keeps_valid_rows(self):
        raw = _make_ohlcv(rows=4)
        raw.iloc[0, :] = float("nan")  # first row all NaN
        with patch(DOWNLOAD_PATH, return_value=raw):
            result = get_price_history("AAPL")
        assert len(result) == 3


# ---------------------------------------------------------------------------
# yfinance error handling
# ---------------------------------------------------------------------------

class TestYfinanceErrors:
    def test_yfinance_exception_wrapped_as_data_fetch_error(self):
        with patch(DOWNLOAD_PATH, side_effect=Exception("network timeout")):
            with pytest.raises(DataFetchError, match="yfinance raised an error"):
                get_price_history("AAPL")
