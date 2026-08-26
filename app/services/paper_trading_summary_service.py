"""
Paper trading summary (enrichment) service.

Reads a simulated account and its open positions via ``paper_trading_service``
(storage + accounting), fetches each ticker's current price through the existing
market-data layer, and computes unrealized gain/loss, open-position value, and
total simulated portfolio value.  This is the *only* place the paper trading
vertical fetches prices — account CRUD and trade recording never touch market
data, mirroring the ``portfolio_service`` / ``portfolio_summary_service`` split.

Realized gain/loss is **not** computed here: it is settled cash, already
accumulated on the account by ``record_sell``.  This module only values what is
still open.

Calculations use exact ``Decimal`` arithmetic and round only at the output
boundary (money and percentages to 2 decimal places).

Partial market-data failure is expected and handled: if a ticker's price cannot
be fetched, that position is marked ``price_available = False`` (its
market-value-dependent fields are ``None``, never zero), a warning is added, and
the run continues.  ``open_positions_value`` and the totals derived from it are
computed only across priced positions and are ``None`` when nothing is priced —
except that an account with no open positions at all values cleanly at zero.

This layer adds no analysis or scoring, and it is simulation only: no broker, no
real order, no real account, no automated trading.

Public functions::

    get_priced_positions(account_id, *, engine=None, price_lookup=None) -> dict
    get_account_summary(account_id, *, engine=None, price_lookup=None) -> dict
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.engine import Engine

from app.data.market_data import get_price_history, latest_valid_close
from app.services.paper_trading_service import get_account, list_positions
from app.utils.helpers import safe_float

# A price lookup returns the current price for a ticker, or ``None`` when no
# usable price is available.  It may also raise; the caller treats any raise as
# an unavailable price with the exception message recorded as a warning.
PriceLookup = Callable[[str], float | None]

_MONEY = Decimal("0.01")
_PERCENT = Decimal("0.01")


def _default_price_lookup(ticker: str) -> float | None:
    """Return the latest valid close for a ticker via the existing market-data layer.

    Reuses ``get_price_history`` (no second provider, no scraping) and the shared
    ``latest_valid_close`` reader, so an in-progress session — whose final row
    can carry a volume but null OHLC values — falls back to the last settled
    close instead of reporting no price.  Returns ``None`` when nothing usable
    is available.
    """
    df = get_price_history(ticker, period="5d", interval="1d")
    return latest_valid_close(df)


def _round_money(value: Decimal) -> float:
    return float(value.quantize(_MONEY, rounding=ROUND_HALF_UP))


def _round_percent(value: Decimal) -> float:
    return float(value.quantize(_PERCENT, rounding=ROUND_HALF_UP))


def _price_decimal(
    lookup: PriceLookup,
    ticker: str,
) -> tuple[Decimal | None, str | None]:
    """Resolve a ticker's current price as a Decimal, or (None, warning message)."""
    try:
        raw = lookup(ticker)
    except Exception as exc:  # noqa: BLE001 — any provider failure is non-fatal here
        return None, str(exc) or type(exc).__name__
    price = safe_float(raw)
    if price is None:
        return None, f"No current price available for {ticker}."
    if price <= 0:
        return None, f"Current price for {ticker} was not usable ({price})."
    return Decimal(str(price)), None


def _value_positions(
    positions: list[dict],
    lookup: PriceLookup,
) -> tuple[list[dict], list[dict], Decimal, Decimal, int]:
    """Price every open position.

    Returns:
        The priced rows, the warning dicts, the aggregate market value across
        priced positions, the aggregate cost basis across priced positions, and
        the number of positions that were successfully priced.
    """
    priced_rows: list[dict] = []
    warnings: list[dict] = []
    priced_market_value = Decimal("0")
    priced_cost_basis = Decimal("0")
    priced_count = 0

    for position in positions:
        quantity = Decimal(str(position["quantity"]))
        average_cost = Decimal(str(position["average_cost"]))
        cost_basis = quantity * average_cost

        price, warning = _price_decimal(lookup, position["ticker"])
        if warning is not None:
            warnings.append({"ticker": position["ticker"], "message": warning})

        market_value: Decimal | None = None
        unrealized: Decimal | None = None
        unrealized_pct: float | None = None
        if price is not None:
            priced_count += 1
            market_value = quantity * price
            unrealized = market_value - cost_basis
            priced_market_value += market_value
            priced_cost_basis += cost_basis
            if cost_basis > 0:
                unrealized_pct = _round_percent(unrealized / cost_basis * 100)

        priced_rows.append(
            {
                "position_id": position["id"],
                "ticker": position["ticker"],
                "quantity": position["quantity"],
                "average_cost": position["average_cost"],
                "cost_basis": _round_money(cost_basis),
                "price_available": price is not None,
                "latest_price": _round_money(price) if price is not None else None,
                "market_value": (
                    _round_money(market_value) if market_value is not None else None
                ),
                "unrealized_gain_loss": (
                    _round_money(unrealized) if unrealized is not None else None
                ),
                "unrealized_gain_loss_percent": unrealized_pct,
            }
        )

    return priced_rows, warnings, priced_market_value, priced_cost_basis, priced_count


