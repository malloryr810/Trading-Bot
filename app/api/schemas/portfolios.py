"""
Request and response schemas for /api/portfolios/* endpoints.

These mirror the dict shapes returned by app/services/portfolio_service.py and
app/services/portfolio_summary_service.py.  The services own all validation and
business logic; these models only describe the HTTP request/response contract.

Shares and average cost are accepted as ``Decimal`` on requests so exact,
decimal-safe values survive parsing (clients should send them as JSON strings to
avoid float rounding).  Numeric values are returned as plain numbers for the
display layer; storage and validation remain decimal-exact in the service.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


# --- Requests --------------------------------------------------------------


class CreatePortfolioRequest(BaseModel):
    """Request body for POST /api/portfolios."""

    name: str
    description: str | None = None


class UpdatePortfolioRequest(BaseModel):
    """Request body for PATCH /api/portfolios/{portfolio_id} (partial update)."""

    name: str | None = None
    description: str | None = None


class AddHoldingRequest(BaseModel):
    """Request body for POST /api/portfolios/{portfolio_id}/holdings."""

    ticker: str
    shares: Decimal
    average_cost: Decimal
    purchase_date: str | None = None
    notes: str | None = None


class UpdateHoldingRequest(BaseModel):
    """Request body for PATCH /api/portfolios/{id}/holdings/{holding_id}.

    All fields optional (partial update).  Only provided fields change.
    """

    ticker: str | None = None
    shares: Decimal | None = None
    average_cost: Decimal | None = None
    purchase_date: str | None = None
    notes: str | None = None


# --- Responses -------------------------------------------------------------


class HoldingResponse(BaseModel):
    """One stored holding — returned by holding CRUD endpoints."""

    id: int
    portfolio_id: int
    ticker: str
    shares: float
    average_cost: float
    purchase_date: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class PortfolioSummary(BaseModel):
    """Summary of a portfolio — returned by the list endpoint."""

    id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    holdings_count: int


class PortfolioDetail(BaseModel):
    """Full portfolio with its stored holdings — returned by single-item endpoints."""

    id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    holdings: list[HoldingResponse]


class DeleteResponse(BaseModel):
    """Confirmation body for DELETE endpoints."""

    status: str = "deleted"
    id: int


# --- Portfolio summary (priced) --------------------------------------------


class HoldingValuation(BaseModel):
    """One holding enriched with current-price calculations.

    Market-value-dependent fields are ``None`` (never zero) when the current
    price is unavailable; ``price_available`` distinguishes the two cases.
    """

    holding_id: int
    ticker: str
    shares: float
    average_cost: float
    purchase_date: str | None
    notes: str | None
    price_available: bool
    current_price: float | None
    cost_basis: float
    market_value: float | None
    unrealized_gain_loss: float | None
    unrealized_return_pct: float | None
    weight_pct: float | None


class PortfolioSummaryWarning(BaseModel):
    """One ticker whose current price could not be fetched for the summary."""

    ticker: str
    message: str


class PortfolioSummaryResponse(BaseModel):
    """Priced portfolio summary — returned by the summary endpoint.

    Market-value-dependent totals are ``None`` when no holding has an available
    price.  ``total_cost_basis`` always reflects all holdings because cost basis
    does not depend on the current price.
    """

    portfolio_id: int
    portfolio_name: str
    generated_at: datetime
    holdings_count: int
    priced_holdings_count: int
    total_cost_basis: float
    total_market_value: float | None
    total_unrealized_gain_loss: float | None
    total_unrealized_return_pct: float | None
    holdings: list[HoldingValuation]
    warnings: list[PortfolioSummaryWarning]
    has_price_warnings: bool
