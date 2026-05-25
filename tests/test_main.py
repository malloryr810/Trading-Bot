"""
Unit tests for app/main.py.

All pipeline functions are mocked — no network calls.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.analysis.fundamentals_analysis import FundamentalAnalysisError
from app.analysis.risk_analysis import RiskAnalysisError
from app.analysis.scoring import ScoringError
from app.analysis.technicals import TechnicalAnalysisError
from app.data.fundamentals import FundamentalDataFetchError
from app.data.market_data import DataFetchError
from app.data.news_data import NewsFetchError
from app.main import analyze_ticker, format_rating_output, main
from app.models.rating import ConfidenceLevel, Rating, RatingCategory
from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal(
    score_impact: float = 0.10,
    direction: SignalDirection = SignalDirection.BULLISH,
    category: SignalCategory = SignalCategory.TECHNICAL,
) -> Signal:
    return Signal(
        name="Test Signal",
        category=category,
        direction=direction,
        strength=SignalStrength.MODERATE,
        description="A test signal.",
        score_impact=score_impact,
        confidence=0.65,
    )


def _make_rating(
    category: RatingCategory = RatingCategory.WATCHLIST,
    score: float = 60.0,
    positives: list[str] | None = None,
    risks: list[str] | None = None,
) -> Rating:
    return Rating(
        ticker="AAPL",
        final_category=category,
        score=score,
        confidence=ConfidenceLevel.MEDIUM,
        explanation="Composite rating for AAPL based on 7 technical and 5 fundamental and 4 risk signals.",
        technical_score=score,
        technical_summary="Technical score: 60.0/100 based on indicators.",
        key_positive_factors=positives or [],
        key_risks=risks or [],
        buy_trigger="Consider after fundamentals confirm.",
        sell_or_avoid_trigger="Reassess if score falls below 45.",
        data_timestamp=datetime(2024, 6, 1, tzinfo=timezone.utc),
        data_sources_used=["yfinance"],
        signals_used=[_make_signal()],
    )


def _make_mock_fundamentals(beta: float | None = 1.1) -> MagicMock:
    m = MagicMock()
    m.beta = beta
    return m


# Patch targets
_FETCH        = "app.main.get_price_history"
_FETCH_FUND   = "app.main.get_company_fundamentals"
_FETCH_NEWS   = "app.main.get_recent_news"
_ANALYZE_NEWS = "app.main.analyze_news"
_CALC         = "app.main.calculate_technical_indicators"
_SUMM         = "app.main.summarize_technical_signals"
_BUILD_TECH   = "app.main.build_technical_signals"
_BUILD_FUND   = "app.main.build_fundamental_signals"
_RISK         = "app.main.analyze_risk_conditions"
_SCORE        = "app.main.score_signals"


def _mock_pipeline(rating: Rating | None = None):
    """Context manager that patches the entire analysis pipeline."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with (
            patch(_FETCH,        return_value=MagicMock()) as mock_fetch,
            patch(_FETCH_FUND,   return_value=_make_mock_fundamentals()) as mock_fetch_fund,
            patch(_FETCH_NEWS,   return_value=[]) as mock_fetch_news,
            patch(_ANALYZE_NEWS, return_value=[_make_signal(category=SignalCategory.NEWS)]) as mock_analyze_news,
            patch(_CALC,         return_value=MagicMock()) as mock_calc,
            patch(_SUMM,         return_value=MagicMock()) as mock_summ,
            patch(_BUILD_TECH,   return_value=[_make_signal()]) as mock_build_tech,
            patch(_BUILD_FUND,   return_value=[_make_signal(category=SignalCategory.FUNDAMENTAL)]) as mock_build_fund,
            patch(_RISK,         return_value=[_make_signal(category=SignalCategory.RISK)]) as mock_risk,
            patch(_SCORE,        return_value=rating or _make_rating()) as mock_score,
        ):
            yield (
                mock_fetch, mock_fetch_fund, mock_fetch_news, mock_analyze_news,
                mock_calc, mock_summ,
                mock_build_tech, mock_build_fund, mock_risk,
                mock_score,
            )

    return _ctx()