def _resolve(
    account_id: int,
    engine: Engine | None,
    price_lookup: PriceLookup | None,
) -> tuple[dict, list[dict], PriceLookup]:
    """Load the account and its open positions, and pick the price lookup."""
    account = get_account(account_id, engine=engine)
    positions = list_positions(account_id, engine=engine)
    return account, positions, price_lookup or _default_price_lookup


def get_priced_positions(
    account_id: int,
    *,
    engine: Engine | None = None,
    price_lookup: PriceLookup | None = None,
) -> dict:
    """Return the account's open positions enriched with current prices.

    Args:
        account_id: Integer primary key of the paper trading account.
        engine: Optional engine for dependency injection in tests.
        price_lookup: Optional current-price function for dependency injection
            in tests.  Defaults to the market-data-backed lookup.

    Returns:
        Dict with ``account_id``, ``generated_at``, ``positions``,
        ``warnings``, and the priced/total counts.  A ticker whose price could
        not be fetched still appears, with ``price_available: false`` and
        ``None`` market fields.

    Raises:
        PaperTradingAccountNotFoundError: If the account id does not exist.
    """
    account, positions, lookup = _resolve(account_id, engine, price_lookup)
    priced_rows, warnings, _market, _basis, priced_count = _value_positions(
        positions, lookup
    )
    return {
        "account_id": account["id"],
        "account_name": account["name"],
        "generated_at": datetime.now(tz=timezone.utc),
        "positions_count": len(positions),
        "priced_positions_count": priced_count,
        "positions": priced_rows,
        "warnings": warnings,
        "has_price_warnings": len(warnings) > 0,
    }


def get_account_summary(
    account_id: int,
    *,
    engine: Engine | None = None,
    price_lookup: PriceLookup | None = None,
) -> dict:
    """Build a valued summary for a simulated trading account.

    ``total_portfolio_value`` is ``cash_balance + open_positions_value``;
    ``total_return`` is that minus ``starting_cash``.  Both are ``None`` when
    the account holds positions but none of them could be priced — the value is
    genuinely unknown then, and reporting cash alone would understate it.  An
    account with no open positions values cleanly: ``open_positions_value`` is
    zero and the totals are exact.

    Args:
        account_id: Integer primary key of the paper trading account.
        engine: Optional engine for dependency injection in tests.
        price_lookup: Optional current-price function for dependency injection
            in tests.  Defaults to the market-data-backed lookup.

    Returns:
        Dict with the account identity, cash, realized and unrealized gain/loss,
        open-position value, total value and return, the priced position rows,
        and a ``warnings`` list describing any unavailable prices.

    Raises:
        PaperTradingAccountNotFoundError: If the account id does not exist.
    """
    account, positions, lookup = _resolve(account_id, engine, price_lookup)
    priced_rows, warnings, priced_market_value, priced_cost_basis, priced_count = (
        _value_positions(positions, lookup)
    )

    starting_cash = Decimal(str(account["starting_cash"]))
    cash_balance = Decimal(str(account["cash_balance"]))

    # Valued when every open position priced, or when there are none at all.
    fully_valued = priced_count == len(positions)

    unrealized: float | None = None
    open_positions_value: float | None = None
    total_portfolio_value: float | None = None
    total_return: float | None = None
    total_return_percent: float | None = None

    if priced_count > 0 or not positions:
        unrealized = _round_money(priced_market_value - priced_cost_basis)
        open_positions_value = _round_money(priced_market_value)

    if fully_valued:
        total_value = cash_balance + priced_market_value
        total_portfolio_value = _round_money(total_value)
        gain = total_value - starting_cash
        total_return = _round_money(gain)
        if starting_cash > 0:
            total_return_percent = _round_percent(gain / starting_cash * 100)

    return {
        "account_id": account["id"],
        "account_name": account["name"],
        "generated_at": datetime.now(tz=timezone.utc),
        "starting_cash": account["starting_cash"],
        "cash_balance": account["cash_balance"],
        "realized_gain_loss": account["realized_gain_loss"],
        "unrealized_gain_loss": unrealized,
        "open_positions_value": open_positions_value,
        "total_portfolio_value": total_portfolio_value,
        "total_return": total_return,
        "total_return_percent": total_return_percent,
        "positions_count": len(positions),
        "priced_positions_count": priced_count,
        "positions": priced_rows,
        "warnings": warnings,
        "has_price_warnings": len(warnings) > 0,
    }
