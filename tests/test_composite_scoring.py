"""
Unit tests for score_signals() in app/analysis/scoring.py.

All tests use locally constructed Signal objects — no network calls.
"""

import pytest

from app.analysis.scoring import ScoringError, score_signals
from app.models.rating import ConfidenceLevel, Rating
from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal(
    name: str,
    category: SignalCategory,
    impact: float,
    confidence: float = 0.65,
    direction: SignalDirection | None = None,
) -> Signal:
    if direction is None:
        direction = (
            SignalDirection.BULLISH if impact > 0
            else SignalDirection.BEARISH if impact < 0
            else SignalDirection.NEUTRAL
        )
    return Signal(
        name=name,
        category=category,
        direction=direction,
        strength=SignalStrength.MODERATE,
        score_impact=impact,
        confidence=confidence,
        description=f"{category.value.capitalize()} {name} signal.",
    )


def _tech(name: str, impact: float, confidence: float = 0.65) -> Signal:
    return _make_signal(name, SignalCategory.TECHNICAL, impact, confidence)


def _fund(name: str, impact: float, confidence: float = 0.65) -> Signal:
    return _make_signal(name, SignalCategory.FUNDAMENTAL, impact, confidence)


def _news(name: str, impact: float = 0.0) -> Signal:
    return _make_signal(name, SignalCategory.NEWS, impact)


def _risk(name: str, impact: float = 0.0) -> Signal:
    return _make_signal(name, SignalCategory.RISK, impact)


# ---------------------------------------------------------------------------
# Return type and ticker normalisation
# ---------------------------------------------------------------------------

class TestReturnType:
    def test_returns_rating_instance(self):
        result = score_signals("AAPL", [_tech("T1", 0.2)])
        assert isinstance(result, Rating)

    def test_ticker_normalised_uppercase(self):
        result = score_signals("aapl", [_tech("T1", 0.2)])
        assert result.ticker == "AAPL"

    def test_ticker_whitespace_stripped(self):
        result = score_signals("  AAPL  ", [_tech("T1", 0.2)])
        assert result.ticker == "AAPL"

    def test_signals_recorded_in_rating(self):
        signals = [_tech("T1", 0.2), _fund("F1", 0.1)]
        result = score_signals("AAPL", signals)
        assert len(result.signals_used) == 2

    def test_data_timestamp_passed_through(self):
        from datetime import datetime, timezone
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        result = score_signals("AAPL", [_tech("T1", 0.0)], data_timestamp=ts)
        assert result.data_timestamp == ts

    def test_data_sources_passed_through(self):
        result = score_signals("AAPL", [_tech("T1", 0.0)], data_sources_used=["yfinance"])
        assert result.data_sources_used == ["yfinance"]

    def test_news_score_is_zero(self):
        result = score_signals("AAPL", [_tech("T1", 0.0)])
        assert result.news_score == pytest.approx(0.0)

    def test_risk_score_is_zero(self):
        result = score_signals("AAPL", [_tech("T1", 0.0)])
        assert result.risk_score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_empty_ticker_raises(self):
        with pytest.raises(ScoringError):
            score_signals("", [_tech("T1", 0.0)])

    def test_whitespace_ticker_raises(self):
        with pytest.raises(ScoringError):
            score_signals("   ", [_tech("T1", 0.0)])

    def test_none_ticker_raises(self):
        with pytest.raises(ScoringError):
            score_signals(None, [_tech("T1", 0.0)])  # type: ignore[arg-type]

    def test_empty_signals_raises(self):
        with pytest.raises(ScoringError):
            score_signals("AAPL", [])

    def test_non_list_signals_raises(self):
        with pytest.raises(ScoringError):
            score_signals("AAPL", "not a list")  # type: ignore[arg-type]

    def test_non_signal_in_list_raises(self):
        with pytest.raises(ScoringError):
            score_signals("AAPL", ["not a signal"])  # type: ignore[arg-type]

    def test_none_in_signals_list_raises(self):
        with pytest.raises(ScoringError):
            score_signals("AAPL", [None])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# No supported categories