# ---------------------------------------------------------------------------
# main() — argument handling
# ---------------------------------------------------------------------------

class TestMainArguments:
    def test_no_ticker_returns_1(self):
        assert main([]) == 1

    def test_no_ticker_prints_usage(self, capsys):
        main([])
        assert "Usage" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# main() — success path
# ---------------------------------------------------------------------------

class TestMainSuccess:
    def test_returns_0_on_success(self):
        with _mock_pipeline():
            assert main(["AAPL"]) == 0

    def test_prints_output_on_success(self, capsys):
        with _mock_pipeline():
            main(["AAPL"])
        out = capsys.readouterr().out
        assert "STOCK RESEARCH REPORT" in out


# ---------------------------------------------------------------------------
# main() — error handling
# ---------------------------------------------------------------------------

class TestMainErrors:
    def test_data_fetch_error_returns_1(self, capsys):
        with patch(_FETCH, side_effect=DataFetchError("bad ticker")):
            result = main(["INVALID"])
        assert result == 1
        assert "Error fetching" in capsys.readouterr().err

    def test_fundamental_fetch_error_returns_1(self, capsys):
        with (
            patch(_FETCH, return_value=MagicMock()),
            patch(_FETCH_FUND, side_effect=FundamentalDataFetchError("no data")),
        ):
            result = main(["AAPL"])
        assert result == 1
        assert "fundamental" in capsys.readouterr().err.lower()

    def test_technical_analysis_error_returns_1(self, capsys):
        with (
            patch(_FETCH,      return_value=MagicMock()),
            patch(_FETCH_FUND, return_value=_make_mock_fundamentals()),
            patch(_CALC, side_effect=TechnicalAnalysisError("bad data")),
        ):
            result = main(["AAPL"])
        assert result == 1
        assert "technical analysis" in capsys.readouterr().err.lower()

    def test_fundamental_analysis_error_returns_1(self, capsys):
        with (
            patch(_FETCH,      return_value=MagicMock()),
            patch(_FETCH_FUND, return_value=_make_mock_fundamentals()),
            patch(_CALC,       return_value=MagicMock()),
            patch(_SUMM,       return_value=MagicMock()),
            patch(_BUILD_TECH, return_value=[_make_signal()]),
            patch(_BUILD_FUND, side_effect=FundamentalAnalysisError("bad fundamentals")),
        ):
            result = main(["AAPL"])
        assert result == 1
        assert "fundamental analysis" in capsys.readouterr().err.lower()

    def test_risk_analysis_error_returns_1(self, capsys):
        with (
            patch(_FETCH,      return_value=MagicMock()),
            patch(_FETCH_FUND, return_value=_make_mock_fundamentals()),
            patch(_CALC,       return_value=MagicMock()),
            patch(_SUMM,       return_value=MagicMock()),
            patch(_BUILD_TECH, return_value=[_make_signal()]),
            patch(_BUILD_FUND, return_value=[_make_signal(category=SignalCategory.FUNDAMENTAL)]),
            patch(_RISK,       side_effect=RiskAnalysisError("bad risk")),
        ):
            result = main(["AAPL"])
        assert result == 1
        assert "risk analysis" in capsys.readouterr().err.lower()

    def test_scoring_error_returns_1(self, capsys):
        with (
            patch(_FETCH,      return_value=MagicMock()),
            patch(_FETCH_FUND, return_value=_make_mock_fundamentals()),
            patch(_CALC,       return_value=MagicMock()),
            patch(_SUMM,       return_value=MagicMock()),
            patch(_BUILD_TECH, return_value=[_make_signal()]),
            patch(_BUILD_FUND, return_value=[_make_signal(category=SignalCategory.FUNDAMENTAL)]),
            patch(_RISK,       return_value=[_make_signal(category=SignalCategory.RISK)]),
            patch(_SCORE,      side_effect=ScoringError("bad signals")),
        ):
            result = main(["AAPL"])
        assert result == 1
        assert "scoring" in capsys.readouterr().err.lower()


# ---------------------------------------------------------------------------
# analyze_ticker()
# ---------------------------------------------------------------------------

