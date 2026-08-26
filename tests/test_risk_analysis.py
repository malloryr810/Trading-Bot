"""
Unit tests for app/analysis/risk_analysis.py.

All tests use locally constructed DataFrames — no network calls.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.analysis.risk_analysis import RiskAnalysisError, analyze_risk_conditions
from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength


# ---------------------------------------------------------------------------
# DataFrame helpers
# ---------------------------------------------------------------------------

_SIGNAL_NAMES = {
    "Volatility Risk",
    "Maximum Drawdown Risk",
    "Recent Trend Risk",
    "Liquidity Risk",
}


def _make_df(
    n: int = 60,
    close: float | list[float] = 100.0,
    volume: float | list[float] = 1_500_000.0,
) -> pd.DataFrame:
    """Build a minimal price history DataFrame."""
    close_vals  = close  if isinstance(close,  list) else [close]  * n
    volume_vals = volume if isinstance(volume, list) else [volume] * n
    # When close is a list, align volume length to it.
    row_count = len(close_vals)
    if not isinstance(volume, list):
        volume_vals = [volume] * row_count
    return pd.DataFrame({"close": close_vals, "volume": volume_vals})


def _flat(n: int = 60, price: float = 100.0, vol: float = 1_500_000.0) -> pd.DataFrame:
    """All-flat prices — zero volatility, zero drawdown."""
    return _make_df(n=n, close=price, volume=vol)


def _alternating(n: int = 60, low: float = 100.0, high: float = 115.0) -> pd.DataFrame:
    """Alternating low/high prices — produces high annualized volatility."""
    prices = [low if i % 2 == 0 else high for i in range(n)]
    return _make_df(close=prices)


def _signal_by_name(signals: list[Signal], name: str) -> Signal:
    for s in signals:
        if s.name == name:
            return s
    raise KeyError(f"No signal named '{name}' found.")


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

class TestStructure:
    def test_returns_list(self):
        assert isinstance(analyze_risk_conditions(_flat()), list)

    def test_all_items_are_signal_instances(self):
        result = analyze_risk_conditions(_flat())
        assert all(isinstance(s, Signal) for s in result)

    def test_returns_4_signals_without_beta(self):
        assert len(analyze_risk_conditions(_flat())) == 4

    def test_returns_5_signals_with_beta(self):
        assert len(analyze_risk_conditions(_flat(), beta=1.2)) == 5

    def test_all_signals_use_risk_category(self):
        result = analyze_risk_conditions(_flat(), beta=1.2)
        assert all(s.category == SignalCategory.RISK for s in result)

    def test_expected_signal_names_present(self):
        result = analyze_risk_conditions(_flat())
        names = {s.name for s in result}
        assert _SIGNAL_NAMES.issubset(names)

    def test_beta_signal_name_when_provided(self):
        result = analyze_risk_conditions(_flat(), beta=1.2)
        assert any(s.name == "Beta Risk" for s in result)

    def test_beta_signal_absent_when_none(self):
        result = analyze_risk_conditions(_flat())
        assert not any(s.name == "Beta Risk" for s in result)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_non_dataframe_raises(self):
        with pytest.raises(RiskAnalysisError, match="DataFrame"):
            analyze_risk_conditions("not a df")  # type: ignore[arg-type]

    def test_empty_dataframe_raises(self):
        with pytest.raises(RiskAnalysisError, match="empty"):
            analyze_risk_conditions(pd.DataFrame())

    def test_missing_close_column_raises(self):
        df = pd.DataFrame({"volume": [1_000_000] * 10})
        with pytest.raises(RiskAnalysisError, match="close"):
            analyze_risk_conditions(df)

    def test_missing_volume_column_raises(self):
        df = pd.DataFrame({"close": [100.0] * 10})
        with pytest.raises(RiskAnalysisError, match="volume"):
            analyze_risk_conditions(df)

    def test_non_finite_beta_nan_raises(self):
        with pytest.raises(RiskAnalysisError, match="finite"):
            analyze_risk_conditions(_flat(), beta=float("nan"))

    def test_non_finite_beta_inf_raises(self):
        with pytest.raises(RiskAnalysisError, match="finite"):
            analyze_risk_conditions(_flat(), beta=float("inf"))

    def test_non_numeric_beta_raises(self):
        with pytest.raises(RiskAnalysisError):
            analyze_risk_conditions(_flat(), beta="high")  # type: ignore[arg-type]

    def test_beta_none_does_not_raise(self):
        result = analyze_risk_conditions(_flat(), beta=None)
        assert len(result) == 4


# ---------------------------------------------------------------------------
# Volatility signal
# ---------------------------------------------------------------------------

class TestVolatilitySignal:
    def _vol_signal(self, df: pd.DataFrame) -> Signal:
        return _signal_by_name(analyze_risk_conditions(df), "Volatility Risk")

    def test_high_volatility_is_bearish(self):
        sig = self._vol_signal(_alternating(low=100.0, high=130.0))
        assert sig.direction == SignalDirection.BEARISH

    def test_high_volatility_is_strong(self):
        sig = self._vol_signal(_alternating(low=100.0, high=130.0))
        assert sig.strength == SignalStrength.STRONG

    def test_high_volatility_negative_impact(self):
        sig = self._vol_signal(_alternating(low=100.0, high=130.0))
        assert sig.score_impact < 0

    def test_flat_prices_are_bullish(self):
        sig = self._vol_signal(_flat())
        assert sig.direction == SignalDirection.BULLISH

    def test_flat_prices_positive_impact(self):
        sig = self._vol_signal(_flat())
        assert sig.score_impact > 0

    def test_single_row_returns_neutral_low_confidence(self):
        sig = self._vol_signal(_make_df(n=1))
        assert sig.direction == SignalDirection.NEUTRAL
        assert sig.confidence == pytest.approx(0.30)

    def test_signal_has_numeric_value_when_computable(self):
        sig = self._vol_signal(_flat())
        assert sig.value is not None
        assert isinstance(sig.value, float)

    def test_signal_value_is_none_when_insufficient_data(self):
        sig = self._vol_signal(_make_df(n=1))
        assert sig.value is None

    def test_moderate_volatility_is_neutral(self):
        # Alternating +2% / -2% returns ≈ daily std 0.02 → annualized ~0.32 → neutral
        prices = []
        p = 100.0
        for i in range(60):
            p = p * 1.02 if i % 2 == 0 else p * 0.98
            prices.append(p)
        sig = self._vol_signal(_make_df(close=prices))
        assert sig.direction == SignalDirection.NEUTRAL


# ---------------------------------------------------------------------------
# Maximum drawdown signal
# ---------------------------------------------------------------------------

class TestMaxDrawdownSignal:
    def _dd_signal(self, df: pd.DataFrame) -> Signal:
        return _signal_by_name(analyze_risk_conditions(df), "Maximum Drawdown Risk")

    def test_severe_drawdown_is_bearish(self):
        # Peak 100, drops to 60 → -40% drawdown
        prices = [100.0] * 10 + [60.0] * 10
        sig = self._dd_signal(_make_df(close=prices))
        assert sig.direction == SignalDirection.BEARISH

    def test_severe_drawdown_is_strong(self):
        prices = [100.0] * 10 + [60.0] * 10
        sig = self._dd_signal(_make_df(close=prices))
        assert sig.strength == SignalStrength.STRONG

    def test_severe_drawdown_negative_impact(self):
        prices = [100.0] * 10 + [60.0] * 10
        sig = self._dd_signal(_make_df(close=prices))
        assert sig.score_impact < 0

    def test_moderate_drawdown_is_neutral(self):
        # Peak 100, drops to 75 → -25% drawdown (between -35% and -15%)
        prices = [100.0] * 10 + [75.0] * 10
        sig = self._dd_signal(_make_df(close=prices))
        assert sig.direction == SignalDirection.NEUTRAL

    def test_mild_drawdown_is_bullish(self):
        # Peak 100, drops to 92 → -8% drawdown (> -15%)
        prices = [100.0] * 10 + [92.0] * 10
        sig = self._dd_signal(_make_df(close=prices))
        assert sig.direction == SignalDirection.BULLISH

    def test_flat_prices_are_bullish(self):
        sig = self._dd_signal(_flat())
        assert sig.direction == SignalDirection.BULLISH

    def test_single_row_returns_neutral_low_confidence(self):
        sig = self._dd_signal(_make_df(n=1))
        assert sig.direction == SignalDirection.NEUTRAL
        assert sig.confidence == pytest.approx(0.30)

    def test_signal_has_numeric_value_when_computable(self):
        sig = self._dd_signal(_flat())
        assert sig.value is not None

    def test_drawdown_value_is_nonpositive(self):
        prices = [100.0] * 5 + [90.0] * 5
        sig = self._dd_signal(_make_df(close=prices))
        assert sig.value <= 0


# ---------------------------------------------------------------------------
# Recent trend signal
# ---------------------------------------------------------------------------

class TestRecentTrendSignal:
    def _trend_signal(self, df: pd.DataFrame) -> Signal:
        return _signal_by_name(analyze_risk_conditions(df), "Recent Trend Risk")

    def test_short_history_under_31_rows_is_neutral(self):
        sig = self._trend_signal(_make_df(n=30))
        assert sig.direction == SignalDirection.NEUTRAL

    def test_short_history_has_low_confidence(self):
        sig = self._trend_signal(_make_df(n=30))
        assert sig.confidence == pytest.approx(0.30)

    def test_short_history_value_is_none(self):
        sig = self._trend_signal(_make_df(n=15))
        assert sig.value is None

    def test_negative_30d_return_is_bearish(self):
        # Start at 100, holds there for 31 days, then drop to 85 → -15% return
        prices = [100.0] * 31 + [85.0] * 29
        sig = self._trend_signal(_make_df(close=prices))
        assert sig.direction == SignalDirection.BEARISH

    def test_positive_30d_return_is_bullish(self):
        # Start at 100, holds there for 31 days, then rise to 115 → +15% return
        prices = [100.0] * 31 + [115.0] * 29
        sig = self._trend_signal(_make_df(close=prices))
        assert sig.direction == SignalDirection.BULLISH

    def test_flat_return_is_neutral(self):
        sig = self._trend_signal(_flat(n=60))
        assert sig.direction == SignalDirection.NEUTRAL

    def test_exactly_31_rows_does_not_use_insufficient_path(self):
        # 31 rows is enough; signal should not be the insufficient-data sentinel
        sig = self._trend_signal(_flat(n=31))
        assert sig.confidence != pytest.approx(0.30)

    def test_recent_trend_has_numeric_value_with_enough_data(self):
        sig = self._trend_signal(_flat(n=60))
        assert sig.value is not None


# ---------------------------------------------------------------------------
# Liquidity signal
# ---------------------------------------------------------------------------

class TestLiquiditySignal:
    def _liq_signal(self, df: pd.DataFrame) -> Signal:
        return _signal_by_name(analyze_risk_conditions(df), "Liquidity Risk")

    def test_low_volume_is_bearish(self):
        sig = self._liq_signal(_make_df(volume=100_000.0))
        assert sig.direction == SignalDirection.BEARISH

    def test_low_volume_negative_impact(self):
        sig = self._liq_signal(_make_df(volume=100_000.0))
        assert sig.score_impact < 0

    def test_high_volume_is_bullish(self):
        sig = self._liq_signal(_make_df(volume=2_000_000.0))
        assert sig.direction == SignalDirection.BULLISH

    def test_high_volume_positive_impact(self):
        sig = self._liq_signal(_make_df(volume=2_000_000.0))
        assert sig.score_impact > 0

    def test_moderate_volume_is_neutral(self):
        sig = self._liq_signal(_make_df(volume=700_000.0))
        assert sig.direction == SignalDirection.NEUTRAL

    def test_all_nan_volume_returns_neutral_low_confidence(self):
        df = pd.DataFrame({"close": [100.0] * 10, "volume": [float("nan")] * 10})
        sig = self._liq_signal(df)
        assert sig.direction == SignalDirection.NEUTRAL
        assert sig.confidence == pytest.approx(0.30)

    def test_average_volume_boundary_at_500k_is_neutral(self):
        sig = self._liq_signal(_make_df(volume=500_000.0))
        assert sig.direction == SignalDirection.NEUTRAL

    def test_average_volume_boundary_at_1m_is_bullish(self):
        sig = self._liq_signal(_make_df(volume=1_000_000.0))
        assert sig.direction == SignalDirection.BULLISH

    def test_signal_value_is_numeric(self):
        sig = self._liq_signal(_make_df(volume=1_500_000.0))
        assert isinstance(sig.value, (int, float))


# ---------------------------------------------------------------------------
# Beta signal
# ---------------------------------------------------------------------------

class TestBetaSignal:
    def _beta_signal(self, beta: float) -> Signal:
        result = analyze_risk_conditions(_flat(), beta=beta)
        return _signal_by_name(result, "Beta Risk")

    def test_high_beta_is_bearish(self):
        assert self._beta_signal(2.0).direction == SignalDirection.BEARISH

    def test_high_beta_negative_impact(self):
        assert self._beta_signal(2.0).score_impact < 0

    def test_normal_beta_is_neutral(self):
        assert self._beta_signal(1.2).direction == SignalDirection.NEUTRAL

    def test_low_beta_is_bullish(self):
        assert self._beta_signal(0.5).direction == SignalDirection.BULLISH

    def test_low_beta_positive_impact(self):
        assert self._beta_signal(0.5).score_impact > 0

    def test_boundary_beta_1_5_is_bearish(self):
        assert self._beta_signal(1.5).direction == SignalDirection.BEARISH

    def test_boundary_beta_0_8_is_neutral(self):
        assert self._beta_signal(0.8).direction == SignalDirection.NEUTRAL

    def test_beta_value_stored_in_signal(self):
        sig = self._beta_signal(1.2)
        assert sig.value == pytest.approx(1.2)

    def test_negative_beta_is_bullish(self):
        # Negative beta means inverse market correlation — treated as low-sensitivity
        assert self._beta_signal(-0.3).direction == SignalDirection.BULLISH


# ---------------------------------------------------------------------------
# NaN handling
# ---------------------------------------------------------------------------

class TestNaNHandling:
    def test_some_nan_close_does_not_crash(self):
        close = [float("nan")] * 5 + [100.0] * 55
        df = _make_df(close=close)
        result = analyze_risk_conditions(df)
        assert isinstance(result, list)

    def test_some_nan_volume_does_not_crash(self):
        volume = [float("nan")] * 5 + [1_500_000.0] * 55
        df = _make_df(volume=volume)
        result = analyze_risk_conditions(df)
        assert isinstance(result, list)

    def test_all_nan_close_does_not_crash(self):
        df = pd.DataFrame({"close": [float("nan")] * 10, "volume": [1_000_000.0] * 10})
        result = analyze_risk_conditions(df)
        assert isinstance(result, list)
        assert len(result) == 4

    def test_all_nan_close_produces_neutral_signals(self):
        df = pd.DataFrame({"close": [float("nan")] * 10, "volume": [1_000_000.0] * 10})
        result = analyze_risk_conditions(df)
        close_signals = [s for s in result if s.name in {"Volatility Risk", "Maximum Drawdown Risk", "Recent Trend Risk"}]
        assert all(s.direction == SignalDirection.NEUTRAL for s in close_signals)


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------

class TestImmutability:
    def test_input_dataframe_not_mutated(self):
        df = _flat()
        original_columns = list(df.columns)
        original_shape   = df.shape
        analyze_risk_conditions(df, beta=1.2)
        assert list(df.columns) == original_columns
        assert df.shape == original_shape

    def test_input_dataframe_values_not_changed(self):
        df = _flat(price=100.0)
        analyze_risk_conditions(df)
        assert all(v == 100.0 for v in df["close"])


# ---------------------------------------------------------------------------
# Short price history
# ---------------------------------------------------------------------------

class TestShortHistory:
    def test_one_row_does_not_crash(self):
        result = analyze_risk_conditions(_make_df(n=1))
        assert len(result) == 4

    def test_two_rows_does_not_crash(self):
        result = analyze_risk_conditions(_make_df(n=2))
        assert len(result) == 4

    def test_thirty_rows_does_not_crash(self):
        result = analyze_risk_conditions(_make_df(n=30))
        assert len(result) == 4

    def test_recent_trend_neutral_for_short_history(self):
        sig = _signal_by_name(analyze_risk_conditions(_make_df(n=20)), "Recent Trend Risk")
        assert sig.direction == SignalDirection.NEUTRAL
        assert sig.confidence == pytest.approx(0.30)

    def test_volatility_neutral_for_single_row(self):
        sig = _signal_by_name(analyze_risk_conditions(_make_df(n=1)), "Volatility Risk")
        assert sig.direction == SignalDirection.NEUTRAL

    def test_max_drawdown_neutral_for_single_row(self):
        sig = _signal_by_name(analyze_risk_conditions(_make_df(n=1)), "Maximum Drawdown Risk")
        assert sig.direction == SignalDirection.NEUTRAL
