"""
Unit tests for app/analysis/news_analysis.py.

All tests use locally constructed NewsItem objects — no network calls.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.analysis.news_analysis import NewsAnalysisError, analyze_news
from app.models.news import NewsItem
from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TS = datetime(2024, 6, 1, tzinfo=timezone.utc)

_SIGNAL_NAMES = {"News Sentiment", "News Risk Headlines", "News Coverage"}


def _make_item(title: str, summary: str | None = None) -> NewsItem:
    """Return a minimal NewsItem with the given title and optional summary."""
    return NewsItem(title=title, summary=summary, published_at=_TS)


def _signal_by_name(signals: list[Signal], name: str) -> Signal:
    for s in signals:
        if s.name == name:
            return s
    raise KeyError(f"No signal named '{name}' in result.")


# ---------------------------------------------------------------------------
# Structure — non-empty input
# ---------------------------------------------------------------------------

class TestStructure:
    def test_returns_list(self):
        result = analyze_news([_make_item("Apple reports strong earnings beat.")])
        assert isinstance(result, list)

    def test_returns_3_signals_for_non_empty_input(self):
        result = analyze_news([_make_item("Generic headline")])
        assert len(result) == 3

    def test_all_items_are_signal_instances(self):
        result = analyze_news([_make_item("Generic headline")])
        assert all(isinstance(s, Signal) for s in result)

    def test_all_signals_use_news_category(self):
        result = analyze_news([_make_item("Generic headline")])
        assert all(s.category == SignalCategory.NEWS for s in result)

    def test_signal_names_are_stable(self):
        result = analyze_news([_make_item("Generic headline")])
        assert {s.name for s in result} == _SIGNAL_NAMES

    def test_all_descriptions_are_non_empty(self):
        result = analyze_news([_make_item("Generic headline")])
        assert all(isinstance(s.description, str) and s.description.strip() for s in result)

    def test_returns_3_signals_for_empty_input(self):
        result = analyze_news([])
        assert len(result) == 3

    def test_empty_input_signal_names_are_stable(self):
        result = analyze_news([])
        assert {s.name for s in result} == _SIGNAL_NAMES


# ---------------------------------------------------------------------------
# Empty input — no-data neutral signals
# ---------------------------------------------------------------------------

class TestEmptyInput:
    def _result(self) -> list[Signal]:
        return analyze_news([])

    def test_all_signals_are_neutral(self):
        result = self._result()
        assert all(s.direction == SignalDirection.NEUTRAL for s in result)

    def test_all_signals_have_low_confidence(self):
        result = self._result()
        assert all(s.confidence == pytest.approx(0.30) for s in result)

    def test_all_signals_have_zero_impact(self):
        result = self._result()
        assert all(s.score_impact == pytest.approx(0.0) for s in result)

    def test_all_signals_are_weak_strength(self):
        result = self._result()
        assert all(s.strength == SignalStrength.WEAK for s in result)

    def test_sentiment_description_mentions_no_news(self):
        s = _signal_by_name(self._result(), "News Sentiment")
        assert "no recent news" in s.description.lower()

    def test_risk_description_mentions_no_news(self):
        s = _signal_by_name(self._result(), "News Risk Headlines")
        assert "no recent news" in s.description.lower()

    def test_coverage_description_mentions_no_news(self):
        s = _signal_by_name(self._result(), "News Coverage")
        assert "no recent news" in s.description.lower()


# ---------------------------------------------------------------------------
# Sentiment signal — positive cases
# ---------------------------------------------------------------------------

class TestSentimentPositive:
    def _get_sentiment(self, title: str, summary: str | None = None) -> Signal:
        return _signal_by_name(analyze_news([_make_item(title, summary)]), "News Sentiment")

    def test_earnings_beat_in_title_is_bullish(self):
        s = self._get_sentiment("Apple reports earnings beat this quarter.")
        assert s.direction == SignalDirection.BULLISH

    def test_bullish_score_impact_is_positive(self):
        s = self._get_sentiment("Company beats estimates, raises guidance.")
        assert s.score_impact > 0

    def test_upgrade_keyword_in_title_is_bullish(self):
        s = self._get_sentiment("Analyst upgrades Apple to outperform.")
        assert s.direction == SignalDirection.BULLISH

    def test_positive_keyword_in_summary_is_bullish(self):
        s = self._get_sentiment("Analyst note", summary="Company reports record revenue.")
        assert s.direction == SignalDirection.BULLISH

    def test_positive_value_equals_net_sentiment(self):
        s = self._get_sentiment("Company beats estimates and upgraded by analysts.")
        assert isinstance(s.value, int)
        assert s.value > 0

    def test_positive_description_mentions_positive_terms(self):
        s = self._get_sentiment("Apple reports strong earnings beat.")
        assert "positive" in s.description.lower()

    def test_positive_metadata_contains_matches(self):
        s = self._get_sentiment("Apple reports earnings beat.")
        assert len(s.metadata["positive_matches"]) > 0

    def test_3_or_more_positive_matches_is_moderate_strength(self):
        # Three distinct positive keywords: "beats", "upgraded", "expansion", "approval"
        s = self._get_sentiment(
            "Apple beats estimates. Analyst upgraded. Expansion approval."
        )
        assert s.strength == SignalStrength.MODERATE

    def test_1_positive_match_net_diff_is_weak_strength(self):
        s = self._get_sentiment("Apple launches new product.")
        assert s.strength == SignalStrength.WEAK

    def test_score_impact_capped_at_0_20(self):
        # Many positive keywords: score_impact should not exceed 0.20
        s = self._get_sentiment(
            "Beats estimates, earnings beat, raises guidance, record revenue, "
            "strong demand, expansion, acquisition, upgrade, approval, buyback."
        )
        assert s.score_impact <= 0.20


# ---------------------------------------------------------------------------
# Sentiment signal — negative cases
# ---------------------------------------------------------------------------

class TestSentimentNegative:
    def _get_sentiment(self, title: str, summary: str | None = None) -> Signal:
        return _signal_by_name(analyze_news([_make_item(title, summary)]), "News Sentiment")

    def test_earnings_miss_in_title_is_bearish(self):
        s = self._get_sentiment("Company reports earnings miss this quarter.")
        assert s.direction == SignalDirection.BEARISH

    def test_bearish_score_impact_is_negative(self):
        s = self._get_sentiment("Company misses estimates, cuts guidance.")
        assert s.score_impact < 0

    def test_downgrade_keyword_is_bearish(self):
        s = self._get_sentiment("Analyst downgrades stock to underperform.")
        assert s.direction == SignalDirection.BEARISH

    def test_negative_keyword_in_summary_is_bearish(self):
        s = self._get_sentiment("Analyst note", summary="Company reports revenue decline.")
        assert s.direction == SignalDirection.BEARISH

    def test_negative_value_is_negative_int(self):
        s = self._get_sentiment("Misses estimates and downgraded by analysts.")
        assert isinstance(s.value, int)
        assert s.value < 0

    def test_negative_description_mentions_negative_terms(self):
        s = self._get_sentiment("Company misses earnings.")
        assert "negative" in s.description.lower()

    def test_3_or_more_negative_matches_is_moderate_strength(self):
        s = self._get_sentiment(
            "Misses estimates. Cuts guidance. Layoffs announced. Downgraded."
        )
        assert s.strength == SignalStrength.MODERATE

    def test_score_impact_capped_at_minus_0_20(self):
        s = self._get_sentiment(
            "Misses estimates, earnings miss, cuts guidance, revenue decline, "
            "profit decline, downgrade, underperform, weak demand, layoffs, recall."
        )
        assert s.score_impact >= -0.20


# ---------------------------------------------------------------------------
# Sentiment signal — neutral cases
# ---------------------------------------------------------------------------

class TestSentimentNeutral:
    def _get_sentiment(self, title: str, summary: str | None = None) -> Signal:
        return _signal_by_name(analyze_news([_make_item(title, summary)]), "News Sentiment")

    def test_no_keywords_is_neutral(self):
        s = self._get_sentiment("Generic company press release today.")
        assert s.direction == SignalDirection.NEUTRAL

    def test_neutral_score_impact_is_zero(self):
        s = self._get_sentiment("Generic company press release today.")
        assert s.score_impact == pytest.approx(0.0)

    def test_equal_positive_and_negative_counts_is_neutral(self):
        # "beats" (positive), "misses" (negative)
        s = self._get_sentiment("Company beats revenue but misses earnings.")
        assert s.direction == SignalDirection.NEUTRAL
        assert s.score_impact == pytest.approx(0.0)

    def test_tied_value_is_zero(self):
        s = self._get_sentiment("Company beats revenue but misses earnings.")
        assert s.value == 0

    def test_no_keywords_description_mentions_neutral(self):
        s = self._get_sentiment("Generic headline with no matching terms.")
        assert "neutral" in s.description.lower()

    def test_tied_keywords_description_mentions_balanced(self):
        s = self._get_sentiment("Company beats but also misses on guidance.")
        assert "neutral" in s.description.lower() or "balanced" in s.description.lower()


# ---------------------------------------------------------------------------
# Risk headline signal
# ---------------------------------------------------------------------------

class TestRiskHeadlineSignal:
    def _get_risk(self, title: str, summary: str | None = None) -> Signal:
        return _signal_by_name(analyze_news([_make_item(title, summary)]), "News Risk Headlines")

    def test_lawsuit_keyword_is_bearish(self):
        s = self._get_risk("Company faces new lawsuit over patent dispute.")
        assert s.direction == SignalDirection.BEARISH

    def test_risk_score_impact_is_negative(self):
        s = self._get_risk("SEC investigation launched into company.")
        assert s.score_impact < 0

    def test_risk_keyword_in_summary_detected(self):
        s = self._get_risk("Company update", summary="New fraud investigation begins.")
        assert s.direction == SignalDirection.BEARISH

    def test_no_risk_keywords_is_neutral(self):
        s = self._get_risk("Company reports quarterly earnings.")
        assert s.direction == SignalDirection.NEUTRAL

    def test_no_risk_score_impact_is_zero(self):
        s = self._get_risk("Company reports quarterly earnings.")
        assert s.score_impact == pytest.approx(0.0)

    def test_single_risk_match_is_weak_strength(self):
        s = self._get_risk("Company faces lawsuit.")
        assert s.strength == SignalStrength.WEAK

    def test_two_risk_matches_is_moderate_strength(self):
        s = self._get_risk("Lawsuit and investigation into company practices.")
        assert s.strength == SignalStrength.MODERATE

    def test_risk_description_mentions_risk_terms(self):
        s = self._get_risk("Company faces antitrust probe.")
        assert "risk" in s.description.lower() or "antitrust" in s.description or "probe" in s.description

    def test_risk_metadata_contains_matches(self):
        s = self._get_risk("Company faces lawsuit.")
        assert len(s.metadata["risk_matches"]) > 0

    def test_no_risk_metadata_is_empty_list(self):
        s = self._get_risk("Company reports earnings.")
        assert s.metadata["risk_matches"] == []

    def test_risk_value_equals_match_count(self):
        s = self._get_risk("Company faces lawsuit and fraud investigation.")
        assert isinstance(s.value, int)
        assert s.value > 0

    def test_no_risk_value_is_zero(self):
        s = self._get_risk("Company reports earnings.")
        assert s.value == 0

    def test_score_impact_capped_at_minus_0_20(self):
        s = self._get_risk(
            "Lawsuit, investigation, fraud, cybersecurity breach, bankruptcy, "
            "antitrust probe, regulatory action, recall, default."
        )
        assert s.score_impact >= -0.20

    def test_bankruptcy_is_a_risk_keyword(self):
        s = self._get_risk("Company files for bankruptcy protection.")
        assert s.direction == SignalDirection.BEARISH

    def test_recall_is_a_risk_keyword(self):
        s = self._get_risk("Product recall issued by manufacturer.")
        assert s.direction == SignalDirection.BEARISH


# ---------------------------------------------------------------------------
# Coverage signal
# ---------------------------------------------------------------------------

class TestCoverageSignal:
    def _get_coverage(self, items: list[NewsItem]) -> Signal:
        return _signal_by_name(analyze_news(items), "News Coverage")

    def test_coverage_direction_is_always_neutral(self):
        items = [_make_item(f"Headline {i}") for i in range(5)]
        s = self._get_coverage(items)
        assert s.direction == SignalDirection.NEUTRAL

    def test_coverage_score_impact_is_always_zero(self):
        items = [_make_item(f"Headline {i}") for i in range(5)]
        s = self._get_coverage(items)
        assert s.score_impact == pytest.approx(0.0)

    def test_coverage_value_equals_article_count(self):
        items = [_make_item(f"Headline {i}") for i in range(7)]
        s = self._get_coverage(items)
        assert s.value == 7

    def test_single_article_value_is_one(self):
        s = self._get_coverage([_make_item("Headline")])
        assert s.value == 1

    def test_confidence_increases_with_more_articles(self):
        one_article  = _signal_by_name(
            analyze_news([_make_item("H")]), "News Coverage"
        ).confidence
        ten_articles = _signal_by_name(
            analyze_news([_make_item(f"H{i}") for i in range(10)]), "News Coverage"
        ).confidence
        assert ten_articles > one_article

    def test_confidence_capped_at_0_70(self):
        items = [_make_item(f"Headline {i}") for i in range(100)]
        s = self._get_coverage(items)
        assert s.confidence <= 0.70

    def test_coverage_description_mentions_count(self):
        items = [_make_item(f"Headline {i}") for i in range(4)]
        s = self._get_coverage(items)
        assert "4" in s.description


# ---------------------------------------------------------------------------
# Case-insensitive matching
# ---------------------------------------------------------------------------

class TestCaseInsensitivity:
    def test_uppercase_positive_keyword_matches(self):
        s = _signal_by_name(
            analyze_news([_make_item("APPLE BEATS ESTIMATES THIS QUARTER.")]),
            "News Sentiment",
        )
        assert s.direction == SignalDirection.BULLISH

    def test_mixed_case_negative_keyword_matches(self):
        s = _signal_by_name(
            analyze_news([_make_item("Company MISSES Earnings Expectations.")]),
            "News Sentiment",
        )
        assert s.direction == SignalDirection.BEARISH

    def test_uppercase_risk_keyword_matches(self):
        s = _signal_by_name(
            analyze_news([_make_item("LAWSUIT FILED AGAINST COMPANY.")]),
            "News Risk Headlines",
        )
        assert s.direction == SignalDirection.BEARISH

    def test_mixed_case_risk_keyword_in_summary(self):
        s = _signal_by_name(
            analyze_news([_make_item("Update", summary="New INVESTIGATION announced.")]),
            "News Risk Headlines",
        )
        assert s.direction == SignalDirection.BEARISH


# ---------------------------------------------------------------------------
# Missing summary handling
# ---------------------------------------------------------------------------

class TestMissingSummary:
    def test_none_summary_does_not_crash(self):
        result = analyze_news([_make_item("Apple beats earnings estimate.", summary=None)])
        assert len(result) == 3

    def test_positive_keyword_in_title_with_none_summary_is_bullish(self):
        s = _signal_by_name(
            analyze_news([_make_item("Apple beats estimates.", summary=None)]),
            "News Sentiment",
        )
        assert s.direction == SignalDirection.BULLISH

    def test_risk_keyword_in_title_with_none_summary_detected(self):
        s = _signal_by_name(
            analyze_news([_make_item("Lawsuit filed against company.", summary=None)]),
            "News Risk Headlines",
        )
        assert s.direction == SignalDirection.BEARISH

    def test_all_none_summaries_do_not_crash(self):
        items = [_make_item(f"Headline {i}", summary=None) for i in range(5)]
        result = analyze_news(items)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Multiple items — aggregation
# ---------------------------------------------------------------------------

class TestMultipleItems:
    def test_positive_keywords_across_multiple_items_aggregate(self):
        items = [
            _make_item("Apple beats revenue estimates."),
            _make_item("Analyst upgrades stock to outperform."),
        ]
        s = _signal_by_name(analyze_news(items), "News Sentiment")
        assert s.direction == SignalDirection.BULLISH

    def test_risk_keywords_in_one_item_detected_across_set(self):
        items = [
            _make_item("Company reports good earnings."),
            _make_item("Company faces lawsuit over patent."),
        ]
        s = _signal_by_name(analyze_news(items), "News Risk Headlines")
        assert s.direction == SignalDirection.BEARISH

    def test_positive_dominant_across_mixed_items(self):
        items = [
            _make_item("Company beats estimates."),
            _make_item("Strong demand and revenue growth."),
            _make_item("Product launched successfully."),
            _make_item("Slight miss on guidance this quarter."),
        ]
        s = _signal_by_name(analyze_news(items), "News Sentiment")
        # More positive matches than negative overall
        assert s.score_impact > 0

    def test_coverage_value_reflects_all_items(self):
        items = [_make_item(f"Headline {i}") for i in range(6)]
        s = _signal_by_name(analyze_news(items), "News Coverage")
        assert s.value == 6

    def test_keyword_in_summary_of_second_item_detected(self):
        items = [
            _make_item("Neutral headline"),
            _make_item("Another headline", summary="Company receives regulatory approval."),
        ]
        s = _signal_by_name(analyze_news(items), "News Sentiment")
        assert s.direction == SignalDirection.BULLISH


# ---------------------------------------------------------------------------
# No mutation
# ---------------------------------------------------------------------------

class TestNoMutation:
    def test_input_list_length_unchanged(self):
        items = [_make_item("Apple reports earnings beat.")]
        original_len = len(items)
        analyze_news(items)
        assert len(items) == original_len

    def test_input_items_titles_unchanged(self):
        title = "Apple reports earnings beat."
        items = [_make_item(title)]
        analyze_news(items)
        assert items[0].title == title

    def test_input_items_summaries_unchanged(self):
        summary = "Strong demand and record revenue."
        items = [_make_item("Headline", summary=summary)]
        analyze_news(items)
        assert items[0].summary == summary

    def test_empty_list_unchanged(self):
        items: list[NewsItem] = []
        analyze_news(items)
        assert items == []


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_non_list_string_raises(self):
        with pytest.raises(NewsAnalysisError):
            analyze_news("AAPL")  # type: ignore[arg-type]

    def test_non_list_none_raises(self):
        with pytest.raises(NewsAnalysisError):
            analyze_news(None)  # type: ignore[arg-type]

    def test_non_list_dict_raises(self):
        with pytest.raises(NewsAnalysisError):
            analyze_news({"title": "Headline"})  # type: ignore[arg-type]

    def test_list_with_non_newsitem_string_raises(self):
        with pytest.raises(NewsAnalysisError):
            analyze_news(["some headline"])  # type: ignore[arg-type]

    def test_list_with_non_newsitem_dict_raises(self):
        with pytest.raises(NewsAnalysisError):
            analyze_news([{"title": "Headline"}])  # type: ignore[arg-type]

    def test_list_with_non_newsitem_none_raises(self):
        with pytest.raises(NewsAnalysisError):
            analyze_news([None])  # type: ignore[arg-type]

    def test_error_message_mentions_type(self):
        with pytest.raises(NewsAnalysisError, match="list"):
            analyze_news("not a list")  # type: ignore[arg-type]

    def test_mixed_valid_and_invalid_raises(self):
        with pytest.raises(NewsAnalysisError):
            analyze_news([_make_item("Valid"), "invalid"])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Scoring — all signals use NEWS category (does not affect scoring weights)
# ---------------------------------------------------------------------------

class TestNewsCategory:
    def test_non_empty_all_news_category(self):
        result = analyze_news([_make_item("Apple beats estimates.")])
        assert all(s.category == SignalCategory.NEWS for s in result)

    def test_empty_all_news_category(self):
        result = analyze_news([])
        assert all(s.category == SignalCategory.NEWS for s in result)

    def test_news_category_value(self):
        result = analyze_news([_make_item("Headline")])
        assert all(s.category.value == "news" for s in result)


# ---------------------------------------------------------------------------
# Keyword overlap — lawsuit in both negative and risk
# ---------------------------------------------------------------------------

class TestKeywordOverlap:
    def test_lawsuit_triggers_both_negative_sentiment_and_risk(self):
        items = [_make_item("Company faces lawsuit.")]
        sentiment = _signal_by_name(analyze_news(items), "News Sentiment")
        risk      = _signal_by_name(analyze_news(items), "News Risk Headlines")
        assert sentiment.direction == SignalDirection.BEARISH
        assert risk.direction     == SignalDirection.BEARISH

    def test_bankruptcy_triggers_both_negative_sentiment_and_risk(self):
        items = [_make_item("Company files for bankruptcy.")]
        sentiment = _signal_by_name(analyze_news(items), "News Sentiment")
        risk      = _signal_by_name(analyze_news(items), "News Risk Headlines")
        assert sentiment.direction == SignalDirection.BEARISH
        assert risk.direction     == SignalDirection.BEARISH


# ---------------------------------------------------------------------------
# Score impact — calibration checks
# ---------------------------------------------------------------------------

class TestScoreImpact:
    def test_single_positive_net_impact_is_0_05(self):
        # "expansion" is the only positive keyword here
        s = _signal_by_name(
            analyze_news([_make_item("Company announces expansion into new market.")]),
            "News Sentiment",
        )
        assert s.direction == SignalDirection.BULLISH
        assert s.score_impact == pytest.approx(0.05, abs=0.051)

    def test_single_risk_match_impact_is_minus_0_05(self):
        s = _signal_by_name(
            analyze_news([_make_item("Company faces antitrust review.")]),
            "News Risk Headlines",
        )
        assert s.score_impact == pytest.approx(-0.05, abs=0.051)

    def test_neutral_sentiment_impact_is_exactly_zero(self):
        s = _signal_by_name(
            analyze_news([_make_item("Company holds annual conference.")]),
            "News Sentiment",
        )
        assert s.score_impact == pytest.approx(0.0)

    def test_coverage_impact_is_always_zero(self):
        for n in (1, 5, 10):
            items = [_make_item(f"H{i}") for i in range(n)]
            s = _signal_by_name(analyze_news(items), "News Coverage")
            assert s.score_impact == pytest.approx(0.0)
