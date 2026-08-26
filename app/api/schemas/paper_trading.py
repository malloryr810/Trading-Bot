"""
Request and response schemas for /api/paper-trading/* endpoints.

These mirror the dict shapes returned by app/services/paper_trading_service.py
and app/services/paper_trading_summary_service.py.  The services own all
validation and accounting logic; these models only describe the HTTP
request/response contract.

Starting cash, quantities, and prices are accepted as ``Decimal`` on requests so
exact, decimal-safe values survive parsing (clients should send them as JSON
strings to avoid float rounding).  Numeric values are returned as plain numbers
for the display layer; storage and accounting remain decimal-exact in the
service.

Simulated trading only — no broker, no real order, no real account.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


# --- Requests --------------------------------------------------------------


class CreateAccountRequest(BaseModel):
    """Request body for POST /api/paper-trading/accounts."""

    name: str
    starting_cash: Decimal


class TradeRequest(BaseModel):
    """Request body for the buy and sell endpoints.

    ``price`` is supplied by the caller — the backend never fetches a price to
    execute a simulated trade.  A "paper buy" launched from a Discover candidate
    simply passes that candidate's displayed price through.
    """

    ticker: str
    quantity: Decimal
    price: Decimal
    executed_at: datetime | None = None


# --- Responses -------------------------------------------------------------


class PositionResponse(BaseModel):
    """One open position as stored, without market data."""

    id: int
    account_id: int
    ticker: str
    quantity: float
    average_cost: float
    cost_basis: float
    created_at: datetime
    updated_at: datetime


class AccountSummary(BaseModel):
    """Summary of an account — returned by the list endpoint."""

    id: int
    name: str
    starting_cash: float
    cash_balance: float
    realized_gain_loss: float
    created_at: datetime
    updated_at: datetime
    positions_count: int


class AccountDetail(BaseModel):
    """Full account with its open positions — returned by single-item endpoints."""

    id: int
    name: str
    starting_cash: float
    cash_balance: float
    realized_gain_loss: float
    created_at: datetime
    updated_at: datetime
    positions: list[PositionResponse]


class TransactionResponse(BaseModel):
    """One ledger row.  ``realized_gain_loss`` is always 0 for BUY rows."""

    id: int
    account_id: int
    transaction_type: str
    ticker: str
    quantity: float
    price: float
    gross_amount: float
    realized_gain_loss: float
    executed_at: datetime
    created_at: datetime


# --- Priced views ----------------------------------------------------------


class PricedPosition(BaseModel):
    """One open position enriched with current-price calculations.

    Market-value-dependent fields are ``None`` (never zero) when the current
    price is unavailable; ``price_available`` distinguishes the two cases.
    """

    position_id: int
    ticker: str
    quantity: float
    average_cost: float
    cost_basis: float
    price_available: bool
    latest_price: float | None
    market_value: float | None
    unrealized_gain_loss: float | None
    unrealized_gain_loss_percent: float | None


class PriceWarning(BaseModel):
    """One ticker whose current price could not be fetched."""

    ticker: str
    message: str


class PositionsResponse(BaseModel):
    """Priced open positions — returned by the positions endpoint."""

    account_id: int
    account_name: str
    generated_at: datetime
    positions_count: int
    priced_positions_count: int
    positions: list[PricedPosition]
    warnings: list[PriceWarning]
    has_price_warnings: bool


class AccountSummaryResponse(BaseModel):
    """Valued account summary — returned by the summary endpoint.

    ``realized_gain_loss`` is settled cash accumulated by past sells and is
    always present.  ``unrealized_gain_loss`` and ``open_positions_value``
    cover the priced open positions.  ``total_portfolio_value``,
    ``total_return``, and ``total_return_percent`` are ``None`` when the account
    holds positions that could not all be priced — the total is genuinely
    unknown then, rather than zero.
    """

    account_id: int
    account_name: str
    generated_at: datetime
    starting_cash: float
    cash_balance: float
    realized_gain_loss: float
    unrealized_gain_loss: float | None
    open_positions_value: float | None
    total_portfolio_value: float | None
    total_return: float | None
    total_return_percent: float | None
    positions_count: int
    priced_positions_count: int
    positions: list[PricedPosition]
    warnings: list[PriceWarning]
    has_price_warnings: bool