# ---------------------------------------------------------------------------

class TestNoSupportedCategories:
    def test_only_news_signals_raises(self):
        with pytest.raises(ScoringError, match="No supported signal categories"):
            score_signals("AAPL", [_news("N1"), _news("N2")])

    def test_only_risk_signals_does_not_raise(self):
        r = score_signals("AAPL", [_risk("R1", 0.2)])
        assert isinstance(r, Rating)

    def test_news_and_risk_only_does_not_raise(self):
        # NEWS is ignored but RISK is now supported; should not raise
        r = score_signals("AAPL", [_news("N1"), _risk("R1", 0.1)])
        assert isinstance(r, Rating)


# ---------------------------------------------------------------------------
# Technical-only mode
# ---------------------------------------------------------------------------

class TestTechnicalOnly:
    def _result(self, *impacts: float) -> Rating:
        signals = [_tech(f"T{i}", imp) for i, imp in enumerate(impacts)]
        return score_signals("AAPL", signals)

    def test_composite_equals_technical_score(self):
        r = self._result(0.2, 0.1)
        assert r.score == pytest.approx(r.technical_score)

    def test_fundamental_score_is_zero(self):
        r = self._result(0.2)
        assert r.fundamental_score == pytest.approx(0.0)

    def test_technical_summary_is_populated(self):
        r = self._result(0.2)
        assert r.technical_summary is not None
        assert r.technical_summary.strip()

    def test_fundamental_summary_is_none(self):
        r = self._result(0.2)
        assert r.fundamental_summary is None

    def test_all_bullish_tech_score_above_50(self):
        r = self._result(0.2, 0.3)
        assert r.score > 50.0

    def test_all_bearish_tech_score_below_50(self):
        r = self._result(-0.2, -0.3)
        assert r.score < 50.0

    def test_neutral_tech_score_is_50(self):
        r = self._result(0.0)
        assert r.score == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Fundamental-only mode
# ---------------------------------------------------------------------------

class TestFundamentalOnly:
    def _result(self, *impacts: float) -> Rating:
        signals = [_fund(f"F{i}", imp) for i, imp in enumerate(impacts)]
        return score_signals("AAPL", signals)

    def test_composite_equals_fundamental_score(self):
        r = self._result(0.2, 0.1)
        assert r.score == pytest.approx(r.fundamental_score)

    def test_technical_score_is_zero(self):
        r = self._result(0.2)
        assert r.technical_score == pytest.approx(0.0)

    def test_fundamental_summary_is_populated(self):
        r = self._result(0.2)
        assert r.fundamental_summary is not None
        assert r.fundamental_summary.strip()

    def test_technical_summary_is_none(self):
        r = self._result(0.2)
        assert r.technical_summary is None

    def test_neutral_fund_score_is_50(self):
        r = self._result(0.0)
        assert r.score == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Tech+Fund composite weighting (weights 0.35 / 0.25; total 0.60)
# ---------------------------------------------------------------------------

