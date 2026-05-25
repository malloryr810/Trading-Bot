"""
Unit tests for app/reports/report_generator.py.

All inputs are built locally — no network calls.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.rating import ConfidenceLevel, Rating, RatingCategory
from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength
from app.models.stock_report import StockReport
from app.reports.report_generator import build_stock_report, generate_plain_text_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal(
    name: str = "Test Signal",
    category: SignalCategory = SignalCategory.TECHNICAL,
    score_impact: float = 0.0,
) -> Signal:
    return Signal(
        name=name,
        category=category,
        direction=SignalDirection.NEUTRAL,
        strength=SignalStrength.MODERATE,
        description=f"Description for {name}.",
        score_impact=score_impact,
        confidence=0.60,
    )


def _make_rating(
    ticker: str = "AAPL",
    score: float = 62.0,
    category: RatingCategory = RatingCategory.WATCHLIST,
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
    signals: list[Signal] | None = None,
    technical_summary: str | None = "Technical score: 62.0/100.",
    fundamental_summary: str | None = None,
    news_summary: str | None = None,
    risk_summary: str | None = None,
    key_positive_factors: list[str] | None = None,
    key_risks: list[str] | None = None,
    buy_trigger: str | None = "Enter above 65.",
    sell_or_avoid_trigger: str | None = "Exit below 45.",
    data_timestamp: datetime | None = None,
    data_sources_used: list[str] | None = None,
) -> Rating:
    return Rating(
        ticker=ticker,
        final_category=category,
        score=score,
        confidence=confidence,
        explanation=f"Rating for {ticker} based on signals.",
        technical_score=score,
        technical_summary=technical_summary,
        fundamental_summary=fundamental_summary,
        news_summary=news_summary,
        risk_summary=risk_summary,
        key_positive_factors=key_positive_factors or [],
        key_risks=key_risks or [],
        buy_trigger=buy_trigger,
        sell_or_avoid_trigger=sell_or_avoid_trigger,
        data_timestamp=data_timestamp or datetime(2024, 6, 1, tzinfo=timezone.utc),
        data_sources_used=data_sources_used or ["yfinance"],
        signals_used=signals or [_make_signal()],
    )


# ---------------------------------------------------------------------------
# build_stock_report — return type and identity
# ---------------------------------------------------------------------------

class TestBuildStockReport:
    def test_returns_stock_report(self):
        rating = _make_rating()
        result = build_stock_report(rating)
        assert isinstance(result, StockReport)

    def test_ticker_matches_rating(self):
        rating = _make_rating(ticker="MSFT")
        result = build_stock_report(rating)
        assert result.ticker == "MSFT"

    def test_final_category_matches_rating(self):
        rating = _make_rating(category=RatingCategory.BUY_CANDIDATE, score=72.0)
        result = build_stock_report(rating)
        assert result.final_category == RatingCategory.BUY_CANDIDATE

    def test_score_matches_rating(self):
        rating = _make_rating(score=77.5)
        result = build_stock_report(rating)
        assert result.score == pytest.approx(77.5)

    def test_confidence_level_maps_from_rating_confidence(self):
        rating = _make_rating(confidence=ConfidenceLevel.HIGH)
        result = build_stock_report(rating)
        assert result.confidence_level == ConfidenceLevel.HIGH

    def test_technical_summary_matches(self):
        rating = _make_rating(technical_summary="Tech: 80.0/100.")
        result = build_stock_report(rating)
        assert result.technical_summary == "Tech: 80.0/100."

    def test_fundamental_summary_matches(self):
        rating = _make_rating(fundamental_summary="Fund: 65.0/100.")
        result = build_stock_report(rating)
        assert result.fundamental_summary == "Fund: 65.0/100."

    def test_news_summary_matches(self):
        rating = _make_rating(news_summary="News: 55.0/100.")
        result = build_stock_report(rating)
        assert result.news_summary == "News: 55.0/100."

    def test_risk_summary_matches(self):
        rating = _make_rating(risk_summary="Risk: 45.0/100.")
        result = build_stock_report(rating)
        assert result.risk_summary == "Risk: 45.0/100."

    def test_key_positive_factors_copied(self):
        factors = ["Strong trend", "Healthy margins"]
        rating = _make_rating(key_positive_factors=factors)
        result = build_stock_report(rating)
        assert result.key_positive_factors == factors

    def test_key_risks_copied(self):
        risks = ["High debt", "Slowing growth"]
        rating = _make_rating(key_risks=risks)
        result = build_stock_report(rating)
        assert result.key_risks == risks

    def test_buy_trigger_matches(self):
        rating = _make_rating(buy_trigger="Enter above 70.")
        result = build_stock_report(rating)
        assert result.buy_trigger == "Enter above 70."

    def test_sell_or_avoid_trigger_matches(self):
        rating = _make_rating(sell_or_avoid_trigger="Exit below 40.")
        result = build_stock_report(rating)
        assert result.sell_or_avoid_trigger == "Exit below 40."

    def test_data_timestamp_matches(self):
        ts = datetime(2024, 3, 15, tzinfo=timezone.utc)
        rating = _make_rating(data_timestamp=ts)
        result = build_stock_report(rating)
        assert result.data_timestamp == ts

    def test_data_sources_used_matches(self):
        rating = _make_rating(data_sources_used=["yfinance", "custom"])
        result = build_stock_report(rating)
        assert result.data_sources_used == ["yfinance", "custom"]


# ---------------------------------------------------------------------------
# build_stock_report — optional parameters
# ---------------------------------------------------------------------------

class TestBuildOptionalParams:
    def test_company_name_defaults_to_none(self):
        result = build_stock_report(_make_rating())
        assert result.company_name is None

    def test_company_name_passed_through(self):
        result = build_stock_report(_make_rating(), company_name="Apple Inc.")
        assert result.company_name == "Apple Inc."

    def test_current_price_defaults_to_none(self):
        result = build_stock_report(_make_rating())
        assert result.current_price is None

    def test_current_price_passed_through(self):
        result = build_stock_report(_make_rating(), current_price=182.50)
        assert result.current_price == pytest.approx(182.50)


# ---------------------------------------------------------------------------
# build_stock_report — signal partitioning
# ---------------------------------------------------------------------------

class TestSignalPartitioning:
    def _cat_signals(self, *categories: SignalCategory) -> list[Signal]:
        return [_make_signal(f"Sig_{cat.value}", cat) for cat in categories]

    def test_technical_signals_isolated(self):
        signals = [
            _make_signal("T1", SignalCategory.TECHNICAL),
            _make_signal("F1", SignalCategory.FUNDAMENTAL),
        ]
        result = build_stock_report(_make_rating(signals=signals))
        assert len(result.technical_signals) == 1
        assert result.technical_signals[0].name == "T1"

    def test_fundamental_signals_isolated(self):
        signals = [
            _make_signal("T1", SignalCategory.TECHNICAL),
            _make_signal("F1", SignalCategory.FUNDAMENTAL),
            _make_signal("F2", SignalCategory.FUNDAMENTAL),
        ]
        result = build_stock_report(_make_rating(signals=signals))
        assert len(result.fundamental_signals) == 2

    def test_news_signals_isolated(self):
        signals = [
            _make_signal("N1", SignalCategory.NEWS),
            _make_signal("T1", SignalCategory.TECHNICAL),
        ]
        result = build_stock_report(_make_rating(signals=signals))
        assert len(result.news_signals) == 1
        assert result.news_signals[0].name == "N1"

    def test_risk_signals_isolated(self):
        signals = [
            _make_signal("R1", SignalCategory.RISK),
            _make_signal("R2", SignalCategory.RISK),
            _make_signal("T1", SignalCategory.TECHNICAL),
        ]
        result = build_stock_report(_make_rating(signals=signals))
        assert len(result.risk_signals) == 2

    def test_all_four_categories_partitioned(self):
        signals = [
            _make_signal("T1", SignalCategory.TECHNICAL),
            _make_signal("F1", SignalCategory.FUNDAMENTAL),
            _make_signal("N1", SignalCategory.NEWS),
            _make_signal("R1", SignalCategory.RISK),
        ]
        result = build_stock_report(_make_rating(signals=signals))
        assert len(result.technical_signals) == 1
        assert len(result.fundamental_signals) == 1
        assert len(result.news_signals) == 1
        assert len(result.risk_signals) == 1

    def test_empty_signals_used_produces_empty_category_lists(self):
        # Can't have empty signals_used in Rating, use a single tech signal
        result = build_stock_report(_make_rating())
        total = (
            len(result.technical_signals)
            + len(result.fundamental_signals)
            + len(result.news_signals)
            + len(result.risk_signals)
        )
        assert total == len(_make_rating().signals_used)

    def test_total_signal_count_preserved(self):
        signals = [
            _make_signal("T1", SignalCategory.TECHNICAL),
            _make_signal("T2", SignalCategory.TECHNICAL),
            _make_signal("F1", SignalCategory.FUNDAMENTAL),
            _make_signal("N1", SignalCategory.NEWS),
            _make_signal("R1", SignalCategory.RISK),
            _make_signal("R2", SignalCategory.RISK),
        ]
        result = build_stock_report(_make_rating(signals=signals))
        total = (
            len(result.technical_signals)
            + len(result.fundamental_signals)
            + len(result.news_signals)
            + len(result.risk_signals)
        )
        assert total == 6

    def test_original_signals_list_not_mutated(self):
        sig = _make_signal("T1", SignalCategory.TECHNICAL)
        signals = [sig]
        rating = _make_rating(signals=signals)
        build_stock_report(rating)
        assert len(rating.signals_used) == 1


# ---------------------------------------------------------------------------
# generate_plain_text_report
# ---------------------------------------------------------------------------

class TestGeneratePlainTextReport:
    def test_returns_string(self):
        report = build_stock_report(_make_rating())
        assert isinstance(generate_plain_text_report(report), str)

    def test_returns_non_empty_string(self):
        report = build_stock_report(_make_rating())
        assert len(generate_plain_text_report(report)) > 0

    def test_contains_report_title(self):
        report = build_stock_report(_make_rating())
        assert "STOCK RESEARCH REPORT" in generate_plain_text_report(report)

    def test_contains_ticker(self):
        report = build_stock_report(_make_rating(ticker="TSLA"))
        assert "TSLA" in generate_plain_text_report(report)

    def test_contains_category(self):
        report = build_stock_report(_make_rating(category=RatingCategory.BUY_CANDIDATE, score=72.0))
        assert "Buy Candidate" in generate_plain_text_report(report)

    def test_contains_score(self):
        report = build_stock_report(_make_rating(score=75.0))
        assert "75.0" in generate_plain_text_report(report)

    def test_delegates_to_format_plain_text_report(self):
        from unittest.mock import patch

        report = build_stock_report(_make_rating())
        with patch(
            "app.reports.report_generator.format_plain_text_report",
            return_value="MOCKED",
        ) as mock_fmt:
            result = generate_plain_text_report(report)

        mock_fmt.assert_called_once_with(report)
        assert result == "MOCKED"
