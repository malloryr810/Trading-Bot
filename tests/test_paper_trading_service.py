"""
Tests for app/services/paper_trading_service.py.

Uses a temporary SQLite database via the ``engine`` fixture — no writes to the
real project database and no network calls.  Storage + accounting layer only:
no market data is fetched here (see test_paper_trading_summary_service.py).

Simulated trading only: nothing under test contacts a broker or places a real
order.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from app.data.database import (
    build_engine,
    paper_trading_accounts,
    paper_trading_positions,
    paper_trading_transactions,
)
from app.services.paper_trading_service import (
    InsufficientFundsError,
    InsufficientSharesError,
    PaperTradingAccountNotFoundError,
    PaperTradingValidationError,
    create_account,
    get_account,
    list_accounts,
    list_positions,
    list_transactions,
    record_buy,
    record_sell,
)


@pytest.fixture()
def engine(tmp_path) -> Engine:
    return build_engine(tmp_path / "test.db")


def _account(engine, name="Sim", starting_cash="10000") -> dict:
    return create_account(name, starting_cash, engine=engine)


def _position(engine, account_id, ticker):
    """Read one raw position row straight from the database."""
    with engine.connect() as conn:
        return conn.execute(
            select(paper_trading_positions).where(
                paper_trading_positions.c.account_id == account_id,
                paper_trading_positions.c.ticker == ticker,
            )
        ).one_or_none()


def _stored_cash(engine, account_id) -> Decimal:
    """Read the exact stored cash balance, bypassing float conversion."""
    with engine.connect() as conn:
        row = conn.execute(
            select(paper_trading_accounts.c.cash_balance).where(
                paper_trading_accounts.c.id == account_id
            )
        ).one()
    return Decimal(row.cash_balance)


# ---------------------------------------------------------------------------
# Account creation
# ---------------------------------------------------------------------------


class TestCreateAccount:
    def test_returns_detail_dict(self, engine):
        result = create_account("Sim", "10000", engine=engine)
        assert result["name"] == "Sim"
        assert isinstance(result["id"], int)
        assert result["positions"] == []

    def test_starting_cash_becomes_cash_balance(self, engine):
        result = create_account("Sim", "2500.50", engine=engine)
        assert result["starting_cash"] == 2500.50
        assert result["cash_balance"] == 2500.50

    def test_realized_gain_loss_starts_at_zero(self, engine):
        assert create_account("Sim", "100", engine=engine)["realized_gain_loss"] == 0.0

    def test_timestamps_are_set_and_utc(self, engine):
        result = create_account("Sim", "100", engine=engine)
        assert result["created_at"].tzinfo is not None
        assert result["updated_at"].tzinfo is not None

    def test_strips_name(self, engine):
        assert create_account("  Sim  ", "100", engine=engine)["name"] == "Sim"

    def test_blank_name_rejected(self, engine):
        with pytest.raises(PaperTradingValidationError):
            create_account("   ", "100", engine=engine)

    def test_non_string_name_rejected(self, engine):
        with pytest.raises(PaperTradingValidationError):
            create_account(5, "100", engine=engine)

    def test_zero_starting_cash_rejected(self, engine):
        with pytest.raises(PaperTradingValidationError):
            create_account("Sim", "0", engine=engine)

    def test_negative_starting_cash_rejected(self, engine):
        with pytest.raises(PaperTradingValidationError):
            create_account("Sim", "-100", engine=engine)

    def test_non_numeric_starting_cash_rejected(self, engine):
        with pytest.raises(PaperTradingValidationError):
            create_account("Sim", "abc", engine=engine)

    def test_boolean_starting_cash_rejected(self, engine):
        with pytest.raises(PaperTradingValidationError):
            create_account("Sim", True, engine=engine)

    def test_accepts_float_without_binary_noise(self, engine):
        result = create_account("Sim", 0.1 + 0.2, engine=engine)
        assert result["starting_cash"] == 0.3

    def test_duplicate_names_are_allowed(self, engine):
        a = create_account("Sim", "100", engine=engine)
        b = create_account("Sim", "100", engine=engine)
        assert a["id"] != b["id"]


class TestListAndGetAccount:
    def test_list_is_newest_first(self, engine):
        _account(engine, "A")
        _account(engine, "B")
        assert [a["name"] for a in list_accounts(engine=engine)] == ["B", "A"]

    def test_list_includes_positions_count(self, engine):
        acct = _account(engine)
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        assert list_accounts(engine=engine)[0]["positions_count"] == 1

    def test_list_empty(self, engine):
        assert list_accounts(engine=engine) == []

    def test_get_returns_positions(self, engine):
        acct = _account(engine)
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        detail = get_account(acct["id"], engine=engine)
        assert [p["ticker"] for p in detail["positions"]] == ["AAPL"]

    def test_get_missing_account_raises(self, engine):
        with pytest.raises(PaperTradingAccountNotFoundError):
            get_account(999, engine=engine)


# ---------------------------------------------------------------------------
# Buy
# ---------------------------------------------------------------------------


class TestBuy:
    def test_returns_buy_transaction(self, engine):
        acct = _account(engine)
        txn = record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        assert txn["transaction_type"] == "BUY"
        assert txn["ticker"] == "AAPL"
        assert txn["quantity"] == 10.0
        assert txn["price"] == 100.0
        assert txn["gross_amount"] == 1000.0

    def test_buy_realized_gain_loss_is_zero(self, engine):
        acct = _account(engine)
        txn = record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        assert txn["realized_gain_loss"] == 0.0

    def test_reduces_cash_balance(self, engine):
        acct = _account(engine, starting_cash="10000")
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        assert get_account(acct["id"], engine=engine)["cash_balance"] == 9000.0

    def test_creates_position(self, engine):
        acct = _account(engine)
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        positions = list_positions(acct["id"], engine=engine)
        assert len(positions) == 1
        assert positions[0]["quantity"] == 10.0
        assert positions[0]["average_cost"] == 100.0
        assert positions[0]["cost_basis"] == 1000.0

    def test_normalizes_ticker_to_uppercase(self, engine):
        acct = _account(engine)
        txn = record_buy(acct["id"], " aapl ", "1", "100", engine=engine)
        assert txn["ticker"] == "AAPL"
        assert list_positions(acct["id"], engine=engine)[0]["ticker"] == "AAPL"

    def test_spending_exactly_all_cash_is_allowed(self, engine):
        acct = _account(engine, starting_cash="1000")
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        assert get_account(acct["id"], engine=engine)["cash_balance"] == 0.0

    def test_insufficient_cash_rejected(self, engine):
        acct = _account(engine, starting_cash="500")
        with pytest.raises(InsufficientFundsError):
            record_buy(acct["id"], "AAPL", "10", "100", engine=engine)

    def test_insufficient_cash_leaves_state_untouched(self, engine):
        acct = _account(engine, starting_cash="500")
        with pytest.raises(InsufficientFundsError):
            record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        assert get_account(acct["id"], engine=engine)["cash_balance"] == 500.0
        assert list_positions(acct["id"], engine=engine) == []
        assert list_transactions(acct["id"], engine=engine) == []

    def test_second_buy_over_remaining_cash_rejected(self, engine):
        acct = _account(engine, starting_cash="1500")
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        with pytest.raises(InsufficientFundsError):
            record_buy(acct["id"], "MSFT", "10", "100", engine=engine)

    def test_missing_account_raises(self, engine):
        with pytest.raises(PaperTradingAccountNotFoundError):
            record_buy(999, "AAPL", "1", "100", engine=engine)

    @pytest.mark.parametrize("quantity", ["0", "-5"])
    def test_non_positive_quantity_rejected(self, engine, quantity):
        acct = _account(engine)
        with pytest.raises(PaperTradingValidationError):
            record_buy(acct["id"], "AAPL", quantity, "100", engine=engine)

    @pytest.mark.parametrize("price", ["0", "-100"])
    def test_non_positive_price_rejected(self, engine, price):
        acct = _account(engine)
        with pytest.raises(PaperTradingValidationError):
            record_buy(acct["id"], "AAPL", "1", price, engine=engine)

    def test_blank_ticker_rejected(self, engine):
        acct = _account(engine)
        with pytest.raises(PaperTradingValidationError):
            record_buy(acct["id"], "   ", "1", "100", engine=engine)

    def test_fractional_quantity_supported(self, engine):
        acct = _account(engine)
        txn = record_buy(acct["id"], "AAPL", "0.5", "100", engine=engine)
        assert txn["gross_amount"] == 50.0
        assert list_positions(acct["id"], engine=engine)[0]["quantity"] == 0.5

    def test_explicit_executed_at_is_stored(self, engine):
        acct = _account(engine)
        when = datetime(2026, 1, 2, 15, 30, tzinfo=timezone.utc)
        txn = record_buy(acct["id"], "AAPL", "1", "100", when, engine=engine)
        assert txn["executed_at"] == when

    def test_iso_string_executed_at_accepted(self, engine):
        acct = _account(engine)
        txn = record_buy(
            acct["id"], "AAPL", "1", "100", "2026-01-02T15:30:00+00:00", engine=engine
        )
        assert txn["executed_at"].year == 2026

    def test_invalid_executed_at_rejected(self, engine):
        acct = _account(engine)
        with pytest.raises(PaperTradingValidationError):
            record_buy(acct["id"], "AAPL", "1", "100", "not-a-date", engine=engine)


class TestWeightedAverageCost:
    def test_same_ticker_twice_updates_average_cost(self, engine):
        acct = _account(engine, starting_cash="10000")
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        record_buy(acct["id"], "AAPL", "10", "120", engine=engine)
        position = list_positions(acct["id"], engine=engine)[0]
        assert position["quantity"] == 20.0
        # (10*100 + 10*120) / 20
        assert position["average_cost"] == 110.0

    def test_uneven_quantities_weight_correctly(self, engine):
        acct = _account(engine, starting_cash="100000")
        record_buy(acct["id"], "AAPL", "5", "100", engine=engine)
        record_buy(acct["id"], "AAPL", "15", "200", engine=engine)
        # (5*100 + 15*200) / 20 == 175
        assert list_positions(acct["id"], engine=engine)[0]["average_cost"] == 175.0

    def test_repeating_decimal_average_is_quantised(self, engine):
        acct = _account(engine, starting_cash="100000")
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        record_buy(acct["id"], "AAPL", "5", "120", engine=engine)
        # (1000 + 600) / 15 == 106.666...
        row = _position(engine, acct["id"], "AAPL")
        assert row.average_cost == "106.66666667"

    def test_three_buys_accumulate(self, engine):
        acct = _account(engine, starting_cash="100000")
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        record_buy(acct["id"], "AAPL", "10", "200", engine=engine)
        record_buy(acct["id"], "AAPL", "20", "300", engine=engine)
        position = list_positions(acct["id"], engine=engine)[0]
        assert position["quantity"] == 40.0
        # (1000 + 2000 + 6000) / 40 == 225
        assert position["average_cost"] == 225.0

    def test_different_tickers_are_separate_positions(self, engine):
        acct = _account(engine, starting_cash="10000")
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        record_buy(acct["id"], "MSFT", "5", "200", engine=engine)
        positions = list_positions(acct["id"], engine=engine)
        assert [p["ticker"] for p in positions] == ["AAPL", "MSFT"]
        assert positions[0]["average_cost"] == 100.0
        assert positions[1]["average_cost"] == 200.0

    def test_different_tickers_share_one_cash_balance(self, engine):
        acct = _account(engine, starting_cash="10000")
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        record_buy(acct["id"], "MSFT", "5", "200", engine=engine)
        assert get_account(acct["id"], engine=engine)["cash_balance"] == 8000.0


# ---------------------------------------------------------------------------
# Sell
# ---------------------------------------------------------------------------


class TestSell:
    @pytest.fixture()
    def held(self, engine):
        """An account holding 10 AAPL at an average cost of 100."""
        acct = _account(engine, starting_cash="10000")
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        return acct

    def test_returns_sell_transaction(self, engine, held):
        txn = record_sell(held["id"], "AAPL", "4", "150", engine=engine)
        assert txn["transaction_type"] == "SELL"
        assert txn["quantity"] == 4.0
        assert txn["gross_amount"] == 600.0

    def test_partial_sell_realized_gain(self, engine, held):
        txn = record_sell(held["id"], "AAPL", "4", "150", engine=engine)
        # (150 - 100) * 4
        assert txn["realized_gain_loss"] == 200.0

    def test_partial_sell_realized_loss(self, engine, held):
        txn = record_sell(held["id"], "AAPL", "4", "80", engine=engine)
        # (80 - 100) * 4
        assert txn["realized_gain_loss"] == -80.0

    def test_partial_sell_increases_cash(self, engine, held):
        record_sell(held["id"], "AAPL", "4", "150", engine=engine)
        # 10000 - 1000 (buy) + 600 (sell)
        assert get_account(held["id"], engine=engine)["cash_balance"] == 9600.0

    def test_partial_sell_reduces_quantity(self, engine, held):
        record_sell(held["id"], "AAPL", "4", "150", engine=engine)
        assert list_positions(held["id"], engine=engine)[0]["quantity"] == 6.0

    def test_partial_sell_leaves_average_cost_unchanged(self, engine, held):
        record_sell(held["id"], "AAPL", "4", "150", engine=engine)
        assert list_positions(held["id"], engine=engine)[0]["average_cost"] == 100.0

    def test_realized_accumulates_on_account(self, engine, held):
        record_sell(held["id"], "AAPL", "2", "150", engine=engine)
        record_sell(held["id"], "AAPL", "2", "50", engine=engine)
        # (150-100)*2 == +100, then (50-100)*2 == -100
        assert get_account(held["id"], engine=engine)["realized_gain_loss"] == 0.0

    def test_full_sell_closes_position(self, engine, held):
        record_sell(held["id"], "AAPL", "10", "150", engine=engine)
        assert list_positions(held["id"], engine=engine) == []
        assert _position(engine, held["id"], "AAPL") is None

    def test_full_sell_keeps_ledger_history(self, engine, held):
        record_sell(held["id"], "AAPL", "10", "150", engine=engine)
        ledger = list_transactions(held["id"], engine=engine)
        assert [t["transaction_type"] for t in ledger] == ["SELL", "BUY"]

    def test_full_sell_realized_and_cash(self, engine, held):
        record_sell(held["id"], "AAPL", "10", "150", engine=engine)
        account = get_account(held["id"], engine=engine)
        assert account["realized_gain_loss"] == 500.0
        assert account["cash_balance"] == 10500.0

    def test_rebuying_after_full_sell_starts_fresh(self, engine, held):
        record_sell(held["id"], "AAPL", "10", "150", engine=engine)
        record_buy(held["id"], "AAPL", "5", "200", engine=engine)
        position = list_positions(held["id"], engine=engine)[0]
        assert position["quantity"] == 5.0
        assert position["average_cost"] == 200.0

    def test_insufficient_shares_rejected(self, engine, held):
        with pytest.raises(InsufficientSharesError):
            record_sell(held["id"], "AAPL", "11", "150", engine=engine)

    def test_insufficient_shares_leaves_state_untouched(self, engine, held):
        with pytest.raises(InsufficientSharesError):
            record_sell(held["id"], "AAPL", "11", "150", engine=engine)
        assert get_account(held["id"], engine=engine)["cash_balance"] == 9000.0
        assert list_positions(held["id"], engine=engine)[0]["quantity"] == 10.0
        assert len(list_transactions(held["id"], engine=engine)) == 1

    def test_selling_unowned_ticker_rejected(self, engine, held):
        with pytest.raises(InsufficientSharesError):
            record_sell(held["id"], "MSFT", "1", "150", engine=engine)

    def test_selling_from_empty_account_rejected(self, engine):
        acct = _account(engine)
        with pytest.raises(InsufficientSharesError):
            record_sell(acct["id"], "AAPL", "1", "150", engine=engine)

    def test_normalizes_ticker_to_uppercase(self, engine, held):
        txn = record_sell(held["id"], " aapl ", "1", "150", engine=engine)
        assert txn["ticker"] == "AAPL"

    @pytest.mark.parametrize("quantity", ["0", "-5"])
    def test_non_positive_quantity_rejected(self, engine, held, quantity):
        with pytest.raises(PaperTradingValidationError):
            record_sell(held["id"], "AAPL", quantity, "150", engine=engine)

    @pytest.mark.parametrize("price", ["0", "-150"])
    def test_non_positive_price_rejected(self, engine, held, price):
        with pytest.raises(PaperTradingValidationError):
            record_sell(held["id"], "AAPL", "1", price, engine=engine)

    def test_missing_account_raises(self, engine):
        with pytest.raises(PaperTradingAccountNotFoundError):
            record_sell(999, "AAPL", "1", "100", engine=engine)


# ---------------------------------------------------------------------------
# Ledger invariants — the accounting must always reconcile
# ---------------------------------------------------------------------------


class TestLedgerInvariants:
    @pytest.fixture()
    def traded(self, engine):
        """An account with a mixed history of buys and sells."""
        acct = _account(engine, starting_cash="50000")
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        record_buy(acct["id"], "MSFT", "5", "200.25", engine=engine)
        record_buy(acct["id"], "AAPL", "5", "120", engine=engine)
        record_sell(acct["id"], "AAPL", "7", "150", engine=engine)
        record_sell(acct["id"], "MSFT", "5", "180.10", engine=engine)
        return acct

    def test_cash_reconciles_against_the_ledger(self, engine, traded):
        ledger = list_transactions(traded["id"], engine=engine)
        expected = Decimal("50000")
        for txn in ledger:
            gross = Decimal(str(txn["gross_amount"]))
            expected += gross if txn["transaction_type"] == "SELL" else -gross
        assert _stored_cash(engine, traded["id"]) == expected

    def test_realized_equals_sum_of_transaction_realized(self, engine, traded):
        ledger = list_transactions(traded["id"], engine=engine)
        total = sum(Decimal(str(t["realized_gain_loss"])) for t in ledger)
        account = get_account(traded["id"], engine=engine)
        assert Decimal(str(account["realized_gain_loss"])) == total

    def test_position_quantity_matches_net_shares_traded(self, engine, traded):
        ledger = list_transactions(traded["id"], engine=engine)
        net = Decimal("0")
        for txn in ledger:
            if txn["ticker"] != "AAPL":
                continue
            quantity = Decimal(str(txn["quantity"]))
            net += quantity if txn["transaction_type"] == "BUY" else -quantity
        assert Decimal(str(list_positions(traded["id"], engine=engine)[0]["quantity"])) == net

    def test_closed_position_is_absent_but_ledgered(self, engine, traded):
        tickers = [p["ticker"] for p in list_positions(traded["id"], engine=engine)]
        assert tickers == ["AAPL"]
        ledger_tickers = {t["ticker"] for t in list_transactions(traded["id"], engine=engine)}
        assert ledger_tickers == {"AAPL", "MSFT"}

    def test_every_buy_row_has_zero_realized(self, engine, traded):
        ledger = list_transactions(traded["id"], engine=engine)
        buys = [t for t in ledger if t["transaction_type"] == "BUY"]
        assert buys and all(t["realized_gain_loss"] == 0.0 for t in buys)

    def test_money_is_stored_to_the_cent(self, engine, traded):
        with engine.connect() as conn:
            rows = conn.execute(select(paper_trading_transactions)).all()
        for row in rows:
            assert Decimal(row.gross_amount).as_tuple().exponent >= -2
            assert Decimal(row.realized_gain_loss).as_tuple().exponent >= -2


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


class TestListPositions:
    def test_empty_account(self, engine):
        acct = _account(engine)
        assert list_positions(acct["id"], engine=engine) == []

    def test_ordered_by_ticker(self, engine):
        acct = _account(engine, starting_cash="100000")
        for ticker in ("MSFT", "AAPL", "NVDA"):
            record_buy(acct["id"], ticker, "1", "100", engine=engine)
        tickers = [p["ticker"] for p in list_positions(acct["id"], engine=engine)]
        assert tickers == ["AAPL", "MSFT", "NVDA"]

    def test_missing_account_raises(self, engine):
        with pytest.raises(PaperTradingAccountNotFoundError):
            list_positions(999, engine=engine)


class TestListTransactions:
    def test_empty_account(self, engine):
        acct = _account(engine)
        assert list_transactions(acct["id"], engine=engine) == []

    def test_sorted_newest_first(self, engine):
        acct = _account(engine, starting_cash="100000")
        record_buy(
            acct["id"], "AAPL", "1", "100",
            datetime(2026, 1, 1, tzinfo=timezone.utc), engine=engine,
        )
        record_buy(
            acct["id"], "MSFT", "1", "100",
            datetime(2026, 3, 1, tzinfo=timezone.utc), engine=engine,
        )
        record_buy(
            acct["id"], "NVDA", "1", "100",
            datetime(2026, 2, 1, tzinfo=timezone.utc), engine=engine,
        )
        tickers = [t["ticker"] for t in list_transactions(acct["id"], engine=engine)]
        assert tickers == ["MSFT", "NVDA", "AAPL"]

    def test_identical_timestamps_break_ties_by_id_desc(self, engine):
        acct = _account(engine, starting_cash="100000")
        when = datetime(2026, 1, 1, tzinfo=timezone.utc)
        first = record_buy(acct["id"], "AAPL", "1", "100", when, engine=engine)
        second = record_buy(acct["id"], "MSFT", "1", "100", when, engine=engine)
        ids = [t["id"] for t in list_transactions(acct["id"], engine=engine)]
        assert ids == [second["id"], first["id"]]

    def test_includes_realized_on_sells(self, engine):
        acct = _account(engine, starting_cash="10000")
        record_buy(acct["id"], "AAPL", "10", "100", engine=engine)
        record_sell(acct["id"], "AAPL", "5", "130", engine=engine)
        newest = list_transactions(acct["id"], engine=engine)[0]
        assert newest["transaction_type"] == "SELL"
        assert newest["realized_gain_loss"] == 150.0

    def test_scoped_to_one_account(self, engine):
        a = _account(engine, "A")
        b = _account(engine, "B")
        record_buy(a["id"], "AAPL", "1", "100", engine=engine)
        assert len(list_transactions(a["id"], engine=engine)) == 1
        assert list_transactions(b["id"], engine=engine) == []

    def test_missing_account_raises(self, engine):
        with pytest.raises(PaperTradingAccountNotFoundError):
            list_transactions(999, engine=engine)


class TestAccountIsolation:
    def test_trades_do_not_leak_between_accounts(self, engine):
        a = _account(engine, "A", "10000")
        b = _account(engine, "B", "10000")
        record_buy(a["id"], "AAPL", "10", "100", engine=engine)
        assert get_account(b["id"], engine=engine)["cash_balance"] == 10000.0
        assert list_positions(b["id"], engine=engine) == []

    def test_same_ticker_in_two_accounts_is_independent(self, engine):
        a = _account(engine, "A", "10000")
        b = _account(engine, "B", "10000")
        record_buy(a["id"], "AAPL", "10", "100", engine=engine)
        record_buy(b["id"], "AAPL", "10", "200", engine=engine)
        assert list_positions(a["id"], engine=engine)[0]["average_cost"] == 100.0
        assert list_positions(b["id"], engine=engine)[0]["average_cost"] == 200.0