class TestCompositeWeighting:
    def test_tech_fund_weights_tech_heavy(self):
        # tech impact=0.4 → tech_score=70; fund impact=0.0 → fund_score=50
        # total_weight=0.60; composite = 70*(7/12) + 50*(5/12) = 740/12 ≈ 61.6667
        tech = [_tech("T1", 0.4)]
        fund = [_fund("F1", 0.0)]
        r = score_signals("AAPL", tech + fund)
        assert r.score == pytest.approx(740 / 12)
        assert r.technical_score == pytest.approx(70.0)
        assert r.fundamental_score == pytest.approx(50.0)

    def test_tech_fund_weights_fund_heavy(self):
        # tech impact=0.0 → tech_score=50; fund impact=0.4 → fund_score=70
        # total_weight=0.60; composite = 50*(7/12) + 70*(5/12) = 700/12 ≈ 58.3333
        tech = [_tech("T1", 0.0, confidence=0.65)]
        fund = [_fund("F1", 0.4)]
        r = score_signals("AAPL", tech + fund)
        assert r.score == pytest.approx(700 / 12)
        assert r.technical_score == pytest.approx(50.0)
        assert r.fundamental_score == pytest.approx(70.0)

    def test_tech_fund_tech_outweighs_fund(self):
        # tech impact=1.0 → 100; fund impact=-1.0 → 0
        # total_weight=0.60; composite = 100*(7/12) + 0*(5/12) = 700/12 ≈ 58.3333
        tech = [_tech("T1", 1.0)]
        fund = [_fund("F1", -1.0)]
        r = score_signals("AAPL", tech + fund)
        assert r.score == pytest.approx(700 / 12)

    def test_composite_sub_scores_match_category_signals(self):
        tech_signals = [_tech("T1", 0.3), _tech("T2", -0.1)]  # net 0.2
        fund_signals = [_fund("F1", 0.2), _fund("F2", 0.0)]   # net 0.2
        r = score_signals("AAPL", tech_signals + fund_signals)
        # Both have same net impact → both sub-scores equal → composite == sub-score
        assert r.score == pytest.approx(r.technical_score)
        assert r.score == pytest.approx(r.fundamental_score)


# ---------------------------------------------------------------------------
# Re-normalisation when category missing
# ---------------------------------------------------------------------------

class TestRenormalisation:
    def test_tech_only_weight_is_100pct(self):
        # composite should equal technical_score exactly (weight = 0.35/0.35 = 1.0)
        impact = 0.3
        tech = [_tech("T1", impact)]
        r = score_signals("AAPL", tech)
        expected = 50.0 + impact * 50.0
        assert r.score == pytest.approx(expected)

    def test_fund_only_weight_is_100pct(self):
        # composite should equal fundamental_score exactly (weight = 0.25/0.25 = 1.0)
        impact = 0.6
        fund = [_fund("F1", impact)]
        r = score_signals("AAPL", fund)
        expected = 50.0 + impact * 50.0
        assert r.score == pytest.approx(expected)

    def test_risk_only_weight_is_100pct(self):
        # composite should equal risk_score exactly (weight = 0.15/0.15 = 1.0)
        impact = 0.4
        risk = [_risk("R1", impact)]
        r = score_signals("AAPL", risk)
        expected = 50.0 + impact * 50.0
        assert r.score == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Unsupported categories are ignored
# ---------------------------------------------------------------------------

class TestUnsupportedCategoriesIgnored:
    def test_news_ignored_alongside_technical(self):
        tech = [_tech("T1", 0.4)]
        news = [_news("N1", 0.9)]
        r_with_news = score_signals("AAPL", tech + news)
        r_tech_only = score_signals("AAPL", tech)
        assert r_with_news.score == pytest.approx(r_tech_only.score)

    def test_news_ignored_alongside_technical_and_risk(self):
        tech = [_tech("T1", 0.4)]
        risk = [_risk("R1", 0.0)]
        news = [_news("N1", 0.9)]
        r_with_news = score_signals("AAPL", tech + risk + news)
        r_clean = score_signals("AAPL", tech + risk)
        assert r_with_news.score == pytest.approx(r_clean.score)

    def test_news_only_score_not_in_sub_scores(self):
        # NEWS signals should not inflate the score
        tech = [_tech("T1", 0.0)]
        news = [_news("N1", 1.0)]
        r = score_signals("AAPL", tech + news)
        assert r.score == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Score stays within [0, 100]
# ---------------------------------------------------------------------------

