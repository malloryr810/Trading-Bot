"""
Unit tests for app/models/signal.py.
"""

import pytest
from pydantic import ValidationError

from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal(**overrides) -> Signal:
    defaults = dict(
        name="RSI Overbought",
        category=SignalCategory.TECHNICAL,
        direction=SignalDirection.BEARISH,
        strength=SignalStrength.MODERATE,
        description="RSI is above 70, indicating overbought conditions.",
    )
    defaults.update(overrides)
    return Signal(**defaults)


# ---------------------------------------------------------------------------
# Enum correctness
# ---------------------------------------------------------------------------

class TestEnums:
    def test_signal_category_values(self):
        assert SignalCategory.TECHNICAL == "technical"
        assert SignalCategory.FUNDAMENTAL == "fundamental"
        assert SignalCategory.NEWS == "news"
        assert SignalCategory.RISK == "risk"

    def test_signal_direction_values(self):
        assert SignalDirection.BULLISH == "bullish"
        assert SignalDirection.BEARISH == "bearish"
        assert SignalDirection.NEUTRAL == "neutral"

    def test_signal_strength_values(self):
        assert SignalStrength.WEAK == "weak"
        assert SignalStrength.MODERATE == "moderate"
        assert SignalStrength.STRONG == "strong"


# ---------------------------------------------------------------------------
# Valid construction
# ---------------------------------------------------------------------------

class TestValidSignal:
    def test_valid_technical_signal(self):
        signal = _make_signal()
        assert signal.name == "RSI Overbought"
        assert signal.category == SignalCategory.TECHNICAL
        assert signal.direction == SignalDirection.BEARISH
        assert signal.strength == SignalStrength.MODERATE

    def test_valid_fundamental_signal(self):
        signal = _make_signal(
            name="Low P/E Ratio",
            category=SignalCategory.FUNDAMENTAL,
            direction=SignalDirection.BULLISH,
            strength=SignalStrength.STRONG,
            description="P/E is below the sector median.",
            value=12.5,
            score_impact=0.4,
            confidence=0.8,
        )
        assert signal.category == SignalCategory.FUNDAMENTAL
        assert signal.value == 12.5
        assert signal.score_impact == 0.4
        assert signal.confidence == 0.8

    def test_default_values(self):
        signal = _make_signal()
        assert signal.value is None
        assert signal.score_impact == 0.0
        assert signal.confidence == 0.5
        assert signal.source is None
        assert signal.timestamp is None
        assert signal.metadata == {}

    def test_score_impact_boundary_values(self):
        _make_signal(score_impact=-1.0)
        _make_signal(score_impact=1.0)
        _make_signal(score_impact=0.0)

    def test_confidence_boundary_values(self):
        _make_signal(confidence=0.0)
        _make_signal(confidence=1.0)

    def test_metadata_accepts_arbitrary_keys(self):
        signal = _make_signal(metadata={"window": 14, "threshold": 70})
        assert signal.metadata["window"] == 14

    def test_optional_source_and_timestamp(self):
        from datetime import datetime, timezone
        ts = datetime(2024, 1, 15, tzinfo=timezone.utc)
        signal = _make_signal(source="yfinance", timestamp=ts)
        assert signal.source == "yfinance"
        assert signal.timestamp == ts


# ---------------------------------------------------------------------------
# Name validation
# ---------------------------------------------------------------------------

class TestNameValidation:
    def test_empty_name_raises(self):
        with pytest.raises(ValidationError, match="name"):
            _make_signal(name="")

    def test_whitespace_name_raises(self):
        with pytest.raises(ValidationError, match="name"):
            _make_signal(name="   ")


# ---------------------------------------------------------------------------
# Description validation
# ---------------------------------------------------------------------------

class TestDescriptionValidation:
    def test_empty_description_raises(self):
        with pytest.raises(ValidationError, match="description"):
            _make_signal(description="")

    def test_whitespace_description_raises(self):
        with pytest.raises(ValidationError, match="description"):
            _make_signal(description="   ")


# ---------------------------------------------------------------------------
# score_impact validation
# ---------------------------------------------------------------------------

class TestScoreImpactValidation:
    def test_below_minus_one_raises(self):
        with pytest.raises(ValidationError):
            _make_signal(score_impact=-1.01)

    def test_above_one_raises(self):
        with pytest.raises(ValidationError):
            _make_signal(score_impact=1.01)


# ---------------------------------------------------------------------------
# confidence validation
# ---------------------------------------------------------------------------

class TestConfidenceValidation:
    def test_below_zero_raises(self):
        with pytest.raises(ValidationError):
            _make_signal(confidence=-0.01)

    def test_above_one_raises(self):
        with pytest.raises(ValidationError):
            _make_signal(confidence=1.01)


# ---------------------------------------------------------------------------
# Metadata immutability
# ---------------------------------------------------------------------------

class TestMetadataMutability:
    def test_metadata_not_shared_between_instances(self):
        a = _make_signal()
        b = _make_signal()
        a.metadata["key"] = "value"
        assert "key" not in b.metadata


# ---------------------------------------------------------------------------
# Direction helper properties
# ---------------------------------------------------------------------------

class TestDirectionProperties:
    def test_is_bullish(self):
        signal = _make_signal(direction=SignalDirection.BULLISH)
        assert signal.is_bullish is True
        assert signal.is_bearish is False
        assert signal.is_neutral is False

    def test_is_bearish(self):
        signal = _make_signal(direction=SignalDirection.BEARISH)
        assert signal.is_bearish is True
        assert signal.is_bullish is False
        assert signal.is_neutral is False

    def test_is_neutral(self):
        signal = _make_signal(direction=SignalDirection.NEUTRAL)
        assert signal.is_neutral is True
        assert signal.is_bullish is False
        assert signal.is_bearish is False
