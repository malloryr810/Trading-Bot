"""
Tests for /api/paper-trading/* endpoints.

Integration tests: routes call the real paper trading services against a
temporary SQLite database injected via the service module-level engine.  The
summary and positions endpoints' current-price lookup is monkeypatched — no
network calls, no writes to the real project database.

Simulated trading only: no broker is contacted and no real order is placed.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.services.paper_trading_service as service
import app.services.portfolio_service as portfolio_service
import app.services.paper_trading_summary_service as summary_service
from app.data.database import build_engine


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """TestClient whose paper trading service uses a temporary SQLite database."""
    engine = build_engine(tmp_path / "test.db")
    monkeypatch.setattr(service, "_engine", engine)

    from app.api.main import create_app

    return TestClient(create_app())


@pytest.fixture()
def priced(monkeypatch):
    """Patch the default current-price lookup used by the priced endpoints."""

    def _install(mapping):
        def _lookup(ticker: str):
            if ticker not in mapping:
                raise RuntimeError(f"no data for {ticker}")
            return mapping[ticker]

        monkeypatch.setattr(summary_service, "_default_price_lookup", _lookup)

    return _install


def _create_account(client, name="Sim", starting_cash="10000"):
    return client.post(
        "/api/paper-trading/accounts",
        json={"name": name, "starting_cash": starting_cash},
    )


def _buy(client, account_id, ticker="AAPL", quantity="10", price="100", **extra):
    body = {"ticker": ticker, "quantity": quantity, "price": price, **extra}
    return client.post(f"/api/paper-trading/accounts/{account_id}/buy", json=body)


def _sell(client, account_id, ticker="AAPL", quantity="5", price="150", **extra):
    body = {"ticker": ticker, "quantity": quantity, "price": price, **extra}
    return client.post(f"/api/paper-trading/accounts/{account_id}/sell", json=body)


def _new_account(client, **kwargs) -> int:
    return _create_account(client, **kwargs).json()["id"]


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------


class TestCreateAccount:
    def test_returns_201(self, client):
        resp = _create_account(client)
        assert resp.status_code == 201

    def test_returns_opened_account(self, client):
        body = _create_account(client, "Sim", "2500.50").json()
        assert body["name"] == "Sim"
        assert body["starting_cash"] == 2500.50
        assert body["cash_balance"] == 2500.50
        assert body["realized_gain_loss"] == 0.0
        assert body["positions"] == []

    def test_blank_name_400(self, client):
        assert _create_account(client, name="   ").status_code == 400

    def test_zero_starting_cash_400(self, client):
        assert _create_account(client, starting_cash="0").status_code == 400

    def test_negative_starting_cash_400(self, client):
        assert _create_account(client, starting_cash="-50").status_code == 400

    def test_non_numeric_starting_cash_422(self, client):
        # Rejected by the Pydantic Decimal field before the route body runs.
        assert _create_account(client, starting_cash="abc").status_code == 422

    def test_missing_field_422(self, client):
        resp = client.post("/api/paper-trading/accounts", json={"name": "Sim"})
        assert resp.status_code == 422


class TestListAccounts:
    def test_empty(self, client):
        resp = client.get("/api/paper-trading/accounts")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_newest_first_with_counts(self, client):
        _create_account(client, "A")
        account_id = _new_account(client, name="B")
        _buy(client, account_id)
        body = client.get("/api/paper-trading/accounts").json()
        assert [a["name"] for a in body] == ["B", "A"]
        assert body[0]["positions_count"] == 1
        assert body[1]["positions_count"] == 0


class TestGetAccount:
    def test_returns_detail_with_positions(self, client):
        account_id = _new_account(client)
        _buy(client, account_id)
        resp = client.get(f"/api/paper-trading/accounts/{account_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["cash_balance"] == 9000.0
        assert [p["ticker"] for p in body["positions"]] == ["AAPL"]

    def test_missing_account_404(self, client):
        assert client.get("/api/paper-trading/accounts/999").status_code == 404


# ---------------------------------------------------------------------------
# Buy
# ---------------------------------------------------------------------------


class TestBuyEndpoint:
    def test_returns_201_and_transaction(self, client):
        account_id = _new_account(client)
        resp = _buy(client, account_id)
        assert resp.status_code == 201
        body = resp.json()
        assert body["transaction_type"] == "BUY"
        assert body["ticker"] == "AAPL"
        assert body["gross_amount"] == 1000.0
        assert body["realized_gain_loss"] == 0.0

    def test_reduces_cash(self, client):
        account_id = _new_account(client)
        _buy(client, account_id)
        body = client.get(f"/api/paper-trading/accounts/{account_id}").json()
        assert body["cash_balance"] == 9000.0

    def test_normalizes_ticker(self, client):
        account_id = _new_account(client)
        assert _buy(client, account_id, ticker=" aapl ").json()["ticker"] == "AAPL"

    def test_insufficient_cash_409(self, client):
        account_id = _new_account(client, starting_cash="500")
        resp = _buy(client, account_id)
        assert resp.status_code == 409
        assert "cash balance" in resp.json()["detail"]

    def test_zero_quantity_400(self, client):
        account_id = _new_account(client)
        assert _buy(client, account_id, quantity="0").status_code == 400

    def test_negative_quantity_400(self, client):
        account_id = _new_account(client)
        assert _buy(client, account_id, quantity="-5").status_code == 400

    def test_zero_price_400(self, client):
        account_id = _new_account(client)
        assert _buy(client, account_id, price="0").status_code == 400

    def test_blank_ticker_400(self, client):
        account_id = _new_account(client)
        assert _buy(client, account_id, ticker="   ").status_code == 400

    def test_non_numeric_quantity_422(self, client):
        account_id = _new_account(client)
        assert _buy(client, account_id, quantity="abc").status_code == 422

    def test_missing_account_404(self, client):
        assert _buy(client, 999).status_code == 404

    def test_accepts_executed_at(self, client):
        account_id = _new_account(client)
        resp = _buy(client, account_id, executed_at="2026-01-02T15:30:00Z")
        assert resp.status_code == 201
        assert resp.json()["executed_at"].startswith("2026-01-02")

    def test_weighted_average_cost_across_two_buys(self, client):
        account_id = _new_account(client)
        _buy(client, account_id, quantity="10", price="100")
        _buy(client, account_id, quantity="10", price="120")
        position = client.get(
            f"/api/paper-trading/accounts/{account_id}"
        ).json()["positions"][0]
        assert position["quantity"] == 20.0
        assert position["average_cost"] == 110.0


# ---------------------------------------------------------------------------
# Sell
# ---------------------------------------------------------------------------


class TestSellEndpoint:
    @pytest.fixture()
    def held(self, client):
        """An account holding 10 AAPL at cost 100."""
        account_id = _new_account(client)
        _buy(client, account_id)
        return account_id

    def test_returns_201_and_transaction(self, client, held):
        resp = _sell(client, held)
        assert resp.status_code == 201
        body = resp.json()
        assert body["transaction_type"] == "SELL"
        assert body["gross_amount"] == 750.0
        assert body["realized_gain_loss"] == 250.0

    def test_updates_cash_and_realized(self, client, held):
        _sell(client, held)
        body = client.get(f"/api/paper-trading/accounts/{held}").json()
        assert body["cash_balance"] == 9750.0
        assert body["realized_gain_loss"] == 250.0

    def test_partial_sell_leaves_position(self, client, held):
        _sell(client, held, quantity="4")
        positions = client.get(
            f"/api/paper-trading/accounts/{held}"
        ).json()["positions"]
        assert positions[0]["quantity"] == 6.0

    def test_full_sell_closes_position(self, client, held):
        _sell(client, held, quantity="10")
        body = client.get(f"/api/paper-trading/accounts/{held}").json()
        assert body["positions"] == []

    def test_insufficient_shares_409(self, client, held):
        resp = _sell(client, held, quantity="11")
        assert resp.status_code == 409
        assert "holds" in resp.json()["detail"]

    def test_unowned_ticker_409(self, client, held):
        resp = _sell(client, held, ticker="MSFT")
        assert resp.status_code == 409

    def test_zero_quantity_400(self, client, held):
        assert _sell(client, held, quantity="0").status_code == 400

    def test_negative_price_400(self, client, held):
        assert _sell(client, held, price="-1").status_code == 400

    def test_missing_account_404(self, client):
        assert _sell(client, 999).status_code == 404


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


class TestTransactionsEndpoint:
    def test_empty_account(self, client):
        account_id = _new_account(client)
        resp = client.get(f"/api/paper-trading/accounts/{account_id}/transactions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_newest_first(self, client):
        account_id = _new_account(client)
        _buy(client, account_id, executed_at="2026-01-01T00:00:00Z")
        _buy(client, account_id, ticker="MSFT", executed_at="2026-03-01T00:00:00Z")
        _buy(client, account_id, ticker="NVDA", executed_at="2026-02-01T00:00:00Z")
        body = client.get(
            f"/api/paper-trading/accounts/{account_id}/transactions"
        ).json()
        assert [t["ticker"] for t in body] == ["MSFT", "NVDA", "AAPL"]

    def test_includes_realized_on_sells(self, client):
        account_id = _new_account(client)
        _buy(client, account_id)
        _sell(client, account_id)
        body = client.get(
            f"/api/paper-trading/accounts/{account_id}/transactions"
        ).json()
        assert body[0]["transaction_type"] == "SELL"
        assert body[0]["realized_gain_loss"] == 250.0
        assert body[1]["realized_gain_loss"] == 0.0

    def test_missing_account_404(self, client):
        resp = client.get("/api/paper-trading/accounts/999/transactions")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Positions (priced)
# ---------------------------------------------------------------------------


class TestPositionsEndpoint:
    def test_empty_account(self, client, priced):
        priced({})
        account_id = _new_account(client)
        resp = client.get(f"/api/paper-trading/accounts/{account_id}/positions")
        assert resp.status_code == 200
        assert resp.json()["positions"] == []

    def test_prices_positions(self, client, priced):
        priced({"AAPL": 150.0})
        account_id = _new_account(client)
        _buy(client, account_id)
        body = client.get(
            f"/api/paper-trading/accounts/{account_id}/positions"
        ).json()
        row = body["positions"][0]
        assert row["latest_price"] == 150.0
        assert row["market_value"] == 1500.0
        assert row["unrealized_gain_loss"] == 500.0
        assert row["unrealized_gain_loss_percent"] == 50.0

    def test_partial_price_failure_still_200(self, client, priced):
        priced({"AAPL": 150.0})
        account_id = _new_account(client)
        _buy(client, account_id)
        _buy(client, account_id, ticker="MSFT", quantity="5", price="200")
        resp = client.get(f"/api/paper-trading/accounts/{account_id}/positions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_price_warnings"] is True
        assert [w["ticker"] for w in body["warnings"]] == ["MSFT"]
        unpriced = next(p for p in body["positions"] if p["ticker"] == "MSFT")
        assert unpriced["price_available"] is False
        assert unpriced["market_value"] is None

    def test_missing_account_404(self, client, priced):
        priced({})
        assert client.get("/api/paper-trading/accounts/999/positions").status_code == 404


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


class TestSummaryEndpoint:
    def test_empty_account(self, client, priced):
        priced({})
        account_id = _new_account(client)
        body = client.get(
            f"/api/paper-trading/accounts/{account_id}/summary"
        ).json()
        assert body["cash_balance"] == 10000.0
        assert body["open_positions_value"] == 0.0
        assert body["total_portfolio_value"] == 10000.0
        assert body["total_return"] == 0.0
        assert body["total_return_percent"] == 0.0

    def test_with_positions(self, client, priced):
        priced({"AAPL": 150.0, "MSFT": 180.0})
        account_id = _new_account(client)
        _buy(client, account_id)
        _buy(client, account_id, ticker="MSFT", quantity="5", price="200")
        resp = client.get(f"/api/paper-trading/accounts/{account_id}/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["cash_balance"] == 8000.0
        assert body["open_positions_value"] == 2400.0
        assert body["unrealized_gain_loss"] == 400.0
        assert body["total_portfolio_value"] == 10400.0
        assert body["total_return"] == 400.0
        assert body["total_return_percent"] == 4.0

    def test_realized_after_a_sell(self, client, priced):
        priced({"AAPL": 150.0})
        account_id = _new_account(client)
        _buy(client, account_id)
        _sell(client, account_id)
        body = client.get(
            f"/api/paper-trading/accounts/{account_id}/summary"
        ).json()
        assert body["realized_gain_loss"] == 250.0
        assert body["unrealized_gain_loss"] == 250.0
        assert body["total_portfolio_value"] == 10500.0

    def test_partial_price_failure_still_200(self, client, priced):
        priced({"AAPL": 150.0})
        account_id = _new_account(client)
        _buy(client, account_id)
        _buy(client, account_id, ticker="MSFT", quantity="5", price="200")
        resp = client.get(f"/api/paper-trading/accounts/{account_id}/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_price_warnings"] is True
        assert body["total_portfolio_value"] is None
        assert body["cash_balance"] == 8000.0

    def test_identity_fields(self, client, priced):
        priced({})
        account_id = _new_account(client, name="Sim")
        body = client.get(
            f"/api/paper-trading/accounts/{account_id}/summary"
        ).json()
        assert body["account_id"] == account_id
        assert body["account_name"] == "Sim"

    def test_missing_account_404(self, client, priced):
        priced({})
        assert client.get("/api/paper-trading/accounts/999/summary").status_code == 404


# ---------------------------------------------------------------------------
# Cross-feature isolation
# ---------------------------------------------------------------------------


class TestSeparateFromManualPortfolios:
    """Paper trading and manual portfolio tracking share no state.

    Both services are pointed at the *same* temporary database here, so the
    isolation being proved is real (separate tables), not an artifact of two
    different files.
    """

    @pytest.fixture()
    def both(self, tmp_path, monkeypatch):
        engine = build_engine(tmp_path / "shared.db")
        monkeypatch.setattr(service, "_engine", engine)
        monkeypatch.setattr(portfolio_service, "_engine", engine)

        from app.api.main import create_app

        return TestClient(create_app())

    def test_paper_trades_do_not_appear_in_portfolios(self, both):
        account_id = _new_account(both)
        _buy(both, account_id)
        assert both.get("/api/portfolios").json() == []

    def test_manual_holdings_do_not_appear_in_paper_positions(self, both):
        portfolio = both.post(
            "/api/portfolios", json={"name": "Real"}
        ).json()
        both.post(
            f"/api/portfolios/{portfolio['id']}/holdings",
            json={"ticker": "AAPL", "shares": "10", "average_cost": "100"},
        )
        account_id = _new_account(both)
        detail = both.get(f"/api/paper-trading/accounts/{account_id}").json()
        assert detail["positions"] == []

    def test_health_endpoint_unaffected(self, client):
        assert client.get("/api/health").status_code == 200
