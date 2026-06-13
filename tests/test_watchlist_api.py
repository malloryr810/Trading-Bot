"""
Tests for /api/watchlists/* endpoints.

These are integration tests: the routes call the real watchlist_service, which
runs against a temporary SQLite database injected via the service's module-level
engine.  No network calls and no writes to the real project database.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.services.watchlist_service as service
from app.data.database import build_engine


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
