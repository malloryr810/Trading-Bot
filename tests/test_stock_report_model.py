"""
Unit tests for app/models/stock_report.py.

All inputs are built locally — no network calls.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.rating import ConfidenceLevel, RatingCategory
from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength
from app.models.stock_report import StockReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal(
    name: str = "Test Signal",
    category: SignalCategory = SignalCategory.TECHNICAL,
) -> Signal:
    return Signal(
        name=name,
        category=category,
        direction=SignalDirection.NEUTRAL,
        strength=SignalStrength.MODERATE,
        description=f"Description for {name}.",
        score_impact=0.0,
        confidence=0.60,
    )


def _make_report(**overrides) -> StockReport:
    defaults: dict = dict(
        ticker="AAPL",
        final_category=RatingCategory.WATCHLIST,
        score=62.0,
        confidence_level=ConfidenceLevel.MEDIUM,
    )
    defaults.update(overrides)
    return StockReport(**defaults)


# ---------------------------------------------------------------------------
# Creation — required fields
# ---------------------------------------------------------------------------

class TestCreation:
    def test_minimal_valid_report(self):
        report = _make_report()
        assert report.ticker == "AAPL"
        assert report.final_category == RatingCategory.WATCHLIST
        assert report.score == 62.0
        assert report.confidence_level == ConfidenceLevel.MEDIUM

    def test_ticker_normalized_to_uppercase(self):
        report = _make_report(ticker="aapl")
        assert report.ticker == "AAPL"

    def test_ticker_whitespace_stripped(self):
        report = _make_report(ticker="  MSFT  ")
        assert report.ticker == "MSFT"

    def test_all_rating_categories_accepted(self):
        for cat in RatingCategory:
            report = _make_report(final_category=cat)
            assert report.final_category == cat

    def test_all_confidence_levels_accepted(self):
        for level in ConfidenceLevel:
            report = _make_report(confidence_level=level)
            assert report.confidence_level == level


# ---------------------------------------------------------------------------
# Validation — ticker
# ---------------------------------------------------------------------------

class TestTickerValidation:
    def test_empty_ticker_raises(self):
        with pytest.raises(ValidationError, match="ticker"):
            _make_report(ticker="")

    def test_whitespace_only_ticker_raises(self):
        with pytest.raises(ValidationError, match="ticker"):
            _make_report(ticker="   ")

    def test_missing_ticker_raises(self):
        with pytest.raises(ValidationError):
            StockReport(
                final_category=RatingCategory.WATCHLIST,
                score=50.0,
                confidence_level=ConfidenceLevel.MEDIUM,
            )


# ---------------------------------------------------------------------------
# Validation — score
# ---------------------------------------------------------------------------

class TestScoreValidation:
    def test_score_at_zero(self):
        report = _make_report(score=0.0)
        assert report.score == 0.0

    def test_score_at_one_hundred(self):
        report = _make_report(score=100.0)
        assert report.score == 100.0

    def test_score_below_zero_raises(self):
        with pytest.raises(ValidationError):
            _make_report(score=-0.1)

    def test_score_above_one_hundred_raises(self):
        with pytest.raises(ValidationError):
            _make_report(score=100.1)

    def test_missing_score_raises(self):
        with pytest.raises(ValidationError):
            StockReport(
                ticker="AAPL",
                final_category=RatingCategory.WATCHLIST,
                confidence_level=ConfidenceLevel.MEDIUM,
            )


# ---------------------------------------------------------------------------
# Optional fields — defaults
# ---------------------------------------------------------------------------

class TestDefaults:
    def test_company_name_defaults_to_none(self):
        assert _make_report().company_name is None

    def test_current_price_defaults_to_none(self):
        assert _make_report().current_price is None

    def test_technical_summary_defaults_to_none(self):
        assert _make_report().technical_summary is None

    def test_fundamental_summary_defaults_to_none(self):
        assert _make_report().fundamental_summary is None

    def test_news_summary_defaults_to_none(self):
        assert _make_report().news_summary is None

    def test_risk_summary_defaults_to_none(self):
        assert _make_report().risk_summary is None

    def test_buy_trigger_defaults_to_none(self):
        assert _make_report().buy_trigger is None

    def test_sell_or_avoid_trigger_defaults_to_none(self):
        assert _make_report().sell_or_avoid_trigger is None

    def test_data_timestamp_defaults_to_none(self):
        assert _make_report().data_timestamp is None

    def test_data_sources_used_defaults_to_empty_list(self):
        assert _make_report().data_sources_used == []

    def test_key_positive_factors_defaults_to_empty_list(self):
        assert _make_report().key_positive_factors == []

    def test_key_risks_defaults_to_empty_list(self):
        assert _make_report().key_risks == []

    def test_technical_signals_defaults_to_empty_list(self):
        assert _make_report().technical_signals == []

    def test_fundamental_signals_defaults_to_empty_list(self):
        assert _make_report().fundamental_signals == []

    def test_news_signals_defaults_to_empty_list(self):
        assert _make_report().news_signals == []

    def test_risk_signals_defaults_to_empty_list(self):
        assert _make_report().risk_signals == []


# ---------------------------------------------------------------------------
# Optional fields — populated
# ---------------------------------------------------------------------------

class TestPopulatedOptionalFields:
    def test_company_name_stored(self):
        report = _make_report(company_name="Apple Inc.")
        assert report.company_name == "Apple Inc."

    def test_current_price_stored(self):
        report = _make_report(current_price=182.50)
        assert report.current_price == pytest.approx(182.50)

    def test_data_timestamp_stored(self):
        ts = datetime(2024, 6, 1, tzinfo=timezone.utc)
        report = _make_report(data_timestamp=ts)
        assert report.data_timestamp == ts

    def test_data_sources_stored(self):
        report = _make_report(data_sources_used=["yfinance"])
        assert report.data_sources_used == ["yfinance"]

    def test_key_positive_factors_stored(self):
        factors = ["Factor A", "Factor B"]
        report = _make_report(key_positive_factors=factors)
        assert report.key_positive_factors == factors

    def test_key_risks_stored(self):
        risks = ["Risk A", "Risk B"]
        report = _make_report(key_risks=risks)
        assert report.key_risks == risks

    def test_buy_trigger_stored(self):
        report = _make_report(buy_trigger="Wait for score above 65.")
        assert report.buy_trigger == "Wait for score above 65."

    def test_sell_or_avoid_trigger_stored(self):
        report = _make_report(sell_or_avoid_trigger="Reassess below 45.")
        assert report.sell_or_avoid_trigger == "Reassess below 45."

    def test_technical_signals_stored(self):
        sig = _make_signal("SMA Trend", SignalCategory.TECHNICAL)
        report = _make_report(technical_signals=[sig])
        assert len(report.technical_signals) == 1
        assert report.technical_signals[0].name == "SMA Trend"

    def test_fundamental_signals_stored(self):
        sig = _make_signal("P/E Ratio", SignalCategory.FUNDAMENTAL)
        report = _make_report(fundamental_signals=[sig])
        assert len(report.fundamental_signals) == 1

    def test_news_signals_stored(self):
        sig = _make_signal("News Sentiment", SignalCategory.NEWS)
        report = _make_report(news_signals=[sig])
        assert len(report.news_signals) == 1

    def test_risk_signals_stored(self):
        sig = _make_signal("Volatility", SignalCategory.RISK)
        report = _make_report(risk_signals=[sig])
        assert len(report.risk_signals) == 1

    def test_multiple_signals_per_category(self):
        sigs = [_make_signal(f"Sig {i}", SignalCategory.TECHNICAL) for i in range(3)]
        report = _make_report(technical_signals=sigs)
        assert len(report.technical_signals) == 3


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------

class TestImmutability:
    def test_mutating_source_list_does_not_affect_report(self):
        source_list = ["yfinance"]
        report = _make_report(data_sources_used=source_list)
        source_list.append("alpha_vantage")
        assert report.data_sources_used == ["yfinance"]

    def test_mutating_signals_list_does_not_affect_report(self):
        sig = _make_signal()
        signals = [sig]
        report = _make_report(technical_signals=signals)
        signals.clear()
        assert len(report.technical_signals) == 1
