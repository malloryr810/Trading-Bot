"""
Unit tests for app/reports/templates.py.

All inputs are built locally — no network calls.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.models.rating import ConfidenceLevel, RatingCategory
from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength
from app.models.stock_report import StockReport
from app.reports.templates import format_plain_text_report, format_report_markdown, format_watchlist_markdown
from app.watchlist import WatchlistResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal(
    name: str = "Test Signal",
    category: SignalCategory = SignalCategory.TECHNICAL,
    direction: SignalDirection = SignalDirection.NEUTRAL,
    score_impact: float = 0.0,
) -> Signal:
    return Signal(
        name=name,
        category=category,
        direction=direction,
        strength=SignalStrength.MODERATE,
        description=f"Description for {name}.",
        score_impact=score_impact,
        confidence=0.60,
    )


def _bullish(name: str = "Bullish Signal") -> Signal:
    return _make_signal(name=name, direction=SignalDirection.BULLISH, score_impact=0.2)


def _bearish(name: str = "Bearish Signal") -> Signal:
    return _make_signal(name=name, direction=SignalDirection.BEARISH, score_impact=-0.2)


def _neutral(name: str = "Neutral Signal") -> Signal:
    return _make_signal(name=name, direction=SignalDirection.NEUTRAL)


def _make_report(**overrides) -> StockReport:
    defaults: dict = dict(
        ticker="AAPL",
        final_category=RatingCategory.WATCHLIST,
        score=62.0,
        confidence_level=ConfidenceLevel.MEDIUM,
        technical_summary="Technical score: 62.0/100 based on indicators.",
        data_sources_used=["yfinance"],
        buy_trigger="Wait for score above 65.",
        sell_or_avoid_trigger="Reassess if score falls below 45.",
        data_timestamp=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return StockReport(**defaults)


def _format(**overrides) -> str:
    return format_plain_text_report(_make_report(**overrides))


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

class TestReturnType:
    def test_returns_string(self):
        assert isinstance(_format(), str)

    def test_returns_non_empty_string(self):
        assert len(_format()) > 0


# ---------------------------------------------------------------------------
# Header section
# ---------------------------------------------------------------------------

class TestHeader:
    def test_contains_report_title(self):
        assert "STOCK RESEARCH REPORT" in _format()

    def test_contains_ticker(self):
        assert "AAPL" in _format()

    def test_ticker_in_header(self):
        out = _format(ticker="MSFT")
        assert "MSFT" in out

    def test_contains_today_date(self):
        assert date.today().isoformat() in _format()

    def test_contains_company_name_when_provided(self):
        assert "Apple Inc." in _format(company_name="Apple Inc.")

    def test_omits_company_name_when_not_provided(self):
        assert "Apple Inc." not in _format(company_name=None)

    def test_contains_price_when_provided(self):
        assert "182.50" in _format(current_price=182.50)

    def test_omits_price_line_when_not_provided(self):
        assert "Price:" not in _format(current_price=None)

    def test_contains_data_source(self):
        assert "yfinance" in _format(data_sources_used=["yfinance"])

    def test_omits_data_line_when_no_sources(self):
        out = format_plain_text_report(StockReport(
            ticker="AAPL",
            final_category=RatingCategory.WATCHLIST,
            score=50.0,
            confidence_level=ConfidenceLevel.MEDIUM,
            data_sources_used=[],
        ))
        assert "Data:" not in out

    def test_contains_data_timestamp_when_provided(self):
        assert "2024-06-01" in _format()

    def test_omits_as_of_line_when_no_timestamp(self):
        out = _format(data_timestamp=None)
        assert "As of:" not in out


# ---------------------------------------------------------------------------
# Recommendation section
# ---------------------------------------------------------------------------

class TestRecommendation:
    def test_recommendation_header_present(self):
        assert "RECOMMENDATION" in _format()

    def test_contains_rating_category(self):
        assert "Watchlist" in _format(final_category=RatingCategory.WATCHLIST)

    def test_contains_strong_buy_category(self):
        assert "Strong Buy Candidate" in _format(
            final_category=RatingCategory.STRONG_BUY_CANDIDATE, score=90.0
        )

    def test_contains_score(self):
        assert "62.0 / 100" in _format(score=62.0)

    def test_contains_confidence(self):
        assert "Medium" in _format(confidence_level=ConfidenceLevel.MEDIUM)

    def test_confidence_high(self):
        assert "High" in _format(confidence_level=ConfidenceLevel.HIGH)

    def test_confidence_low(self):
        assert "Low" in _format(confidence_level=ConfidenceLevel.LOW)


# ---------------------------------------------------------------------------
# Analysis summaries
# ---------------------------------------------------------------------------

class TestAnalysisSummaries:
    def test_technical_summary_included_when_present(self):
        assert "TECHNICAL ANALYSIS" in _format()

    def test_technical_summary_text_shown(self):
        assert "62.0/100 based on indicators" in _format()

    def test_technical_summary_omitted_when_none(self):
        out = _format(technical_summary=None)
        assert "TECHNICAL ANALYSIS" not in out

    def test_fundamental_summary_included_when_present(self):
        out = _format(fundamental_summary="Fundamental score: 55.0/100.")
        assert "FUNDAMENTAL ANALYSIS" in out
        assert "Fundamental score: 55.0/100." in out

    def test_fundamental_summary_omitted_when_none(self):
        out = _format(fundamental_summary=None)
        assert "FUNDAMENTAL ANALYSIS" not in out

    def test_news_summary_included_when_present(self):
        out = _format(news_summary="News score: 60.0/100.")
        assert "NEWS / SENTIMENT" in out

    def test_news_summary_omitted_when_none(self):
        out = _format(news_summary=None)
        assert "NEWS / SENTIMENT" not in out

    def test_risk_conditions_header_present(self):
        assert "RISK CONDITIONS" in _format()

    def test_risk_fallback_text_when_no_risk_summary(self):
        out = _format(risk_summary=None)
        assert "not assessed" in out.lower()

    def test_risk_summary_shown_when_provided(self):
        out = _format(risk_summary="Risk score: 55.0/100 based on volatility.")
        assert "Risk score: 55.0/100 based on volatility." in out


# ---------------------------------------------------------------------------
# Signals section
# ---------------------------------------------------------------------------

class TestSignalsSection:
    def test_signals_header_present(self):
        assert "SIGNALS" in _format()

    def test_zero_signals_shown(self):
        report = _make_report(technical_signals=[], fundamental_signals=[], news_signals=[], risk_signals=[])
        out = format_plain_text_report(report)
        assert "0 signals" in out

    def test_signal_count_shown(self):
        report = _make_report(
            technical_signals=[_bullish(), _bearish()],
            fundamental_signals=[_neutral()],
        )
        out = format_plain_text_report(report)
        assert "3 signals" in out

    def test_singular_for_one_signal(self):
        report = _make_report(technical_signals=[_neutral()])
        out = format_plain_text_report(report)
        assert "1 signal" in out

    def test_bullish_indicator_present(self):
        report = _make_report(technical_signals=[_bullish()])
        assert "[+]" in format_plain_text_report(report)

    def test_bearish_indicator_present(self):
        report = _make_report(technical_signals=[_bearish()])
        assert "[-]" in format_plain_text_report(report)

    def test_neutral_indicator_present(self):
        report = _make_report(technical_signals=[_neutral()])
        assert "[ ]" in format_plain_text_report(report)

    def test_signal_name_shown(self):
        report = _make_report(technical_signals=[_make_signal("SMA Trend")])
        assert "SMA Trend" in format_plain_text_report(report)

    def test_signal_description_shown(self):
        report = _make_report(technical_signals=[_make_signal("SMA Trend")])
        assert "Description for SMA Trend." in format_plain_text_report(report)

    def test_signals_from_all_categories_shown(self):
        report = _make_report(
            technical_signals=[_make_signal("TechSig", SignalCategory.TECHNICAL)],
            fundamental_signals=[_make_signal("FundSig", SignalCategory.FUNDAMENTAL)],
            news_signals=[_make_signal("NewsSig", SignalCategory.NEWS)],
            risk_signals=[_make_signal("RiskSig", SignalCategory.RISK)],
        )
        out = format_plain_text_report(report)
        assert "TechSig" in out
        assert "FundSig" in out
        assert "NewsSig" in out
        assert "RiskSig" in out

    def test_technical_signals_appear_before_fundamental(self):
        report = _make_report(
            technical_signals=[_make_signal("TechSig", SignalCategory.TECHNICAL)],
            fundamental_signals=[_make_signal("FundSig", SignalCategory.FUNDAMENTAL)],
        )
        out = format_plain_text_report(report)
        assert out.index("TechSig") < out.index("FundSig")

    def test_fundamental_signals_appear_before_news(self):
        report = _make_report(
            fundamental_signals=[_make_signal("FundSig", SignalCategory.FUNDAMENTAL)],
            news_signals=[_make_signal("NewsSig", SignalCategory.NEWS)],
        )
        out = format_plain_text_format = format_plain_text_report(report)
        assert out.index("FundSig") < out.index("NewsSig")

    def test_news_signals_appear_before_risk(self):
        report = _make_report(
            news_signals=[_make_signal("NewsSig", SignalCategory.NEWS)],
            risk_signals=[_make_signal("RiskSig", SignalCategory.RISK)],
        )
        out = format_plain_text_report(report)
        assert out.index("NewsSig") < out.index("RiskSig")

    def test_bullish_count_shown(self):
        report = _make_report(technical_signals=[_bullish(), _bullish(), _neutral()])
        out = format_plain_text_report(report)
        assert "2 bullish" in out

    def test_bearish_count_shown(self):
        report = _make_report(technical_signals=[_bearish(), _neutral()])
        out = format_plain_text_report(report)
        assert "1 bearish" in out


# ---------------------------------------------------------------------------
# Key strengths
# ---------------------------------------------------------------------------

class TestKeyStrengths:
    def test_section_present(self):
        assert "KEY STRENGTHS" in _format()

    def test_factors_shown(self):
        out = _format(key_positive_factors=["Price above SMA 200", "RSI neutral"])
        assert "Price above SMA 200" in out
        assert "RSI neutral" in out

    def test_none_identified_when_empty(self):
        out = _format(key_positive_factors=[])
        lines = out.split("\n")
        idx = next(i for i, l in enumerate(lines) if "KEY STRENGTHS" in l)
        block = "\n".join(lines[idx:idx + 6])
        assert "(none identified)" in block


# ---------------------------------------------------------------------------
# Key risks
# ---------------------------------------------------------------------------

class TestKeyRisks:
    def test_section_present(self):
        assert "KEY RISKS" in _format()

    def test_risks_shown(self):
        out = _format(key_risks=["RSI overbought", "Below SMA 200"])
        assert "RSI overbought" in out
        assert "Below SMA 200" in out

    def test_none_identified_when_empty(self):
        out = _format(key_risks=[])
        lines = out.split("\n")
        idx = next(i for i, l in enumerate(lines) if "KEY RISKS" in l)
        block = "\n".join(lines[idx:idx + 6])
        assert "(none identified)" in block


# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------

class TestTriggers:
    def test_section_present(self):
        assert "TRIGGERS" in _format()

    def test_buy_trigger_shown(self):
        assert "Wait for score above 65." in _format()

    def test_sell_trigger_shown(self):
        assert "Reassess if score falls below 45." in _format()

    def test_buy_trigger_label_present(self):
        assert "Buy Trigger:" in _format()

    def test_sell_avoid_label_present(self):
        assert "Sell / Avoid Trigger:" in _format()

    def test_no_triggers_message_when_both_none(self):
        out = _format(buy_trigger=None, sell_or_avoid_trigger=None)
        assert "no triggers defined" in out

    def test_buy_trigger_shown_without_sell_trigger(self):
        out = _format(buy_trigger="Enter above 65.", sell_or_avoid_trigger=None)
        assert "Enter above 65." in out
        assert "Sell / Avoid Trigger:" not in out


# ---------------------------------------------------------------------------
# Disclaimer
# ---------------------------------------------------------------------------

class TestDisclaimer:
    def test_disclaimer_section_present(self):
        assert "DISCLAIMER" in _format()

    def test_not_financial_advice(self):
        assert "not financial advice" in _format()

    def test_no_trades_text(self):
        assert "does not place" in _format()


# ===========================================================================
# format_report_markdown tests
# ===========================================================================

def _md(**overrides) -> str:
    return format_report_markdown(_make_report(**overrides))


class TestMarkdownReturnType:
    def test_returns_string(self):
        assert isinstance(_md(), str)

    def test_returns_non_empty_string(self):
        assert len(_md()) > 0


class TestMarkdownHeader:
    def test_h1_title_present(self):
        assert "# AAPL" in _md()

    def test_h1_contains_report_label(self):
        assert "Stock Research Report" in _md()

    def test_contains_ticker(self):
        assert "AAPL" in _md(ticker="AAPL")

    def test_contains_company_name_when_provided(self):
        assert "Apple Inc." in _md(company_name="Apple Inc.")

    def test_omits_company_name_when_not_provided(self):
        assert "Apple Inc." not in _md(company_name=None)

    def test_contains_today_date(self):
        assert date.today().isoformat() in _md()

    def test_contains_price_when_provided(self):
        assert "182.50" in _md(current_price=182.50)

    def test_omits_price_when_not_provided(self):
        assert "Price:" not in _md(current_price=None)

    def test_contains_data_timestamp_when_provided(self):
        assert "2024-06-01" in _md()

    def test_omits_as_of_when_no_timestamp(self):
        assert "As of:" not in _md(data_timestamp=None)

    def test_contains_data_source(self):
        assert "yfinance" in _md(data_sources_used=["yfinance"])

    def test_omits_data_line_when_no_sources(self):
        out = format_report_markdown(StockReport(
            ticker="AAPL",
            final_category=RatingCategory.WATCHLIST,
            score=50.0,
            confidence_level=ConfidenceLevel.MEDIUM,
            data_sources_used=[],
        ))
        assert "Data:" not in out


class TestMarkdownRecommendation:
    def test_recommendation_section_present(self):
        assert "## Recommendation" in _md()

    def test_contains_rating_category(self):
        assert "Watchlist" in _md(final_category=RatingCategory.WATCHLIST)

    def test_contains_strong_buy_category(self):
        assert "Strong Buy Candidate" in _md(
            final_category=RatingCategory.STRONG_BUY_CANDIDATE, score=90.0
        )

    def test_contains_score(self):
        assert "62.0 / 100" in _md(score=62.0)

    def test_contains_confidence(self):
        assert "Medium" in _md(confidence_level=ConfidenceLevel.MEDIUM)

    def test_contains_high_confidence(self):
        assert "High" in _md(confidence_level=ConfidenceLevel.HIGH)

    def test_contains_low_confidence(self):
        assert "Low" in _md(confidence_level=ConfidenceLevel.LOW)

    def test_recommendation_table_uses_markdown_pipe_syntax(self):
        out = _md()
        assert "| Rating |" in out
        assert "| Score |" in out
        assert "| Confidence |" in out


class TestMarkdownAnalysisSummaries:
    def test_technical_section_present_when_summary_provided(self):
        assert "## Technical Analysis" in _md()

    def test_technical_summary_text_shown(self):
        assert "62.0/100 based on indicators" in _md()

    def test_technical_section_omitted_when_none(self):
        assert "## Technical Analysis" not in _md(technical_summary=None)

    def test_fundamental_section_present_when_provided(self):
        out = _md(fundamental_summary="Fundamentals look solid.")
        assert "## Fundamental Analysis" in out
        assert "Fundamentals look solid." in out

    def test_fundamental_section_omitted_when_none(self):
        assert "## Fundamental Analysis" not in _md(fundamental_summary=None)

    def test_news_section_present_when_provided(self):
        out = _md(news_summary="Mostly neutral coverage.")
        assert "## News / Sentiment" in out

    def test_news_section_omitted_when_none(self):
        assert "## News / Sentiment" not in _md(news_summary=None)

    def test_risk_section_present(self):
        assert "## Risk Conditions" in _md()

    def test_risk_fallback_text_when_no_risk_summary(self):
        out = _md(risk_summary=None)
        assert "not assessed" in out.lower()

    def test_risk_summary_shown_when_provided(self):
        out = _md(risk_summary="Elevated volatility detected.")
        assert "Elevated volatility detected." in out


class TestMarkdownKeyStrengths:
    def test_section_present(self):
        assert "## Key Strengths" in _md()

    def test_factors_rendered_as_bullets(self):
        out = _md(key_positive_factors=["Above SMA 200", "RSI neutral"])
        assert "- Above SMA 200" in out
        assert "- RSI neutral" in out

    def test_none_identified_when_empty(self):
        assert "none identified" in _md(key_positive_factors=[])


class TestMarkdownKeyRisks:
    def test_section_present(self):
        assert "## Key Risks" in _md()

    def test_risks_rendered_as_bullets(self):
        out = _md(key_risks=["RSI overbought", "Below SMA 200"])
        assert "- RSI overbought" in out
        assert "- Below SMA 200" in out

    def test_none_identified_when_empty(self):
        assert "none identified" in _md(key_risks=[])


class TestMarkdownTriggers:
    def test_section_present(self):
        assert "## Triggers" in _md()

    def test_buy_trigger_shown(self):
        assert "Wait for score above 65." in _md()

    def test_sell_trigger_shown(self):
        assert "Reassess if score falls below 45." in _md()

    def test_buy_trigger_uses_bold_label(self):
        assert "**Buy Trigger:**" in _md()

    def test_sell_trigger_uses_bold_label(self):
        assert "**Sell / Avoid Trigger:**" in _md()

    def test_no_triggers_message_when_both_none(self):
        assert "no triggers defined" in _md(buy_trigger=None, sell_or_avoid_trigger=None)

    def test_sell_trigger_omitted_when_only_buy_set(self):
        out = _md(buy_trigger="Enter above 65.", sell_or_avoid_trigger=None)
        assert "Enter above 65." in out
        assert "Sell / Avoid Trigger:" not in out


class TestMarkdownMetadata:
    def test_metadata_section_present_when_timestamp_provided(self):
        assert "## Metadata" in _md()

    def test_metadata_contains_timestamp(self):
        assert "2024-06-01" in _md()

    def test_metadata_contains_data_source(self):
        assert "yfinance" in _md(data_sources_used=["yfinance"])

    def test_metadata_section_omitted_when_no_data(self):
        out = format_report_markdown(StockReport(
            ticker="AAPL",
            final_category=RatingCategory.WATCHLIST,
            score=50.0,
            confidence_level=ConfidenceLevel.MEDIUM,
            data_sources_used=[],
            data_timestamp=None,
        ))
        assert "## Metadata" not in out


class TestMarkdownDisclaimer:
    def test_disclaimer_separator_present(self):
        assert "---" in _md()

    def test_not_financial_advice(self):
        assert "not financial advice" in _md()

    def test_does_not_place_trades(self):
        assert "does not place" in _md()

    def test_disclaimer_uses_italic_markdown(self):
        out = _md()
        assert "*This report" in out


# ===========================================================================
# format_watchlist_markdown tests
# ===========================================================================

def _make_wl_success(
    ticker: str = "AAPL",
    company_name: str | None = "Apple Inc.",
    category: RatingCategory = RatingCategory.WATCHLIST,
    score: float = 62.0,
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
    current_price: float | None = 182.50,
) -> WatchlistResult:
    return WatchlistResult(
        ticker=ticker,
        company_name=company_name,
        final_category=category,
        score=score,
        confidence_level=confidence,
        current_price=current_price,
    )


def _make_wl_failure(ticker: str = "BAD", message: str = "fetch failed") -> WatchlistResult:
    return WatchlistResult(ticker=ticker, error_message=message)


def _wl_md(results: list[WatchlistResult] | None = None) -> str:
    if results is None:
        results = [_make_wl_success()]
    return format_watchlist_markdown(results)


class TestWatchlistMarkdownReturnType:
    def test_returns_string(self):
        assert isinstance(_wl_md(), str)

    def test_returns_non_empty_string(self):
        assert len(_wl_md()) > 0


class TestWatchlistMarkdownHeader:
    def test_h1_title_present(self):
        assert _wl_md().startswith("# Watchlist Report")

    def test_contains_generated_date(self):
        assert date.today().isoformat() in _wl_md()

    def test_contains_tickers_scanned_count(self):
        results = [_make_wl_success("AAPL"), _make_wl_success("MSFT")]
        assert "Tickers scanned:** 2" in format_watchlist_markdown(results)

    def test_contains_success_count(self):
        results = [_make_wl_success("AAPL"), _make_wl_failure("BAD")]
        out = format_watchlist_markdown(results)
        assert "Success: 1" in out

    def test_contains_failed_count(self):
        results = [_make_wl_success("AAPL"), _make_wl_failure("BAD")]
        out = format_watchlist_markdown(results)
        assert "Failed: 1" in out


class TestWatchlistMarkdownResultsTable:
    def test_table_header_ticker_column(self):
        assert "| Ticker |" in _wl_md()

    def test_table_header_category_column(self):
        assert "Category" in _wl_md()

    def test_table_header_score_column(self):
        assert "Score" in _wl_md()

    def test_table_header_confidence_column(self):
        assert "Confidence" in _wl_md()

    def test_table_header_price_column(self):
        assert "Price" in _wl_md()

    def test_table_separator_row_present(self):
        assert "|--------|" in _wl_md()

    def test_success_ticker_appears_in_table(self):
        assert "AAPL" in _wl_md([_make_wl_success("AAPL")])

    def test_score_value_in_table(self):
        assert "72.5" in _wl_md([_make_wl_success(score=72.5)])

    def test_category_value_in_table(self):
        out = _wl_md([_make_wl_success(category=RatingCategory.BUY_CANDIDATE)])
        assert "Buy Candidate" in out

    def test_confidence_value_in_table(self):
        out = _wl_md([_make_wl_success(confidence=ConfidenceLevel.HIGH)])
        assert "High" in out

    def test_price_value_in_table(self):
        out = _wl_md([_make_wl_success(current_price=182.50)])
        assert "182.50" in out

    def test_company_name_in_table(self):
        out = _wl_md([_make_wl_success(company_name="Microsoft Corp.")])
        assert "Microsoft Corp." in out

    def test_missing_price_shown_as_dash_placeholder(self):
        out = _wl_md([_make_wl_success(current_price=None)])
        assert "—" in out

    def test_missing_company_shown_as_dash_placeholder(self):
        out = _wl_md([_make_wl_success(company_name=None)])
        assert "—" in out

    def test_multiple_tickers_all_appear(self):
        results = [
            _make_wl_success("AAPL"),
            _make_wl_success("MSFT"),
            _make_wl_success("NVDA"),
        ]
        out = format_watchlist_markdown(results)
        assert "AAPL" in out
        assert "MSFT" in out
        assert "NVDA" in out

    def test_results_section_heading_present(self):
        assert "## Results" in _wl_md()


class TestWatchlistMarkdownEmpty:
    def test_empty_results_does_not_crash(self):
        out = format_watchlist_markdown([])
        assert isinstance(out, str)
        assert len(out) > 0

    def test_empty_results_starts_with_h1(self):
        out = format_watchlist_markdown([])
        assert out.startswith("# Watchlist Report")

    def test_empty_results_contains_no_results_message(self):
        out = format_watchlist_markdown([])
        assert "no results" in out.lower()

    def test_empty_results_no_failures_section(self):
        out = format_watchlist_markdown([])
        assert "## Failures" not in out


class TestWatchlistMarkdownFailures:
    def test_failures_section_present_when_failures_exist(self):
        assert "## Failures" in _wl_md([_make_wl_failure("BAD", "network error")])

    def test_failed_ticker_in_failures_table(self):
        assert "BAD" in _wl_md([_make_wl_failure("BAD", "network error")])

    def test_error_message_in_failures_table(self):
        assert "network error" in _wl_md([_make_wl_failure("BAD", "network error")])

    def test_failures_section_absent_when_no_failures(self):
        assert "## Failures" not in _wl_md([_make_wl_success()])

    def test_mixed_results_success_in_table(self):
        out = _wl_md([_make_wl_success("AAPL"), _make_wl_failure("BAD")])
        assert "AAPL" in out
        assert "## Results" in out

    def test_mixed_results_failure_in_failures_section(self):
        out = _wl_md([_make_wl_success("AAPL"), _make_wl_failure("BAD", "timeout")])
        assert "## Failures" in out
        assert "timeout" in out

    def test_only_failures_results_section_shows_no_results(self):
        out = _wl_md([_make_wl_failure("BAD")])
        assert "no results" in out.lower()

    def test_failures_table_has_header(self):
        out = _wl_md([_make_wl_failure("BAD")])
        assert "| Ticker |" in out
        assert "| Error |" in out


class TestWatchlistMarkdownDisclaimer:
    def test_disclaimer_separator_present(self):
        assert "---" in _wl_md()

    def test_not_financial_advice(self):
        assert "not financial advice" in _wl_md()

    def test_does_not_place_trades(self):
        assert "does not place" in _wl_md()

    def test_disclaimer_uses_italic_markdown(self):
        assert "*This report" in _wl_md()
