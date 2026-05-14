"""
Unit tests for app/main.py.

All pipeline functions are mocked — no network calls.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from app.analysis.scoring import ScoringError
from app.analysis.technicals import TechnicalAnalysisError
from app.data.market_data import DataFetchError
from app.main import analyze_ticker, format_rating_output, main
from app.models.rating import ConfidenceLevel, Rating, RatingCategory
from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal(score_impact: float = 0.10, direction: SignalDirection = SignalDirection.BULLISH) -> Signal:
    return Signal(
        name="Test Signal",
        category=SignalCategory.TECHNICAL,
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
        explanation="Technical-only rating for AAPL based on 7 technical signals.",
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


# Patch targets
_FETCH   = "app.main.get_price_history"
_CALC    = "app.main.calculate_technical_indicators"
_SUMM    = "app.main.summarize_technical_signals"
_BUILD   = "app.main.build_technical_signals"
_SCORE   = "app.main.score_technical_signals"


def _mock_pipeline(rating: Rating | None = None):
    """Context manager that patches the entire analysis pipeline."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with (
            patch(_FETCH, return_value=MagicMock()) as mock_fetch,
            patch(_CALC,  return_value=MagicMock()) as mock_calc,
            patch(_SUMM,  return_value=MagicMock()) as mock_summ,
            patch(_BUILD, return_value=[_make_signal()]) as mock_build,
            patch(_SCORE, return_value=rating or _make_rating()) as mock_score,
        ):
            yield mock_fetch, mock_calc, mock_summ, mock_build, mock_score

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
        assert "Investment Bot Technical Analysis" in out


# ---------------------------------------------------------------------------
# main() — error handling
# ---------------------------------------------------------------------------

class TestMainErrors:
    def test_data_fetch_error_returns_1(self, capsys):
        with patch(_FETCH, side_effect=DataFetchError("bad ticker")):
            result = main(["INVALID"])
        assert result == 1
        assert "Error fetching" in capsys.readouterr().err

    def test_technical_analysis_error_returns_1(self, capsys):
        with (
            patch(_FETCH, return_value=MagicMock()),
            patch(_CALC, side_effect=TechnicalAnalysisError("bad data")),
        ):
            result = main(["AAPL"])
        assert result == 1
        assert "technical analysis" in capsys.readouterr().err.lower()

    def test_scoring_error_returns_1(self, capsys):
        with (
            patch(_FETCH, return_value=MagicMock()),
            patch(_CALC,  return_value=MagicMock()),
            patch(_SUMM,  return_value=MagicMock()),
            patch(_BUILD, return_value=[_make_signal()]),
            patch(_SCORE, side_effect=ScoringError("bad signals")),
        ):
            result = main(["AAPL"])
        assert result == 1
        assert "scoring" in capsys.readouterr().err.lower()


# ---------------------------------------------------------------------------
# analyze_ticker()
# ---------------------------------------------------------------------------

class TestAnalyzeTicker:
    def test_returns_rating(self):
        with _mock_pipeline() as (_, __, ___, ____, mock_score):
            result = analyze_ticker("AAPL")
        assert isinstance(result, Rating)

    def test_calls_pipeline_in_order(self):
        call_order: list[str] = []

        with (
            patch(_FETCH, side_effect=lambda *a, **kw: call_order.append("fetch") or MagicMock()),
            patch(_CALC,  side_effect=lambda *a, **kw: call_order.append("calc") or MagicMock()),
            patch(_SUMM,  side_effect=lambda *a, **kw: call_order.append("summ") or MagicMock()),
            patch(_BUILD, side_effect=lambda *a, **kw: call_order.append("build") or [_make_signal()]),
            patch(_SCORE, side_effect=lambda **kw: call_order.append("score") or _make_rating()),
        ):
            analyze_ticker("AAPL")

        assert call_order == ["fetch", "calc", "summ", "build", "score"]

    def test_passes_yfinance_as_data_source(self):
        with _mock_pipeline() as (_, __, ___, ____, mock_score):
            analyze_ticker("AAPL")
        call_kwargs = mock_score.call_args.kwargs
        assert "yfinance" in call_kwargs["data_sources_used"]


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
        assert "Technical-only rating" in self._output()

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