class TestScoreRange:
    def test_maximum_bullish_score_at_most_100(self):
        signals = [_tech(f"T{i}", 0.3) for i in range(10)]
        r = score_signals("AAPL", signals)
        assert 0.0 <= r.score <= 100.0

    def test_maximum_bearish_score_at_least_0(self):
        signals = [_fund(f"F{i}", -0.3) for i in range(10)]
        r = score_signals("AAPL", signals)
        assert 0.0 <= r.score <= 100.0

    def test_composite_sub_scores_within_range(self):
        tech = [_tech("T1", 0.5), _tech("T2", 0.5)]
        fund = [_fund("F1", -0.5), _fund("F2", -0.5)]
        r = score_signals("AAPL", tech + fund)
        assert 0.0 <= r.technical_score <= 100.0
        assert 0.0 <= r.fundamental_score <= 100.0
        assert 0.0 <= r.score <= 100.0


# ---------------------------------------------------------------------------
# Positive factors and key risks from both categories
# ---------------------------------------------------------------------------

class TestFactors:
    def test_positive_factors_include_technical_bullish(self):
        t = _tech("TrendUp", 0.3)
        r = score_signals("AAPL", [t])
        assert any("Technical" in f or "technical" in f.lower() for f in r.key_positive_factors)

    def test_positive_factors_include_fundamental_bullish(self):
        f = _fund("ValuationGood", 0.2)
        r = score_signals("AAPL", [f])
        assert r.key_positive_factors

    def test_risk_factors_include_technical_bearish(self):
        t = _tech("WeakTrend", -0.3)
        r = score_signals("AAPL", [t])
        assert r.key_risks

    def test_risk_factors_include_fundamental_bearish(self):
        f = _fund("HighDebt", -0.2)
        r = score_signals("AAPL", [f])
        assert r.key_risks

    def test_mixed_signals_split_factors(self):
        signals = [_tech("Trend", 0.3), _fund("Debt", -0.2)]
        r = score_signals("AAPL", signals)
        assert r.key_positive_factors
        assert r.key_risks

    def test_all_neutral_no_positive_no_risk(self):
        signals = [
            _tech("T1", 0.0, confidence=0.65),
            _fund("F1", 0.0, confidence=0.65),
        ]
        r = score_signals("AAPL", signals)
        assert r.key_positive_factors == []
        assert r.key_risks == []


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

class TestSummaries:
    def test_technical_summary_mentions_score(self):
        r = score_signals("AAPL", [_tech("T1", 0.2)])
        assert "score" in r.technical_summary.lower()  # type: ignore[union-attr]

    def test_fundamental_summary_mentions_score(self):
        r = score_signals("AAPL", [_fund("F1", 0.2)])
        assert "score" in r.fundamental_summary.lower()  # type: ignore[union-attr]

    def test_both_summaries_populated_when_both_categories(self):
        r = score_signals("AAPL", [_tech("T1", 0.2), _fund("F1", 0.1)])
        assert r.technical_summary is not None
        assert r.fundamental_summary is not None


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------

class TestConfidence:
    def test_high_confidence_signals_yield_high_confidence(self):
        signals = [_tech("T1", 0.2, confidence=0.80), _tech("T2", 0.1, confidence=0.75)]
        r = score_signals("AAPL", signals)
        assert r.confidence == ConfidenceLevel.HIGH

    def test_low_confidence_signals_yield_low_confidence(self):
        signals = [_tech("T1", 0.2, confidence=0.30), _fund("F1", 0.1, confidence=0.30)]
        r = score_signals("AAPL", signals)
        assert r.confidence == ConfidenceLevel.LOW

    def test_mixed_confidence_yields_medium(self):
        signals = [_tech("T1", 0.2, confidence=0.60), _tech("T2", 0.1, confidence=0.50)]
        r = score_signals("AAPL", signals)
        assert r.confidence == ConfidenceLevel.MEDIUM


# ---------------------------------------------------------------------------
# Score direction
# ---------------------------------------------------------------------------

