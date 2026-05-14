"""
Unit tests for app/models/rating.py.
"""

import pytest
from pydantic import ValidationError

from app.models.rating import ConfidenceLevel, Rating, RatingCategory
from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rating(**overrides) -> Rating:
    defaults = dict(
        ticker="AAPL",
        final_category=RatingCategory.BUY_CANDIDATE,
        score=72.0,
        confidence=ConfidenceLevel.MEDIUM,
        explanation="Strong technical trend with moderate fundamentals.",
    )
    defaults.update(overrides)
    return Rating(**defaults)


def _make_signal() -> Signal:
    return Signal(
        name="Trend",
        category=SignalCategory.TECHNICAL,
        direction=SignalDirection.BULLISH,
        strength=SignalStrength.MODERATE,
        description="Price is above SMA 20 and SMA 50.",
        score_impact=0.25,
        confidence=0.70,
    )


# ---------------------------------------------------------------------------
# Enum correctness
# ---------------------------------------------------------------------------

class TestEnums:
    def test_rating_category_values(self):
        assert RatingCategory.STRONG_BUY_CANDIDATE == "Strong Buy Candidate"
        assert RatingCategory.BUY_CANDIDATE == "Buy Candidate"
        assert RatingCategory.WATCHLIST == "Watchlist"
        assert RatingCategory.HOLD == "Hold"
        assert RatingCategory.AVOID == "Avoid"
        assert RatingCategory.SELL_EXIT_WARNING == "Sell / Exit Warning"

    def test_confidence_level_values(self):
        assert ConfidenceLevel.LOW == "low"
        assert ConfidenceLevel.MEDIUM == "medium"
        assert ConfidenceLevel.HIGH == "high"


# ---------------------------------------------------------------------------
# Valid construction
# ---------------------------------------------------------------------------

class TestValidRating:
    def test_valid_rating_created(self):
        rating = _make_rating()
        assert rating.ticker == "AAPL"
        assert rating.final_category == RatingCategory.BUY_CANDIDATE
        assert rating.score == 72.0
        assert rating.confidence == ConfidenceLevel.MEDIUM

    def test_default_sub_scores_are_zero(self):
        rating = _make_rating()
        assert rating.technical_score == 0.0
        assert rating.fundamental_score == 0.0
        assert rating.news_score == 0.0
        assert rating.risk_score == 0.0

    def test_default_optional_fields_are_none(self):
        rating = _make_rating()
        assert rating.technical_summary is None
        assert rating.fundamental_summary is None
        assert rating.news_summary is None
        assert rating.risk_summary is None
        assert rating.buy_trigger is None
        assert rating.sell_or_avoid_trigger is None
        assert rating.data_timestamp is None

    def test_default_list_fields_are_empty(self):
        rating = _make_rating()
        assert rating.key_positive_factors == []
        assert rating.key_risks == []
        assert rating.data_sources_used == []
        assert rating.signals_used == []

    def test_score_boundary_values_accepted(self):
        _make_rating(score=0.0)
        _make_rating(score=100.0)

    def test_sub_score_boundary_values_accepted(self):
        _make_rating(technical_score=0.0)
        _make_rating(technical_score=100.0)
        _make_rating(fundamental_score=0.0)
        _make_rating(fundamental_score=100.0)

    def test_signals_used_accepts_signal_list(self):
        signals = [_make_signal()]
        rating = _make_rating(signals_used=signals)
        assert len(rating.signals_used) == 1
        assert rating.signals_used[0].name == "Trend"

    def test_full_rating_with_all_fields(self):
        from datetime import datetime, timezone
        ts = datetime(2024, 6, 1, tzinfo=timezone.utc)
        rating = _make_rating(
            technical_score=80.0,
            fundamental_score=60.0,
            news_score=55.0,
            risk_score=70.0,
            technical_summary="Strong uptrend.",
            key_positive_factors=["Above SMA 200", "RSI neutral"],
            key_risks=["High P/E ratio"],
            buy_trigger="Break above 155 on volume.",
            data_timestamp=ts,
            data_sources_used=["yfinance"],
            signals_used=[_make_signal()],
        )
        assert rating.technical_score == 80.0
        assert rating.data_timestamp == ts
        assert "Above SMA 200" in rating.key_positive_factors


# ---------------------------------------------------------------------------
# Ticker normalization
# ---------------------------------------------------------------------------

class TestTickerNormalization:
    def test_lowercase_ticker_uppercased(self):
        rating = _make_rating(ticker="aapl")
        assert rating.ticker == "AAPL"

    def test_whitespace_stripped_from_ticker(self):
        rating = _make_rating(ticker="  MSFT  ")
        assert rating.ticker == "MSFT"

    def test_mixed_case_and_whitespace_normalized(self):
        rating = _make_rating(ticker="  tsla  ")
        assert rating.ticker == "TSLA"

    def test_empty_ticker_raises(self):
        with pytest.raises(ValidationError, match="ticker"):
            _make_rating(ticker="")

    def test_whitespace_only_ticker_raises(self):
        with pytest.raises(ValidationError, match="ticker"):
            _make_rating(ticker="   ")


