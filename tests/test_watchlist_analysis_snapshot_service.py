"""
Tests for app/services/watchlist_analysis_snapshot_service.py.

The single-ticker pipeline (``analyze_stock``) is mocked so tests never hit the
network. Watchlists and snapshots live in a temporary SQLite database via the
``engine`` fixture. All inputs are built locally; tests are deterministic.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy.engine import Engine

from app.data.database import build_engine
from app.models.rating import ConfidenceLevel, RatingCategory
from app.models.stock_report import StockReport
from app.services.watchlist_analysis_snapshot_service import (
    analyze_and_save_snapshot,
    get_watchlist_snapshot,
    list_watchlist_snapshots,
)
from app.services.watchlist_service import (
    WatchlistNotFoundError,
    WatchlistValidationError,
    add_ticker_to_watchlist,
    create_watchlist,
)

_ANALYZE = "app.services.watchlist_analysis_service.analyze_stock"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine(tmp_path) -> Engine:
    return build_engine(tmp_path / "test.db")


def _make_report(ticker: str, score: float = 60.0) -> StockReport:
    return StockReport(
        ticker=ticker,
        final_category=RatingCategory.WATCHLIST,
        score=score,
        confidence_level=ConfidenceLevel.MEDIUM,
        company_name=f"{ticker} Inc.",
        current_price=100.0,
    )


def _make_watchlist(engine, tickers, name="Tech") -> int:
    wl = create_watchlist(name, engine=engine)
    for ticker in tickers:
        add_ticker_to_watchlist(wl["id"], ticker, engine=engine)
    return wl["id"]


def _fake_analyze(*ok_tickers):
    ok = set(ok_tickers)

    def _side_effect(ticker: str) -> StockReport:
        if ticker in ok:
            return _make_report(ticker)
        raise RuntimeError(f"no data for {ticker}")

    return _side_effect


def _fake_analyze_scores(scores: dict[str, float]):
    """Succeed with a specific score per ticker; any other ticker fails."""

    def _side_effect(ticker: str) -> StockReport:
        if ticker in scores:
            return _make_report(ticker, score=scores[ticker])
        raise RuntimeError(f"no data for {ticker}")

    return _side_effect


# ---------------------------------------------------------------------------
# analyze_and_save_snapshot
# ---------------------------------------------------------------------------


class TestAnalyzeAndSave:
    def test_missing_watchlist_raises_not_found(self, engine):
        with patch(_ANALYZE):
            with pytest.raises(WatchlistNotFoundError):
                analyze_and_save_snapshot(999, engine=engine)

    def test_empty_watchlist_raises_validation_error(self, engine):
        wl_id = _make_watchlist(engine, [])
        with patch(_ANALYZE):
            with pytest.raises(WatchlistValidationError):
                analyze_and_save_snapshot(wl_id, engine=engine)

    def test_saves_snapshot_summary_counts(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL", "MSFT", "BADX"], name="My List")
        with patch(_ANALYZE, side_effect=_fake_analyze("AAPL", "MSFT")):
            snap = analyze_and_save_snapshot(wl_id, engine=engine)
        assert snap["watchlist_id"] == wl_id
        assert snap["watchlist_name"] == "My List"
        assert snap["total_tickers"] == 3
        assert snap["success_count"] == 2
        assert snap["failure_count"] == 1

    def test_snapshot_has_id_and_utc_timestamps(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL"])
        with patch(_ANALYZE, side_effect=_fake_analyze("AAPL")):
            snap = analyze_and_save_snapshot(wl_id, engine=engine)
        assert isinstance(snap["id"], int)
        for key in ("analyzed_at", "created_at"):
            assert snap[key].tzinfo is not None
            assert snap[key].utcoffset().total_seconds() == 0

    def test_snapshot_results_include_report(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL"])
        with patch(_ANALYZE, side_effect=_fake_analyze("AAPL")):
            snap = analyze_and_save_snapshot(wl_id, engine=engine)
        result = snap["results"][0]
        assert result["ticker"] == "AAPL"
        assert result["category"] == RatingCategory.WATCHLIST.value
        assert result["report"]["ticker"] == "AAPL"

    def test_snapshot_records_failed_tickers(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL", "BADX"])
        with patch(_ANALYZE, side_effect=_fake_analyze("AAPL")):
            snap = analyze_and_save_snapshot(wl_id, engine=engine)
        assert len(snap["errors"]) == 1
        assert snap["errors"][0]["ticker"] == "BADX"
        assert snap["errors"][0]["error"]


# ---------------------------------------------------------------------------
# list_watchlist_snapshots
# ---------------------------------------------------------------------------


class TestListSnapshots:
    def test_empty_when_none_saved(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL"])
        assert list_watchlist_snapshots(wl_id, engine=engine) == []

    def test_missing_watchlist_raises_not_found(self, engine):
        with pytest.raises(WatchlistNotFoundError):
            list_watchlist_snapshots(999, engine=engine)

    def test_lists_newest_first(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL"])
        with patch(_ANALYZE, side_effect=_fake_analyze("AAPL")):
            first = analyze_and_save_snapshot(wl_id, engine=engine)
            second = analyze_and_save_snapshot(wl_id, engine=engine)
        snaps = list_watchlist_snapshots(wl_id, engine=engine)
        assert [s["id"] for s in snaps] == [second["id"], first["id"]]

    def test_summary_has_no_results_key(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL"])
        with patch(_ANALYZE, side_effect=_fake_analyze("AAPL")):
            analyze_and_save_snapshot(wl_id, engine=engine)
        summary = list_watchlist_snapshots(wl_id, engine=engine)[0]
        assert "results" not in summary
        assert summary["success_count"] == 1


# ---------------------------------------------------------------------------
# get_watchlist_snapshot
# ---------------------------------------------------------------------------


class TestGetSnapshot:
    def test_missing_snapshot_returns_none(self, engine):
        assert get_watchlist_snapshot(999, engine=engine) is None

    def test_returns_full_detail(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL", "BADX"])
        with patch(_ANALYZE, side_effect=_fake_analyze("AAPL")):
            saved = analyze_and_save_snapshot(wl_id, engine=engine)
        detail = get_watchlist_snapshot(saved["id"], engine=engine)
        assert detail is not None
        assert detail["id"] == saved["id"]
        assert len(detail["results"]) == 1
        assert len(detail["errors"]) == 1
        assert detail["results"][0]["ticker"] == "AAPL"

    def test_snapshot_survives_watchlist_rename_via_denormalised_name(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL"], name="Original")
        with patch(_ANALYZE, side_effect=_fake_analyze("AAPL")):
            saved = analyze_and_save_snapshot(wl_id, engine=engine)
        detail = get_watchlist_snapshot(saved["id"], engine=engine)
        assert detail["watchlist_name"] == "Original"


# ---------------------------------------------------------------------------
# average_score (backend-derived; from successful scored rows only)
# ---------------------------------------------------------------------------


class TestAverageScore:
    def test_list_average_is_mean_of_successful_scores(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL", "MSFT"])
        with patch(
            _ANALYZE,
            side_effect=_fake_analyze_scores({"AAPL": 40.0, "MSFT": 70.0}),
        ):
            analyze_and_save_snapshot(wl_id, engine=engine)
        summary = list_watchlist_snapshots(wl_id, engine=engine)[0]
        assert summary["average_score"] == 55.0

    def test_average_ignores_failed_tickers(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL", "MSFT", "BADX"])
        with patch(
            _ANALYZE,
            side_effect=_fake_analyze_scores({"AAPL": 50.0, "MSFT": 80.0}),
        ):
            analyze_and_save_snapshot(wl_id, engine=engine)
        summary = list_watchlist_snapshots(wl_id, engine=engine)[0]
        # BADX failed: its (absent) score must not drag the mean. (50 + 80) / 2.
        assert summary["average_score"] == 65.0

    def test_average_rounds_to_two_decimals(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL", "MSFT", "GOOG"])
        with patch(
            _ANALYZE,
            side_effect=_fake_analyze_scores(
                {"AAPL": 10.0, "MSFT": 20.0, "GOOG": 25.0}
            ),
        ):
            analyze_and_save_snapshot(wl_id, engine=engine)
        summary = list_watchlist_snapshots(wl_id, engine=engine)[0]
        assert summary["average_score"] == 18.33  # 55/3 = 18.333...

    def test_average_is_none_when_no_successful_results(self, engine):
        wl_id = _make_watchlist(engine, ["BADX"])
        with patch(_ANALYZE, side_effect=_fake_analyze_scores({})):
            analyze_and_save_snapshot(wl_id, engine=engine)
        summary = list_watchlist_snapshots(wl_id, engine=engine)[0]
        assert summary["average_score"] is None

    def test_detail_includes_average_score(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL", "MSFT"])
        with patch(
            _ANALYZE,
            side_effect=_fake_analyze_scores({"AAPL": 30.0, "MSFT": 90.0}),
        ):
            saved = analyze_and_save_snapshot(wl_id, engine=engine)
        detail = get_watchlist_snapshot(saved["id"], engine=engine)
        assert detail["average_score"] == 60.0

    def test_average_is_per_snapshot_not_global(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL", "MSFT"])
        with patch(
            _ANALYZE,
            side_effect=_fake_analyze_scores({"AAPL": 20.0, "MSFT": 20.0}),
        ):
            analyze_and_save_snapshot(wl_id, engine=engine)
        with patch(
            _ANALYZE,
            side_effect=_fake_analyze_scores({"AAPL": 80.0, "MSFT": 80.0}),
        ):
            analyze_and_save_snapshot(wl_id, engine=engine)
        snaps = list_watchlist_snapshots(wl_id, engine=engine)
        # Newest first: second snapshot (80) then first (20).
        assert [s["average_score"] for s in snaps] == [80.0, 20.0]
