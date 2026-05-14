"""
Unit tests for build_technical_signals() in app/analysis/technicals.py.

Tests use deterministic dicts built inline — no network calls.
"""

import pytest

from app.analysis.technicals import TechnicalAnalysisError, build_technical_signals
from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_summary(**overrides) -> dict:
    """Return a valid bullish technical summary with optional field overrides."""
    defaults: dict = {
        "latest_close": 150.0,
        "sma_20": 145.0,
        "sma_50": 140.0,
        "sma_200": 130.0,
        "rsi_14": 55.0,
        "macd": 1.5,
        "macd_signal": 1.0,
        "volume": 1_200_000.0,
        "volume_sma_20": 1_000_000.0,
        "trend": "bullish",
        "price_above_sma_20": True,
        "price_above_sma_50": True,
        "price_above_sma_200": True,
        "rsi_condition": "neutral",
        "macd_condition": "bullish",
    }
    defaults.update(overrides)
    return defaults


def _signal_by_name(signals: list[Signal], name: str) -> Signal:
    for s in signals:
        if s.name == name:
            return s
    raise KeyError(f"No signal named '{name}' in result.")


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

class TestStructure:
    def test_returns_list(self):
        result = build_technical_signals(_make_summary())
        assert isinstance(result, list)

    def test_returns_exactly_7_signals(self):
        result = build_technical_signals(_make_summary())
        assert len(result) == 7

    def test_every_item_is_a_signal(self):
        result = build_technical_signals(_make_summary())
        assert all(isinstance(s, Signal) for s in result)

    def test_every_signal_is_technical_category(self):
        result = build_technical_signals(_make_summary())
        assert all(s.category == SignalCategory.TECHNICAL for s in result)


# ---------------------------------------------------------------------------
# Trend signal
# ---------------------------------------------------------------------------

class TestTrendSignal:
    def test_bullish_trend(self):
        signals = build_technical_signals(_make_summary(trend="bullish"))
        s = _signal_by_name(signals, "Trend")
        assert s.direction == SignalDirection.BULLISH
        assert s.score_impact > 0

    def test_bearish_trend(self):
        signals = build_technical_signals(_make_summary(trend="bearish"))
        s = _signal_by_name(signals, "Trend")
        assert s.direction == SignalDirection.BEARISH
        assert s.score_impact < 0

    def test_mixed_trend(self):
        signals = build_technical_signals(_make_summary(trend="mixed"))
        s = _signal_by_name(signals, "Trend")
        assert s.direction == SignalDirection.NEUTRAL
        assert s.score_impact == 0.0

    def test_unknown_trend_treated_as_mixed(self):
        signals = build_technical_signals(_make_summary(trend="unknown"))
        s = _signal_by_name(signals, "Trend")
        assert s.direction == SignalDirection.NEUTRAL


# ---------------------------------------------------------------------------
# RSI signal
# ---------------------------------------------------------------------------

class TestRsiSignal:
    def test_overbought(self):
        signals = build_technical_signals(_make_summary(rsi_condition="overbought"))
        s = _signal_by_name(signals, "RSI Condition")
        assert s.direction == SignalDirection.BEARISH
        assert s.score_impact < 0

    def test_oversold(self):
        signals = build_technical_signals(_make_summary(rsi_condition="oversold"))
        s = _signal_by_name(signals, "RSI Condition")
        assert s.direction == SignalDirection.BULLISH
        assert s.score_impact > 0

    def test_neutral(self):
        signals = build_technical_signals(_make_summary(rsi_condition="neutral"))
        s = _signal_by_name(signals, "RSI Condition")
        assert s.direction == SignalDirection.NEUTRAL
        assert s.score_impact == 0.0


# ---------------------------------------------------------------------------
# MACD signal
# ---------------------------------------------------------------------------

class TestMacdSignal:
    def test_bullish(self):
        signals = build_technical_signals(_make_summary(macd_condition="bullish"))
        s = _signal_by_name(signals, "MACD Condition")
        assert s.direction == SignalDirection.BULLISH
        assert s.score_impact > 0

    def test_bearish(self):
        signals = build_technical_signals(_make_summary(macd_condition="bearish"))
        s = _signal_by_name(signals, "MACD Condition")
        assert s.direction == SignalDirection.BEARISH
        assert s.score_impact < 0

    def test_neutral(self):
        signals = build_technical_signals(_make_summary(macd_condition="neutral"))
        s = _signal_by_name(signals, "MACD Condition")
        assert s.direction == SignalDirection.NEUTRAL
        assert s.score_impact == 0.0


