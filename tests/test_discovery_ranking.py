"""
Tests for app/services/discovery_ranking.py.

Ranking is pure: every test builds Rating objects locally and asserts the
resulting order. No network calls, no analysis pipeline, no database.
"""

from __future__ import annotations

import pytest

from app.models.discovery import DiscoveryMode
from app.models.rating import ConfidenceLevel, Rating, RatingCategory
from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength
from app.services.discovery_ranking import (
    list_mode_info,
    match_reason,
    rank_ratings,
    valuation_lean,
)


def _valuation_signal(score_impact: float, description: str = "Valuation signal.") -> Signal:
    return Signal(
        name="Valuation",
        category=SignalCategory.FUNDAMENTAL,
        direction=(
            SignalDirection.BULLISH if score_impact > 0 else SignalDirection.BEARISH
        ),
        strength=SignalStrength.MODERATE,
        description=description,
        score_impact=score_impact,
    )


def _rating(
    ticker: str,
    *,
    score: float = 60.0,
    technical: float = 50.0,
    fundamental: float = 50.0,
    news: float = 50.0,
    risk: float = 50.0,
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
    category: RatingCategory = RatingCategory.WATCHLIST,
    signals: list[Signal] | None = None,
) -> Rating:
    return Rating(
        ticker=ticker,
        final_category=category,
        score=score,
        confidence=confidence,
        explanation=f"Rating for {ticker}.",
        technical_score=technical,
        fundamental_score=fundamental,
        news_score=news,
        risk_score=risk,
        signals_used=signals or [],
    )


def _order(mode: DiscoveryMode, ratings: list[Rating]) -> list[str]:
    return [rating.ticker for rating in rank_ratings(mode, ratings)]


# ---------------------------------------------------------------------------
# Mode metadata
# ---------------------------------------------------------------------------


class TestModeInfo:
    def test_every_mode_is_described(self):
        assert {info.key for info in list_mode_info()} == set(DiscoveryMode)

    def test_descriptions_are_populated(self):
        for info in list_mode_info():
            assert info.label
            assert info.description
            assert info.ranking


# ---------------------------------------------------------------------------
# Per-mode ranking
# ---------------------------------------------------------------------------


class TestOverallRanking:
    def test_sorts_by_score_descending(self):
        ratings = [_rating("A", score=40.0), _rating("B", score=80.0), _rating("C", score=60.0)]
        assert _order(DiscoveryMode.OVERALL, ratings) == ["B", "C", "A"]

    def test_breaks_score_ties_by_confidence(self):
        ratings = [
            _rating("A", score=70.0, confidence=ConfidenceLevel.LOW),
            _rating("B", score=70.0, confidence=ConfidenceLevel.HIGH),
        ]
        assert _order(DiscoveryMode.OVERALL, ratings) == ["B", "A"]

    def test_breaks_remaining_ties_by_ticker(self):
        ratings = [_rating("Z", score=70.0), _rating("A", score=70.0)]
        assert _order(DiscoveryMode.OVERALL, ratings) == ["A", "Z"]

    def test_does_not_mutate_input(self):
        ratings = [_rating("A", score=10.0), _rating("B", score=90.0)]
        rank_ratings(DiscoveryMode.OVERALL, ratings)
        assert [r.ticker for r in ratings] == ["A", "B"]


class TestMomentumRanking:
    def test_prioritizes_technical_sub_score(self):
        ratings = [
            _rating("A", score=90.0, technical=30.0),
            _rating("B", score=50.0, technical=88.0),
        ]
        assert _order(DiscoveryMode.MOMENTUM, ratings) == ["B", "A"]

    def test_falls_back_to_composite_score(self):
        ratings = [
            _rating("A", score=55.0, technical=70.0),
            _rating("B", score=75.0, technical=70.0),
        ]
        assert _order(DiscoveryMode.MOMENTUM, ratings) == ["B", "A"]


class TestQualityRanking:
    def test_prioritizes_fundamental_sub_score(self):
        ratings = [
            _rating("A", score=88.0, fundamental=40.0),
            _rating("B", score=52.0, fundamental=85.0),
        ]
        assert _order(DiscoveryMode.QUALITY, ratings) == ["B", "A"]

    def test_falls_back_to_composite_score(self):
        ratings = [
            _rating("A", score=51.0, fundamental=60.0),
            _rating("B", score=69.0, fundamental=60.0),
        ]
        assert _order(DiscoveryMode.QUALITY, ratings) == ["B", "A"]