class TestScoreDirection:
    def test_both_bullish_score_above_50(self):
        r = score_signals("AAPL", [_tech("T1", 0.3), _fund("F1", 0.2)])
        assert r.score > 50.0

    def test_both_bearish_score_below_50(self):
        r = score_signals("AAPL", [_tech("T1", -0.3), _fund("F1", -0.2)])
        assert r.score < 50.0

    def test_mixed_bullish_tech_bearish_fund_between_both(self):
        # tech_score > 50, fund_score < 50; composite somewhere in between
        tech_only = score_signals("AAPL", [_tech("T1", 0.4)])
        fund_only = score_signals("AAPL", [_fund("F1", -0.4)])
        combined = score_signals("AAPL", [_tech("T1", 0.4), _fund("F1", -0.4)])
        assert fund_only.score < combined.score < tech_only.score


# ---------------------------------------------------------------------------
# Risk signals
# ---------------------------------------------------------------------------

class TestRiskSignals:
    def _result(self, *impacts: float) -> Rating:
        signals = [_risk(f"R{i}", imp) for i, imp in enumerate(impacts)]
        return score_signals("AAPL", signals)

    def test_composite_equals_risk_score_when_risk_only(self):
        r = self._result(0.2, 0.1)
        assert r.score == pytest.approx(r.risk_score)

    def test_technical_score_zero_when_risk_only(self):
        r = self._result(0.2)
        assert r.technical_score == pytest.approx(0.0)

    def test_fundamental_score_zero_when_risk_only(self):
        r = self._result(0.2)
        assert r.fundamental_score == pytest.approx(0.0)

    def test_risk_summary_populated_when_risk_signals_present(self):
        r = self._result(0.2)
        assert r.risk_summary is not None
        assert "score" in r.risk_summary.lower()

    def test_risk_summary_none_when_no_risk_signals(self):
        r = score_signals("AAPL", [_tech("T1", 0.2)])
        assert r.risk_summary is None

    def test_neutral_risk_score_is_50(self):
        r = self._result(0.0)
        assert r.score == pytest.approx(50.0)

    def test_risk_score_nonzero_when_risk_signals_present(self):
        r = score_signals("AAPL", [_tech("T1", 0.0), _risk("R1", 0.3)])
        assert r.risk_score > 50.0


# ---------------------------------------------------------------------------
# Three-way composite weighting (Tech 0.35 / Fund 0.25 / Risk 0.15; total 0.75)
# ---------------------------------------------------------------------------

class TestThreeWayWeighting:
    def test_three_way_equal_impacts_composite_equals_sub_scores(self):
        # All categories same net impact → sub-scores equal → composite == any sub-score
        impact = 0.2
        r = score_signals("AAPL", [
            _tech("T1", impact),
            _fund("F1", impact),
            _risk("R1", impact),
        ])
        assert r.score == pytest.approx(r.technical_score)
        assert r.score == pytest.approx(r.fundamental_score)
        assert r.score == pytest.approx(r.risk_score)

    def test_three_way_weights_tech_dominant(self):
        # tech_score=70 (impact 0.4), fund_score=50 (impact 0), risk_score=50 (impact 0)
        # total_weight = 0.75
        # composite = 70*(0.35/0.75) + 50*(0.25/0.75) + 50*(0.15/0.75)
        #           = 70*(7/15) + 50*(5/15) + 50*(3/15)
        #           = 490/15 + 250/15 + 150/15 = 890/15 ≈ 59.3333
        r = score_signals("AAPL", [
            _tech("T1", 0.4),
            _fund("F1", 0.0),
            _risk("R1", 0.0),
        ])
        assert r.score == pytest.approx(890 / 15)

    def test_three_way_all_summaries_populated(self):
        r = score_signals("AAPL", [
            _tech("T1", 0.2),
            _fund("F1", 0.1),
            _risk("R1", -0.1),
        ])
        assert r.technical_summary is not None
        assert r.fundamental_summary is not None
        assert r.risk_summary is not None

    def test_three_way_explanation_mentions_risk(self):
        r = score_signals("AAPL", [
            _tech("T1", 0.2),
            _fund("F1", 0.1),
            _risk("R1", 0.0),
        ])
        assert "risk" in r.explanation.lower()
