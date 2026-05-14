"""
Unit tests for app/analysis/technicals.py.

All tests use locally constructed DataFrames — no network calls.
"""

import pandas as pd
import pytest

from app.analysis.technicals import (
    TechnicalAnalysisError,
    calculate_technical_indicators,
    summarize_technical_signals,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(rows: int = 250, close_price: float = 100.0) -> pd.DataFrame:
    """Minimal well-formed OHLCV DataFrame with a DatetimeIndex."""
    index = pd.date_range("2023-01-01", periods=rows, freq="B")
    return pd.DataFrame(
        {
            "open": close_price,
            "high": close_price + 2,
            "low": close_price - 2,
            "close": close_price,
            "volume": 1_000_000,
        },
        index=index,
    )


def _make_trending(rows: int = 250) -> pd.DataFrame:
    """OHLCV where close rises steadily from 50 to 150."""
    index = pd.date_range("2023-01-01", periods=rows, freq="B")
    prices = [50 + (100 * i / (rows - 1)) for i in range(rows)]
    return pd.DataFrame(
        {
            "open": prices,
            "high": [p + 1 for p in prices],
            "low": [p - 1 for p in prices],
            "close": prices,
            "volume": 1_000_000,
        },
        index=index,
    )


def _make_declining(rows: int = 250) -> pd.DataFrame:
    """OHLCV where close falls steadily from 150 to 50."""
    index = pd.date_range("2023-01-01", periods=rows, freq="B")
    prices = [150 - (100 * i / (rows - 1)) for i in range(rows)]
    return pd.DataFrame(
        {
            "open": prices,
            "high": [p + 1 for p in prices],
            "low": [p - 1 for p in prices],
            "close": prices,
            "volume": 1_000_000,
        },
        index=index,
    )


# ---------------------------------------------------------------------------
# calculate_technical_indicators — input validation
# ---------------------------------------------------------------------------

class TestCalculateInputValidation:
    def test_non_dataframe_raises(self):
        with pytest.raises(TechnicalAnalysisError):
            calculate_technical_indicators("AAPL")  # type: ignore[arg-type]

    def test_none_raises(self):
        with pytest.raises(TechnicalAnalysisError):
            calculate_technical_indicators(None)  # type: ignore[arg-type]

    def test_empty_dataframe_raises(self):
        with pytest.raises(TechnicalAnalysisError):
            calculate_technical_indicators(pd.DataFrame())

    def test_missing_close_raises(self):
        df = _make_ohlcv().drop(columns=["close"])
        with pytest.raises(TechnicalAnalysisError, match="missing required OHLCV"):
            calculate_technical_indicators(df)

    def test_missing_volume_raises(self):
        df = _make_ohlcv().drop(columns=["volume"])
        with pytest.raises(TechnicalAnalysisError):
            calculate_technical_indicators(df)


# ---------------------------------------------------------------------------
# calculate_technical_indicators — output correctness
# ---------------------------------------------------------------------------

class TestCalculateOutput:
    def test_returns_dataframe(self):
        result = calculate_technical_indicators(_make_ohlcv())
        assert isinstance(result, pd.DataFrame)

    def test_indicator_columns_added(self):
        result = calculate_technical_indicators(_make_ohlcv())
        expected = {
            "sma_20", "sma_50", "sma_200",
            "rsi_14",
            "macd", "macd_signal", "macd_histogram",
            "volume_sma_20",
            "daily_return",
        }
        for col in expected:
            assert col in result.columns, f"Missing column: {col}"

    def test_input_not_mutated(self):
        original = _make_ohlcv()
        original_cols = list(original.columns)
        calculate_technical_indicators(original)
        assert list(original.columns) == original_cols

    def test_row_count_preserved(self):
        df = _make_ohlcv(rows=100)
        result = calculate_technical_indicators(df)
        assert len(result) == 100

    def test_daily_return_calculated(self):
        df = _make_ohlcv(rows=50)
        result = calculate_technical_indicators(df)
        # Constant prices → daily return is 0.0 (first row is NaN)
        assert result["daily_return"].iloc[-1] == pytest.approx(0.0)

    def test_sma_20_value_for_constant_prices(self):
        df = _make_ohlcv(rows=50, close_price=100.0)
        result = calculate_technical_indicators(df)
        assert result["sma_20"].iloc[-1] == pytest.approx(100.0)

    def test_short_data_produces_nan_for_long_windows(self):
        df = _make_ohlcv(rows=10)
        result = calculate_technical_indicators(df)
        # Only 10 rows — sma_20, sma_50, sma_200 should all be NaN
        assert result["sma_20"].isna().all()
        assert result["sma_200"].isna().all()

    def test_rsi_bounds(self):
        df = _make_ohlcv(rows=100)
        result = calculate_technical_indicators(df)
        valid_rsi = result["rsi_14"].dropna()
        assert (valid_rsi >= 0).all() and (valid_rsi <= 100).all()


# ---------------------------------------------------------------------------
# summarize_technical_signals — input validation
# ---------------------------------------------------------------------------

class TestSummarizeInputValidation:
    def test_non_dataframe_raises(self):
        with pytest.raises(TechnicalAnalysisError):
            summarize_technical_signals([1, 2, 3])  # type: ignore[arg-type]

    def test_empty_dataframe_raises(self):
        with pytest.raises(TechnicalAnalysisError):
            summarize_technical_signals(pd.DataFrame())

    def test_missing_indicator_columns_raises(self):
        df = _make_ohlcv(rows=30)  # no indicator columns
        with pytest.raises(TechnicalAnalysisError, match="missing required columns"):
            summarize_technical_signals(df)


# ---------------------------------------------------------------------------
# summarize_technical_signals — output correctness
# ---------------------------------------------------------------------------

class TestSummarizeOutput:
    def _get_summary(self, rows: int = 250, df: pd.DataFrame | None = None) -> dict:
        source = df if df is not None else _make_ohlcv(rows=rows)
        indicators = calculate_technical_indicators(source)
        return summarize_technical_signals(indicators)

    def test_returns_all_expected_keys(self):
        summary = self._get_summary()
        expected_keys = {
            "latest_close", "sma_20", "sma_50", "sma_200",
            "rsi_14", "macd", "macd_signal",
            "volume", "volume_sma_20",
            "trend", "price_above_sma_20", "price_above_sma_50",
            "price_above_sma_200", "rsi_condition", "macd_condition",
        }
        assert expected_keys == set(summary.keys())

    def test_trend_bullish(self):
        summary = self._get_summary(df=_make_trending())
        assert summary["trend"] == "bullish"

    def test_trend_bearish(self):
        summary = self._get_summary(df=_make_declining())
        assert summary["trend"] == "bearish"

    def test_trend_mixed_for_constant_prices(self):
        # Constant prices → close == sma_20 == sma_50, not strictly greater/less
        summary = self._get_summary(rows=250)
        assert summary["trend"] == "mixed"

    def test_rsi_condition_neutral_for_flat_prices(self):
        # Constant prices → no gains or losses → RSI = 100 initially,
        # but after the first diff all deltas are 0.
        # With all-zero deltas avg_gain=0, avg_loss=0 → RSI filled to 100 → overbought.
        summary = self._get_summary(rows=250)
        assert summary["rsi_condition"] in ("overbought", "oversold", "neutral")

    def test_rsi_condition_overbought(self):
        # Steadily rising prices drive RSI toward 100
        summary = self._get_summary(df=_make_trending(rows=100))
        assert summary["rsi_condition"] == "overbought"

    def test_rsi_condition_oversold(self):
        # Steadily declining prices drive RSI toward 0
        summary = self._get_summary(df=_make_declining(rows=100))
        assert summary["rsi_condition"] == "oversold"

    def test_macd_condition_bullish(self):
        # Rising prices → faster EMA (12) above slower EMA (26) → bullish
        summary = self._get_summary(df=_make_trending())
        assert summary["macd_condition"] == "bullish"

    def test_macd_condition_bearish(self):
        # Declining prices → faster EMA (12) below slower EMA (26) → bearish
        summary = self._get_summary(df=_make_declining())
        assert summary["macd_condition"] == "bearish"

    def test_latest_close_matches_last_row(self):
        df = _make_ohlcv(rows=250, close_price=123.45)
        summary = self._get_summary(df=df)
        assert summary["latest_close"] == pytest.approx(123.45)
