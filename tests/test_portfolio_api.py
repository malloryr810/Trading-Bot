"""
Tests for /api/portfolios/* endpoints.

Integration tests: routes call the real portfolio services against a temporary
SQLite database injected via the service module-level engine.  The summary
endpoint's current-price lookup is monkeypatched — no network calls, no writes
to the real project database.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.services.portfolio_service as service
import app.services.portfolio_summary_service as summary_service
from app.data.database import build_engine


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """TestClient whose portfolio service uses a temporary SQLite database."""
    engine = build_engine(tmp_path / "test.db")
    monkeypatch.setattr(service, "_engine", engine)

    from app.api.main import create_app

    return TestClient(create_app())


@pytest.fixture()
def priced(monkeypatch):
    """Patch the default current-price lookup used by the summary endpoint."""

    def _install(mapping):
        def _lookup(ticker: str):
            if ticker not in mapping:
                raise RuntimeError(f"no data for {ticker}")
            return mapping[ticker]

        monkeypatch.setattr(summary_service, "_default_price_lookup", _lookup)

    return _install


def _create_portfolio(client, name="Core", description=None):
    body: dict = {"name": name}
    if description is not None:
        body["description"] = description
    return client.post("/api/portfolios", json=body)


def _add_holding(client, pid, ticker="AAPL", shares="10", average_cost="100"):
    return client.post(
        f"/api/portfolios/{pid}/holdings",
        json={"ticker": ticker, "shares": shares, "average_cost": average_cost},
    )


# ---------------------------------------------------------------------------
# Portfolio CRUD
# ---------------------------------------------------------------------------


class TestPortfolioCrud:
    def test_create_returns_201(self, client):
        resp = _create_portfolio(client)
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Core"
        assert body["holdings"] == []

    def test_create_blank_name_400(self, client):
        assert _create_portfolio(client, name="  ").status_code == 400

    def test_list_returns_summaries(self, client):
        _create_portfolio(client, "A")
        _create_portfolio(client, "B")
        resp = client.get("/api/portfolios")
        assert resp.status_code == 200
        rows = resp.json()
        assert {r["name"] for r in rows} == {"A", "B"}
        assert all("holdings_count" in r for r in rows)

    def test_get_missing_404(self, client):
        assert client.get("/api/portfolios/999").status_code == 404

    def test_patch_updates(self, client):
        pid = _create_portfolio(client).json()["id"]
        resp = client.patch(f"/api/portfolios/{pid}", json={"name": "Renamed"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed"

    def test_patch_missing_404(self, client):
        assert client.patch("/api/portfolios/999", json={"name": "X"}).status_code == 404

    def test_patch_blank_name_400(self, client):
        pid = _create_portfolio(client).json()["id"]
        assert client.patch(f"/api/portfolios/{pid}", json={"name": "  "}).status_code == 400

    def test_delete_returns_status(self, client):
        pid = _create_portfolio(client).json()["id"]
        resp = client.delete(f"/api/portfolios/{pid}")
        assert resp.status_code == 200
        assert resp.json() == {"status": "deleted", "id": pid}
        assert client.get(f"/api/portfolios/{pid}").status_code == 404

    def test_delete_missing_404(self, client):
        assert client.delete("/api/portfolios/999").status_code == 404


# ---------------------------------------------------------------------------
# Holding CRUD
# ---------------------------------------------------------------------------


class TestHoldingCrud:
    def test_add_returns_201(self, client):
        pid = _create_portfolio(client).json()["id"]
        resp = _add_holding(client, pid)
        assert resp.status_code == 201
        body = resp.json()
        assert body["ticker"] == "AAPL"
        assert body["shares"] == 10.0
        assert body["portfolio_id"] == pid

    def test_add_normalizes_ticker(self, client):
        pid = _create_portfolio(client).json()["id"]
        assert _add_holding(client, pid, ticker="aapl").json()["ticker"] == "AAPL"

    def test_add_duplicate_409(self, client):
        pid = _create_portfolio(client).json()["id"]
        _add_holding(client, pid, ticker="AAPL")
        assert _add_holding(client, pid, ticker="aapl").status_code == 409

    def test_add_zero_shares_400(self, client):
        pid = _create_portfolio(client).json()["id"]
        assert _add_holding(client, pid, shares="0").status_code == 400

    def test_add_negative_cost_400(self, client):
        pid = _create_portfolio(client).json()["id"]
        assert _add_holding(client, pid, average_cost="-5").status_code == 400

    def test_add_missing_portfolio_404(self, client):
        assert _add_holding(client, 999).status_code == 404

    def test_patch_holding_updates(self, client):
        pid = _create_portfolio(client).json()["id"]
        hid = _add_holding(client, pid).json()["id"]
        resp = client.patch(
            f"/api/portfolios/{pid}/holdings/{hid}", json={"shares": "25"}
        )
        assert resp.status_code == 200
        assert resp.json()["shares"] == 25.0

    def test_patch_holding_duplicate_409(self, client):
        pid = _create_portfolio(client).json()["id"]
        _add_holding(client, pid, ticker="AAPL")
        hid = _add_holding(client, pid, ticker="MSFT").json()["id"]
        resp = client.patch(
            f"/api/portfolios/{pid}/holdings/{hid}", json={"ticker": "AAPL"}
        )
        assert resp.status_code == 409

    def test_patch_holding_missing_404(self, client):
        pid = _create_portfolio(client).json()["id"]
        resp = client.patch(
            f"/api/portfolios/{pid}/holdings/999", json={"shares": "2"}
        )
        assert resp.status_code == 404

    def test_delete_holding(self, client):
        pid = _create_portfolio(client).json()["id"]
        hid = _add_holding(client, pid).json()["id"]
        resp = client.delete(f"/api/portfolios/{pid}/holdings/{hid}")
        assert resp.status_code == 200
        assert resp.json() == {"status": "deleted", "id": hid}

    def test_delete_holding_missing_404(self, client):
        pid = _create_portfolio(client).json()["id"]
        assert client.delete(f"/api/portfolios/{pid}/holdings/999").status_code == 404


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_missing_portfolio_404(self, client, priced):
        priced({})
        assert client.get("/api/portfolios/999/summary").status_code == 404

    def test_fully_priced(self, client, priced):
        pid = _create_portfolio(client).json()["id"]
        _add_holding(client, pid, ticker="AAPL", shares="10", average_cost="100")
        _add_holding(client, pid, ticker="MSFT", shares="5", average_cost="200")
        priced({"AAPL": 150.0, "MSFT": 250.0})

        resp = client.get(f"/api/portfolios/{pid}/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_cost_basis"] == 2000.0
        assert body["total_market_value"] == 2750.0
        assert body["total_unrealized_gain_loss"] == 750.0
        assert body["total_unrealized_return_pct"] == 37.5
        assert body["has_price_warnings"] is False
        assert body["priced_holdings_count"] == 2

    def test_partial_failure_returns_200_with_warnings(self, client, priced):
        pid = _create_portfolio(client).json()["id"]
        _add_holding(client, pid, ticker="AAPL", shares="10", average_cost="100")
        _add_holding(client, pid, ticker="BADX", shares="5", average_cost="200")
        priced({"AAPL": 150.0})

        resp = client.get(f"/api/portfolios/{pid}/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_price_warnings"] is True
        assert [w["ticker"] for w in body["warnings"]] == ["BADX"]
        assert body["total_market_value"] == 1500.0
        bad = next(h for h in body["holdings"] if h["ticker"] == "BADX")
        assert bad["price_available"] is False
        assert bad["market_value"] is None

    def test_empty_portfolio_summary(self, client, priced):
        pid = _create_portfolio(client).json()["id"]
        priced({})
        resp = client.get(f"/api/portfolios/{pid}/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["holdings"] == []
        assert body["total_cost_basis"] == 0.0
        assert body["total_market_value"] is None