class TestAnalyzeTicker:
    def test_returns_rating(self):
        with _mock_pipeline() as mocks:
            result = analyze_ticker("AAPL")
        assert isinstance(result, Rating)

    def test_calls_pipeline_in_order(self):
        call_order: list[str] = []

        fund_mock = _make_mock_fundamentals()

        with (
            patch(_FETCH,        side_effect=lambda *a, **kw: call_order.append("fetch") or MagicMock()),
            patch(_FETCH_FUND,   side_effect=lambda *a, **kw: call_order.append("fetch_fund") or fund_mock),
            patch(_FETCH_NEWS,   side_effect=lambda *a, **kw: call_order.append("fetch_news") or []),
            patch(_CALC,         side_effect=lambda *a, **kw: call_order.append("calc") or MagicMock()),
            patch(_SUMM,         side_effect=lambda *a, **kw: call_order.append("summ") or MagicMock()),
            patch(_BUILD_TECH,   side_effect=lambda *a, **kw: call_order.append("build_tech") or [_make_signal()]),
            patch(_BUILD_FUND,   side_effect=lambda *a, **kw: call_order.append("build_fund") or []),
            patch(_RISK,         side_effect=lambda *a, **kw: call_order.append("risk") or []),
            patch(_ANALYZE_NEWS, side_effect=lambda *a, **kw: call_order.append("analyze_news") or []),
            patch(_SCORE,        side_effect=lambda **kw: call_order.append("score") or _make_rating()),
        ):
            analyze_ticker("AAPL")

        assert call_order == [
            "fetch", "fetch_fund", "fetch_news",
            "calc", "summ",
            "build_tech", "build_fund", "risk", "analyze_news",
            "score",
        ]

    def test_passes_yfinance_as_data_source(self):
        with _mock_pipeline() as mocks:
            analyze_ticker("AAPL")
        mock_score = mocks[-1]
        call_kwargs = mock_score.call_args.kwargs
        assert "yfinance" in call_kwargs["data_sources_used"]

    def test_passes_beta_from_fundamentals_to_risk(self):
        fund_mock = _make_mock_fundamentals(beta=1.3)
        with (
            patch(_FETCH,        return_value=MagicMock()),
            patch(_FETCH_FUND,   return_value=fund_mock),
            patch(_FETCH_NEWS,   return_value=[]),
            patch(_CALC,         return_value=MagicMock()),
            patch(_SUMM,         return_value=MagicMock()),
            patch(_BUILD_TECH,   return_value=[_make_signal()]),
            patch(_BUILD_FUND,   return_value=[]),
            patch(_RISK,         return_value=[]) as mock_risk,
            patch(_ANALYZE_NEWS, return_value=[]),
            patch(_SCORE,        return_value=_make_rating()),
        ):
            analyze_ticker("AAPL")
        call_kwargs = mock_risk.call_args.kwargs
        assert call_kwargs.get("beta") == pytest.approx(1.3)

    def test_passes_none_beta_when_fundamentals_has_no_beta(self):
        fund_mock = _make_mock_fundamentals(beta=None)
        with (
            patch(_FETCH,        return_value=MagicMock()),
            patch(_FETCH_FUND,   return_value=fund_mock),
            patch(_FETCH_NEWS,   return_value=[]),
            patch(_CALC,         return_value=MagicMock()),
            patch(_SUMM,         return_value=MagicMock()),
            patch(_BUILD_TECH,   return_value=[_make_signal()]),
            patch(_BUILD_FUND,   return_value=[]),
            patch(_RISK,         return_value=[]) as mock_risk,
            patch(_ANALYZE_NEWS, return_value=[]),
            patch(_SCORE,        return_value=_make_rating()),
        ):
            analyze_ticker("AAPL")
        call_kwargs = mock_risk.call_args.kwargs
        assert call_kwargs.get("beta") is None


# ---------------------------------------------------------------------------
# format_rating_output()
# ---------------------------------------------------------------------------