# ---------------------------------------------------------------------------
# Price vs SMA signals
# ---------------------------------------------------------------------------

class TestPriceVsSmaSignals:
    @pytest.mark.parametrize("window", [20, 50, 200])
    def test_above_sma_is_bullish(self, window: int):
        signals = build_technical_signals(
            _make_summary(**{f"price_above_sma_{window}": True})
        )
        s = _signal_by_name(signals, f"Price vs SMA {window}")
        assert s.direction == SignalDirection.BULLISH
        assert s.score_impact > 0

    @pytest.mark.parametrize("window", [20, 50, 200])
    def test_below_sma_is_bearish(self, window: int):
        signals = build_technical_signals(
            _make_summary(**{f"price_above_sma_{window}": False})
        )
        s = _signal_by_name(signals, f"Price vs SMA {window}")
        assert s.direction == SignalDirection.BEARISH
        assert s.score_impact < 0

    @pytest.mark.parametrize("window", [20, 50, 200])
    def test_none_sma_is_neutral_with_low_confidence(self, window: int):
        signals = build_technical_signals(
            _make_summary(**{f"price_above_sma_{window}": None, f"sma_{window}": None})
        )
        s = _signal_by_name(signals, f"Price vs SMA {window}")
        assert s.direction == SignalDirection.NEUTRAL
        assert s.score_impact == 0.0
        assert s.confidence == pytest.approx(0.30)

    def test_sma_200_above_is_strong(self):
        signals = build_technical_signals(_make_summary(price_above_sma_200=True))
        s = _signal_by_name(signals, "Price vs SMA 200")
        assert s.strength == SignalStrength.STRONG

    def test_sma_20_above_is_weak(self):
        signals = build_technical_signals(_make_summary(price_above_sma_20=True))
        s = _signal_by_name(signals, "Price vs SMA 20")
        assert s.strength == SignalStrength.WEAK


# ---------------------------------------------------------------------------
# Volume signal
# ---------------------------------------------------------------------------

class TestVolumeSignal:
    def test_volume_above_sma_is_bullish(self):
        signals = build_technical_signals(
            _make_summary(volume=2_000_000.0, volume_sma_20=1_000_000.0)
        )
        s = _signal_by_name(signals, "Volume vs Volume SMA 20")
        assert s.direction == SignalDirection.BULLISH
        assert s.score_impact == pytest.approx(0.05)

    def test_volume_below_sma_is_neutral(self):
        signals = build_technical_signals(
            _make_summary(volume=500_000.0, volume_sma_20=1_000_000.0)
        )
        s = _signal_by_name(signals, "Volume vs Volume SMA 20")
        assert s.direction == SignalDirection.NEUTRAL
        assert s.score_impact == 0.0

    def test_volume_equal_to_sma_is_neutral(self):
        signals = build_technical_signals(
            _make_summary(volume=1_000_000.0, volume_sma_20=1_000_000.0)
        )
        s = _signal_by_name(signals, "Volume vs Volume SMA 20")
        assert s.direction == SignalDirection.NEUTRAL

    def test_volume_sma_none_is_neutral_low_confidence(self):
        signals = build_technical_signals(
            _make_summary(volume_sma_20=None)
        )
        s = _signal_by_name(signals, "Volume vs Volume SMA 20")
        assert s.direction == SignalDirection.NEUTRAL
        assert s.confidence == pytest.approx(0.30)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_non_dict_raises(self):
        with pytest.raises(TechnicalAnalysisError):
            build_technical_signals("not a dict")  # type: ignore[arg-type]

    def test_none_raises(self):
        with pytest.raises(TechnicalAnalysisError):
            build_technical_signals(None)  # type: ignore[arg-type]

    def test_empty_dict_raises(self):
        with pytest.raises(TechnicalAnalysisError):
            build_technical_signals({})

    def test_missing_required_key_raises(self):
        summary = _make_summary()
        del summary["trend"]
        with pytest.raises(TechnicalAnalysisError, match="missing required keys"):
            build_technical_signals(summary)

    def test_input_not_mutated(self):
        summary = _make_summary()
        original_keys = set(summary.keys())
        build_technical_signals(summary)
        assert set(summary.keys()) == original_keys
