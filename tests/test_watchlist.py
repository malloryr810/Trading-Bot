"""
Unit tests for app/watchlist.py and watchlist CLI mode in app/main.py.

All tests are deterministic — no live yfinance or API calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.main import main
from app.models.rating import ConfidenceLevel, RatingCategory
from app.models.stock_report import StockReport
from app.watchlist import (
    WatchlistLoadError,
    WatchlistResult,
    format_watchlist_summary,
    load_watchlist,
    scan_watchlist,
    serialize_watchlist_results,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_report(
    ticker: str = "AAPL",
    score: float = 62.0,
    category: RatingCategory = RatingCategory.WATCHLIST,
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
    company_name: str | None = None,
    current_price: float | None = None,
) -> StockReport:
    return StockReport(
        ticker=ticker,
        company_name=company_name,
        current_price=current_price,
        final_category=category,
        score=score,
        confidence_level=confidence,
    )


def _fake_analyze(report: StockReport):
    """Return a fixed analyze_func that always returns the given StockReport."""
    def _analyze(ticker: str) -> StockReport:
        return report
    return _analyze


def _score_analyze(scores: dict[str, float]):
    """Return an analyze_func that maps ticker → StockReport with the given score."""
    def _analyze(ticker: str) -> StockReport:
        return _make_report(ticker=ticker, score=scores[ticker])
    return _analyze


def _failing_analyze(message: str = "network error"):
    """Return an analyze_func that always raises RuntimeError."""
    def _analyze(ticker: str) -> StockReport:
        raise RuntimeError(message)
    return _analyze


def _write_watchlist(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "watchlist.txt"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# load_watchlist — happy path
# ---------------------------------------------------------------------------

class TestLoadWatchlist:
    def test_returns_list_of_tickers(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\nMSFT\nNVDA\n")
        assert load_watchlist(p) == ["AAPL", "MSFT", "NVDA"]

    def test_ignores_blank_lines(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\n\nMSFT\n\n")
        assert load_watchlist(p) == ["AAPL", "MSFT"]

    def test_ignores_comment_lines(self, tmp_path):
        p = _write_watchlist(tmp_path, "# comment\nAAPL\n# another\nMSFT\n")
        assert load_watchlist(p) == ["AAPL", "MSFT"]

    def test_ignores_inline_comment_at_start(self, tmp_path):
        p = _write_watchlist(tmp_path, "#AAPL\nMSFT\n")
        assert load_watchlist(p) == ["MSFT"]

    def test_normalizes_lowercase_to_uppercase(self, tmp_path):
        p = _write_watchlist(tmp_path, "aapl\nmsft\n")
        assert load_watchlist(p) == ["AAPL", "MSFT"]

    def test_normalizes_mixed_case(self, tmp_path):
        p = _write_watchlist(tmp_path, "Nvda\ngOoGl\n")
        assert load_watchlist(p) == ["NVDA", "GOOGL"]

    def test_strips_whitespace_from_tickers(self, tmp_path):
        p = _write_watchlist(tmp_path, "  AAPL  \n  MSFT\n")
        assert load_watchlist(p) == ["AAPL", "MSFT"]

    def test_removes_duplicates(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\nMSFT\nAAPL\n")
        assert load_watchlist(p) == ["AAPL", "MSFT"]

    def test_preserves_first_seen_order_on_dedup(self, tmp_path):
        p = _write_watchlist(tmp_path, "MSFT\nAAPL\nMSFT\nNVDA\n")
        assert load_watchlist(p) == ["MSFT", "AAPL", "NVDA"]

    def test_dedup_is_case_insensitive(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\naapl\nAapl\n")
        assert load_watchlist(p) == ["AAPL"]

    def test_accepts_path_string(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\n")
        result = load_watchlist(str(p))
        assert result == ["AAPL"]

    def test_accepts_pathlib_path(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\n")
        result = load_watchlist(p)
        assert result == ["AAPL"]

    def test_single_ticker(self, tmp_path):
        p = _write_watchlist(tmp_path, "TSLA\n")
        assert load_watchlist(p) == ["TSLA"]


# ---------------------------------------------------------------------------
# load_watchlist — error cases
# ---------------------------------------------------------------------------

class TestLoadWatchlistErrors:
    def test_missing_file_raises_watchlist_load_error(self, tmp_path):
        with pytest.raises(WatchlistLoadError, match="not found"):
            load_watchlist(tmp_path / "missing.txt")

    def test_empty_file_raises_watchlist_load_error(self, tmp_path):
        p = _write_watchlist(tmp_path, "")
        with pytest.raises(WatchlistLoadError, match="no valid tickers"):
            load_watchlist(p)

    def test_only_blank_lines_raises(self, tmp_path):
        p = _write_watchlist(tmp_path, "\n\n\n")
        with pytest.raises(WatchlistLoadError, match="no valid tickers"):
            load_watchlist(p)

    def test_only_comments_raises(self, tmp_path):
        p = _write_watchlist(tmp_path, "# comment one\n# comment two\n")
        with pytest.raises(WatchlistLoadError, match="no valid tickers"):
            load_watchlist(p)

    def test_error_message_includes_path(self, tmp_path):
        missing = tmp_path / "watchlist.txt"
        with pytest.raises(WatchlistLoadError) as exc_info:
            load_watchlist(missing)
        assert "watchlist.txt" in str(exc_info.value)


# ---------------------------------------------------------------------------
# scan_watchlist — success
# ---------------------------------------------------------------------------

class TestScanWatchlistSuccess:
    def test_returns_list(self):
        results = scan_watchlist(["AAPL"], _fake_analyze(_make_report("AAPL")))
        assert isinstance(results, list)

    def test_single_ticker_success(self):
        results = scan_watchlist(["AAPL"], _fake_analyze(_make_report("AAPL", score=62.0)))
        assert len(results) == 1
        assert results[0].ticker == "AAPL"
        assert results[0].score == pytest.approx(62.0)
        assert results[0].succeeded is True

    def test_fields_populated_from_report(self):
        report = _make_report(
            ticker="MSFT",
            score=72.0,
            category=RatingCategory.BUY_CANDIDATE,
            confidence=ConfidenceLevel.HIGH,
            company_name="Microsoft Corp.",
            current_price=420.0,
        )
        results = scan_watchlist(["MSFT"], _fake_analyze(report))
        r = results[0]
        assert r.company_name == "Microsoft Corp."
        assert r.final_category == RatingCategory.BUY_CANDIDATE
        assert r.confidence_level == ConfidenceLevel.HIGH
        assert r.current_price == pytest.approx(420.0)

    def test_multiple_tickers_all_succeed(self):
        def _analyze(ticker: str) -> StockReport:
            return _make_report(ticker=ticker, score=50.0)

        results = scan_watchlist(["AAPL", "MSFT", "NVDA"], _analyze)
        assert len(results) == 3
        assert all(r.succeeded for r in results)

    def test_empty_tickers_returns_empty_list(self):
        results = scan_watchlist([], _fake_analyze(_make_report()))
        assert results == []


# ---------------------------------------------------------------------------
# scan_watchlist — sorting
# ---------------------------------------------------------------------------

class TestScanWatchlistSorting:
    def test_sorted_by_score_descending(self):
        results = scan_watchlist(
            ["LOW", "MID", "HIGH"],
            _score_analyze({"LOW": 30.0, "MID": 55.0, "HIGH": 80.0}),
        )
        scores = [r.score for r in results]
        assert scores == [80.0, 55.0, 30.0]

    def test_preserves_relative_order_for_equal_scores(self):
        def _analyze(ticker: str) -> StockReport:
            return _make_report(ticker=ticker, score=60.0)

        results = scan_watchlist(["AAPL", "MSFT"], _analyze)
        tickers = [r.ticker for r in results]
        assert tickers == ["AAPL", "MSFT"]

    def test_higher_score_appears_first(self):
        results = scan_watchlist(
            ["AAPL", "NVDA"],
            _score_analyze({"AAPL": 60.0, "NVDA": 90.0}),
        )
        assert results[0].ticker == "NVDA"
        assert results[1].ticker == "AAPL"


# ---------------------------------------------------------------------------
# scan_watchlist — failures
# ---------------------------------------------------------------------------

class TestScanWatchlistFailures:
    def test_failure_does_not_abort_scan(self):
        call_count = 0

        def _analyze(ticker: str) -> StockReport:
            nonlocal call_count
            call_count += 1
            if ticker == "BAD":
                raise RuntimeError("network error")
            return _make_report(ticker=ticker, score=60.0)

        results = scan_watchlist(["AAPL", "BAD", "MSFT"], _analyze)
        assert call_count == 3
        assert len(results) == 3

    def test_failed_ticker_has_error_message(self):
        results = scan_watchlist(["BAD"], _failing_analyze("fetch failed"))
        assert results[0].error_message == "fetch failed"
        assert results[0].succeeded is False

    def test_failed_ticker_score_is_none(self):
        results = scan_watchlist(["BAD"], _failing_analyze())
        assert results[0].score is None

    def test_failures_appear_after_successes(self):
        def _analyze(ticker: str) -> StockReport:
            if ticker == "BAD":
                raise RuntimeError("error")
            return _make_report(ticker=ticker, score=40.0)

        results = scan_watchlist(["AAPL", "BAD", "MSFT"], _analyze)
        succeeded = [r for r in results if r.succeeded]
        failed = [r for r in results if not r.succeeded]
        assert results == succeeded + failed

    def test_failures_preserve_encounter_order(self):
        results = scan_watchlist(
            ["FAIL1", "FAIL2", "FAIL3"],
            _failing_analyze(),
        )
        tickers = [r.ticker for r in results]
        assert tickers == ["FAIL1", "FAIL2", "FAIL3"]

    def test_partial_failure_mixed_results(self):
        def _analyze(ticker: str) -> StockReport:
            if ticker in {"BAD1", "BAD2"}:
                raise ValueError(f"bad: {ticker}")
            return _make_report(ticker=ticker, score=70.0)

        results = scan_watchlist(["AAPL", "BAD1", "MSFT", "BAD2"], _analyze)
        assert sum(1 for r in results if r.succeeded) == 2
        assert sum(1 for r in results if not r.succeeded) == 2

    def test_all_failures_returns_all_failed(self):
        results = scan_watchlist(["A", "B", "C"], _failing_analyze())
        assert all(not r.succeeded for r in results)
        assert len(results) == 3

    def test_error_message_non_empty_for_exception_with_empty_str(self):
        def _analyze(ticker: str) -> StockReport:
            raise RuntimeError()

        results = scan_watchlist(["AAPL"], _analyze)
        assert results[0].error_message  # truthy — not empty


# ---------------------------------------------------------------------------
# format_watchlist_summary
# ---------------------------------------------------------------------------

class TestFormatWatchlistSummary:
    def _success(
        self,
        ticker: str = "AAPL",
        score: float = 62.0,
        category: RatingCategory = RatingCategory.WATCHLIST,
        confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
    ) -> WatchlistResult:
        return WatchlistResult(
            ticker=ticker,
            final_category=category,
            score=score,
            confidence_level=confidence,
        )

    def _failure(self, ticker: str = "BAD", message: str = "fetch failed") -> WatchlistResult:
        return WatchlistResult(ticker=ticker, error_message=message)

    def test_returns_string(self):
        assert isinstance(format_watchlist_summary([self._success()]), str)

    def test_non_empty_string(self):
        assert len(format_watchlist_summary([self._success()])) > 0

    def test_contains_watchlist_scan_header(self):
        assert "WATCHLIST SCAN" in format_watchlist_summary([self._success()])

    def test_contains_ticker(self):
        assert "AAPL" in format_watchlist_summary([self._success("AAPL")])

    def test_contains_category(self):
        out = format_watchlist_summary([self._success(category=RatingCategory.BUY_CANDIDATE)])
        assert "Buy Candidate" in out

    def test_contains_score(self):
        assert "72.5" in format_watchlist_summary([self._success(score=72.5)])

    def test_contains_confidence(self):
        assert "Medium" in format_watchlist_summary([self._success(confidence=ConfidenceLevel.MEDIUM)])

    def test_shows_error_for_failed_result(self):
        out = format_watchlist_summary([self._failure("BAD", "network down")])
        assert "ERROR" in out
        assert "network down" in out

    def test_failed_ticker_shown(self):
        out = format_watchlist_summary([self._failure("TSLA")])
        assert "TSLA" in out

    def test_scanned_count_in_footer(self):
        results = [self._success("AAPL"), self._success("MSFT")]
        assert "Scanned: 2" in format_watchlist_summary(results)

    def test_success_count_in_footer(self):
        results = [self._success(), self._failure()]
        assert "Success: 1" in format_watchlist_summary(results)

    def test_failed_count_in_footer(self):
        results = [self._success(), self._failure()]
        assert "Failed: 1" in format_watchlist_summary(results)

    def test_zero_failed_when_all_succeed(self):
        results = [self._success("AAPL"), self._success("MSFT")]
        assert "Failed: 0" in format_watchlist_summary(results)

    def test_ticker_count_in_header(self):
        results = [self._success("AAPL"), self._success("MSFT"), self._success("NVDA")]
        assert "3 tickers" in format_watchlist_summary(results)

    def test_singular_ticker_in_header(self):
        assert "1 ticker" in format_watchlist_summary([self._success()])

    def test_output_preserves_given_order(self):
        # format_watchlist_summary renders in the order provided; sorting is scan_watchlist's job
        results = [
            self._success("FIRST", score=85.0),
            self._success("SECOND", score=30.0),
        ]
        out = format_watchlist_summary(results)
        assert out.index("FIRST") < out.index("SECOND")

    def test_empty_results_does_not_crash(self):
        out = format_watchlist_summary([])
        assert "Scanned: 0" in out

    def test_column_headers_present(self):
        out = format_watchlist_summary([self._success()])
        assert "TICKER" in out
        assert "CATEGORY" in out
        assert "SCORE" in out
        assert "CONFIDENCE" in out

    def test_long_error_message_truncated(self):
        long_err = "A" * 200
        out = format_watchlist_summary([self._failure(message=long_err)])
        for line in out.splitlines():
            assert len(line) <= 120, f"line too long: {len(line)}"


# ---------------------------------------------------------------------------
# CLI integration — watchlist mode in main()
# ---------------------------------------------------------------------------

class TestMainWatchlistCLI:
    def test_watchlist_flag_runs_watchlist_mode(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with patch("app.main._run_watchlist", return_value=0) as mock_run:
            result = main(["--watchlist", str(p)])
        mock_run.assert_called_once_with(str(p), False, False)
        assert result == 0

    def test_watchlist_passes_save_report_flag(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with patch("app.main._run_watchlist", return_value=0) as mock_run:
            main(["--watchlist", str(p), "--save-report"])
        mock_run.assert_called_once_with(str(p), True, False)

    def test_watchlist_passes_save_json_flag(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with patch("app.main._run_watchlist", return_value=0) as mock_run:
            main(["--watchlist", str(p), "--save-json"])
        mock_run.assert_called_once_with(str(p), False, True)

    def test_watchlist_passes_both_save_flags(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with patch("app.main._run_watchlist", return_value=0) as mock_run:
            main(["--watchlist", str(p), "--save-report", "--save-json"])
        mock_run.assert_called_once_with(str(p), True, True)

    def test_watchlist_flag_missing_path_returns_1(self, capsys):
        result = main(["--watchlist"])
        assert result == 1
        assert "requires a file path" in capsys.readouterr().err

    def test_watchlist_and_ticker_together_returns_1(self, tmp_path, capsys):
        p = _write_watchlist(tmp_path, "AAPL\n")
        result = main(["MSFT", "--watchlist", str(p)])
        assert result == 1
        assert "not both" in capsys.readouterr().err

    def test_missing_watchlist_file_returns_1(self, tmp_path, capsys):
        missing = tmp_path / "missing.txt"
        result = main(["--watchlist", str(missing)])
        assert result == 1
        assert "Error" in capsys.readouterr().err

    def test_watchlist_success_prints_output(self, tmp_path, capsys):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with patch(
            "app.main.analyze_ticker",
            return_value=_make_mock_rating("AAPL"),
        ):
            result = main(["--watchlist", str(p)])
        out = capsys.readouterr().out
        assert result == 0
        assert "WATCHLIST SCAN" in out

    def test_watchlist_partial_failure_still_returns_0(self, tmp_path, capsys):
        p = _write_watchlist(tmp_path, "AAPL\nBAD\n")

        def _fake_pipeline(ticker: str):
            if ticker == "BAD":
                raise RuntimeError("bad ticker")
            from app.models.rating import ConfidenceLevel, Rating, RatingCategory
            from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength
            sig = Signal(
                name="T", category=SignalCategory.TECHNICAL,
                direction=SignalDirection.NEUTRAL, strength=SignalStrength.MODERATE,
                description="desc.", score_impact=0.0, confidence=0.5,
            )
            return Rating(
                ticker=ticker, final_category=RatingCategory.WATCHLIST, score=60.0,
                confidence=ConfidenceLevel.MEDIUM, explanation="ok",
                technical_score=60.0, signals_used=[sig], data_sources_used=["yfinance"],
            )

        with patch("app.main.analyze_ticker", side_effect=_fake_pipeline):
            result = main(["--watchlist", str(p)])
        assert result == 0

    def test_single_ticker_still_works_with_watchlist_code_present(self):
        """Existing single-ticker path is unaffected by watchlist additions."""
        from app.models.rating import ConfidenceLevel, Rating, RatingCategory
        from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength
        sig = Signal(
            name="T", category=SignalCategory.TECHNICAL,
            direction=SignalDirection.NEUTRAL, strength=SignalStrength.MODERATE,
            description="desc.", score_impact=0.1, confidence=0.6,
        )
        rating = Rating(
            ticker="AAPL", final_category=RatingCategory.WATCHLIST, score=60.0,
            confidence=ConfidenceLevel.MEDIUM, explanation="ok",
            technical_score=60.0, signals_used=[sig], data_sources_used=["yfinance"],
        )
        with patch("app.main.analyze_ticker", return_value=rating):
            result = main(["AAPL"])
        assert result == 0

    def test_no_args_still_returns_1(self):
        assert main([]) == 1

    def test_no_args_still_prints_usage(self, capsys):
        main([])
        assert "Usage" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Watchlist save CLI — --save-report
# ---------------------------------------------------------------------------

_FAKE_REPORT_PATH = Path("outputs/reports/WATCHLIST_20240601_000000.txt")
_FAKE_JSON_PATH   = Path("outputs/results/WATCHLIST_20240601_000000.json")

_PATCH_SAVE_TEXT = "app.main.save_text_report"
_PATCH_SAVE_JSON = "app.main.save_json_result"


class TestWatchlistSaveReport:
    def test_save_report_calls_save_text_report(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_TEXT, return_value=_FAKE_REPORT_PATH) as mock_save,
        ):
            main(["--watchlist", str(p), "--save-report"])
        mock_save.assert_called_once()

    def test_save_report_receives_summary_text(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_TEXT, return_value=_FAKE_REPORT_PATH) as mock_save,
        ):
            main(["--watchlist", str(p), "--save-report"])
        text_arg = mock_save.call_args.args[0]
        assert isinstance(text_arg, str)
        assert "WATCHLIST SCAN" in text_arg

    def test_save_report_uses_watchlist_label(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_TEXT, return_value=_FAKE_REPORT_PATH) as mock_save,
        ):
            main(["--watchlist", str(p), "--save-report"])
        ticker_arg = mock_save.call_args.args[1]
        assert ticker_arg == "WATCHLIST"

    def test_save_report_confirmation_printed(self, tmp_path, capsys):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_TEXT, return_value=_FAKE_REPORT_PATH),
        ):
            main(["--watchlist", str(p), "--save-report"])
        out = capsys.readouterr().out
        assert "Saved text report to:" in out
        assert str(_FAKE_REPORT_PATH) in out

    def test_save_report_text_same_as_printed_summary(self, tmp_path, capsys):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_TEXT, return_value=_FAKE_REPORT_PATH) as mock_save,
        ):
            main(["--watchlist", str(p), "--save-report"])
        printed = capsys.readouterr().out
        saved_text = mock_save.call_args.args[0]
        assert saved_text in printed

    def test_save_report_storage_error_prints_warning(self, tmp_path, capsys):
        from app.data.storage import StorageError
        p = _write_watchlist(tmp_path, "AAPL\n")
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_TEXT, side_effect=StorageError("disk full")),
        ):
            result = main(["--watchlist", str(p), "--save-report"])
        assert result == 0
        assert "Warning" in capsys.readouterr().err

    def test_no_save_report_without_flag(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_TEXT) as mock_save,
        ):
            main(["--watchlist", str(p)])
        mock_save.assert_not_called()

    def test_summary_still_printed_with_save_report(self, tmp_path, capsys):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_TEXT, return_value=_FAKE_REPORT_PATH),
        ):
            main(["--watchlist", str(p), "--save-report"])
        assert "WATCHLIST SCAN" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Watchlist save CLI — --save-json
# ---------------------------------------------------------------------------

class TestWatchlistSaveJson:
    def test_save_json_calls_save_json_result(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_JSON, return_value=_FAKE_JSON_PATH) as mock_save,
        ):
            main(["--watchlist", str(p), "--save-json"])
        mock_save.assert_called_once()

    def test_save_json_uses_watchlist_label(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_JSON, return_value=_FAKE_JSON_PATH) as mock_save,
        ):
            main(["--watchlist", str(p), "--save-json"])
        ticker_arg = mock_save.call_args.args[1]
        assert ticker_arg == "WATCHLIST"

    def test_save_json_data_contains_results_key(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_JSON, return_value=_FAKE_JSON_PATH) as mock_save,
        ):
            main(["--watchlist", str(p), "--save-json"])
        data_arg = mock_save.call_args.args[0]
        assert "results" in data_arg

    def test_save_json_includes_successful_results(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_JSON, return_value=_FAKE_JSON_PATH) as mock_save,
        ):
            main(["--watchlist", str(p), "--save-json"])
        data_arg = mock_save.call_args.args[0]
        assert any(r["ticker"] == "AAPL" for r in data_arg["results"])

    def test_save_json_includes_failed_results(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\nBAD\n")

        def _pipeline(ticker: str):
            if ticker == "BAD":
                raise RuntimeError("bad ticker")
            return _make_mock_rating(ticker)

        with (
            patch("app.main.analyze_ticker", side_effect=_pipeline),
            patch(_PATCH_SAVE_JSON, return_value=_FAKE_JSON_PATH) as mock_save,
        ):
            main(["--watchlist", str(p), "--save-json"])
        data_arg = mock_save.call_args.args[0]
        failed = [r for r in data_arg["results"] if not r["succeeded"]]
        assert any(r["ticker"] == "BAD" for r in failed)

    def test_save_json_confirmation_printed(self, tmp_path, capsys):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_JSON, return_value=_FAKE_JSON_PATH),
        ):
            main(["--watchlist", str(p), "--save-json"])
        out = capsys.readouterr().out
        assert "Saved JSON result to:" in out
        assert str(_FAKE_JSON_PATH) in out

    def test_save_json_storage_error_prints_warning(self, tmp_path, capsys):
        from app.data.storage import StorageError
        p = _write_watchlist(tmp_path, "AAPL\n")
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_JSON, side_effect=StorageError("no space")),
        ):
            result = main(["--watchlist", str(p), "--save-json"])
        assert result == 0
        assert "Warning" in capsys.readouterr().err

    def test_no_save_json_without_flag(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_JSON) as mock_save,
        ):
            main(["--watchlist", str(p)])
        mock_save.assert_not_called()

    def test_summary_still_printed_with_save_json(self, tmp_path, capsys):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_JSON, return_value=_FAKE_JSON_PATH),
        ):
            main(["--watchlist", str(p), "--save-json"])
        assert "WATCHLIST SCAN" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Watchlist save CLI — both flags
# ---------------------------------------------------------------------------

class TestWatchlistBothSaveFlags:
    def test_both_flags_call_both_save_functions(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_TEXT, return_value=_FAKE_REPORT_PATH) as mock_txt,
            patch(_PATCH_SAVE_JSON, return_value=_FAKE_JSON_PATH) as mock_json,
        ):
            result = main(["--watchlist", str(p), "--save-report", "--save-json"])
        assert result == 0
        mock_txt.assert_called_once()
        mock_json.assert_called_once()

    def test_both_flags_print_both_confirmations(self, tmp_path, capsys):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_TEXT, return_value=_FAKE_REPORT_PATH),
            patch(_PATCH_SAVE_JSON, return_value=_FAKE_JSON_PATH),
        ):
            main(["--watchlist", str(p), "--save-report", "--save-json"])
        out = capsys.readouterr().out
        assert "Saved text report to:" in out
        assert "Saved JSON result to:" in out

    def test_json_error_does_not_prevent_text_save(self, tmp_path, capsys):
        from app.data.storage import StorageError
        p = _write_watchlist(tmp_path, "AAPL\n")
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_TEXT, return_value=_FAKE_REPORT_PATH) as mock_txt,
            patch(_PATCH_SAVE_JSON, side_effect=StorageError("no space")),
        ):
            result = main(["--watchlist", str(p), "--save-report", "--save-json"])
        assert result == 0
        mock_txt.assert_called_once()

    def test_returns_0_with_both_flags(self, tmp_path):
        p = _write_watchlist(tmp_path, "AAPL\n")
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_TEXT, return_value=_FAKE_REPORT_PATH),
            patch(_PATCH_SAVE_JSON, return_value=_FAKE_JSON_PATH),
        ):
            assert main(["--watchlist", str(p), "--save-report", "--save-json"]) == 0


# ---------------------------------------------------------------------------
# serialize_watchlist_results
# ---------------------------------------------------------------------------

class TestSerializeWatchlistResults:
    def _success(
        self,
        ticker: str = "AAPL",
        score: float = 62.0,
        category: RatingCategory = RatingCategory.WATCHLIST,
        confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
        company_name: str | None = None,
        current_price: float | None = None,
    ) -> WatchlistResult:
        return WatchlistResult(
            ticker=ticker,
            company_name=company_name,
            final_category=category,
            score=score,
            confidence_level=confidence,
            current_price=current_price,
        )

    def _failure(self, ticker: str = "BAD", message: str = "error") -> WatchlistResult:
        return WatchlistResult(ticker=ticker, error_message=message)

    def test_returns_list(self):
        assert isinstance(serialize_watchlist_results([self._success()]), list)

    def test_length_matches_input(self):
        assert len(serialize_watchlist_results([self._success(), self._failure()])) == 2

    def test_ticker_preserved(self):
        result = serialize_watchlist_results([self._success("MSFT")])
        assert result[0]["ticker"] == "MSFT"

    def test_score_preserved(self):
        result = serialize_watchlist_results([self._success(score=72.5)])
        assert result[0]["score"] == pytest.approx(72.5)

    def test_final_category_serialized_as_string(self):
        result = serialize_watchlist_results([self._success(category=RatingCategory.BUY_CANDIDATE)])
        assert result[0]["final_category"] == "Buy Candidate"

    def test_confidence_level_serialized_as_string(self):
        result = serialize_watchlist_results([self._success(confidence=ConfidenceLevel.HIGH)])
        assert result[0]["confidence_level"] == "high"

    def test_company_name_included(self):
        result = serialize_watchlist_results([self._success(company_name="Apple Inc.")])
        assert result[0]["company_name"] == "Apple Inc."

    def test_current_price_included(self):
        result = serialize_watchlist_results([self._success(current_price=182.50)])
        assert result[0]["current_price"] == pytest.approx(182.50)

    def test_none_fields_preserved_as_none(self):
        result = serialize_watchlist_results([self._success(company_name=None, current_price=None)])
        assert result[0]["company_name"] is None
        assert result[0]["current_price"] is None

    def test_succeeded_true_for_success(self):
        result = serialize_watchlist_results([self._success()])
        assert result[0]["succeeded"] is True

    def test_error_message_none_for_success(self):
        result = serialize_watchlist_results([self._success()])
        assert result[0]["error_message"] is None

    def test_failure_has_error_message(self):
        result = serialize_watchlist_results([self._failure(message="timeout")])
        assert result[0]["error_message"] == "timeout"

    def test_succeeded_false_for_failure(self):
        result = serialize_watchlist_results([self._failure()])
        assert result[0]["succeeded"] is False

    def test_failure_category_is_none(self):
        result = serialize_watchlist_results([self._failure()])
        assert result[0]["final_category"] is None

    def test_failure_score_is_none(self):
        result = serialize_watchlist_results([self._failure()])
        assert result[0]["score"] is None

    def test_failure_confidence_is_none(self):
        result = serialize_watchlist_results([self._failure()])
        assert result[0]["confidence_level"] is None

    def test_order_preserved(self):
        results = [self._success("FIRST"), self._success("SECOND"), self._failure("THIRD")]
        serialized = serialize_watchlist_results(results)
        assert [r["ticker"] for r in serialized] == ["FIRST", "SECOND", "THIRD"]

    def test_output_is_json_serializable(self):
        results = [self._success(), self._failure()]
        serialized = serialize_watchlist_results(results)
        # Should not raise
        json_text = json.dumps({"results": serialized})
        parsed = json.loads(json_text)
        assert len(parsed["results"]) == 2

    def test_all_required_keys_present(self):
        result = serialize_watchlist_results([self._success()])[0]
        required = {
            "ticker", "company_name", "final_category", "score",
            "confidence_level", "current_price", "error_message", "succeeded",
        }
        assert required <= result.keys()

    def test_empty_list_returns_empty_list(self):
        assert serialize_watchlist_results([]) == []


# ---------------------------------------------------------------------------
# Single-ticker save behavior unchanged
# ---------------------------------------------------------------------------

class TestSingleTickerSaveUnchanged:
    """Verify that single-ticker --save-report/--save-json are unaffected."""

    _FAKE_SINGLE_TXT  = Path("outputs/reports/AAPL_20240601_000000.txt")
    _FAKE_SINGLE_JSON = Path("outputs/results/AAPL_20240601_000000.json")

    def test_save_report_flag_still_works_for_single_ticker(self, tmp_path):
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_TEXT, return_value=self._FAKE_SINGLE_TXT) as mock_save,
        ):
            result = main(["AAPL", "--save-report"])
        assert result == 0
        mock_save.assert_called_once()

    def test_save_json_flag_still_works_for_single_ticker(self, tmp_path):
        from app.models.rating import Rating
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_JSON, return_value=self._FAKE_SINGLE_JSON) as mock_save,
        ):
            result = main(["AAPL", "--save-json"])
        assert result == 0
        mock_save.assert_called_once()
        # Single-ticker JSON receives a Rating model, not a dict
        data_arg = mock_save.call_args.args[0]
        from app.models.rating import Rating
        assert isinstance(data_arg, Rating)

    def test_single_ticker_save_does_not_call_watchlist_save(self, tmp_path):
        with (
            patch("app.main.analyze_ticker", return_value=_make_mock_rating("AAPL")),
            patch(_PATCH_SAVE_TEXT, return_value=self._FAKE_SINGLE_TXT),
            patch("app.main._run_watchlist") as mock_watchlist,
        ):
            main(["AAPL", "--save-report"])
        mock_watchlist.assert_not_called()


# ---------------------------------------------------------------------------
# Helpers for CLI tests
# ---------------------------------------------------------------------------

def _make_mock_rating(ticker: str):
    from app.models.rating import ConfidenceLevel, Rating, RatingCategory
    from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength
    sig = Signal(
        name="T", category=SignalCategory.TECHNICAL,
        direction=SignalDirection.NEUTRAL, strength=SignalStrength.MODERATE,
        description="Test signal.", score_impact=0.1, confidence=0.6,
    )
    return Rating(
        ticker=ticker,
        final_category=RatingCategory.WATCHLIST,
        score=60.0,
        confidence=ConfidenceLevel.MEDIUM,
        explanation="Test rating.",
        technical_score=60.0,
        signals_used=[sig],
        data_sources_used=["yfinance"],
    )
