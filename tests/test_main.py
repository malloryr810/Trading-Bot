"""
Unit tests for app/main.py.

All pipeline functions are mocked — no network calls.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.analysis.fundamentals_analysis import FundamentalAnalysisError
from app.analysis.news_analysis import NewsAnalysisError
from app.analysis.risk_analysis import RiskAnalysisError
from app.analysis.scoring import ScoringError
from app.analysis.technicals import TechnicalAnalysisError
from app.data.fundamentals import FundamentalDataFetchError
from app.data.market_data import DataFetchError
from app.data.news_data import NewsFetchError
from app.data.storage import StorageError
from app.main import analyze_ticker, build_parser, main, parse_args

_SAVE_MARKDOWN = "app.main.save_markdown_report"
_FAKE_MD_PATH  = Path("outputs/reports/AAPL_20240601_000000.md")
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
_SAVE_REPORT  = "app.main.save_text_report"
_SAVE_JSON    = "app.main.save_json_result"

_FAKE_REPORT_PATH = Path("outputs/reports/AAPL_20240601_000000.txt")
_FAKE_JSON_PATH   = Path("outputs/results/AAPL_20240601_000000.json")


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
        assert "usage" in capsys.readouterr().err


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

    def test_news_analysis_error_returns_1(self, capsys):
        with (
            patch(_FETCH,        return_value=MagicMock()),
            patch(_FETCH_FUND,   return_value=_make_mock_fundamentals()),
            patch(_FETCH_NEWS,   return_value=[]),
            patch(_CALC,         return_value=MagicMock()),
            patch(_SUMM,         return_value=MagicMock()),
            patch(_BUILD_TECH,   return_value=[_make_signal()]),
            patch(_BUILD_FUND,   return_value=[_make_signal(category=SignalCategory.FUNDAMENTAL)]),
            patch(_RISK,         return_value=[_make_signal(category=SignalCategory.RISK)]),
            patch(_ANALYZE_NEWS, side_effect=NewsAnalysisError("bad news input")),
        ):
            result = main(["AAPL"])
        assert result == 1
        assert "news analysis" in capsys.readouterr().err.lower()

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


# ---------------------------------------------------------------------------
# main() — --save-report and --save-json flags
# ---------------------------------------------------------------------------

class TestSaveFlags:
    def test_default_does_not_call_save_text_report(self):
        with _mock_pipeline():
            with patch(_SAVE_REPORT) as mock_save:
                main(["AAPL"])
        mock_save.assert_not_called()

    def test_default_does_not_call_save_json_result(self):
        with _mock_pipeline():
            with patch(_SAVE_JSON) as mock_save:
                main(["AAPL"])
        mock_save.assert_not_called()

    def test_save_report_flag_calls_save_text_report(self):
        with _mock_pipeline():
            with patch(_SAVE_REPORT, return_value=_FAKE_REPORT_PATH) as mock_save:
                main(["AAPL", "--save-report"])
        mock_save.assert_called_once()

    def test_save_json_flag_calls_save_json_result(self):
        with _mock_pipeline():
            with patch(_SAVE_JSON, return_value=_FAKE_JSON_PATH) as mock_save:
                main(["AAPL", "--save-json"])
        mock_save.assert_called_once()

    def test_both_flags_call_both_save_functions(self):
        with _mock_pipeline():
            with (
                patch(_SAVE_REPORT, return_value=_FAKE_REPORT_PATH) as mock_report,
                patch(_SAVE_JSON,   return_value=_FAKE_JSON_PATH)   as mock_json,
            ):
                main(["AAPL", "--save-report", "--save-json"])
        mock_report.assert_called_once()
        mock_json.assert_called_once()

    def test_save_report_receives_report_text_and_ticker(self):
        with _mock_pipeline():
            with patch(_SAVE_REPORT, return_value=_FAKE_REPORT_PATH) as mock_save:
                main(["AAPL", "--save-report"])
        call_args = mock_save.call_args.args
        assert isinstance(call_args[0], str)   # report_text is a non-empty string
        assert len(call_args[0]) > 0
        assert call_args[1] == "AAPL"          # ticker

    def test_save_report_text_matches_printed_report(self, capsys):
        with _mock_pipeline():
            with patch(_SAVE_REPORT, return_value=_FAKE_REPORT_PATH) as mock_save:
                main(["AAPL", "--save-report"])
        printed = capsys.readouterr().out
        saved_text = mock_save.call_args.args[0]
        # The same text printed to stdout is passed to save_text_report
        assert saved_text in printed

    def test_save_json_receives_rating_and_ticker(self):
        with _mock_pipeline():
            with patch(_SAVE_JSON, return_value=_FAKE_JSON_PATH) as mock_save:
                main(["AAPL", "--save-json"])
        call_args = mock_save.call_args.args
        assert isinstance(call_args[0], Rating)  # result is the Rating model
        assert call_args[0].ticker == "AAPL"
        assert call_args[1] == "AAPL"            # ticker

    def test_save_json_rating_has_score(self):
        with _mock_pipeline():
            with patch(_SAVE_JSON, return_value=_FAKE_JSON_PATH) as mock_save:
                main(["AAPL", "--save-json"])
        rating_arg = mock_save.call_args.args[0]
        assert hasattr(rating_arg, "score")
        assert hasattr(rating_arg, "final_category")

    def test_save_report_confirmation_printed(self, capsys):
        with _mock_pipeline():
            with patch(_SAVE_REPORT, return_value=_FAKE_REPORT_PATH):
                main(["AAPL", "--save-report"])
        out = capsys.readouterr().out
        assert "Saved text report to:" in out
        assert str(_FAKE_REPORT_PATH) in out

    def test_save_json_confirmation_printed(self, capsys):
        with _mock_pipeline():
            with patch(_SAVE_JSON, return_value=_FAKE_JSON_PATH):
                main(["AAPL", "--save-json"])
        out = capsys.readouterr().out
        assert "Saved JSON result to:" in out
        assert str(_FAKE_JSON_PATH) in out

    def test_save_report_storage_error_does_not_crash(self, capsys):
        with _mock_pipeline():
            with patch(_SAVE_REPORT, side_effect=StorageError("disk full")):
                result = main(["AAPL", "--save-report"])
        assert result == 0

    def test_save_report_storage_error_prints_warning(self, capsys):
        with _mock_pipeline():
            with patch(_SAVE_REPORT, side_effect=StorageError("disk full")):
                main(["AAPL", "--save-report"])
        assert "Warning" in capsys.readouterr().err

    def test_save_json_storage_error_does_not_crash(self, capsys):
        with _mock_pipeline():
            with patch(_SAVE_JSON, side_effect=StorageError("no space")):
                result = main(["AAPL", "--save-json"])
        assert result == 0

    def test_save_json_storage_error_prints_warning(self, capsys):
        with _mock_pipeline():
            with patch(_SAVE_JSON, side_effect=StorageError("no space")):
                main(["AAPL", "--save-json"])
        assert "Warning" in capsys.readouterr().err

    def test_report_still_printed_when_save_fails(self, capsys):
        with _mock_pipeline():
            with patch(_SAVE_REPORT, side_effect=StorageError("disk full")):
                main(["AAPL", "--save-report"])
        out = capsys.readouterr().out
        assert "STOCK RESEARCH REPORT" in out

    def test_both_flags_independent_errors(self, capsys):
        with _mock_pipeline():
            with (
                patch(_SAVE_REPORT, return_value=_FAKE_REPORT_PATH),
                patch(_SAVE_JSON,   side_effect=StorageError("json err")),
            ):
                result = main(["AAPL", "--save-report", "--save-json"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Saved text report to:" in captured.out
        assert "Warning" in captured.err

    def test_save_report_does_not_call_save_json(self):
        with _mock_pipeline():
            with (
                patch(_SAVE_REPORT, return_value=_FAKE_REPORT_PATH),
                patch(_SAVE_JSON) as mock_json,
            ):
                main(["AAPL", "--save-report"])
        mock_json.assert_not_called()

    def test_save_json_does_not_call_save_report(self):
        with _mock_pipeline():
            with (
                patch(_SAVE_REPORT) as mock_report,
                patch(_SAVE_JSON,   return_value=_FAKE_JSON_PATH),
            ):
                main(["AAPL", "--save-json"])
        mock_report.assert_not_called()

    def test_save_flags_return_0_on_success(self):
        with _mock_pipeline():
            with (
                patch(_SAVE_REPORT, return_value=_FAKE_REPORT_PATH),
                patch(_SAVE_JSON,   return_value=_FAKE_JSON_PATH),
            ):
                result = main(["AAPL", "--save-report", "--save-json"])
        assert result == 0


# ---------------------------------------------------------------------------
# parse_args() — parser unit tests
# ---------------------------------------------------------------------------

class TestArgParser:
    def test_single_ticker_parses_correctly(self):
        args = parse_args(["AAPL"])
        assert args.ticker == "AAPL"
        assert args.watchlist is None
        assert args.save_report is False
        assert args.save_json is False

    def test_save_report_flag_parsed(self):
        args = parse_args(["AAPL", "--save-report"])
        assert args.save_report is True
        assert args.save_json is False

    def test_save_json_flag_parsed(self):
        args = parse_args(["AAPL", "--save-json"])
        assert args.save_json is True
        assert args.save_report is False

    def test_both_save_flags_parsed(self):
        args = parse_args(["AAPL", "--save-report", "--save-json"])
        assert args.save_report is True
        assert args.save_json is True

    def test_watchlist_path_parsed(self):
        args = parse_args(["--watchlist", "watchlists/default.txt"])
        assert args.watchlist == "watchlists/default.txt"
        assert args.ticker is None
        assert args.save_report is False
        assert args.save_json is False

    def test_watchlist_with_save_report(self):
        args = parse_args(["--watchlist", "watchlists/default.txt", "--save-report"])
        assert args.watchlist == "watchlists/default.txt"
        assert args.save_report is True
        assert args.save_json is False

    def test_watchlist_with_save_json(self):
        args = parse_args(["--watchlist", "watchlists/default.txt", "--save-json"])
        assert args.watchlist == "watchlists/default.txt"
        assert args.save_json is True

    def test_watchlist_with_both_save_flags(self):
        args = parse_args(["--watchlist", "watchlists/default.txt", "--save-report", "--save-json"])
        assert args.save_report is True
        assert args.save_json is True

    def test_no_args_ticker_is_none(self):
        args = parse_args([])
        assert args.ticker is None

    def test_no_args_watchlist_is_none(self):
        args = parse_args([])
        assert args.watchlist is None

    def test_no_args_save_flags_default_false(self):
        args = parse_args([])
        assert args.save_report is False
        assert args.save_json is False

    def test_unknown_flag_raises_system_exit(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["AAPL", "--unknown-flag"])
        assert exc_info.value.code != 0

    def test_help_raises_system_exit_0(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--help"])
        assert exc_info.value.code == 0

    def test_build_parser_returns_argument_parser(self):
        import argparse
        assert isinstance(build_parser(), argparse.ArgumentParser)

    def test_flags_order_does_not_matter(self):
        args1 = parse_args(["--save-report", "AAPL", "--save-json"])
        args2 = parse_args(["AAPL", "--save-json", "--save-report"])
        assert args1.ticker == args2.ticker == "AAPL"
        assert args1.save_report == args2.save_report is True
        assert args1.save_json == args2.save_json is True


# ---------------------------------------------------------------------------
# main() — validation and error behavior
# ---------------------------------------------------------------------------

class TestMainBehaviorValidation:
    def test_unknown_flag_returns_1(self, capsys):
        result = main(["AAPL", "--unknown-flag"])
        assert result == 1

    def test_unknown_flag_prints_error_to_stderr(self, capsys):
        main(["AAPL", "--unknown-flag"])
        assert "unrecognized" in capsys.readouterr().err

    def test_help_returns_0(self, capsys):
        result = main(["--help"])
        assert result == 0

    def test_help_output_mentions_ticker(self, capsys):
        main(["--help"])
        assert "ticker" in capsys.readouterr().out.lower()

    def test_help_output_mentions_watchlist(self, capsys):
        main(["--help"])
        assert "--watchlist" in capsys.readouterr().out

    def test_help_output_mentions_save_report(self, capsys):
        main(["--help"])
        assert "--save-report" in capsys.readouterr().out

    def test_help_output_mentions_save_json(self, capsys):
        main(["--help"])
        assert "--save-json" in capsys.readouterr().out

    def test_ticker_and_watchlist_together_returns_1(self, tmp_path):
        p = tmp_path / "w.txt"
        p.write_text("AAPL\n", encoding="utf-8")
        result = main(["AAPL", "--watchlist", str(p)])
        assert result == 1

    def test_ticker_and_watchlist_together_prints_not_both(self, tmp_path, capsys):
        p = tmp_path / "w.txt"
        p.write_text("AAPL\n", encoding="utf-8")
        main(["AAPL", "--watchlist", str(p)])
        assert "not both" in capsys.readouterr().err

    def test_no_args_returns_1(self):
        assert main([]) == 1

    def test_no_args_prints_usage_to_stderr(self, capsys):
        main([])
        assert "usage" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# main() — --save-markdown flag (single-ticker)
# ---------------------------------------------------------------------------

class TestSaveMarkdownFlag:
    def test_default_does_not_call_save_markdown(self):
        with _mock_pipeline():
            with patch(_SAVE_MARKDOWN) as mock_save:
                main(["AAPL"])
        mock_save.assert_not_called()

    def test_save_markdown_flag_calls_save_markdown_report(self):
        with _mock_pipeline():
            with patch(_SAVE_MARKDOWN, return_value=_FAKE_MD_PATH) as mock_save:
                main(["AAPL", "--save-markdown"])
        mock_save.assert_called_once()

    def test_save_markdown_returns_0_on_success(self):
        with _mock_pipeline():
            with patch(_SAVE_MARKDOWN, return_value=_FAKE_MD_PATH):
                result = main(["AAPL", "--save-markdown"])
        assert result == 0

    def test_save_markdown_receives_markdown_string_and_ticker(self):
        with _mock_pipeline():
            with patch(_SAVE_MARKDOWN, return_value=_FAKE_MD_PATH) as mock_save:
                main(["AAPL", "--save-markdown"])
        call_args = mock_save.call_args.args
        assert isinstance(call_args[0], str)
        assert len(call_args[0]) > 0
        assert call_args[1] == "AAPL"

    def test_save_markdown_text_contains_markdown_heading(self):
        with _mock_pipeline():
            with patch(_SAVE_MARKDOWN, return_value=_FAKE_MD_PATH) as mock_save:
                main(["AAPL", "--save-markdown"])
        md_text = mock_save.call_args.args[0]
        assert md_text.startswith("#")

    def test_save_markdown_confirmation_printed(self, capsys):
        with _mock_pipeline():
            with patch(_SAVE_MARKDOWN, return_value=_FAKE_MD_PATH):
                main(["AAPL", "--save-markdown"])
        out = capsys.readouterr().out
        assert "Saved Markdown report to:" in out
        assert str(_FAKE_MD_PATH) in out

    def test_save_markdown_storage_error_does_not_crash(self, capsys):
        with _mock_pipeline():
            with patch(_SAVE_MARKDOWN, side_effect=StorageError("disk full")):
                result = main(["AAPL", "--save-markdown"])
        assert result == 0

    def test_save_markdown_storage_error_prints_warning(self, capsys):
        with _mock_pipeline():
            with patch(_SAVE_MARKDOWN, side_effect=StorageError("disk full")):
                main(["AAPL", "--save-markdown"])
        assert "Warning" in capsys.readouterr().err

    def test_report_still_printed_when_markdown_save_fails(self, capsys):
        with _mock_pipeline():
            with patch(_SAVE_MARKDOWN, side_effect=StorageError("disk full")):
                main(["AAPL", "--save-markdown"])
        out = capsys.readouterr().out
        assert "STOCK RESEARCH REPORT" in out

    def test_save_markdown_does_not_call_save_report(self):
        with _mock_pipeline():
            with (
                patch(_SAVE_MARKDOWN, return_value=_FAKE_MD_PATH),
                patch(_SAVE_REPORT) as mock_report,
            ):
                main(["AAPL", "--save-markdown"])
        mock_report.assert_not_called()

    def test_save_markdown_does_not_call_save_json(self):
        with _mock_pipeline():
            with (
                patch(_SAVE_MARKDOWN, return_value=_FAKE_MD_PATH),
                patch(_SAVE_JSON) as mock_json,
            ):
                main(["AAPL", "--save-markdown"])
        mock_json.assert_not_called()

    def test_all_three_save_flags_work_together(self):
        with _mock_pipeline():
            with (
                patch(_SAVE_REPORT,   return_value=_FAKE_REPORT_PATH) as mock_report,
                patch(_SAVE_MARKDOWN, return_value=_FAKE_MD_PATH)     as mock_md,
                patch(_SAVE_JSON,     return_value=_FAKE_JSON_PATH)   as mock_json,
            ):
                result = main(["AAPL", "--save-report", "--save-markdown", "--save-json"])
        assert result == 0
        mock_report.assert_called_once()
        mock_md.assert_called_once()
        mock_json.assert_called_once()


# ---------------------------------------------------------------------------
# parse_args() — --save-markdown parser tests
# ---------------------------------------------------------------------------

class TestArgParserMarkdown:
    def test_save_markdown_flag_parsed(self):
        args = parse_args(["AAPL", "--save-markdown"])
        assert args.save_markdown is True

    def test_save_markdown_defaults_false(self):
        args = parse_args(["AAPL"])
        assert args.save_markdown is False

    def test_save_markdown_with_watchlist(self):
        args = parse_args(["--watchlist", "watchlists/default.txt", "--save-markdown"])
        assert args.save_markdown is True
        assert args.watchlist == "watchlists/default.txt"

    def test_all_three_save_flags_parsed(self):
        args = parse_args(["AAPL", "--save-report", "--save-json", "--save-markdown"])
        assert args.save_report is True
        assert args.save_json is True
        assert args.save_markdown is True

    def test_help_output_mentions_save_markdown(self, capsys):
        main(["--help"])
        assert "--save-markdown" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# main() — --save-markdown flag (watchlist mode)
# ---------------------------------------------------------------------------

class TestWatchlistSaveMarkdown:
    """Tests for --save-markdown in watchlist mode.

    load_watchlist / scan_watchlist / format_watchlist_summary are imported
    locally inside _run_watchlist, so they must be patched at app.watchlist.*.
    save_markdown_report is a module-level import in app.main, so it is patched
    at app.main.save_markdown_report.
    """

    def _make_watchlist_file(self, tmp_path) -> str:
        p = tmp_path / "w.txt"
        p.write_text("AAPL\n", encoding="utf-8")
        return str(p)

    def _wl_internals(self, mock_md_return=None, mock_md_side_effect=None):
        """Context manager patching the internals of _run_watchlist."""
        import contextlib

        fake_path = mock_md_return or Path("outputs/reports/WATCHLIST.md")

        @contextlib.contextmanager
        def _ctx():
            md_kwargs = (
                {"side_effect": mock_md_side_effect}
                if mock_md_side_effect
                else {"return_value": fake_path}
            )
            with (
                patch("app.watchlist.load_watchlist", return_value=["AAPL"]),
                patch("app.watchlist.scan_watchlist", return_value=[]),
                patch("app.watchlist.format_watchlist_summary", return_value="WATCHLIST SUMMARY"),
                patch("app.main.save_markdown_report", **md_kwargs) as mock_md,
                patch("app.main.save_text_report", return_value=Path("outputs/reports/WATCHLIST.txt")),
                patch("app.main.save_json_result", return_value=Path("outputs/results/WATCHLIST.json")),
                patch("app.watchlist.serialize_watchlist_results", return_value=[]),
            ):
                yield mock_md

        return _ctx()

    def test_save_markdown_flag_passed_to_run_watchlist(self, tmp_path):
        wl = self._make_watchlist_file(tmp_path)
        with patch("app.main._run_watchlist", return_value=0) as mock_run:
            main(["--watchlist", wl, "--save-markdown"])
        mock_run.assert_called_once_with(wl, False, False, True)

    def test_no_markdown_flag_passes_false_to_run_watchlist(self, tmp_path):
        wl = self._make_watchlist_file(tmp_path)
        with patch("app.main._run_watchlist", return_value=0) as mock_run:
            main(["--watchlist", wl])
        mock_run.assert_called_once_with(wl, False, False, False)

    def test_save_markdown_not_called_by_default(self, tmp_path):
        wl = self._make_watchlist_file(tmp_path)
        with self._wl_internals() as mock_md:
            from app.main import _run_watchlist
            _run_watchlist(wl, False, False, False)
        mock_md.assert_not_called()

    def test_save_markdown_called_with_flag(self, tmp_path):
        wl = self._make_watchlist_file(tmp_path)
        with self._wl_internals() as mock_md:
            from app.main import _run_watchlist
            _run_watchlist(wl, False, False, True)
        mock_md.assert_called_once()

    def test_save_markdown_confirmation_printed(self, tmp_path, capsys):
        wl = self._make_watchlist_file(tmp_path)
        with self._wl_internals():
            from app.main import _run_watchlist
            _run_watchlist(wl, False, False, True)
        out = capsys.readouterr().out
        assert "Saved Markdown report to:" in out

    def test_save_markdown_storage_error_does_not_crash(self, tmp_path):
        wl = self._make_watchlist_file(tmp_path)
        with self._wl_internals(mock_md_side_effect=StorageError("no space")):
            from app.main import _run_watchlist
            result = _run_watchlist(wl, False, False, True)
        assert result == 0

    def test_save_markdown_storage_error_prints_warning(self, tmp_path, capsys):
        wl = self._make_watchlist_file(tmp_path)
        with self._wl_internals(mock_md_side_effect=StorageError("no space")):
            from app.main import _run_watchlist
            _run_watchlist(wl, False, False, True)
        assert "Warning" in capsys.readouterr().err
