"""
Unit tests for app/data/market_data.py.

All tests mock yfinance so no network calls are made.
"""

from __future__ import annotations

import pandas as pd
import pytest
from unittest.mock import patch

from app.data.market_data import (
    DataFetchError,
    _normalize_columns,
    _validate_column_nullability,
    _validate_numeric_columns,
    _validate_price_history,
    _validate_required_columns,
    get_price_history,
    latest_valid_close,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(rows: int = 5) -> pd.DataFrame:
    """Return a minimal well-formed OHLCV DataFrame (title-case columns, like yfinance)."""
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


def _make_normalized_ohlcv(rows: int = 5) -> pd.DataFrame:
    """Return a well-formed OHLCV DataFrame with lowercase column names."""
    index = pd.date_range("2024-01-01", periods=rows, freq="D")
    return pd.DataFrame(
        {
            "open": [100.0] * rows,
            "high": [105.0] * rows,
            "low": [95.0] * rows,
            "close": [102.0] * rows,
            "volume": [1_000_000] * rows,
        },
        index=index,
    )


DOWNLOAD_PATH = "app.data.market_data.yf.download"


# ---------------------------------------------------------------------------
# Input validation — ticker
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

    def test_empty_string_error_is_data_fetch_error(self):
        with pytest.raises(DataFetchError):
            get_price_history("")

    def test_non_string_error_message_mentions_type(self):
        with pytest.raises(DataFetchError, match="string"):
            get_price_history(42)  # type: ignore[arg-type]


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

    def test_values_are_numeric(self):
        with patch(DOWNLOAD_PATH, return_value=_make_ohlcv()):
            result = get_price_history("AAPL")
        for col in ("open", "high", "low", "close", "volume"):
            assert pd.api.types.is_numeric_dtype(result[col])

    def test_non_required_extra_columns_preserved(self):
        raw = _make_ohlcv(rows=3)
        raw["Adj Close"] = [101.0, 102.0, 103.0]
        with patch(DOWNLOAD_PATH, return_value=raw):
            result = get_price_history("AAPL")
        assert "adj_close" in result.columns


# ---------------------------------------------------------------------------
# Data validation — structure and content
# ---------------------------------------------------------------------------

class TestDataValidation:
    def test_empty_dataframe_raises(self):
        with patch(DOWNLOAD_PATH, return_value=pd.DataFrame()):
            with pytest.raises(DataFetchError, match="No data returned"):
                get_price_history("INVALID")

    def test_empty_dataframe_error_includes_ticker(self):
        with patch(DOWNLOAD_PATH, return_value=pd.DataFrame()):
            with pytest.raises(DataFetchError, match="BOGUS"):
                get_price_history("BOGUS")

    def test_empty_dataframe_error_includes_period(self):
        with patch(DOWNLOAD_PATH, return_value=pd.DataFrame()):
            with pytest.raises(DataFetchError, match="6mo"):
                get_price_history("AAPL", period="6mo")

    def test_empty_dataframe_error_includes_interval(self):
        with patch(DOWNLOAD_PATH, return_value=pd.DataFrame()):
            with pytest.raises(DataFetchError, match="1wk"):
                get_price_history("AAPL", interval="1wk")

    def test_non_dataframe_return_raises(self):
        with patch(DOWNLOAD_PATH, return_value={"Close": [100.0]}):
            with pytest.raises(DataFetchError, match="unexpected result type"):
                get_price_history("AAPL")

    def test_none_return_raises(self):
        with patch(DOWNLOAD_PATH, return_value=None):
            with pytest.raises(DataFetchError, match="unexpected result type"):
                get_price_history("AAPL")

    def test_none_return_error_mentions_nonetype(self):
        with patch(DOWNLOAD_PATH, return_value=None):
            with pytest.raises(DataFetchError, match="NoneType"):
                get_price_history("AAPL")

    def test_missing_required_column_raises(self):
        incomplete = _make_ohlcv().drop(columns=["Volume"])
        with patch(DOWNLOAD_PATH, return_value=incomplete):
            with pytest.raises(DataFetchError, match="missing required columns"):
                get_price_history("AAPL")

    def test_missing_column_error_names_the_column(self):
        incomplete = _make_ohlcv().drop(columns=["Volume"])
        with patch(DOWNLOAD_PATH, return_value=incomplete):
            with pytest.raises(DataFetchError, match="volume"):
                get_price_history("AAPL")

    def test_missing_column_error_lists_present_columns(self):
        incomplete = _make_ohlcv().drop(columns=["Volume"])
        with patch(DOWNLOAD_PATH, return_value=incomplete):
            with pytest.raises(DataFetchError, match="Columns present"):
                get_price_history("AAPL")

    def test_single_column_entirely_null_raises(self):
        raw = _make_ohlcv(rows=3)
        raw["Volume"] = float("nan")  # volume entirely null, others fine
        with patch(DOWNLOAD_PATH, return_value=raw):
            with pytest.raises(DataFetchError, match="contains no usable values"):
                get_price_history("AAPL")

    def test_single_column_entirely_null_error_names_column(self):
        raw = _make_ohlcv(rows=3)
        raw["Close"] = float("nan")
        with patch(DOWNLOAD_PATH, return_value=raw):
            with pytest.raises(DataFetchError, match="close"):
                get_price_history("AAPL")

    def test_all_columns_entirely_null_raises(self):
        raw = _make_ohlcv(rows=3)
        raw[["Open", "High", "Low", "Close", "Volume"]] = float("nan")
        with patch(DOWNLOAD_PATH, return_value=raw):
            with pytest.raises(DataFetchError, match="contains no usable values"):
                get_price_history("AAPL")

    def test_non_numeric_column_raises(self):
        raw = _make_ohlcv(rows=3)
        raw["Close"] = ["not", "a", "number"]
        with patch(DOWNLOAD_PATH, return_value=raw):
            with pytest.raises(DataFetchError, match="non-numeric dtype"):
                get_price_history("AAPL")

    def test_non_numeric_column_error_names_the_column(self):
        raw = _make_ohlcv(rows=3)
        raw["Open"] = ["x", "y", "z"]
        with patch(DOWNLOAD_PATH, return_value=raw):
            with pytest.raises(DataFetchError, match="open"):
                get_price_history("AAPL")

    def test_partial_nan_rows_dropped_keeps_valid_rows(self):
        raw = _make_ohlcv(rows=4)
        raw.iloc[0, :] = float("nan")  # first row all NaN
        with patch(DOWNLOAD_PATH, return_value=raw):
            result = get_price_history("AAPL")
        assert len(result) == 3

    def test_all_rows_fully_nan_after_dropna_raises(self):
        # Build a DataFrame where columns all exist and have a mix,
        # but dropna(how='all') removes everything (each row has at least one
        # non-null in a non-required extra column — this forces the after-dropna check).
        # Easier: use an empty DataFrame that already passed the raw.empty check by
        # inserting a single NaN row that gets removed.
        raw = pd.DataFrame(
            {
                "Open": [float("nan")],
                "High": [float("nan")],
                "Low": [float("nan")],
                "Close": [float("nan")],
                "Volume": [float("nan")],
                "Extra": ["something"],  # non-null extra column keeps row alive initially
            },
            index=pd.date_range("2024-01-01", periods=1),
        )
        with patch(DOWNLOAD_PATH, return_value=raw):
            with pytest.raises(DataFetchError):
                get_price_history("AAPL")


# ---------------------------------------------------------------------------
# yfinance error handling
# ---------------------------------------------------------------------------

class TestYfinanceErrors:
    def test_yfinance_exception_wrapped_as_data_fetch_error(self):
        with patch(DOWNLOAD_PATH, side_effect=Exception("network timeout")):
            with pytest.raises(DataFetchError, match="yfinance raised an error"):
                get_price_history("AAPL")

    def test_yfinance_exception_preserves_original_message(self):
        with patch(DOWNLOAD_PATH, side_effect=Exception("connection refused")):
            with pytest.raises(DataFetchError, match="connection refused"):
                get_price_history("AAPL")

    def test_yfinance_exception_includes_ticker(self):
        with patch(DOWNLOAD_PATH, side_effect=Exception("fail")):
            with pytest.raises(DataFetchError, match="MSFT"):
                get_price_history("MSFT")

    def test_yfinance_exception_includes_period(self):
        with patch(DOWNLOAD_PATH, side_effect=Exception("fail")):
            with pytest.raises(DataFetchError, match="3mo"):
                get_price_history("AAPL", period="3mo")

    def test_yfinance_exception_includes_interval(self):
        with patch(DOWNLOAD_PATH, side_effect=Exception("fail")):
            with pytest.raises(DataFetchError, match="1wk"):
                get_price_history("AAPL", interval="1wk")

    def test_yfinance_exception_chained(self):
        original = Exception("root cause")
        with patch(DOWNLOAD_PATH, side_effect=original):
            with pytest.raises(DataFetchError) as exc_info:
                get_price_history("AAPL")
        assert exc_info.value.__cause__ is original

    def test_ticker_validation_error_chained(self):
        with pytest.raises(DataFetchError) as exc_info:
            get_price_history("")
        assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# _normalize_columns unit tests
# ---------------------------------------------------------------------------

class TestNormalizeColumns:
    def test_title_case_columns_lowercased(self):
        df = pd.DataFrame({"Open": [1.0], "High": [2.0], "Close": [3.0]})
        result = _normalize_columns(df)
        assert list(result.columns) == ["open", "high", "close"]

    def test_spaces_replaced_with_underscores(self):
        df = pd.DataFrame({"Adj Close": [1.0], "Open": [2.0]})
        result = _normalize_columns(df)
        assert "adj_close" in result.columns

    def test_multiindex_flattened(self):
        # yfinance MultiIndex: level 0 = field names, level 1 = ticker symbols
        arrays = [["Open", "Close"], ["AAPL", "AAPL"]]
        tuples = list(zip(*arrays))
        midx = pd.MultiIndex.from_tuples(tuples)
        df = pd.DataFrame([[1.0, 2.0]], columns=midx)
        result = _normalize_columns(df)
        assert result.columns.nlevels == 1
        assert "open" in result.columns
        assert "close" in result.columns

    def test_already_lowercase_unchanged(self):
        df = pd.DataFrame({"open": [1.0], "close": [2.0]})
        result = _normalize_columns(df)
        assert list(result.columns) == ["open", "close"]


# ---------------------------------------------------------------------------
# _validate_required_columns unit tests
# ---------------------------------------------------------------------------

class TestValidateRequiredColumns:
    def test_passes_with_all_required_columns(self):
        df = _make_normalized_ohlcv()
        _validate_required_columns(df, "AAPL")  # should not raise

    def test_raises_on_missing_single_column(self):
        df = _make_normalized_ohlcv().drop(columns=["volume"])
        with pytest.raises(DataFetchError, match="volume"):
            _validate_required_columns(df, "AAPL")

    def test_raises_on_missing_multiple_columns(self):
        df = _make_normalized_ohlcv().drop(columns=["open", "close"])
        with pytest.raises(DataFetchError, match="missing required columns"):
            _validate_required_columns(df, "AAPL")

    def test_error_message_lists_present_columns(self):
        df = _make_normalized_ohlcv().drop(columns=["volume"])
        with pytest.raises(DataFetchError, match="Columns present"):
            _validate_required_columns(df, "AAPL")

    def test_error_message_includes_symbol(self):
        df = _make_normalized_ohlcv().drop(columns=["close"])
        with pytest.raises(DataFetchError, match="TSLA"):
            _validate_required_columns(df, "TSLA")


# ---------------------------------------------------------------------------
# _validate_column_nullability unit tests
# ---------------------------------------------------------------------------

class TestValidateColumnNullability:
    def test_passes_with_valid_data(self):
        df = _make_normalized_ohlcv()
        _validate_column_nullability(df, "AAPL")  # should not raise

    def test_raises_if_close_entirely_null(self):
        df = _make_normalized_ohlcv()
        df["close"] = float("nan")
        with pytest.raises(DataFetchError, match="close"):
            _validate_column_nullability(df, "AAPL")

    def test_raises_if_volume_entirely_null(self):
        df = _make_normalized_ohlcv()
        df["volume"] = float("nan")
        with pytest.raises(DataFetchError, match="volume"):
            _validate_column_nullability(df, "AAPL")

    def test_passes_if_only_some_rows_null(self):
        df = _make_normalized_ohlcv(rows=4)
        df.loc[df.index[0], "close"] = float("nan")  # one row null, rest fine
        _validate_column_nullability(df, "AAPL")  # should not raise

    def test_error_mentions_all_null(self):
        df = _make_normalized_ohlcv()
        df["open"] = float("nan")
        with pytest.raises(DataFetchError, match="null"):
            _validate_column_nullability(df, "AAPL")

    def test_error_includes_symbol(self):
        df = _make_normalized_ohlcv()
        df["high"] = float("nan")
        with pytest.raises(DataFetchError, match="GOOGL"):
            _validate_column_nullability(df, "GOOGL")


# ---------------------------------------------------------------------------
# _validate_numeric_columns unit tests
# ---------------------------------------------------------------------------

class TestValidateNumericColumns:
    def test_passes_with_float_columns(self):
        df = _make_normalized_ohlcv()
        _validate_numeric_columns(df, "AAPL")  # should not raise

    def test_passes_with_int_volume(self):
        df = _make_normalized_ohlcv()
        df["volume"] = df["volume"].astype(int)
        _validate_numeric_columns(df, "AAPL")  # should not raise

    def test_raises_if_close_is_strings(self):
        df = _make_normalized_ohlcv()
        df["close"] = ["a", "b", "c", "d", "e"]
        with pytest.raises(DataFetchError, match="non-numeric dtype"):
            _validate_numeric_columns(df, "AAPL")

    def test_raises_error_names_the_column(self):
        df = _make_normalized_ohlcv()
        df["open"] = ["x", "y", "z", "w", "v"]
        with pytest.raises(DataFetchError, match="open"):
            _validate_numeric_columns(df, "AAPL")

    def test_raises_error_includes_symbol(self):
        df = _make_normalized_ohlcv()
        df["volume"] = ["a", "b", "c", "d", "e"]
        with pytest.raises(DataFetchError, match="NVDA"):
            _validate_numeric_columns(df, "NVDA")

    def test_skips_missing_column_gracefully(self):
        df = _make_normalized_ohlcv().drop(columns=["volume"])
        # missing columns are _validate_required_columns' job; numeric check skips them
        _validate_numeric_columns(df, "AAPL")  # should not raise


# ---------------------------------------------------------------------------
# _validate_price_history integration tests
# ---------------------------------------------------------------------------

class TestValidatePriceHistory:
    def test_passes_with_valid_normalized_dataframe(self):
        df = _make_normalized_ohlcv()
        _validate_price_history(df, "AAPL")  # should not raise

    def test_raises_on_missing_column(self):
        df = _make_normalized_ohlcv().drop(columns=["close"])
        with pytest.raises(DataFetchError, match="missing required columns"):
            _validate_price_history(df, "AAPL")

    def test_raises_on_entirely_null_column(self):
        df = _make_normalized_ohlcv()
        df["volume"] = float("nan")
        with pytest.raises(DataFetchError, match="contains no usable values"):
            _validate_price_history(df, "AAPL")

    def test_raises_on_non_numeric_column(self):
        df = _make_normalized_ohlcv()
        df["close"] = ["a", "b", "c", "d", "e"]
        with pytest.raises(DataFetchError, match="non-numeric dtype"):
            _validate_price_history(df, "AAPL")

    def test_column_check_runs_before_nullability_check(self):
        # If a required column is missing entirely, we should get the
        # "missing required columns" error, not a nullability error.
        df = _make_normalized_ohlcv().drop(columns=["close"])
        with pytest.raises(DataFetchError, match="missing required columns"):
            _validate_price_history(df, "AAPL")


# ---------------------------------------------------------------------------
# latest_valid_close — the canonical current-price reader
# ---------------------------------------------------------------------------

class TestLatestValidClose:
    def test_returns_latest_close_when_final_row_is_valid(self):
        df = _make_normalized_ohlcv(rows=5)
        df.loc[df.index[-1], "close"] = 187.25
        assert latest_valid_close(df) == pytest.approx(187.25)

    def test_normal_data_is_unaffected(self):
        # Every row valid and identical — behavior must match plain last-row access.
        df = _make_normalized_ohlcv(rows=5)
        assert latest_valid_close(df) == pytest.approx(df["close"].iloc[-1])

    def test_falls_back_when_final_close_is_none(self):
        df = _make_normalized_ohlcv(rows=5)
        df.loc[df.index[-2], "close"] = 150.0
        df["close"] = df["close"].astype(object)
        df.loc[df.index[-1], "close"] = None
        assert latest_valid_close(df) == pytest.approx(150.0)

    def test_falls_back_when_final_close_is_nan(self):
        df = _make_normalized_ohlcv(rows=5)
        df.loc[df.index[-2], "close"] = 150.0
        df.loc[df.index[-1], "close"] = float("nan")
        assert latest_valid_close(df) == pytest.approx(150.0)

    def test_in_progress_session_row_keeps_volume_but_not_price(self):
        # The real-world shape: the provider posts a current-day row with a
        # volume while OHLC are still null.
        df = _make_normalized_ohlcv(rows=5)
        df.loc[df.index[-2], "close"] = 333.0
        df.loc[df.index[-1], ["open", "high", "low", "close"]] = float("nan")
        df.loc[df.index[-1], "volume"] = 71_988_041
        assert latest_valid_close(df) == pytest.approx(333.0)

    def test_skips_multiple_trailing_invalid_rows(self):
        df = _make_normalized_ohlcv(rows=6)
        df.loc[df.index[2], "close"] = 120.0
        df.loc[df.index[3:], "close"] = float("nan")
        assert latest_valid_close(df) == pytest.approx(120.0)

    def test_skips_infinite_close(self):
        df = _make_normalized_ohlcv(rows=3)
        df.loc[df.index[-2], "close"] = 111.0
        df.loc[df.index[-1], "close"] = float("inf")
        assert latest_valid_close(df) == pytest.approx(111.0)

    def test_skips_non_numeric_close(self):
        df = _make_normalized_ohlcv(rows=3)
        df["close"] = [101.0, 102.0, "n/a"]
        assert latest_valid_close(df) == pytest.approx(102.0)

    def test_returns_none_when_no_valid_close_exists(self):
        df = _make_normalized_ohlcv(rows=4)
        df["close"] = float("nan")
        assert latest_valid_close(df) is None

    def test_returns_none_for_an_empty_frame(self):
        assert latest_valid_close(_make_normalized_ohlcv(rows=0)) is None

    def test_returns_none_when_close_column_is_absent(self):
        df = _make_normalized_ohlcv().drop(columns=["close"])
        assert latest_valid_close(df) is None

    def test_returns_none_for_a_non_dataframe(self):
        assert latest_valid_close(None) is None

    def test_missing_close_is_never_reported_as_zero(self):
        df = _make_normalized_ohlcv(rows=3)
        df["close"] = float("nan")
        result = latest_valid_close(df)
        assert result is None
        assert result != 0

    def test_zero_close_is_returned_rather_than_skipped(self):
        # Zero is numerically valid; callers that need a positive price check it.
        df = _make_normalized_ohlcv(rows=3)
        df.loc[df.index[-1], "close"] = 0.0
        assert latest_valid_close(df) == 0.0

    def test_does_not_mutate_the_frame(self):
        df = _make_normalized_ohlcv(rows=4)
        df.loc[df.index[-1], "close"] = float("nan")
        before = df.copy()
        latest_valid_close(df)
        pd.testing.assert_frame_equal(df, before)