class TestValueRanking:
    def test_prioritizes_favorable_valuation_signal(self):
        ratings = [
            _rating("A", score=80.0, fundamental=80.0, signals=[_valuation_signal(-0.2)]),
            _rating("B", score=55.0, fundamental=50.0, signals=[_valuation_signal(0.3)]),
        ]
        assert _order(DiscoveryMode.VALUE, ratings) == ["B", "A"]

    def test_missing_valuation_signal_ranks_between_favorable_and_unfavorable(self):
        ratings = [
            _rating("CHEAP", signals=[_valuation_signal(0.25)]),
            _rating("NONE"),
            _rating("RICH", signals=[_valuation_signal(-0.25)]),
        ]
        assert _order(DiscoveryMode.VALUE, ratings) == ["CHEAP", "NONE", "RICH"]

    def test_falls_back_to_fundamental_sub_score(self):
        ratings = [
            _rating("A", fundamental=40.0, signals=[_valuation_signal(0.2)]),
            _rating("B", fundamental=75.0, signals=[_valuation_signal(0.2)]),
        ]
        assert _order(DiscoveryMode.VALUE, ratings) == ["B", "A"]

    def test_valuation_lean_reads_the_existing_signal(self):
        assert valuation_lean(_rating("A", signals=[_valuation_signal(0.4)])) == 0.4

    def test_valuation_lean_defaults_to_zero(self):
        assert valuation_lean(_rating("A")) == 0.0

    def test_valuation_lean_ignores_non_fundamental_signals(self):
        technical_valuation = Signal(
            name="Valuation",
            category=SignalCategory.TECHNICAL,
            direction=SignalDirection.BULLISH,
            strength=SignalStrength.MODERATE,
            description="Not a fundamental valuation signal.",
            score_impact=0.9,
        )
        assert valuation_lean(_rating("A", signals=[technical_valuation])) == 0.0


class TestDefensiveRanking:
    def test_prioritizes_favorable_risk_sub_score(self):
        ratings = [
            _rating("A", score=85.0, risk=30.0),
            _rating("B", score=60.0, risk=82.0),
        ]
        assert _order(DiscoveryMode.DEFENSIVE, ratings) == ["B", "A"]

    def test_breaks_risk_ties_by_confidence(self):
        ratings = [
            _rating("A", risk=70.0, confidence=ConfidenceLevel.LOW),
            _rating("B", risk=70.0, confidence=ConfidenceLevel.HIGH),
        ]
        assert _order(DiscoveryMode.DEFENSIVE, ratings) == ["B", "A"]


class TestAvoidRanking:
    def test_puts_negative_categories_first(self):
        ratings = [
            _rating("GOOD", score=20.0, category=RatingCategory.WATCHLIST),
            _rating("BAD", score=45.0, category=RatingCategory.AVOID),
        ]
        assert _order(DiscoveryMode.AVOID, ratings) == ["BAD", "GOOD"]

    def test_sorts_by_lowest_score_within_a_group(self):
        ratings = [
            _rating("A", score=44.0, category=RatingCategory.AVOID),
            _rating("B", score=22.0, category=RatingCategory.SELL_EXIT_WARNING),
        ]
        assert _order(DiscoveryMode.AVOID, ratings) == ["B", "A"]

    def test_breaks_score_ties_by_least_favorable_risk(self):
        ratings = [
            _rating("A", score=30.0, risk=60.0, category=RatingCategory.AVOID),
            _rating("B", score=30.0, risk=20.0, category=RatingCategory.AVOID),
        ]
        assert _order(DiscoveryMode.AVOID, ratings) == ["B", "A"]


# ---------------------------------------------------------------------------
# Explanations
# ---------------------------------------------------------------------------


class TestMatchReason:
    @pytest.mark.parametrize("mode", list(DiscoveryMode))
    def test_every_mode_produces_a_non_empty_reason(self, mode):
        assert match_reason(mode, _rating("AAPL")).strip()

    def test_overall_reason_quotes_score_and_category(self):
        rating = _rating("AAPL", score=72.5, category=RatingCategory.BUY_CANDIDATE)
        reason = match_reason(DiscoveryMode.OVERALL, rating)
        assert "72.5" in reason
        assert "Buy Candidate" in reason

    def test_momentum_reason_quotes_technical_sub_score(self):
        reason = match_reason(DiscoveryMode.MOMENTUM, _rating("AAPL", technical=77.7))
        assert "77.7" in reason

    def test_quality_reason_quotes_fundamental_sub_score(self):
        reason = match_reason(DiscoveryMode.QUALITY, _rating("AAPL", fundamental=66.6))
        assert "66.6" in reason

    def test_value_reason_quotes_the_valuation_signal(self):
        rating = _rating(
            "AAPL", signals=[_valuation_signal(0.2, "P/E of 12.0 looks inexpensive.")]
        )
        assert "P/E of 12.0 looks inexpensive." in match_reason(DiscoveryMode.VALUE, rating)

    def test_value_reason_states_when_no_valuation_signal_exists(self):
        reason = match_reason(DiscoveryMode.VALUE, _rating("AAPL"))
        assert "No valuation signal" in reason

    def test_defensive_reason_quotes_risk_sub_score(self):
        reason = match_reason(DiscoveryMode.DEFENSIVE, _rating("AAPL", risk=81.2))
        assert "81.2" in reason

    def test_avoid_reason_frames_the_result_as_a_caution(self):
        reason = match_reason(DiscoveryMode.AVOID, _rating("AAPL", category=RatingCategory.AVOID))
        assert "caution" in reason.lower()
