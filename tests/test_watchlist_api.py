"""
Tests for /api/watchlists/* endpoints.

These are integration tests: the routes call the real watchlist_service, which
runs against a temporary SQLite database injected via the service's module-level
engine.  No network calls and no writes to the real project database.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import app.services.watchlist_service as service
from app.data.database import build_engine
from app.models.rating import ConfidenceLevel, RatingCategory
from app.models.stock_report import StockReport

# analyze_stock as imported inside the watchlist analysis service module.
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
    """side_effect: succeed for ok_tickers, raise for everything else."""
    ok = set(ok_tickers)

    def _side_effect(ticker: str) -> StockReport:
        if ticker in ok:
            return _report_for(ticker)
        raise RuntimeError(f"no data for {ticker}")

    return _side_effect


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """TestClient whose watchlist service uses a temporary SQLite database."""
    engine = build_engine(tmp_path / "test.db")
    # Routes call service functions without an explicit engine, so they fall
    # back to the module-level shared engine.  Point that at the temp DB.
    monkeypatch.setattr(service, "_engine", engine)

    from app.api.main import create_app

    return TestClient(create_app())


def _create(client, name="Tech", description=None):
    body: dict = {"name": name}
    if description is not None:
        body["description"] = description
    return client.post("/api/watchlists", json=body)


# ---------------------------------------------------------------------------
# GET /api/watchlists
# ---------------------------------------------------------------------------


class TestListWatchlists:
    def test_returns_200(self, client):
        assert client.get("/api/watchlists").status_code == 200

    def test_empty_initially(self, client):
        assert client.get("/api/watchlists").json() == []

    def test_returns_created(self, client):
        _create(client, "Tech")
        _create(client, "Energy")
        data = client.get("/api/watchlists").json()
        assert len(data) == 2

    def test_summary_has_ticker_count(self, client):
        created = _create(client, "Tech").json()
        client.post(f"/api/watchlists/{created['id']}/tickers", json={"ticker": "AAPL"})
        data = client.get("/api/watchlists").json()
        assert data[0]["ticker_count"] == 1


# ---------------------------------------------------------------------------
# POST /api/watchlists
# ---------------------------------------------------------------------------


class TestCreateWatchlist:
    def test_returns_201(self, client):
        assert _create(client, "Tech").status_code == 201

    def test_response_has_id(self, client):
        assert isinstance(_create(client, "Tech").json()["id"], int)

    def test_stores_name(self, client):
        assert _create(client, "Tech").json()["name"] == "Tech"

    def test_stores_description(self, client):
        assert _create(client, "Tech", "Big tech").json()["description"] == "Big tech"

    def test_description_defaults_none(self, client):
        assert _create(client, "Tech").json()["description"] is None

    def test_tickers_start_empty(self, client):
        assert _create(client, "Tech").json()["tickers"] == []

    def test_blank_name_returns_400(self, client):
        assert _create(client, "   ").status_code == 400

    def test_missing_name_returns_422(self, client):
        # Pydantic request validation (missing required field) → 422.
        assert client.post("/api/watchlists", json={}).status_code == 422


# ---------------------------------------------------------------------------
# GET /api/watchlists/{id}
# ---------------------------------------------------------------------------


class TestGetWatchlist:
    def test_returns_detail(self, client):
        created = _create(client, "Tech").json()
        resp = client.get(f"/api/watchlists/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_includes_tickers(self, client):
        created = _create(client, "Tech").json()
        client.post(f"/api/watchlists/{created['id']}/tickers", json={"ticker": "AAPL"})
        assert client.get(f"/api/watchlists/{created['id']}").json()["tickers"] == ["AAPL"]

    def test_missing_returns_404(self, client):
        assert client.get("/api/watchlists/999").status_code == 404

    def test_non_integer_id_returns_422(self, client):
        assert client.get("/api/watchlists/abc").status_code == 422


# ---------------------------------------------------------------------------
# PATCH /api/watchlists/{id}
# ---------------------------------------------------------------------------


class TestUpdateWatchlist:
    def test_updates_name(self, client):
        created = _create(client, "Tech").json()
        resp = client.patch(f"/api/watchlists/{created['id']}", json={"name": "Technology"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Technology"

    def test_updates_description(self, client):
        created = _create(client, "Tech").json()
        resp = client.patch(
            f"/api/watchlists/{created['id']}", json={"description": "Updated"}
        )
        assert resp.json()["description"] == "Updated"

    def test_blank_name_returns_400(self, client):
        created = _create(client, "Tech").json()
        resp = client.patch(f"/api/watchlists/{created['id']}", json={"name": "  "})
        assert resp.status_code == 400

    def test_missing_returns_404(self, client):
        assert client.patch("/api/watchlists/999", json={"name": "X"}).status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/watchlists/{id}
# ---------------------------------------------------------------------------


class TestDeleteWatchlist:
    def test_returns_200(self, client):
        created = _create(client, "Tech").json()
        assert client.delete(f"/api/watchlists/{created['id']}").status_code == 200

    def test_removes_watchlist(self, client):
        created = _create(client, "Tech").json()
        client.delete(f"/api/watchlists/{created['id']}")
        assert client.get(f"/api/watchlists/{created['id']}").status_code == 404

    def test_response_reports_id(self, client):
        created = _create(client, "Tech").json()
        assert client.delete(f"/api/watchlists/{created['id']}").json()["id"] == created["id"]

    def test_missing_returns_404(self, client):
        assert client.delete("/api/watchlists/999").status_code == 404


# ---------------------------------------------------------------------------
# POST /api/watchlists/{id}/tickers
# ---------------------------------------------------------------------------


class TestAddTicker:
    def test_adds_ticker(self, client):
        created = _create(client, "Tech").json()
        resp = client.post(
            f"/api/watchlists/{created['id']}/tickers", json={"ticker": "AAPL"}
        )
        assert resp.status_code == 200
        assert resp.json()["tickers"] == ["AAPL"]

    def test_normalizes_lowercase_and_whitespace(self, client):
        created = _create(client, "Tech").json()
        resp = client.post(
            f"/api/watchlists/{created['id']}/tickers", json={"ticker": "  aapl "}
        )
        assert resp.json()["tickers"] == ["AAPL"]

    def test_duplicate_is_idempotent(self, client):
        created = _create(client, "Tech").json()
        client.post(f"/api/watchlists/{created['id']}/tickers", json={"ticker": "AAPL"})
        resp = client.post(
            f"/api/watchlists/{created['id']}/tickers", json={"ticker": "aapl"}
        )
        assert resp.json()["tickers"] == ["AAPL"]

    def test_blank_ticker_returns_400(self, client):
        created = _create(client, "Tech").json()
        resp = client.post(
            f"/api/watchlists/{created['id']}/tickers", json={"ticker": "   "}
        )
        assert resp.status_code == 400

    def test_missing_watchlist_returns_404(self, client):
        assert (
            client.post("/api/watchlists/999/tickers", json={"ticker": "AAPL"}).status_code
            == 404
        )


# ---------------------------------------------------------------------------
# DELETE /api/watchlists/{id}/tickers/{ticker}
# ---------------------------------------------------------------------------


class TestRemoveTicker:
    def test_removes_ticker(self, client):
        created = _create(client, "Tech").json()
        client.post(f"/api/watchlists/{created['id']}/tickers", json={"ticker": "AAPL"})
        resp = client.delete(f"/api/watchlists/{created['id']}/tickers/AAPL")
        assert resp.status_code == 200
        assert resp.json()["tickers"] == []

    def test_normalizes_lowercase(self, client):
        created = _create(client, "Tech").json()
        client.post(f"/api/watchlists/{created['id']}/tickers", json={"ticker": "AAPL"})
        resp = client.delete(f"/api/watchlists/{created['id']}/tickers/aapl")
        assert resp.json()["tickers"] == []

    def test_missing_ticker_is_idempotent(self, client):
        # Service treats removing an absent ticker as a no-op (not an error).
        created = _create(client, "Tech").json()
        client.post(f"/api/watchlists/{created['id']}/tickers", json={"ticker": "AAPL"})
        resp = client.delete(f"/api/watchlists/{created['id']}/tickers/MSFT")
        assert resp.status_code == 200
        assert resp.json()["tickers"] == ["AAPL"]

    def test_missing_watchlist_returns_404(self, client):
        assert client.delete("/api/watchlists/999/tickers/AAPL").status_code == 404


# ---------------------------------------------------------------------------
# CORS — PATCH/DELETE must be allowed for the browser frontend
# ---------------------------------------------------------------------------


class TestCorsMethods:
    _ORIGIN = "http://localhost:5173"

    def test_preflight_allows_patch(self, client):
        resp = client.options(
            "/api/watchlists/1",
            headers={
                "Origin": self._ORIGIN,
                "Access-Control-Request-Method": "PATCH",
            },
        )
        assert resp.status_code == 200
        allowed = resp.headers.get("access-control-allow-methods", "")
        assert "PATCH" in allowed

    def test_preflight_allows_delete(self, client):
        resp = client.options(
            "/api/watchlists/1",
            headers={
                "Origin": self._ORIGIN,
                "Access-Control-Request-Method": "DELETE",
            },
        )
        assert resp.status_code == 200
        allowed = resp.headers.get("access-control-allow-methods", "")
        assert "DELETE" in allowed


# ---------------------------------------------------------------------------
# POST /api/watchlists/{id}/analyze
# ---------------------------------------------------------------------------


def _create_with_tickers(client, tickers, name="Tech"):
    wl = _create(client, name).json()
    for ticker in tickers:
        client.post(f"/api/watchlists/{wl['id']}/tickers", json={"ticker": ticker})
    return wl["id"]


class TestAnalyzeWatchlist:
    def test_valid_watchlist_returns_200(self, client):
        wl_id = _create_with_tickers(client, ["AAPL", "MSFT"])
        with patch(_ANALYZE, side_effect=_analyze_ok("AAPL", "MSFT")):
            resp = client.post(f"/api/watchlists/{wl_id}/analyze")
        assert resp.status_code == 200

    def test_response_contract(self, client):
        wl_id = _create_with_tickers(client, ["AAPL", "MSFT"], name="My List")
        with patch(_ANALYZE, side_effect=_analyze_ok("AAPL", "MSFT")):
            data = client.post(f"/api/watchlists/{wl_id}/analyze").json()
        assert data["watchlist_id"] == wl_id
        assert data["watchlist_name"] == "My List"
        assert "analyzed_at" in data
        assert data["total_tickers"] == 2
        assert data["successful_count"] == 2
        assert data["failed_count"] == 0
        assert len(data["results"]) == 2
        assert data["errors"] == []

    def test_result_item_has_report_and_summary(self, client):
        wl_id = _create_with_tickers(client, ["AAPL"])
        with patch(_ANALYZE, side_effect=_analyze_ok("AAPL")):
            data = client.post(f"/api/watchlists/{wl_id}/analyze").json()
        item = data["results"][0]
        assert item["ticker"] == "AAPL"
        assert item["category"] == RatingCategory.WATCHLIST.value
        assert item["score"] == 60.0
        assert item["confidence"] == ConfidenceLevel.MEDIUM.value
        assert item["current_price"] == 100.0
        assert item["report"]["ticker"] == "AAPL"

    def test_missing_watchlist_returns_404(self, client):
        with patch(_ANALYZE, side_effect=_analyze_ok("AAPL")):
            assert client.post("/api/watchlists/999/analyze").status_code == 404

    def test_empty_watchlist_returns_400(self, client):
        wl_id = _create_with_tickers(client, [])
        with patch(_ANALYZE) as mock_analyze:
            resp = client.post(f"/api/watchlists/{wl_id}/analyze")
        assert resp.status_code == 400
        mock_analyze.assert_not_called()

    def test_partial_failure_returns_200_with_counts(self, client):
        wl_id = _create_with_tickers(client, ["AAPL", "BADX", "MSFT"])
        with patch(_ANALYZE, side_effect=_analyze_ok("AAPL", "MSFT")):
            resp = client.post(f"/api/watchlists/{wl_id}/analyze")
        assert resp.status_code == 200
        data = resp.json()
        assert data["successful_count"] == 2
        assert data["failed_count"] == 1
        assert data["errors"][0]["ticker"] == "BADX"
        assert isinstance(data["errors"][0]["error"], str)

    def test_all_failures_returns_200(self, client):
        wl_id = _create_with_tickers(client, ["BADX", "BADY"])
        with patch(_ANALYZE, side_effect=_analyze_ok()):
            data = client.post(f"/api/watchlists/{wl_id}/analyze").json()
        assert data["successful_count"] == 0
        assert data["failed_count"] == 2
        assert data["results"] == []
