"""
Paper trading persistence and accounting service.

Public boundary for **simulated** trading: hand-entered buys and sells against a
made-up cash balance.  Nothing in this module (or anywhere in this vertical)
connects to a broker, places a real order, reads a real brokerage account, or
trades automatically.  Every transaction exists because the user asked for it,
at a price the user supplied.

This layer is storage + accounting only — it never fetches market data.
Current-price enrichment (unrealized gain/loss, market value, total portfolio
value) lives in ``app.services.paper_trading_summary_service`` and runs only
when a summary or a priced position list is requested.  That mirrors the
``portfolio_service`` / ``portfolio_summary_service`` split.

Kept deliberately separate from manual portfolio tracking: ``portfolios`` /
``portfolio_holdings`` record real holdings the user owns and carry no cash,
ledger, or realized gains.  The two features share no tables and no code.

Accounting model
----------------
``paper_trading_transactions`` is the append-only ledger and the source of
truth.  ``paper_trading_positions`` is a derived current-state cache updated
inside the *same* database transaction as the cash movement and the ledger
insert, so an account can never be observed half-updated.  A position that is
fully sold is deleted; the ledger keeps the history.

Two invariants hold after every trade and are covered by tests::

    cash_balance       == starting_cash - sum(BUY gross) + sum(SELL gross)
    realized_gain_loss == sum(transaction.realized_gain_loss)

Public functions::

    create_account(name, starting_cash)                  — open an account.
    list_accounts()                                      — all account summaries.
    get_account(account_id)                              — one account + positions.
    record_buy(account_id, ticker, quantity, price, ...) — simulated buy.
    record_sell(account_id, ticker, quantity, price, ...)— simulated sell.
    list_positions(account_id)                           — open positions (no prices).
    list_transactions(account_id)                        — ledger, newest first.

Each function accepts an optional keyword-only ``engine`` parameter for
dependency injection in tests.  Production callers omit it; a shared engine is
lazily initialised on the first call.

Decimal safety: every quantity, price, and money amount is validated and stored
as an exact ``Decimal`` (persisted as a canonical string).  Money is quantised
to cents at the point it is computed, so the ledger reconciles exactly against
the cash balance.  Weighted average cost is quantised to 8 decimal places.

Errors:
    PaperTradingValidationError — invalid input (blank name, bad number/ticker).
    PaperTradingAccountNotFoundError — the account id does not exist.
    InsufficientFundsError      — a buy costs more than the cash balance.
    InsufficientSharesError     — a sell exceeds the owned quantity (or the
                                  account holds none of that ticker).
The first two subclass the matching builtin (``ValueError`` / ``LookupError``).
The last two subclass ``PaperTradingError`` and are caught ahead of validation
at the API layer so they can map to HTTP 409 (a conflict with current account
state) rather than 400 (malformed input).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Engine

from app.data.database import (
    as_utc,
    build_engine,
    paper_trading_accounts,
    paper_trading_positions,
    paper_trading_transactions,
)
from app.utils.helpers import normalize_ticker

_engine: Engine | None = None

# Money is exact to the cent; weighted average cost keeps more precision so
# repeated partial buys do not drift.
_MONEY = Decimal("0.01")
_COST = Decimal("0.00000001")

BUY = "BUY"
SELL = "SELL"


class PaperTradingError(Exception):
    """Base class for paper trading service errors."""


class PaperTradingValidationError(PaperTradingError, ValueError):
    """Raised when account or trade input fails validation."""


class PaperTradingAccountNotFoundError(PaperTradingError, LookupError):
    """Raised when a paper trading account id does not exist."""


class InsufficientFundsError(PaperTradingError):
    """Raised when a simulated buy would overdraw the cash balance."""


class InsufficientSharesError(PaperTradingError):
    """Raised when a simulated sell exceeds the owned quantity."""


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine


# ---------------------------------------------------------------------------
# Input cleaners
# ---------------------------------------------------------------------------

def _clean_name(name: object) -> str:
    if not isinstance(name, str):
        raise PaperTradingValidationError(
            f"Account name must be a string, got {type(name).__name__}."
        )
    stripped = name.strip()
    if not stripped:
        raise PaperTradingValidationError(
            "Account name must not be empty or whitespace."
        )
    return stripped


def _clean_ticker(ticker: object) -> str:
    """Validate and normalize a ticker, reusing the shared normalizer."""
    try:
        return normalize_ticker(ticker)
    except ValueError as exc:
        raise PaperTradingValidationError(str(exc)) from exc


def _to_decimal(value: object, field: str) -> Decimal:
    """Parse a value into an exact Decimal without float artifacts.

    Mirrors ``portfolio_service._to_decimal``: ``bool`` is rejected explicitly
    (it is an ``int`` subclass) and floats are routed through ``str`` so ``0.1``
    becomes ``Decimal("0.1")`` rather than binary-float noise.
    """
    if isinstance(value, bool):
        raise PaperTradingValidationError(f"{field} must be a number, got bool.")
    if isinstance(value, Decimal):
        candidate = value
    elif isinstance(value, (int, str)):
        try:
            candidate = Decimal(str(value).strip())
        except (InvalidOperation, ValueError) as exc:
            raise PaperTradingValidationError(
                f"{field} must be a valid number, got {value!r}."
            ) from exc
    elif isinstance(value, float):
        candidate = Decimal(str(value))
    else:
        raise PaperTradingValidationError(
            f"{field} must be a number, got {type(value).__name__}."
        )
    if not candidate.is_finite():
        raise PaperTradingValidationError(
            f"{field} must be a finite number, got {value!r}."
        )
    return candidate


def _clean_starting_cash(value: object) -> Decimal:
    cash = _to_decimal(value, "Starting cash")
    if cash <= 0:
        raise PaperTradingValidationError("Starting cash must be greater than zero.")
    return _money(cash)


def _clean_quantity(value: object) -> Decimal:
    quantity = _to_decimal(value, "Quantity")
    if quantity <= 0:
        raise PaperTradingValidationError("Quantity must be greater than zero.")
    return quantity


def _clean_price(value: object) -> Decimal:
    price = _to_decimal(value, "Price")
    if price <= 0:
        raise PaperTradingValidationError("Price must be greater than zero.")
    return price


def _clean_executed_at(value: object) -> datetime:
    """Validate an optional execution timestamp; default to now (UTC)."""
    if value is None:
        return datetime.now(tz=timezone.utc)
    if isinstance(value, datetime):
        return as_utc(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return datetime.now(tz=timezone.utc)
        try:
            return as_utc(datetime.fromisoformat(stripped))
        except ValueError as exc:
            raise PaperTradingValidationError(
                f"Executed at must be an ISO datetime, got {value!r}."
            ) from exc
    raise PaperTradingValidationError(
        f"Executed at must be a datetime or ISO string, got {type(value).__name__}."
    )


def _money(value: Decimal) -> Decimal:
    """Quantise a money amount to cents (half-up)."""
    return value.quantize(_MONEY, rounding=ROUND_HALF_UP)


def _cost(value: Decimal) -> Decimal:
    """Quantise a per-share cost to 8 decimal places (half-up)."""
    return value.quantize(_COST, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Row builders
# ---------------------------------------------------------------------------

def _account_from_row(row: Any) -> dict:
    """Shape an account row into a JSON-friendly dict.

    Decimal columns are stored as canonical strings and returned as floats for
    the display layer; storage and accounting remain decimal-exact.
    """
    return {
        "id": row.id,
        "name": row.name,
        "starting_cash": float(Decimal(row.starting_cash)),
        "cash_balance": float(Decimal(row.cash_balance)),
        "realized_gain_loss": float(Decimal(row.realized_gain_loss)),
        "created_at": as_utc(row.created_at),
        "updated_at": as_utc(row.updated_at),
    }


def _position_from_row(row: Any) -> dict:
    """Shape a position row into a JSON-friendly dict, including cost basis."""
    quantity = Decimal(row.quantity)
    average_cost = Decimal(row.average_cost)
    return {
        "id": row.id,
        "account_id": row.account_id,
        "ticker": row.ticker,
        "quantity": float(quantity),
        "average_cost": float(average_cost),
        "cost_basis": float(_money(quantity * average_cost)),
        "created_at": as_utc(row.created_at),
        "updated_at": as_utc(row.updated_at),
    }


def _transaction_from_row(row: Any) -> dict:
    """Shape a ledger row into a JSON-friendly dict."""
    return {
        "id": row.id,
        "account_id": row.account_id,
        "transaction_type": row.transaction_type,
        "ticker": row.ticker,
        "quantity": float(Decimal(row.quantity)),
        "price": float(Decimal(row.price)),
        "gross_amount": float(Decimal(row.gross_amount)),
        "realized_gain_loss": float(Decimal(row.realized_gain_loss)),
        "executed_at": as_utc(row.executed_at),
        "created_at": as_utc(row.created_at),
    }


def _positions_for(conn: Any, account_id: int) -> list[dict]:
    """Open positions for an account, ordered by ticker for stable output."""
    stmt = (
        select(paper_trading_positions)
        .where(paper_trading_positions.c.account_id == account_id)
        .order_by(paper_trading_positions.c.ticker.asc())
    )
    return [_position_from_row(row) for row in conn.execute(stmt).all()]


def _account_row(conn: Any, account_id: int) -> Any:
    """Return the account row, raising PaperTradingAccountNotFoundError if absent."""
    row = conn.execute(
        select(paper_trading_accounts).where(
            paper_trading_accounts.c.id == account_id
        )
    ).one_or_none()
    if row is None:
        raise PaperTradingAccountNotFoundError(
            f"Paper trading account {account_id} not found."
        )
    return row


def _detail_for(conn: Any, account_id: int) -> dict:
    """Build the full account detail dict (account fields + open positions)."""
    detail = _account_from_row(_account_row(conn, account_id))
    detail["positions"] = _positions_for(conn, account_id)
    return detail


def _position_row(conn: Any, account_id: int, ticker: str) -> Any:
    """Return the open position row for a ticker, or None when not held."""
    return conn.execute(
        select(paper_trading_positions).where(
            paper_trading_positions.c.account_id == account_id,
            paper_trading_positions.c.ticker == ticker,
        )
    ).one_or_none()


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

def create_account(
    name: str,
    starting_cash: object,
    *,
    engine: Engine | None = None,
) -> dict:
    """Open a simulated trading account and return its detail.

    Args:
        name: Human-readable account name (required, stripped).
        starting_cash: Opening simulated cash; must be greater than zero.
        engine: Optional engine for dependency injection in tests.

    Returns:
        Account detail dict.  ``cash_balance`` starts at ``starting_cash``,
        ``realized_gain_loss`` at 0, and ``positions`` is empty.

    Raises:
        PaperTradingValidationError: If the name is blank or the cash is not
            greater than zero.
    """
    _e = engine or _get_engine()
    clean_name = _clean_name(name)
    clean_cash = _clean_starting_cash(starting_cash)
    now = datetime.now(tz=timezone.utc)

    stmt = insert(paper_trading_accounts).values(
        name=clean_name,
        starting_cash=str(clean_cash),
        cash_balance=str(clean_cash),
        realized_gain_loss=str(_money(Decimal("0"))),
        created_at=now,
        updated_at=now,
    )
    with _e.begin() as conn:
        new_id = conn.execute(stmt).lastrowid
        return _detail_for(conn, new_id)


def list_accounts(*, engine: Engine | None = None) -> list[dict]:
    """Return all paper trading accounts, newest first, with position counts."""
    _e = engine or _get_engine()
    stmt = select(paper_trading_accounts).order_by(
        paper_trading_accounts.c.id.desc()
    )
    with _e.connect() as conn:
        rows = conn.execute(stmt).all()
        return [
            {
                **_account_from_row(row),
                "positions_count": len(_positions_for(conn, row.id)),
            }
            for row in rows
        ]


def get_account(account_id: int, *, engine: Engine | None = None) -> dict:
    """Return one account with its open positions (no market data).

    Raises:
        PaperTradingAccountNotFoundError: If the id does not exist.
    """
    _e = engine or _get_engine()
    with _e.connect() as conn:
        return _detail_for(conn, account_id)


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------

def record_buy(
    account_id: int,
    ticker: str,
    quantity: object,
    price: object,
    executed_at: object = None,
    *,
    engine: Engine | None = None,
) -> dict:
    """Record a simulated buy and return the resulting ledger transaction.

    Cash, the open position, and the ledger row are written inside one database
    transaction, so the account is never observable half-updated.

    The buy price is supplied by the caller — this service fetches no market
    data.  A future "paper buy this candidate" action can pass a Discover
    candidate's ``current_price`` straight through; no coupling to the
    discovery or research layers is needed or wanted.

    Args:
        account_id: Account to trade in.
        ticker: Ticker symbol (normalized to uppercase).
        quantity: Shares to buy; must be greater than zero.
        price: Per-share price; must be greater than zero.
        executed_at: Optional execution timestamp (datetime or ISO string);
            defaults to now.
        engine: Optional engine for dependency injection in tests.

    Returns:
        The created transaction dict (``transaction_type`` ``"BUY"``,
        ``realized_gain_loss`` 0.0).

    Raises:
        PaperTradingAccountNotFoundError: If the account does not exist.
        PaperTradingValidationError: If any field fails validation.
        InsufficientFundsError: If the cost exceeds the cash balance.
    """
    _e = engine or _get_engine()
    clean_ticker = _clean_ticker(ticker)
    clean_quantity = _clean_quantity(quantity)
    clean_price = _clean_price(price)
    clean_executed_at = _clean_executed_at(executed_at)
    gross = _money(clean_quantity * clean_price)
    now = datetime.now(tz=timezone.utc)

    with _e.begin() as conn:
        account = _account_row(conn, account_id)
        cash = Decimal(account.cash_balance)
        if gross > cash:
            raise InsufficientFundsError(
                f"Buying {clean_quantity} {clean_ticker} costs {gross}, "
                f"but the account cash balance is {cash}."
            )

        conn.execute(
            update(paper_trading_accounts)
            .where(paper_trading_accounts.c.id == account_id)
            .values(cash_balance=str(cash - gross), updated_at=now)
        )

        existing = _position_row(conn, account_id, clean_ticker)
        if existing is None:
            conn.execute(
                insert(paper_trading_positions).values(
                    account_id=account_id,
                    ticker=clean_ticker,
                    quantity=str(clean_quantity),
                    average_cost=str(_cost(clean_price)),
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            old_quantity = Decimal(existing.quantity)
            old_cost = Decimal(existing.average_cost)
            new_quantity = old_quantity + clean_quantity
            # Weighted average cost across the combined position.
            new_cost = _cost(
                (old_quantity * old_cost + clean_quantity * clean_price)
                / new_quantity
            )
            conn.execute(
                update(paper_trading_positions)
                .where(paper_trading_positions.c.id == existing.id)
                .values(
                    quantity=str(new_quantity),
                    average_cost=str(new_cost),
                    updated_at=now,
                )
            )

        return _insert_transaction(
            conn,
            account_id=account_id,
            transaction_type=BUY,
            ticker=clean_ticker,
            quantity=clean_quantity,
            price=clean_price,
            gross=gross,
            realized=_money(Decimal("0")),
            executed_at=clean_executed_at,
            now=now,
        )


def record_sell(
    account_id: int,
    ticker: str,
    quantity: object,
    price: object,
    executed_at: object = None,
    *,
    engine: Engine | None = None,
) -> dict:
    """Record a simulated sell and return the resulting ledger transaction.

    Realized gain/loss is ``(sell_price - average_cost) * quantity``, quantised
    to cents, and is added to the account's cumulative
    ``realized_gain_loss``.  Selling the whole position deletes the open
    position row; the ledger remains the audit trail.

    Short selling is not supported: a sell may never exceed the owned quantity.

    Args:
        account_id: Account to trade in.
        ticker: Ticker symbol (normalized to uppercase).
        quantity: Shares to sell; must be greater than zero and at most the
            owned quantity.
        price: Per-share price; must be greater than zero.
        executed_at: Optional execution timestamp (datetime or ISO string);
            defaults to now.
        engine: Optional engine for dependency injection in tests.

    Returns:
        The created transaction dict (``transaction_type`` ``"SELL"``, with the
        realized result on ``realized_gain_loss``).

    Raises:
        PaperTradingAccountNotFoundError: If the account does not exist.
        PaperTradingValidationError: If any field fails validation.
        InsufficientSharesError: If the account holds none of that ticker, or
            fewer shares than requested.
    """
    _e = engine or _get_engine()
    clean_ticker = _clean_ticker(ticker)
    clean_quantity = _clean_quantity(quantity)
    clean_price = _clean_price(price)
    clean_executed_at = _clean_executed_at(executed_at)
    gross = _money(clean_quantity * clean_price)
    now = datetime.now(tz=timezone.utc)

    with _e.begin() as conn:
        account = _account_row(conn, account_id)

        existing = _position_row(conn, account_id, clean_ticker)
        if existing is None:
            raise InsufficientSharesError(
                f"Account {account_id} holds no {clean_ticker} to sell."
            )

        owned = Decimal(existing.quantity)
        if clean_quantity > owned:
            raise InsufficientSharesError(
                f"Cannot sell {clean_quantity} {clean_ticker}: the account "
                f"holds {owned}."
            )

        average_cost = Decimal(existing.average_cost)
        realized = _money((clean_price - average_cost) * clean_quantity)

        conn.execute(
            update(paper_trading_accounts)
            .where(paper_trading_accounts.c.id == account_id)
            .values(
                cash_balance=str(Decimal(account.cash_balance) + gross),
                realized_gain_loss=str(
                    Decimal(account.realized_gain_loss) + realized
                ),
                updated_at=now,
            )
        )

        remaining = owned - clean_quantity
        if remaining == 0:
            # Position closed. The ledger keeps the full history.
            conn.execute(
                delete(paper_trading_positions).where(
                    paper_trading_positions.c.id == existing.id
                )
            )
        else:
            # Average cost is unchanged by a sell — only the quantity shrinks.
            conn.execute(
                update(paper_trading_positions)
                .where(paper_trading_positions.c.id == existing.id)
                .values(quantity=str(remaining), updated_at=now)
            )

        return _insert_transaction(
            conn,
            account_id=account_id,
            transaction_type=SELL,
            ticker=clean_ticker,
            quantity=clean_quantity,
            price=clean_price,
            gross=gross,
            realized=realized,
            executed_at=clean_executed_at,
            now=now,
        )


def _insert_transaction(
    conn: Any,
    *,
    account_id: int,
    transaction_type: str,
    ticker: str,
    quantity: Decimal,
    price: Decimal,
    gross: Decimal,
    realized: Decimal,
    executed_at: datetime,
    now: datetime,
) -> dict:
    """Append one row to the ledger and return it, on an open connection."""
    new_id = conn.execute(
        insert(paper_trading_transactions).values(
            account_id=account_id,
            transaction_type=transaction_type,
            ticker=ticker,
            quantity=str(quantity),
            price=str(price),
            gross_amount=str(gross),
            realized_gain_loss=str(realized),
            executed_at=executed_at,
            created_at=now,
        )
    ).lastrowid
    row = conn.execute(
        select(paper_trading_transactions).where(
            paper_trading_transactions.c.id == new_id
        )
    ).one()
    return _transaction_from_row(row)


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def list_positions(account_id: int, *, engine: Engine | None = None) -> list[dict]:
    """Return the account's open positions, ordered by ticker.

    Storage only — no market data.  Use
    ``paper_trading_summary_service.get_priced_positions`` for current prices
    and unrealized gain/loss.

    Raises:
        PaperTradingAccountNotFoundError: If the account does not exist.
    """
    _e = engine or _get_engine()
    with _e.connect() as conn:
        _account_row(conn, account_id)
        return _positions_for(conn, account_id)


def list_transactions(
    account_id: int,
    *,
    engine: Engine | None = None,
) -> list[dict]:
    """Return the account's full transaction ledger, newest first.

    Ordered by ``executed_at`` descending, with the row id as a deterministic
    tie-breaker so trades recorded in the same instant keep a stable order.

    Raises:
        PaperTradingAccountNotFoundError: If the account does not exist.
    """
    _e = engine or _get_engine()
    stmt = (
        select(paper_trading_transactions)
        .where(paper_trading_transactions.c.account_id == account_id)
        .order_by(
            paper_trading_transactions.c.executed_at.desc(),
            paper_trading_transactions.c.id.desc(),
        )
    )
    with _e.connect() as conn:
        _account_row(conn, account_id)
        return [_transaction_from_row(row) for row in conn.execute(stmt).all()]