# ---------------------------------------------------------------------------
# Explanation validation
# ---------------------------------------------------------------------------

class TestExplanationValidation:
    def test_empty_explanation_raises(self):
        with pytest.raises(ValidationError, match="explanation"):
            _make_rating(explanation="")

    def test_whitespace_explanation_raises(self):
        with pytest.raises(ValidationError, match="explanation"):
            _make_rating(explanation="   ")


# ---------------------------------------------------------------------------
# Score validation
# ---------------------------------------------------------------------------

class TestScoreValidation:
    def test_score_below_zero_raises(self):
        with pytest.raises(ValidationError):
            _make_rating(score=-0.01)

    def test_score_above_100_raises(self):
        with pytest.raises(ValidationError):
            _make_rating(score=100.01)

    def test_technical_score_below_zero_raises(self):
        with pytest.raises(ValidationError):
            _make_rating(technical_score=-1.0)

    def test_technical_score_above_100_raises(self):
        with pytest.raises(ValidationError):
            _make_rating(technical_score=101.0)

    def test_fundamental_score_below_zero_raises(self):
        with pytest.raises(ValidationError):
            _make_rating(fundamental_score=-1.0)

    def test_news_score_above_100_raises(self):
        with pytest.raises(ValidationError):
            _make_rating(news_score=101.0)

    def test_risk_score_below_zero_raises(self):
        with pytest.raises(ValidationError):
            _make_rating(risk_score=-1.0)


# ---------------------------------------------------------------------------
# Mutable default safety
# ---------------------------------------------------------------------------

class TestMutableDefaults:
    def test_key_positive_factors_not_shared(self):
        a = _make_rating()
        b = _make_rating()
        a.key_positive_factors.append("factor")
        assert "factor" not in b.key_positive_factors

    def test_key_risks_not_shared(self):
        a = _make_rating()
        b = _make_rating()
        a.key_risks.append("risk")
        assert "risk" not in b.key_risks

    def test_metadata_not_shared(self):
        a = _make_rating()
        b = _make_rating()
        a.metadata["key"] = "value"
        assert "key" not in b.metadata

    def test_signals_used_not_shared(self):
        a = _make_rating()
        b = _make_rating()
        a.signals_used.append(_make_signal())
        assert len(b.signals_used) == 0


# ---------------------------------------------------------------------------
# Convenience properties
# ---------------------------------------------------------------------------

class TestConvenienceProperties:
    def test_is_positive_for_strong_buy(self):
        rating = _make_rating(final_category=RatingCategory.STRONG_BUY_CANDIDATE)
        assert rating.is_positive_rating is True
        assert rating.is_negative_rating is False
        assert rating.is_neutral_rating is False

    def test_is_positive_for_buy(self):
        rating = _make_rating(final_category=RatingCategory.BUY_CANDIDATE)
        assert rating.is_positive_rating is True

    def test_is_negative_for_avoid(self):
        rating = _make_rating(final_category=RatingCategory.AVOID)
        assert rating.is_negative_rating is True
        assert rating.is_positive_rating is False
        assert rating.is_neutral_rating is False

    def test_is_negative_for_sell_exit_warning(self):
        rating = _make_rating(final_category=RatingCategory.SELL_EXIT_WARNING)
        assert rating.is_negative_rating is True

    def test_is_neutral_for_watchlist(self):
        rating = _make_rating(final_category=RatingCategory.WATCHLIST)
        assert rating.is_neutral_rating is True
        assert rating.is_positive_rating is False
        assert rating.is_negative_rating is False

    def test_is_neutral_for_hold(self):
        rating = _make_rating(final_category=RatingCategory.HOLD)
        assert rating.is_neutral_rating is True


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_model_dump_includes_enum_values(self):
        rating = _make_rating()
        data = rating.model_dump()
        assert data["final_category"] == "Buy Candidate"
        assert data["confidence"] == "medium"

    def test_model_dump_with_nested_signals(self):
        rating = _make_rating(signals_used=[_make_signal()])
        data = rating.model_dump()
        assert len(data["signals_used"]) == 1
        assert data["signals_used"][0]["name"] == "Trend"

    def test_model_json_round_trip(self):
        rating = _make_rating(signals_used=[_make_signal()])
        json_str = rating.model_dump_json()
        restored = Rating.model_validate_json(json_str)
        assert restored.ticker == rating.ticker
        assert restored.final_category == rating.final_category
        assert len(restored.signals_used) == 1
