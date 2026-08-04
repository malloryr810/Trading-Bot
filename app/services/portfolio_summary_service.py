"""
Portfolio summary (enrichment) service.

Reads a portfolio and its holdings via ``portfolio_service`` (storage), fetches
each ticker's current price through the existing market-data layer, and computes
holding-level and portfolio-level values.  This is the *only* place current
prices are fetched — ordinary portfolio/holding CRUD never touches market data.

Calculations use exact ``Decimal`` arithmetic and round only at the output
boundary (money and percentages to 2 decimal places).

Partial market-data failure is expected and handled: if a ticker's price cannot
be fetched, that holding is marked ``price_available = False`` (its
market-value-dependent fields are ``None``, never zero), a warning is added, and
the run continues.  Market-value-dependent portfolio totals are computed only
across holdings with an available price; ``total_cost_basis`` reflects all
holdings because cost basis does not depend on the current price.

This layer adds no analysis or scoring.  It never connects to a broker, executes
orders, tracks cash, or computes realized gains, dividends, or taxes.

Public function::

    get_portfolio_summary(portfolio_id, *, engine=None, price_lookup=None) -> dict
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy.engine import Engine

from app.data.market_data import get_price_history
from app.services.portfolio_service import get_portfolio
from app.utils.helpers import safe_float

# A price lookup returns the current price for a ticker, or ``None`` when no
# usable price is available.  It may also raise; the caller treats any raise as
# an unavailable price with the exception message recorded as a warning.
PriceLookup = Callable[[str], float | None]

_MONEY = Decimal("0.01")
_PERCENT = Decimal("0.01")


def _default_price_lookup(ticker: str) -> float | None:
    """Return the latest close for a ticker via the existing market-data layer.

    Reuses ``get_price_history`` (no second provider, no scraping).  Returns the
    most recent close as the current price, or ``None`` if it is not usable.
    """
    df = get_price_history(ticker, period="5d", interval="1d")
    if df.empty:
        return None
    return safe_float(df["close"].iloc[-1])


def _round_money(value: Decimal) -> float:
    return float(value.quantize(_MONEY, rounding=ROUND_HALF_UP))


def _round_percent(value: Decimal) -> float:
    return float(value.quantize(_PERCENT, rounding=ROUND_HALF_UP))


def _price_decimal(lookup: PriceLookup, ticker: str) -> tuple[Decimal | None, str | None]:
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


def get_portfolio_summary(
    portfolio_id: int,
    *,
    engine: Engine | None = None,
    price_lookup: PriceLookup | None = None,
) -> dict:
    """Build a priced summary for a portfolio.

    Args:
        portfolio_id: Integer primary key of the portfolio.
        engine: Optional engine for dependency injection in tests (passed to the
            storage lookup).
        price_lookup: Optional current-price function for dependency injection in
            tests.  Defaults to the market-data-backed lookup.

    Returns:
        Dict with portfolio metadata, a ``holdings`` list of priced rows, the
        aggregate totals, and a ``warnings`` list describing any unavailable
        prices.  Market-value-dependent totals are ``None`` when no holding has
        an available price.

    Raises:
        PortfolioNotFoundError: If the portfolio id does not exist.
    """
    lookup = price_lookup or _default_price_lookup
    portfolio = get_portfolio(portfolio_id, engine=engine)
    holdings = portfolio["holdings"]

    priced_rows: list[dict] = []
    warnings: list[dict] = []

    total_cost_basis = Decimal("0")
    priced_market_value = Decimal("0")
    priced_cost_basis = Decimal("0")

    # First pass: per-holding cost basis + price resolution (totals need pass two
    # for weights, which depend on the aggregate market value).
    computed: list[dict[str, Any]] = []
    for holding in holdings:
        shares = Decimal(str(holding["shares"]))
        average_cost = Decimal(str(holding["average_cost"]))
        cost_basis = shares * average_cost
        total_cost_basis += cost_basis

        price, warning = _price_decimal(lookup, holding["ticker"])
        if warning is not None:
            warnings.append({"ticker": holding["ticker"], "message": warning})

        market_value: Decimal | None = None
        if price is not None:
            market_value = shares * price
            priced_market_value += market_value
            priced_cost_basis += cost_basis

        computed.append(
            {
                "holding": holding,
                "cost_basis": cost_basis,
                "price": price,
                "market_value": market_value,
            }
        )

    # Second pass: assemble output rows, including portfolio weight (only for
    # priced holdings, relative to the aggregate priced market value).
    for item in computed:
        holding = item["holding"]
        cost_basis: Decimal = item["cost_basis"]
        price: Decimal | None = item["price"]
        market_value: Decimal | None = item["market_value"]

        unrealized_gl: Decimal | None = None
        unrealized_return_pct: float | None = None
        weight_pct: float | None = None
        if market_value is not None:
            unrealized_gl = market_value - cost_basis
            if cost_basis > 0:
                unrealized_return_pct = _round_percent(unrealized_gl / cost_basis * 100)
            if priced_market_value > 0:
                weight_pct = _round_percent(market_value / priced_market_value * 100)

        priced_rows.append(
            {
                "holding_id": holding["id"],
                "ticker": holding["ticker"],
                "shares": holding["shares"],
                "average_cost": holding["average_cost"],
                "purchase_date": holding["purchase_date"],
                "notes": holding["notes"],
                "price_available": price is not None,
                "current_price": _round_money(price) if price is not None else None,
                "cost_basis": _round_money(cost_basis),
                "market_value": _round_money(market_value) if market_value is not None else None,
                "unrealized_gain_loss": _round_money(unrealized_gl) if unrealized_gl is not None else None,
                "unrealized_return_pct": unrealized_return_pct,
                "weight_pct": weight_pct,
            }
        )

    priced_count = sum(1 for item in computed if item["price"] is not None)
    has_priced = priced_count > 0

    total_market_value = _round_money(priced_market_value) if has_priced else None
    total_unrealized_gl: float | None = None
    total_unrealized_return_pct: float | None = None
    if has_priced:
        gl = priced_market_value - priced_cost_basis
        total_unrealized_gl = _round_money(gl)
        if priced_cost_basis > 0:
            total_unrealized_return_pct = _round_percent(gl / priced_cost_basis * 100)

    return {
        "portfolio_id": portfolio["id"],
        "portfolio_name": portfolio["name"],
        "generated_at": datetime.now(tz=timezone.utc),
        "holdings_count": len(holdings),
        "priced_holdings_count": priced_count,
        "total_cost_basis": _round_money(total_cost_basis),
        "total_market_value": total_market_value,
        "total_unrealized_gain_loss": total_unrealized_gl,
        "total_unrealized_return_pct": total_unrealized_return_pct,
        "holdings": priced_rows,
        "warnings": warnings,
        "has_price_warnings": len(warnings) > 0,
    }
