"""
Tests for the saved watchlist analysis snapshot endpoints.

Integration tests: routes call the real services against a temporary SQLite
database. ``analyze_stock`` is mocked so no network calls happen. Both the
watchlist service and the snapshot service are pointed at the same temp engine.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import app.services.watchlist_analysis_snapshot_service as snapshot_service
import app.services.watchlist_service as watchlist_service
from app.data.database import build_engine
from app.models.rating import ConfidenceLevel, RatingCategory
from app.models.stock_report import StockReport

_ANALYZE = "app.services.watchlist_analysis_service.analyze_stock"


def _report_for(ticker: str) -> StockReport:
    return StockReport(
        ticker=ticker,
        final_category=RatingCategory.WATCHLIST,
        score=60.0,
        confidence_level=ConfidenceLevel.MEDIUM,
        company_name=f"{ticker} Inc.",
        current_price=100.0,
    )


def _analyze_ok(*ok_tickers):
    ok = set(ok_tickers)

    def _side_effect(ticker: str) -> StockReport:
        if ticker in ok:
            return _report_for(ticker)
        raise RuntimeError(f"no data for {ticker}")

    return _side_effect


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """TestClient whose watchlist + snapshot services share one temp database."""
    engine = build_engine(tmp_path / "test.db")
    monkeypatch.setattr(watchlist_service, "_engine", engine)
    monkeypatch.setattr(snapshot_service, "_engine", engine)

    from app.api.main import create_app

    return TestClient(create_app())


def _make_watchlist(client, tickers, name="Tech") -> int:
    wl_id = client.post("/api/watchlists", json={"name": name}).json()["id"]
    for ticker in tickers:
        client.post(f"/api/watchlists/{wl_id}/tickers", json={"ticker": ticker})
    return wl_id


# ---------------------------------------------------------------------------
# POST analyze-and-save
# ---------------------------------------------------------------------------


class TestCreateSnapshot:
    def test_returns_201(self, client):
        wl_id = _make_watchlist(client, ["AAPL"])
        with patch(_ANALYZE, side_effect=_analyze_ok("AAPL")):
            resp = client.post(f"/api/watchlists/{wl_id}/analysis-snapshots")
        assert resp.status_code == 201

    def test_response_counts_and_results(self, client):
        wl_id = _make_watchlist(client, ["AAPL", "MSFT", "BADX"], name="My List")
        with patch(_ANALYZE, side_effect=_analyze_ok("AAPL", "MSFT")):
            data = client.post(
                f"/api/watchlists/{wl_id}/analysis-snapshots"
            ).json()
        assert data["watchlist_name"] == "My List"
        assert data["total_tickers"] == 3
        assert data["success_count"] == 2
        assert data["failure_count"] == 1
        assert {r["ticker"] for r in data["results"]} == {"AAPL", "MSFT"}

    def test_snapshot_includes_failed_ticker_errors(self, client):
        wl_id = _make_watchlist(client, ["AAPL", "BADX"])
        with patch(_ANALYZE, side_effect=_analyze_ok("AAPL")):
            data = client.post(
                f"/api/watchlists/{wl_id}/analysis-snapshots"
            ).json()
        assert len(data["errors"]) == 1
        assert data["errors"][0]["ticker"] == "BADX"
        assert data["errors"][0]["error"]

    def test_missing_watchlist_returns_404(self, client):
        with patch(_ANALYZE):
            resp = client.post("/api/watchlists/999/analysis-snapshots")
        assert resp.status_code == 404

    def test_empty_watchlist_returns_400(self, client):
        wl_id = _make_watchlist(client, [])
        with patch(_ANALYZE):
            resp = client.post(f"/api/watchlists/{wl_id}/analysis-snapshots")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET list
# ---------------------------------------------------------------------------


class TestListSnapshots:
    def test_empty_when_none_saved(self, client):
        wl_id = _make_watchlist(client, ["AAPL"])
        resp = client.get(f"/api/watchlists/{wl_id}/analysis-snapshots")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_lists_saved_snapshot(self, client):
        wl_id = _make_watchlist(client, ["AAPL"])
        with patch(_ANALYZE, side_effect=_analyze_ok("AAPL")):
            client.post(f"/api/watchlists/{wl_id}/analysis-snapshots")
        data = client.get(f"/api/watchlists/{wl_id}/analysis-snapshots").json()
        assert len(data) == 1
        assert data[0]["success_count"] == 1
        # Summaries must not carry the heavy per-ticker results.
        assert "results" not in data[0]

    def test_missing_watchlist_returns_404(self, client):
        assert client.get("/api/watchlists/999/analysis-snapshots").status_code == 404


# ---------------------------------------------------------------------------
# GET detail
# ---------------------------------------------------------------------------


class TestSnapshotDetail:
    def test_returns_detail(self, client):
        wl_id = _make_watchlist(client, ["AAPL", "BADX"])
        with patch(_ANALYZE, side_effect=_analyze_ok("AAPL")):
            snap_id = client.post(
                f"/api/watchlists/{wl_id}/analysis-snapshots"
            ).json()["id"]
        data = client.get(f"/api/watchlist-analysis-snapshots/{snap_id}").json()
        assert data["id"] == snap_id
        assert len(data["results"]) == 1
        assert len(data["errors"]) == 1
        assert data["results"][0]["report"]["ticker"] == "AAPL"

    def test_missing_snapshot_returns_404(self, client):
        assert (
            client.get("/api/watchlist-analysis-snapshots/999").status_code == 404
        )


# ---------------------------------------------------------------------------
# Analyze-only must NOT save
# ---------------------------------------------------------------------------


class TestAnalyzeOnlyDoesNotSave:
    def test_analyze_only_creates_no_snapshot(self, client):
        wl_id = _make_watchlist(client, ["AAPL"])
        with patch(_ANALYZE, side_effect=_analyze_ok("AAPL")):
            analyze = client.post(f"/api/watchlists/{wl_id}/analyze")
        assert analyze.status_code == 200
        # No snapshot should have been written by the analyze-only endpoint.
        snaps = client.get(f"/api/watchlists/{wl_id}/analysis-snapshots").json()
        assert snaps == []
