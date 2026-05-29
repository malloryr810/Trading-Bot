"""
Unit tests for app/main.py.

All pipeline functions are mocked — no network calls.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.analysis.fundamentals_analysis import FundamentalAnalysisError
from app.analysis.news_analysis import NewsAnalysisError
from app.analysis.risk_analysis import RiskAnalysisError
from app.analysis.scoring import ScoringError
from app.analysis.technicals import TechnicalAnalysisError
from app.data.fundamentals import FundamentalDataFetchError
from app.data.market_data import DataFetchError
from app.data.storage import StorageError
from app.main import build_parser, main, parse_args
from app.models.rating import ConfidenceLevel, RatingCategory
from app.models.stock_report import StockReport

_SAVE_REPORT           = "app.main.save_text_report"
_SAVE_JSON             = "app.main.save_json_result"
_SAVE_MARKDOWN         = "app.main.save_markdown_report"
_PATCH_WL_MD_FORMATTER = "app.main.format_watchlist_markdown"

_FAKE_REPORT_PATH = Path("outputs/reports/AAPL_20240601_000000.txt")
_FAKE_JSON_PATH   = Path("outputs/results/AAPL_20240601_000000.json")
_FAKE_MD_PATH     = Path("outputs/reports/AAPL_20240601_000000.md")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stock_report(ticker: str = "AAPL") -> StockReport:
    return StockReport(
        ticker=ticker,
        final_category=RatingCategory.WATCHLIST,
        score=60.0,
        confidence_level=ConfidenceLevel.MEDIUM,
    )


def _mock_pipeline(stock_report: StockReport | None = None):
    """Patches analyze_stock at the CLI boundary."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("app.main.analyze_stock", return_value=stock_report or _make_stock_report()):
            yield

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
        with patch("app.main.analyze_stock", side_effect=DataFetchError("bad ticker")):
            result = main(["INVALID"])
        assert result == 1
        assert "Error fetching" in capsys.readouterr().err

    def test_fundamental_fetch_error_returns_1(self, capsys):
        with patch("app.main.analyze_stock", side_effect=FundamentalDataFetchError("no data")):
            result = main(["AAPL"])
        assert result == 1
        assert "fundamental" in capsys.readouterr().err.lower()

    def test_technical_analysis_error_returns_1(self, capsys):
        with patch("app.main.analyze_stock", side_effect=TechnicalAnalysisError("bad data")):
            result = main(["AAPL"])
        assert result == 1
        assert "technical analysis" in capsys.readouterr().err.lower()

    def test_fundamental_analysis_error_returns_1(self, capsys):
        with patch("app.main.analyze_stock", side_effect=FundamentalAnalysisError("bad fundamentals")):
            result = main(["AAPL"])
        assert result == 1
        assert "fundamental analysis" in capsys.readouterr().err.lower()

    def test_risk_analysis_error_returns_1(self, capsys):
        with patch("app.main.analyze_stock", side_effect=RiskAnalysisError("bad risk")):
            result = main(["AAPL"])
        assert result == 1
        assert "risk analysis" in capsys.readouterr().err.lower()

    def test_news_analysis_error_returns_1(self, capsys):
        with patch("app.main.analyze_stock", side_effect=NewsAnalysisError("bad news input")):
            result = main(["AAPL"])
        assert result == 1
        assert "news analysis" in capsys.readouterr().err.lower()

    def test_scoring_error_returns_1(self, capsys):
        with patch("app.main.analyze_stock", side_effect=ScoringError("bad signals")):
            result = main(["AAPL"])
        assert result == 1
        assert "scoring" in capsys.readouterr().err.lower()


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

    def test_save_json_receives_stock_report_and_ticker(self):
        with _mock_pipeline():
            with patch(_SAVE_JSON, return_value=_FAKE_JSON_PATH) as mock_save:
                main(["AAPL", "--save-json"])
        call_args = mock_save.call_args.args
        assert isinstance(call_args[0], StockReport)  # result is the StockReport model
        assert call_args[0].ticker == "AAPL"
        assert call_args[1] == "AAPL"                 # ticker

    def test_save_json_stock_report_has_score_and_category(self):
        with _mock_pipeline():
            with patch(_SAVE_JSON, return_value=_FAKE_JSON_PATH) as mock_save:
                main(["AAPL", "--save-json"])
        report_arg = mock_save.call_args.args[0]
        assert hasattr(report_arg, "score")
        assert hasattr(report_arg, "final_category")

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

    _run_watchlist now calls analyze_watchlist_file (from the service layer)
    for the scan step, so tests patch app.main.analyze_watchlist_file.
    save_markdown_report is a module-level import in app.main, patched there.
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
                patch("app.main.analyze_watchlist_file", return_value=[]),
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

    def test_save_markdown_uses_watchlist_markdown_formatter(self, tmp_path):
        """--save-markdown must call format_watchlist_markdown, not format_watchlist_summary."""
        wl = self._make_watchlist_file(tmp_path)
        fake_path = Path("outputs/reports/WATCHLIST.md")
        with (
            patch("app.main.analyze_watchlist_file", return_value=[]),
            patch("app.watchlist.format_watchlist_summary", return_value="PLAIN TEXT SUMMARY"),
            patch(_PATCH_WL_MD_FORMATTER, return_value="# WL MARKDOWN") as mock_formatter,
            patch("app.main.save_markdown_report", return_value=fake_path) as mock_save,
        ):
            from app.main import _run_watchlist
            _run_watchlist(wl, False, False, True)
        mock_formatter.assert_called_once()
        saved_text = mock_save.call_args.args[0]
        assert saved_text == "# WL MARKDOWN"
        assert saved_text != "PLAIN TEXT SUMMARY"

    def test_save_markdown_content_starts_with_markdown_heading(self, tmp_path):
        """Real format_watchlist_markdown output starts with a Markdown H1."""
        wl = self._make_watchlist_file(tmp_path)
        fake_path = Path("outputs/reports/WATCHLIST.md")
        with (
            patch("app.main.analyze_watchlist_file", return_value=[]),
            patch("app.watchlist.format_watchlist_summary", return_value="PLAIN TEXT SUMMARY"),
            patch("app.main.save_markdown_report", return_value=fake_path) as mock_save,
        ):
            from app.main import _run_watchlist
            _run_watchlist(wl, False, False, True)
        saved_text = mock_save.call_args.args[0]
        assert saved_text.startswith("# ")

    def test_save_report_still_uses_plain_text_summary(self, tmp_path):
        """--save-report must still save the plain-text summary, not Markdown."""
        wl = self._make_watchlist_file(tmp_path)
        fake_path = Path("outputs/reports/WATCHLIST.txt")
        with (
            patch("app.main.analyze_watchlist_file", return_value=[]),
            patch("app.watchlist.format_watchlist_summary", return_value="PLAIN TEXT SUMMARY"),
            patch("app.main.save_text_report", return_value=fake_path) as mock_save,
        ):
            from app.main import _run_watchlist
            _run_watchlist(wl, True, False, False)
        saved_text = mock_save.call_args.args[0]
        assert saved_text == "PLAIN TEXT SUMMARY"
