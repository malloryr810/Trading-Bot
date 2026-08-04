"""
Tests for app/services/portfolio_service.py.

Uses a temporary SQLite database via the ``engine`` fixture — no writes to the
real project database and no network calls.  Storage layer only: no market data
is fetched here.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from app.data.database import build_engine, portfolio_holdings
from app.services.portfolio_service import (
    DuplicateHoldingError,
    HoldingNotFoundError,
    PortfolioNotFoundError,
    PortfolioValidationError,
    add_holding,
    create_portfolio,
    delete_portfolio,
    get_portfolio,
    list_portfolios,
    remove_holding,
    update_holding,
    update_portfolio,
)


@pytest.fixture()
def engine(tmp_path) -> Engine:
    return build_engine(tmp_path / "test.db")


def _portfolio(engine, name="Core") -> dict:
    return create_portfolio(name, engine=engine)


# ---------------------------------------------------------------------------
# Portfolio CRUD
# ---------------------------------------------------------------------------


class TestCreatePortfolio:
    def test_returns_detail_dict(self, engine):
        result = create_portfolio("Core", engine=engine)
        assert result["name"] == "Core"
        assert result["holdings"] == []
        assert isinstance(result["id"], int)

    def test_strips_name(self, engine):
        assert create_portfolio("  Core  ", engine=engine)["name"] == "Core"

    def test_blank_name_rejected(self, engine):
        with pytest.raises(PortfolioValidationError):
            create_portfolio("   ", engine=engine)

    def test_blank_description_collapses_to_none(self, engine):
        assert create_portfolio("Core", "  ", engine=engine)["description"] is None


class TestListPortfolios:
    def test_empty(self, engine):
        assert list_portfolios(engine=engine) == []

    def test_newest_first_with_counts(self, engine):
        a = _portfolio(engine, "A")
        b = _portfolio(engine, "B")
        add_holding(a["id"], "AAPL", 1, 10, engine=engine)
        rows = list_portfolios(engine=engine)
        assert [r["name"] for r in rows] == ["B", "A"]
        counts = {r["id"]: r["holdings_count"] for r in rows}
        assert counts[a["id"]] == 1
        assert counts[b["id"]] == 0


class TestGetPortfolio:
    def test_missing_raises(self, engine):
        with pytest.raises(PortfolioNotFoundError):
            get_portfolio(999, engine=engine)

    def test_includes_holdings(self, engine):
        p = _portfolio(engine)
        add_holding(p["id"], "AAPL", 3, 100, engine=engine)
        detail = get_portfolio(p["id"], engine=engine)
        assert [h["ticker"] for h in detail["holdings"]] == ["AAPL"]


class TestUpdatePortfolio:
    def test_updates_name(self, engine):
        p = _portfolio(engine)
        updated = update_portfolio(p["id"], name="Renamed", engine=engine)
        assert updated["name"] == "Renamed"

    def test_missing_raises(self, engine):
        with pytest.raises(PortfolioNotFoundError):
            update_portfolio(999, name="X", engine=engine)

    def test_blank_name_rejected(self, engine):
        p = _portfolio(engine)
        with pytest.raises(PortfolioValidationError):
            update_portfolio(p["id"], name="  ", engine=engine)


class TestDeletePortfolio:
    def test_missing_raises(self, engine):
        with pytest.raises(PortfolioNotFoundError):
            delete_portfolio(999, engine=engine)

    def test_cascade_deletes_holdings(self, engine):
        p = _portfolio(engine)
        add_holding(p["id"], "AAPL", 1, 10, engine=engine)
        add_holding(p["id"], "MSFT", 1, 10, engine=engine)
        delete_portfolio(p["id"], engine=engine)
        with pytest.raises(PortfolioNotFoundError):
            get_portfolio(p["id"], engine=engine)
        with engine.connect() as conn:
            remaining = conn.execute(
                select(portfolio_holdings.c.id).where(
                    portfolio_holdings.c.portfolio_id == p["id"]
                )
            ).all()
        assert remaining == []


# ---------------------------------------------------------------------------
# Holding CRUD
# ---------------------------------------------------------------------------


class TestAddHolding:
    def test_normalizes_ticker(self, engine):
        p = _portfolio(engine)
        holding = add_holding(p["id"], "  aapl ", 2, 100, engine=engine)
        assert holding["ticker"] == "AAPL"

    def test_stores_optional_fields(self, engine):
        p = _portfolio(engine)
        holding = add_holding(
            p["id"], "AAPL", 2, 100, "2025-01-15", "core position", engine=engine
        )
        assert holding["purchase_date"] == "2025-01-15"
        assert holding["notes"] == "core position"

    def test_decimal_shares_preserved(self, engine):
        p = _portfolio(engine)
        add_holding(p["id"], "AAPL", "10.123456", "145.30", engine=engine)
        with engine.connect() as conn:
            row = conn.execute(
                select(portfolio_holdings.c.shares, portfolio_holdings.c.average_cost)
            ).one()
        assert Decimal(row.shares) == Decimal("10.123456")
        assert Decimal(row.average_cost) == Decimal("145.30")

    def test_zero_shares_rejected(self, engine):
        p = _portfolio(engine)
        with pytest.raises(PortfolioValidationError):
            add_holding(p["id"], "AAPL", 0, 100, engine=engine)

    def test_negative_shares_rejected(self, engine):
        p = _portfolio(engine)
        with pytest.raises(PortfolioValidationError):
            add_holding(p["id"], "AAPL", -1, 100, engine=engine)

    def test_negative_average_cost_rejected(self, engine):
        p = _portfolio(engine)
        with pytest.raises(PortfolioValidationError):
            add_holding(p["id"], "AAPL", 1, -5, engine=engine)

    def test_zero_average_cost_allowed(self, engine):
        p = _portfolio(engine)
        holding = add_holding(p["id"], "AAPL", 1, 0, engine=engine)
        assert holding["average_cost"] == 0.0

    def test_bad_ticker_rejected(self, engine):
        p = _portfolio(engine)
        with pytest.raises(PortfolioValidationError):
            add_holding(p["id"], "   ", 1, 10, engine=engine)

    def test_bad_number_rejected(self, engine):
        p = _portfolio(engine)
        with pytest.raises(PortfolioValidationError):
            add_holding(p["id"], "AAPL", "not-a-number", 10, engine=engine)

    def test_missing_portfolio_rejected(self, engine):
        with pytest.raises(PortfolioNotFoundError):
            add_holding(999, "AAPL", 1, 10, engine=engine)

    def test_duplicate_ticker_rejected(self, engine):
        p = _portfolio(engine)
        add_holding(p["id"], "AAPL", 1, 10, engine=engine)
        with pytest.raises(DuplicateHoldingError):
            add_holding(p["id"], "aapl", 2, 20, engine=engine)

    def test_bad_purchase_date_rejected(self, engine):
        p = _portfolio(engine)
        with pytest.raises(PortfolioValidationError):
            add_holding(p["id"], "AAPL", 1, 10, "15-01-2025", engine=engine)


class TestUpdateHolding:
    def test_updates_shares(self, engine):
        p = _portfolio(engine)
        h = add_holding(p["id"], "AAPL", 1, 10, engine=engine)
        updated = update_holding(p["id"], h["id"], shares=25, engine=engine)
        assert updated["shares"] == 25.0

    def test_change_ticker_normalized(self, engine):
        p = _portfolio(engine)
        h = add_holding(p["id"], "AAPL", 1, 10, engine=engine)
        updated = update_holding(p["id"], h["id"], ticker="msft", engine=engine)
        assert updated["ticker"] == "MSFT"

    def test_duplicate_ticker_on_update_rejected(self, engine):
        p = _portfolio(engine)
        add_holding(p["id"], "AAPL", 1, 10, engine=engine)
        h2 = add_holding(p["id"], "MSFT", 1, 10, engine=engine)
        with pytest.raises(DuplicateHoldingError):
            update_holding(p["id"], h2["id"], ticker="AAPL", engine=engine)

    def test_same_ticker_on_update_allowed(self, engine):
        p = _portfolio(engine)
        h = add_holding(p["id"], "AAPL", 1, 10, engine=engine)
        updated = update_holding(p["id"], h["id"], ticker="AAPL", shares=2, engine=engine)
        assert updated["shares"] == 2.0

    def test_invalid_shares_on_update_rejected(self, engine):
        p = _portfolio(engine)
        h = add_holding(p["id"], "AAPL", 1, 10, engine=engine)
        with pytest.raises(PortfolioValidationError):
            update_holding(p["id"], h["id"], shares=0, engine=engine)

    def test_missing_holding_rejected(self, engine):
        p = _portfolio(engine)
        with pytest.raises(HoldingNotFoundError):
            update_holding(p["id"], 999, shares=2, engine=engine)

    def test_missing_portfolio_rejected(self, engine):
        with pytest.raises(PortfolioNotFoundError):
            update_holding(999, 1, shares=2, engine=engine)

    def test_clear_notes(self, engine):
        p = _portfolio(engine)
        h = add_holding(p["id"], "AAPL", 1, 10, notes="x", engine=engine)
        updated = update_holding(p["id"], h["id"], clear_notes=True, engine=engine)
        assert updated["notes"] is None


class TestRemoveHolding:
    def test_removes(self, engine):
        p = _portfolio(engine)
        h = add_holding(p["id"], "AAPL", 1, 10, engine=engine)
        remove_holding(p["id"], h["id"], engine=engine)
        assert get_portfolio(p["id"], engine=engine)["holdings"] == []

    def test_missing_holding_rejected(self, engine):
        p = _portfolio(engine)
        with pytest.raises(HoldingNotFoundError):
            remove_holding(p["id"], 999, engine=engine)

    def test_missing_portfolio_rejected(self, engine):
        with pytest.raises(PortfolioNotFoundError):
            remove_holding(999, 1, engine=engine)
