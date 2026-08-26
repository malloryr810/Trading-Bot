"""
Tests for app/services/paper_trading_summary_service.py.

Market data is always injected via the ``price_lookup`` dependency — no network
calls.  A temporary SQLite database backs the storage layer.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest
from sqlalchemy.engine import Engine

from app.data.database import build_engine
from app.services.paper_trading_service import (
    PaperTradingAccountNotFoundError,
    create_account,
    record_buy,
    record_sell,
)
from app.services.paper_trading_summary_service import (
    _default_price_lookup,
    get_account_summary,
    get_priced_positions,
)

# get_price_history as imported inside the paper trading summary service module.
_FETCH = "app.services.paper_trading_summary_service.get_price_history"


@pytest.fixture()
def engine(tmp_path) -> Engine:
    return build_engine(tmp_path / "test.db")


def _prices(mapping):
    """Build a price_lookup that returns mapped prices and raises for the rest."""

    def _lookup(ticker: str):
        if ticker not in mapping:
            raise RuntimeError(f"no data for {ticker}")
        return mapping[ticker]

    return _lookup


def _by_ticker(payload, ticker):
    return next(p for p in payload["positions"] if p["ticker"] == ticker)


# ---------------------------------------------------------------------------
# Empty account
# ---------------------------------------------------------------------------


class TestEmptyAccount:
    @pytest.fixture()
    def summary(self, engine):
        acct = create_account("Sim", "10000", engine=engine)
        return get_account_summary(
            acct["id"], engine=engine, price_lookup=_prices({})
        )

    def test_no_positions_and_no_warnings(self, summary):
        assert summary["positions"] == []
        assert summary["positions_count"] == 0
        assert summary["has_price_warnings"] is False

    def test_open_positions_value_is_zero(self, summary):
        assert summary["open_positions_value"] == 0.0
        assert summary["unrealized_gain_loss"] == 0.0

    def test_total_value_equals_cash(self, summary):
        assert summary["total_portfolio_value"] == 10000.0

    def test_return_is_zero(self, summary):
        assert summary["total_return"] == 0.0
        assert summary["total_return_percent"] == 0.0

    def test_realized_is_zero(self, summary):
        assert summary["realized_gain_loss"] == 0.0

    def test_identity_fields(self, summary):
        assert summary["account_name"] == "Sim"
        assert summary["generated_at"].tzinfo is not None


# ---------------------------------------------------------------------------
# Fully priced
# ---------------------------------------------------------------------------


class TestFullyPriced:
    @pytest.fixture()
    def summary(self, engine):
        acct = create_account("Sim", "10000", engine=engine)
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        record_buy(acct["id"], "MSFT", "5", "200", engine=engine)
        # Cash: 10000 - 1000 - 1000 == 8000
        return get_account_summary(
            acct["id"],
            engine=engine,
            price_lookup=_prices({"AAPL": 150.0, "MSFT": 180.0}),
        )

    def test_cash_balance_after_buys(self, summary):
        assert summary["cash_balance"] == 8000.0

    def test_per_position_market_value(self, summary):
        assert _by_ticker(summary, "AAPL")["market_value"] == 1500.0
        assert _by_ticker(summary, "MSFT")["market_value"] == 900.0

    def test_per_position_unrealized(self, summary):
        assert _by_ticker(summary, "AAPL")["unrealized_gain_loss"] == 500.0
        assert _by_ticker(summary, "MSFT")["unrealized_gain_loss"] == -100.0

    def test_per_position_unrealized_percent(self, summary):
        assert _by_ticker(summary, "AAPL")["unrealized_gain_loss_percent"] == 50.0
        assert _by_ticker(summary, "MSFT")["unrealized_gain_loss_percent"] == -10.0

    def test_price_available_flags(self, summary):
        assert all(p["price_available"] for p in summary["positions"])

    def test_latest_price_reported(self, summary):
        assert _by_ticker(summary, "AAPL")["latest_price"] == 150.0

    def test_cost_basis(self, summary):
        assert _by_ticker(summary, "AAPL")["cost_basis"] == 1000.0

    def test_open_positions_value(self, summary):
        assert summary["open_positions_value"] == 2400.0

    def test_total_unrealized(self, summary):
        assert summary["unrealized_gain_loss"] == 400.0

    def test_total_portfolio_value_is_cash_plus_positions(self, summary):
        # 8000 cash + 2400 positions
        assert summary["total_portfolio_value"] == 10400.0

    def test_total_return(self, summary):
        assert summary["total_return"] == 400.0

    def test_total_return_percent(self, summary):
        assert summary["total_return_percent"] == 4.0

    def test_no_warnings(self, summary):
        assert summary["warnings"] == []
        assert summary["has_price_warnings"] is False
        assert summary["priced_positions_count"] == 2


class TestRealizedAndUnrealizedAreSeparate:
    @pytest.fixture()
    def summary(self, engine):
        acct = create_account("Sim", "10000", engine=engine)
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        record_sell(acct["id"], "AAPL", "5", "150", engine=engine)
        # Cash: 10000 - 1000 + 750 == 9750; realized == +250; 5 shares left @100
        return get_account_summary(
            acct["id"], engine=engine, price_lookup=_prices({"AAPL": 150.0})
        )

    def test_realized_reflects_the_sell_only(self, summary):
        assert summary["realized_gain_loss"] == 250.0

    def test_unrealized_reflects_the_remaining_shares_only(self, summary):
        assert summary["unrealized_gain_loss"] == 250.0

    def test_cash_reflects_the_sale_proceeds(self, summary):
        assert summary["cash_balance"] == 9750.0

    def test_total_value_counts_each_gain_once(self, summary):
        # 9750 cash + 750 open position == 10500
        assert summary["total_portfolio_value"] == 10500.0
        assert summary["total_return"] == 500.0

    def test_return_percent(self, summary):
        assert summary["total_return_percent"] == 5.0


# ---------------------------------------------------------------------------
# Partial and total price failure
# ---------------------------------------------------------------------------


class TestPartialPriceFailure:
    @pytest.fixture()
    def summary(self, engine):
        acct = create_account("Sim", "10000", engine=engine)
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        record_buy(acct["id"], "MSFT", "5", "200", engine=engine)
        return get_account_summary(
            acct["id"], engine=engine, price_lookup=_prices({"AAPL": 150.0})
        )

    def test_request_does_not_raise(self, summary):
        assert summary["positions_count"] == 2

    def test_priced_position_is_valued(self, summary):
        assert _by_ticker(summary, "AAPL")["market_value"] == 1500.0

    def test_unpriced_position_still_appears(self, summary):
        row = _by_ticker(summary, "MSFT")
        assert row["price_available"] is False
        assert row["latest_price"] is None
        assert row["market_value"] is None
        assert row["unrealized_gain_loss"] is None
        assert row["unrealized_gain_loss_percent"] is None

    def test_unpriced_position_keeps_its_cost_basis(self, summary):
        assert _by_ticker(summary, "MSFT")["cost_basis"] == 1000.0

    def test_warning_recorded(self, summary):
        assert summary["has_price_warnings"] is True
        assert [w["ticker"] for w in summary["warnings"]] == ["MSFT"]

    def test_priced_count(self, summary):
        assert summary["priced_positions_count"] == 1

    def test_unrealized_covers_only_priced_positions(self, summary):
        assert summary["unrealized_gain_loss"] == 500.0
        assert summary["open_positions_value"] == 1500.0

    def test_totals_are_none_not_understated(self, summary):
        assert summary["total_portfolio_value"] is None
        assert summary["total_return"] is None
        assert summary["total_return_percent"] is None

    def test_cash_and_realized_are_still_reported(self, summary):
        assert summary["cash_balance"] == 8000.0
        assert summary["realized_gain_loss"] == 0.0


class TestAllPricesFail:
    @pytest.fixture()
    def summary(self, engine):
        acct = create_account("Sim", "10000", engine=engine)
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        return get_account_summary(
            acct["id"], engine=engine, price_lookup=_prices({})
        )

    def test_does_not_raise(self, summary):
        assert summary["positions_count"] == 1

    def test_values_are_none_never_zero(self, summary):
        assert summary["open_positions_value"] is None
        assert summary["unrealized_gain_loss"] is None
        assert summary["total_portfolio_value"] is None

    def test_warning_recorded(self, summary):
        assert summary["has_price_warnings"] is True


class TestUnusablePrices:
    def test_none_price_is_a_warning(self, engine):
        acct = create_account("Sim", "10000", engine=engine)
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        summary = get_account_summary(
            acct["id"], engine=engine, price_lookup=lambda _t: None
        )
        assert summary["positions"][0]["price_available"] is False
        assert "No current price" in summary["warnings"][0]["message"]

    def test_zero_price_is_a_warning(self, engine):
        acct = create_account("Sim", "10000", engine=engine)
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        summary = get_account_summary(
            acct["id"], engine=engine, price_lookup=lambda _t: 0.0
        )
        assert summary["positions"][0]["price_available"] is False

    def test_negative_price_is_a_warning(self, engine):
        acct = create_account("Sim", "10000", engine=engine)
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        summary = get_account_summary(
            acct["id"], engine=engine, price_lookup=lambda _t: -5.0
        )
        assert summary["positions"][0]["price_available"] is False


# ---------------------------------------------------------------------------
# Priced positions endpoint payload
# ---------------------------------------------------------------------------


class TestGetPricedPositions:
    def test_empty_account(self, engine):
        acct = create_account("Sim", "10000", engine=engine)
        payload = get_priced_positions(
            acct["id"], engine=engine, price_lookup=_prices({})
        )
        assert payload["positions"] == []
        assert payload["positions_count"] == 0
        assert payload["has_price_warnings"] is False

    def test_prices_each_position(self, engine):
        acct = create_account("Sim", "10000", engine=engine)
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        payload = get_priced_positions(
            acct["id"], engine=engine, price_lookup=_prices({"AAPL": 150.0})
        )
        row = payload["positions"][0]
        assert row["market_value"] == 1500.0
        assert row["unrealized_gain_loss"] == 500.0
        assert payload["priced_positions_count"] == 1

    def test_partial_failure_is_non_fatal(self, engine):
        acct = create_account("Sim", "10000", engine=engine)
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        record_buy(acct["id"], "MSFT", "5", "200", engine=engine)
        payload = get_priced_positions(
            acct["id"], engine=engine, price_lookup=_prices({"AAPL": 150.0})
        )
        assert payload["positions_count"] == 2
        assert payload["priced_positions_count"] == 1
        assert payload["has_price_warnings"] is True

    def test_includes_position_id(self, engine):
        acct = create_account("Sim", "10000", engine=engine)
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        payload = get_priced_positions(
            acct["id"], engine=engine, price_lookup=_prices({"AAPL": 150.0})
        )
        assert isinstance(payload["positions"][0]["position_id"], int)


class TestMissingAccount:
    def test_summary_raises(self, engine):
        with pytest.raises(PaperTradingAccountNotFoundError):
            get_account_summary(999, engine=engine, price_lookup=_prices({}))

    def test_positions_raises(self, engine):
        with pytest.raises(PaperTradingAccountNotFoundError):
            get_priced_positions(999, engine=engine, price_lookup=_prices({}))


# ---------------------------------------------------------------------------
# Default price lookup — reuses the shared market-data reader
# ---------------------------------------------------------------------------


class TestDefaultPriceLookup:
    def test_returns_latest_valid_close(self):
        df = pd.DataFrame({"close": [100.0, 110.0, 120.0]})
        with patch(_FETCH, return_value=df):
            assert _default_price_lookup("AAPL") == 120.0

    def test_skips_an_in_progress_session_row(self):
        # The provider can return a row with volume but null OHLC mid-session.
        df = pd.DataFrame({"close": [100.0, 110.0, float("nan")]})
        with patch(_FETCH, return_value=df):
            assert _default_price_lookup("AAPL") == 110.0

    def test_returns_none_when_nothing_usable(self):
        df = pd.DataFrame({"close": [float("nan")]})
        with patch(_FETCH, return_value=df):
            assert _default_price_lookup("AAPL") is None

    def test_requests_a_short_window(self):
        df = pd.DataFrame({"close": [100.0]})
        with patch(_FETCH, return_value=df) as fetch:
            _default_price_lookup("AAPL")
        assert fetch.call_args.kwargs["period"] == "5d"
        assert fetch.call_args.kwargs["interval"] == "1d"

    def test_fetch_failure_becomes_a_warning_not_a_crash(self, engine):
        acct = create_account("Sim", "10000", engine=engine)
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        with patch(_FETCH, side_effect=RuntimeError("provider down")):
            summary = get_account_summary(acct["id"], engine=engine)
        assert summary["has_price_warnings"] is True
        assert "provider down" in summary["warnings"][0]["message"]
