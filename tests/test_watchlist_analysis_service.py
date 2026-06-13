"""
Tests for app/services/watchlist_analysis_service.py.

The single-ticker pipeline (``analyze_stock``) is mocked so tests never hit
yfinance or the network. Watchlists are created in a temporary SQLite database
via the ``engine`` fixture. All inputs are built locally; tests are deterministic.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy.engine import Engine

from app.data.database import build_engine
from app.models.rating import ConfidenceLevel, RatingCategory
from app.models.stock_report import StockReport
from app.services.watchlist_analysis_service import analyze_watchlist
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


def _make_report(ticker: str) -> StockReport:
    return StockReport(
        ticker=ticker,
        final_category=RatingCategory.WATCHLIST,
        score=60.0,
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
    """Return a side_effect: succeeds for ok_tickers, raises for the rest."""
    ok = set(ok_tickers)

    def _side_effect(ticker: str) -> StockReport:
        if ticker in ok:
            return _make_report(ticker)
        raise RuntimeError(f"no data for {ticker}")

    return _side_effect


# ---------------------------------------------------------------------------
# Watchlist-level errors
# ---------------------------------------------------------------------------


class TestWatchlistErrors:
    def test_missing_watchlist_raises_not_found(self, engine):
        with patch(_ANALYZE):
            with pytest.raises(WatchlistNotFoundError):
                analyze_watchlist(999, engine=engine)

    def test_empty_watchlist_raises_validation_error(self, engine):
        wl_id = _make_watchlist(engine, [])
        with patch(_ANALYZE):
            with pytest.raises(WatchlistValidationError):
                analyze_watchlist(wl_id, engine=engine)

    def test_empty_watchlist_does_not_call_analyze(self, engine):
        wl_id = _make_watchlist(engine, [])
        with patch(_ANALYZE) as mock_analyze:
            with pytest.raises(WatchlistValidationError):
                analyze_watchlist(wl_id, engine=engine)
        mock_analyze.assert_not_called()


# ---------------------------------------------------------------------------
# Successful analysis
# ---------------------------------------------------------------------------


class TestSuccessfulAnalysis:
    def test_single_ticker_one_result(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL"])
        with patch(_ANALYZE, side_effect=_fake_analyze("AAPL")):
            result = analyze_watchlist(wl_id, engine=engine)
        assert result["successful_count"] == 1
        assert result["failed_count"] == 0
        assert len(result["results"]) == 1

    def test_multiple_tickers_multiple_results(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL", "MSFT", "NVDA"])
        with patch(_ANALYZE, side_effect=_fake_analyze("AAPL", "MSFT", "NVDA")):
            result = analyze_watchlist(wl_id, engine=engine)
        assert result["total_tickers"] == 3
        assert result["successful_count"] == 3
        assert result["failed_count"] == 0
        assert {r["ticker"] for r in result["results"]} == {"AAPL", "MSFT", "NVDA"}

    def test_result_item_shape(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL"])
        with patch(_ANALYZE, side_effect=_fake_analyze("AAPL")):
            result = analyze_watchlist(wl_id, engine=engine)
        item = result["results"][0]
        assert item["ticker"] == "AAPL"
        assert item["company_name"] == "AAPL Inc."
        assert item["category"] == RatingCategory.WATCHLIST.value
        assert item["score"] == 60.0
        assert item["confidence"] == ConfidenceLevel.MEDIUM.value
        assert item["current_price"] == 100.0

    def test_result_item_includes_full_report(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL"])
        with patch(_ANALYZE, side_effect=_fake_analyze("AAPL")):
            result = analyze_watchlist(wl_id, engine=engine)
        report = result["results"][0]["report"]
        assert isinstance(report, dict)
        assert report["ticker"] == "AAPL"
        assert report["final_category"] == RatingCategory.WATCHLIST.value


# ---------------------------------------------------------------------------
# Partial / total failure
# ---------------------------------------------------------------------------


class TestPartialAndTotalFailure:
    def test_one_failure_does_not_block_others(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL", "BADX", "MSFT"])
        with patch(_ANALYZE, side_effect=_fake_analyze("AAPL", "MSFT")):
            result = analyze_watchlist(wl_id, engine=engine)
        assert result["successful_count"] == 2
        assert result["failed_count"] == 1
        assert {r["ticker"] for r in result["results"]} == {"AAPL", "MSFT"}
        assert result["errors"][0]["ticker"] == "BADX"

    def test_error_item_shape(self, engine):
        wl_id = _make_watchlist(engine, ["BADX"])
        with patch(_ANALYZE, side_effect=_fake_analyze()):
            result = analyze_watchlist(wl_id, engine=engine)
        err = result["errors"][0]
        assert err["ticker"] == "BADX"
        assert isinstance(err["error"], str)
        assert err["error"]

    def test_all_failures(self, engine):
        wl_id = _make_watchlist(engine, ["BADX", "BADY"])
        with patch(_ANALYZE, side_effect=_fake_analyze()):
            result = analyze_watchlist(wl_id, engine=engine)
        assert result["total_tickers"] == 2
        assert result["successful_count"] == 0
        assert result["failed_count"] == 2
        assert result["results"] == []
        assert {e["ticker"] for e in result["errors"]} == {"BADX", "BADY"}


# ---------------------------------------------------------------------------
# Response envelope
# ---------------------------------------------------------------------------


class TestResponseEnvelope:
    def test_has_all_keys(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL"], name="My List")
        with patch(_ANALYZE, side_effect=_fake_analyze("AAPL")):
            result = analyze_watchlist(wl_id, engine=engine)
        for key in (
            "watchlist_id",
            "watchlist_name",
            "analyzed_at",
            "total_tickers",
            "successful_count",
            "failed_count",
            "results",
            "errors",
        ):
            assert key in result

    def test_watchlist_identity(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL"], name="My List")
        with patch(_ANALYZE, side_effect=_fake_analyze("AAPL")):
            result = analyze_watchlist(wl_id, engine=engine)
        assert result["watchlist_id"] == wl_id
        assert result["watchlist_name"] == "My List"

    def test_analyzed_at_is_utc_aware(self, engine):
        wl_id = _make_watchlist(engine, ["AAPL"])
        with patch(_ANALYZE, side_effect=_fake_analyze("AAPL")):
            result = analyze_watchlist(wl_id, engine=engine)
        analyzed_at = result["analyzed_at"]
        assert analyzed_at.tzinfo is not None
        assert analyzed_at.utcoffset().total_seconds() == 0