class TestFormatRatingOutput:
    def _output(self, **overrides) -> str:
        return format_rating_output(_make_rating(**overrides))

    def test_includes_ticker(self):
        assert "AAPL" in self._output()

    def test_includes_final_category(self):
        assert "Watchlist" in self._output()

    def test_includes_score(self):
        assert "60.0/100" in self._output()

    def test_includes_confidence(self):
        assert "medium" in self._output()

    def test_includes_technical_score(self):
        out = format_rating_output(_make_rating(score=60.0))
        assert "60.0/100" in out

    def test_includes_explanation(self):
        assert "Composite rating" in self._output()

    def test_includes_technical_summary(self):
        assert "Technical score" in self._output()

    def test_includes_positive_factors(self):
        out = format_rating_output(
            _make_rating(positives=["Above SMA 200", "RSI neutral"])
        )
        assert "Above SMA 200" in out
        assert "RSI neutral" in out

    def test_empty_positive_factors_prints_none(self):
        out = format_rating_output(_make_rating(positives=[]))
        assert "- None" in out

    def test_includes_key_risks(self):
        out = format_rating_output(_make_rating(risks=["RSI overbought"]))
        assert "RSI overbought" in out

    def test_empty_risks_prints_none(self):
        out = format_rating_output(_make_rating(risks=[]))
        assert "- None" in out

    def test_includes_buy_trigger(self):
        assert "Consider after fundamentals" in self._output()

    def test_includes_sell_avoid_trigger(self):
        assert "Reassess if score falls" in self._output()

    def test_includes_disclaimer(self):
        assert "not financial advice" in self._output()


# ---------------------------------------------------------------------------
# analyze_ticker() — news fetch behaviour
# ---------------------------------------------------------------------------

class TestNewsFetchInPipeline:
    def test_news_fetch_failure_does_not_abort(self):
        with (
            patch(_FETCH,        return_value=MagicMock()),
            patch(_FETCH_FUND,   return_value=_make_mock_fundamentals()),
            patch(_FETCH_NEWS,   side_effect=Exception("news down")),
            patch(_CALC,         return_value=MagicMock()),
            patch(_SUMM,         return_value=MagicMock()),
            patch(_BUILD_TECH,   return_value=[_make_signal()]),
            patch(_BUILD_FUND,   return_value=[_make_signal(category=SignalCategory.FUNDAMENTAL)]),
            patch(_RISK,         return_value=[]),
            patch(_ANALYZE_NEWS, return_value=[]),
            patch(_SCORE,        return_value=_make_rating()),
        ):
            result = main(["AAPL"])
        assert result == 0

    def test_news_failure_falls_back_to_empty_analysis(self):
        with (
            patch(_FETCH,        return_value=MagicMock()),
            patch(_FETCH_FUND,   return_value=_make_mock_fundamentals()),
            patch(_FETCH_NEWS,   side_effect=NewsFetchError("timeout")),
            patch(_CALC,         return_value=MagicMock()),
            patch(_SUMM,         return_value=MagicMock()),
            patch(_BUILD_TECH,   return_value=[_make_signal()]),
            patch(_BUILD_FUND,   return_value=[]),
            patch(_RISK,         return_value=[]),
            patch(_ANALYZE_NEWS, return_value=[]) as mock_analyze,
            patch(_SCORE,        return_value=_make_rating()),
        ):
            analyze_ticker("AAPL")
        mock_analyze.assert_called_once_with([])

    def test_news_signals_included_in_score_call(self):
        news_signals = [_make_signal(category=SignalCategory.NEWS)]
        with (
            patch(_FETCH,        return_value=MagicMock()),
            patch(_FETCH_FUND,   return_value=_make_mock_fundamentals()),
            patch(_FETCH_NEWS,   return_value=[]),
            patch(_CALC,         return_value=MagicMock()),
            patch(_SUMM,         return_value=MagicMock()),
            patch(_BUILD_TECH,   return_value=[_make_signal()]),
            patch(_BUILD_FUND,   return_value=[]),
            patch(_RISK,         return_value=[]),
            patch(_ANALYZE_NEWS, return_value=news_signals),
            patch(_SCORE,        return_value=_make_rating()) as mock_score,
        ):
            analyze_ticker("AAPL")
        called_signals = mock_score.call_args.kwargs["signals"]
        assert any(s.category == SignalCategory.NEWS for s in called_signals)
