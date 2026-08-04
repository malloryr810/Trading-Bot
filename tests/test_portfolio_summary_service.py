"""
Tests for app/services/portfolio_summary_service.py.

Market data is always injected via the ``price_lookup`` dependency — no network
calls.  A temporary SQLite database backs the storage layer.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest
from sqlalchemy.engine import Engine

from app.data.database import build_engine
from app.services.portfolio_service import (
    PortfolioNotFoundError,
    add_holding,
    create_portfolio,
)
from app.services.portfolio_summary_service import (
    _default_price_lookup,
    get_portfolio_summary,
)

# get_price_history as imported inside the portfolio summary service module.
_FETCH = "app.services.portfolio_summary_service.get_price_history"


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


def _by_ticker(summary, ticker):
    return next(h for h in summary["holdings"] if h["ticker"] == ticker)


class TestEmptyPortfolio:
    def test_zeroes_and_no_warnings(self, engine):
        p = create_portfolio("Empty", engine=engine)
        summary = get_portfolio_summary(
            p["id"], engine=engine, price_lookup=_prices({})
        )
        assert summary["holdings"] == []
        assert summary["holdings_count"] == 0
        assert summary["total_cost_basis"] == 0.0
        assert summary["total_market_value"] is None
        assert summary["has_price_warnings"] is False


class TestFullyPriced:
    @pytest.fixture()
    def summary(self, engine):
        p = create_portfolio("Core", engine=engine)
        add_holding(p["id"], "AAPL", 10, 100, engine=engine)
        add_holding(p["id"], "MSFT", 5, 200, engine=engine)
        return get_portfolio_summary(
            p["id"],
            engine=engine,
            price_lookup=_prices({"AAPL": 150.0, "MSFT": 250.0}),
        )

    def test_holding_values(self, summary):
        aapl = _by_ticker(summary, "AAPL")
        assert aapl["cost_basis"] == 1000.0
        assert aapl["market_value"] == 1500.0
        assert aapl["unrealized_gain_loss"] == 500.0
        assert aapl["unrealized_return_pct"] == 50.0
        assert aapl["price_available"] is True

    def test_totals(self, summary):
        assert summary["total_cost_basis"] == 2000.0
        assert summary["total_market_value"] == 2750.0
        assert summary["total_unrealized_gain_loss"] == 750.0
        assert summary["total_unrealized_return_pct"] == 37.5

    def test_weights_sum_to_100(self, summary):
        aapl = _by_ticker(summary, "AAPL")
        msft = _by_ticker(summary, "MSFT")
        assert aapl["weight_pct"] == 54.55
        assert msft["weight_pct"] == 45.45
        assert round(aapl["weight_pct"] + msft["weight_pct"], 2) == 100.0

    def test_no_warnings(self, summary):
        assert summary["has_price_warnings"] is False
        assert summary["priced_holdings_count"] == 2


class TestPartialPriceFailure:
    @pytest.fixture()
    def summary(self, engine):
        p = create_portfolio("Core", engine=engine)
        add_holding(p["id"], "AAPL", 10, 100, engine=engine)
        add_holding(p["id"], "MSFT", 5, 200, engine=engine)
        # Only AAPL has a price; MSFT lookup raises.
        return get_portfolio_summary(
            p["id"], engine=engine, price_lookup=_prices({"AAPL": 150.0})
        )

    def test_unavailable_holding_marked(self, summary):
        msft = _by_ticker(summary, "MSFT")
        assert msft["price_available"] is False
        assert msft["current_price"] is None
        assert msft["market_value"] is None
        assert msft["unrealized_gain_loss"] is None
        assert msft["weight_pct"] is None
        # Cost basis does not depend on price and is still present.
        assert msft["cost_basis"] == 1000.0

    def test_warning_present(self, summary):
        assert summary["has_price_warnings"] is True
        assert [w["ticker"] for w in summary["warnings"]] == ["MSFT"]

    def test_totals_exclude_unavailable(self, summary):
        # total_cost_basis reflects all holdings; market-dependent totals only
        # the priced holding (AAPL: mv 1500, cost 1000 → gl 500, 50%).
        assert summary["total_cost_basis"] == 2000.0
        assert summary["total_market_value"] == 1500.0
        assert summary["total_unrealized_gain_loss"] == 500.0
        assert summary["total_unrealized_return_pct"] == 50.0
        assert summary["priced_holdings_count"] == 1

    def test_priced_holding_weight_is_full(self, summary):
        assert _by_ticker(summary, "AAPL")["weight_pct"] == 100.0


class TestCompletePriceFailure:
    @pytest.fixture()
    def summary(self, engine):
        p = create_portfolio("Core", engine=engine)
        add_holding(p["id"], "AAPL", 10, 100, engine=engine)
        add_holding(p["id"], "MSFT", 5, 200, engine=engine)
        return get_portfolio_summary(
            p["id"], engine=engine, price_lookup=_prices({})
        )

    def test_all_holdings_returned(self, summary):
        assert summary["holdings_count"] == 2
        assert len(summary["holdings"]) == 2
        assert all(h["price_available"] is False for h in summary["holdings"])

    def test_market_totals_are_none_not_zero(self, summary):
        assert summary["total_market_value"] is None
        assert summary["total_unrealized_gain_loss"] is None
        assert summary["total_unrealized_return_pct"] is None
        # Cost basis is still computable.
        assert summary["total_cost_basis"] == 2000.0

    def test_all_warned(self, summary):
        assert summary["priced_holdings_count"] == 0
        assert len(summary["warnings"]) == 2


class TestNonePriceIsNotZero:
    def test_none_price_marks_unavailable(self, engine):
        p = create_portfolio("Core", engine=engine)
        add_holding(p["id"], "AAPL", 10, 100, engine=engine)
        summary = get_portfolio_summary(
            p["id"], engine=engine, price_lookup=_prices({"AAPL": None})
        )
        aapl = _by_ticker(summary, "AAPL")
        assert aapl["price_available"] is False
        assert aapl["market_value"] is None
        assert summary["has_price_warnings"] is True


class TestMissingPortfolio:
    def test_raises(self, engine):
        with pytest.raises(PortfolioNotFoundError):
            get_portfolio_summary(999, engine=engine, price_lookup=_prices({}))


# ---------------------------------------------------------------------------
# Default price lookup — shared latest-valid-close reader
# ---------------------------------------------------------------------------

def _price_frame(closes: list[float]) -> pd.DataFrame:
    """Build a normalized OHLCV frame with the given closes (volume always set)."""
    index = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1_000_000] * len(closes),
        },
        index=index,
    )


class TestDefaultPriceLookup:
    """The market-data-backed lookup used when no price_lookup is injected."""

    def test_returns_the_latest_close_for_normal_data(self):
        with patch(_FETCH, return_value=_price_frame([100.0, 101.0, 102.5])):
            assert _default_price_lookup("AAPL") == pytest.approx(102.5)

    def test_falls_back_past_an_in_progress_session_row(self):
        with patch(_FETCH, return_value=_price_frame([100.0, 104.25, float("nan")])):
            assert _default_price_lookup("AAPL") == pytest.approx(104.25)

    def test_skips_several_trailing_null_closes(self):
        frame = _price_frame([100.0, 99.5, float("nan"), float("nan")])
        with patch(_FETCH, return_value=frame):
            assert _default_price_lookup("AAPL") == pytest.approx(99.5)

    def test_returns_none_when_no_close_is_usable(self):
        with patch(_FETCH, return_value=_price_frame([float("nan"), float("nan")])):
            assert _default_price_lookup("AAPL") is None

    def test_returns_none_for_an_empty_frame(self):
        with patch(_FETCH, return_value=_price_frame([])):
            assert _default_price_lookup("AAPL") is None


class TestSummaryUsesTheSharedReader:
    def test_holding_is_priced_from_the_last_settled_close(self, engine):
        portfolio = create_portfolio("Core", engine=engine)
        add_holding(portfolio["id"], "AAPL", 10, 100.0, engine=engine)

        with patch(_FETCH, return_value=_price_frame([180.0, 200.0, float("nan")])):
            summary = get_portfolio_summary(portfolio["id"], engine=engine)

        row = summary["holdings"][0]
        assert row["price_available"] is True
        assert row["current_price"] == pytest.approx(200.0)
        assert row["market_value"] == pytest.approx(2000.0)
        assert summary["warnings"] == []
