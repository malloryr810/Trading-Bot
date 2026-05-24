"""
Unit tests for app/reports/stock_report.py.

All inputs are built locally — no network calls.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.rating import ConfidenceLevel, Rating, RatingCategory
from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength
from app.reports.stock_report import generate_stock_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal(
    name: str = "Test Signal",
    direction: SignalDirection = SignalDirection.NEUTRAL,
    strength: SignalStrength = SignalStrength.MODERATE,
    score_impact: float = 0.0,
    confidence: float = 0.60,
    category: SignalCategory = SignalCategory.TECHNICAL,
) -> Signal:
    return Signal(
        name=name,
        category=category,
        direction=direction,
        strength=strength,
        description=f"Description for {name}.",
        score_impact=score_impact,
        confidence=confidence,
    )


def _bullish(name: str = "Bullish Signal") -> Signal:
    return _make_signal(
        name=name,
        direction=SignalDirection.BULLISH,
        score_impact=0.20,
        confidence=0.75,
    )


def _bearish(name: str = "Bearish Signal") -> Signal:
    return _make_signal(
        name=name,
        direction=SignalDirection.BEARISH,
        score_impact=-0.20,
        confidence=0.70,
    )


def _neutral(name: str = "Neutral Signal") -> Signal:
    return _make_signal(name=name, direction=SignalDirection.NEUTRAL, score_impact=0.0)


def _make_rating(
    ticker: str = "AAPL",
    score: float = 62.0,
    category: RatingCategory = RatingCategory.WATCHLIST,
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
    technical_score: float = 62.0,
    fundamental_score: float = 0.0,
    positives: list[str] | None = None,
    risks: list[str] | None = None,
    technical_summary: str | None = "Technical score: 62.0/100 based on indicators.",
    fundamental_summary: str | None = None,
    buy_trigger: str | None = "Confirm with fundamentals before entering.",
    sell_trigger: str | None = "Reassess if score falls below 45.",
    signals: list[Signal] | None = None,
    data_sources: list[str] | None = None,
) -> Rating:
    return Rating(
        ticker=ticker,
        final_category=category,
        score=score,
        confidence=confidence,
        explanation=f"Technical-only rating for {ticker} based on 7 signals.",
        technical_score=technical_score,
        fundamental_score=fundamental_score,
        news_score=0.0,
        risk_score=0.0,
        technical_summary=technical_summary,
        fundamental_summary=fundamental_summary,
        key_positive_factors=positives or [],
        key_risks=risks or [],
        buy_trigger=buy_trigger,
        sell_or_avoid_trigger=sell_trigger,
        data_timestamp=datetime(2024, 6, 1, tzinfo=timezone.utc),
        data_sources_used=data_sources or ["yfinance"],
        signals_used=signals or [_neutral()],
    )


def _report(**kwargs) -> str:
    """Convenience wrapper with sensible defaults."""
    return generate_stock_report(
        ticker=kwargs.pop("ticker", "AAPL"),
        rating=kwargs.pop("rating", _make_rating()),
        signals=kwargs.pop("signals", [_neutral()]),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_empty_ticker_raises(self):
        with pytest.raises(ValueError, match="ticker"):
            generate_stock_report("", _make_rating(), [])

    def test_whitespace_ticker_raises(self):
        with pytest.raises(ValueError, match="ticker"):
            generate_stock_report("   ", _make_rating(), [])

    def test_non_string_ticker_raises(self):
        with pytest.raises(ValueError, match="ticker"):
            generate_stock_report(None, _make_rating(), [])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

class TestReturnType:
    def test_returns_string(self):
        assert isinstance(_report(), str)

    def test_returns_non_empty_string(self):
        assert len(_report()) > 0


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

class TestHeader:
    def test_contains_ticker(self):
        assert "AAPL" in _report(ticker="AAPL")

    def test_ticker_normalized_to_uppercase(self):
        out = _report(ticker="aapl")
        assert "AAPL" in out

    def test_contains_report_title(self):
        assert "STOCK RESEARCH REPORT" in _report()

    def test_contains_today_date(self):
        from datetime import date
        assert date.today().isoformat() in _report()

    def test_contains_company_name_when_provided(self):
        assert "Apple Inc." in _report(company_name="Apple Inc.")

    def test_omits_company_name_when_not_provided(self):
        out = _report(company_name=None)
        assert "Apple Inc." not in out

    def test_contains_price_when_provided(self):
        assert "182.50" in _report(current_price=182.50)

    def test_omits_price_when_not_provided(self):
        out = _report(current_price=None)
        assert "Price:" not in out

    def test_contains_data_source_when_provided(self):
        assert "yfinance" in _report(data_sources=["yfinance"])

    def test_omits_data_line_when_no_sources(self):
        rating = _make_rating(data_sources=[])
        out = generate_stock_report("AAPL", rating, [], data_sources=[])
        assert "Data:" not in out


# ---------------------------------------------------------------------------
# Recommendation section
# ---------------------------------------------------------------------------

class TestRecommendation:
    def test_contains_rating_category(self):
        assert "Watchlist" in _report(rating=_make_rating(category=RatingCategory.WATCHLIST))

    def test_contains_score(self):
        assert "62.0 / 100" in _report(rating=_make_rating(score=62.0))

    def test_contains_confidence(self):
        out = _report(rating=_make_rating(confidence=ConfidenceLevel.MEDIUM))
        assert "Medium" in out

    def test_contains_explanation(self):
        assert "Technical-only rating for AAPL" in _report()


# ---------------------------------------------------------------------------
# Score breakdown
# ---------------------------------------------------------------------------

class TestScoreBreakdown:
    def test_contains_technical_score(self):
        assert "62.0 / 100" in _report(rating=_make_rating(technical_score=62.0))

    def test_shows_not_scored_for_zero_fundamental(self):
        assert "(not scored)" in _report(rating=_make_rating(fundamental_score=0.0))

    def test_no_not_scored_tag_when_fundamental_nonzero(self):
        rating = _make_rating(fundamental_score=55.0, score=55.0)
        out = generate_stock_report("AAPL", rating, [_neutral()])
        lines = out.split("\n")
        fundamental_line = next(l for l in lines if "Fundamental:" in l)
        assert "(not scored)" not in fundamental_line

    def test_all_four_sub_score_labels_present(self):
        out = _report()
        assert "Technical:" in out
        assert "Fundamental:" in out
        assert "News:" in out
        assert "Risk:" in out


# ---------------------------------------------------------------------------
# Analysis summaries
# ---------------------------------------------------------------------------

class TestAnalysisSummaries:
    def test_technical_summary_included_when_present(self):
        assert "Technical score:" in _report()

    def test_technical_summary_omitted_when_none(self):
        rating = _make_rating(technical_summary=None)
        out = generate_stock_report("AAPL", rating, [])
        assert "TECHNICAL ANALYSIS" not in out

    def test_fundamental_summary_included_when_present(self):
        rating = _make_rating(fundamental_summary="Fundamental score: 55.0/100.")
        out = generate_stock_report("AAPL", rating, [])
        assert "FUNDAMENTAL ANALYSIS" in out
        assert "Fundamental score: 55.0/100." in out

    def test_fundamental_summary_omitted_when_none(self):
        rating = _make_rating(fundamental_summary=None)
        out = generate_stock_report("AAPL", rating, [])
        assert "FUNDAMENTAL ANALYSIS" not in out

    def test_no_summaries_section_when_all_none(self):
        rating = _make_rating(technical_summary=None, fundamental_summary=None)
        out = generate_stock_report("AAPL", rating, [])
        assert "TECHNICAL ANALYSIS" not in out
        assert "FUNDAMENTAL ANALYSIS" not in out


# ---------------------------------------------------------------------------
# Signals section
# ---------------------------------------------------------------------------

class TestSignalsSection:
    def test_signals_section_heading_always_present(self):
        assert "SIGNALS" in _report(signals=[])

    def test_shows_total_count(self):
        assert "3 signals" in _report(signals=[_bullish(), _bearish(), _neutral()])

    def test_shows_singular_for_one_signal(self):
        assert "1 signal" in _report(signals=[_neutral()])

    def test_shows_bullish_count(self):
        out = _report(signals=[_bullish(), _bullish(), _neutral()])
        assert "2 bullish" in out

    def test_shows_bearish_count(self):
        out = _report(signals=[_bearish(), _neutral()])
        assert "1 bearish" in out

    def test_shows_neutral_count(self):
        out = _report(signals=[_neutral(), _neutral()])
        assert "2 neutral" in out

    def test_shows_signal_name(self):
        sig = _make_signal(name="SMA Trend")
        assert "SMA Trend" in _report(signals=[sig])

    def test_shows_signal_description(self):
        sig = _make_signal(name="SMA Trend")
        assert "Description for SMA Trend." in _report(signals=[sig])

    def test_bullish_indicator_for_bullish_signal(self):
        assert "[+]" in _report(signals=[_bullish()])

    def test_bearish_indicator_for_bearish_signal(self):
        assert "[-]" in _report(signals=[_bearish()])

    def test_neutral_indicator_for_neutral_signal(self):
        assert "[ ]" in _report(signals=[_neutral()])

    def test_empty_signals_list_shows_zero_counts(self):
        out = _report(signals=[])
        assert "0 signals" in out


# ---------------------------------------------------------------------------
# Key strengths
# ---------------------------------------------------------------------------

class TestKeyStrengths:
    def test_section_always_present(self):
        assert "KEY STRENGTHS" in _report()

    def test_shows_positive_factors(self):
        rating = _make_rating(positives=["Price above SMA 200", "RSI neutral"])
        out = generate_stock_report("AAPL", rating, [])
        assert "Price above SMA 200" in out
        assert "RSI neutral" in out

    def test_none_identified_when_empty(self):
        rating = _make_rating(positives=[])
        out = generate_stock_report("AAPL", rating, [])
        lines = out.split("\n")
        strengths_idx = next(i for i, l in enumerate(lines) if "KEY STRENGTHS" in l)
        strengths_block = "\n".join(lines[strengths_idx:strengths_idx + 6])
        assert "(none identified)" in strengths_block

    def test_multiple_factors_all_present(self):
        factors = ["Factor A", "Factor B", "Factor C"]
        rating = _make_rating(positives=factors)
        out = generate_stock_report("AAPL", rating, [])
        for f in factors:
            assert f in out


# ---------------------------------------------------------------------------
# Key risks
# ---------------------------------------------------------------------------

class TestKeyRisks:
    def test_section_always_present(self):
        assert "KEY RISKS" in _report()

    def test_shows_risk_factors(self):
        rating = _make_rating(risks=["RSI overbought", "Below SMA 200"])
        out = generate_stock_report("AAPL", rating, [])
        assert "RSI overbought" in out
        assert "Below SMA 200" in out

    def test_none_identified_when_empty(self):
        rating = _make_rating(risks=[])
        out = generate_stock_report("AAPL", rating, [])
        lines = out.split("\n")
        risks_idx = next(i for i, l in enumerate(lines) if "KEY RISKS" in l)
        risks_block = "\n".join(lines[risks_idx:risks_idx + 6])
        assert "(none identified)" in risks_block


# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------

class TestTriggers:
    def test_section_always_present(self):
        assert "TRIGGERS" in _report()

    def test_buy_trigger_included_when_present(self):
        assert "Confirm with fundamentals" in _report()

    def test_sell_trigger_included_when_present(self):
        assert "Reassess if score falls" in _report()

    def test_no_triggers_message_when_both_none(self):
        rating = _make_rating(buy_trigger=None, sell_trigger=None)
        out = generate_stock_report("AAPL", rating, [])
        assert "no triggers defined" in out

    def test_buy_trigger_label_present(self):
        assert "Buy Trigger:" in _report()

    def test_sell_avoid_label_present(self):
        assert "Sell / Avoid Trigger:" in _report()


# ---------------------------------------------------------------------------
# Disclaimer
# ---------------------------------------------------------------------------

class TestDisclaimer:
    def test_disclaimer_section_present(self):
        assert "DISCLAIMER" in _report()

    def test_not_financial_advice_text_present(self):
        assert "not financial advice" in _report()

    def test_no_trades_text_present(self):
        assert "does not place" in _report()


# ---------------------------------------------------------------------------
# Optional parameters
# ---------------------------------------------------------------------------

class TestOptionalParams:
    def test_works_without_company_name(self):
        out = _report(company_name=None)
        assert isinstance(out, str)

    def test_works_without_current_price(self):
        out = _report(current_price=None)
        assert isinstance(out, str)

    def test_works_without_data_sources_param(self):
        out = generate_stock_report("AAPL", _make_rating(), [_neutral()])
        assert isinstance(out, str)

    def test_data_sources_param_overrides_rating_sources(self):
        rating = _make_rating(data_sources=["yfinance"])
        out = generate_stock_report("AAPL", rating, [], data_sources=["custom-source"])
        assert "custom-source" in out
        assert "yfinance" not in out

    def test_falls_back_to_rating_data_sources_when_param_absent(self):
        rating = _make_rating(data_sources=["yfinance"])
        out = generate_stock_report("AAPL", rating, [])
        assert "yfinance" in out

    def test_empty_signals_list_is_accepted(self):
        out = generate_stock_report("AAPL", _make_rating(), [])
        assert isinstance(out, str)


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------

class TestImmutability:
    def test_signals_list_not_mutated(self):
        signals = [_bullish(), _neutral()]
        original = list(signals)
        _report(signals=signals)
        assert signals == original

    def test_data_sources_list_not_mutated(self):
        sources = ["yfinance"]
        _report(data_sources=sources)
        assert sources == ["yfinance"]


# ---------------------------------------------------------------------------
# Risk conditions section
# ---------------------------------------------------------------------------

class TestRiskConditionsSection:
    def test_risk_conditions_header_always_present(self):
        # RISK CONDITIONS should appear even when risk_summary is None
        out = _report(rating=_make_rating())
        assert "RISK CONDITIONS" in out

    def test_fallback_text_when_no_risk_summary(self):
        rating = _make_rating()  # risk_summary defaults to None
        out = generate_stock_report("AAPL", rating, [])
        assert "not assessed" in out.lower()

    def test_risk_summary_shown_when_present(self):
        rating = Rating(
            ticker="AAPL",
            final_category=RatingCategory.WATCHLIST,
            score=62.0,
            confidence=ConfidenceLevel.MEDIUM,
            explanation="Test.",
            technical_score=62.0,
            risk_score=55.0,
            risk_summary="Risk score: 55.0/100 based on volatility and drawdown signals.",
            key_positive_factors=[],
            key_risks=[],
            data_sources_used=["yfinance"],
            signals_used=[_neutral()],
        )
        out = generate_stock_report("AAPL", rating, [])
        assert "Risk score: 55.0/100" in out
