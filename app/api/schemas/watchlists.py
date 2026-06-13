"""
Request and response schemas for /api/watchlists/* endpoints.

These mirror the dict shapes returned by app/services/watchlist_service.py.
The service owns all validation and business logic; these models only describe
the HTTP request/response contract.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


# --- Requests --------------------------------------------------------------


class CreateWatchlistRequest(BaseModel):
    """Request body for POST /api/watchlists."""

    name: str
    description: str | None = None


class UpdateWatchlistRequest(BaseModel):
    """Request body for PATCH /api/watchlists/{watchlist_id} (partial update)."""

    name: str | None = None
    description: str | None = None


class AddTickerRequest(BaseModel):
    """Request body for POST /api/watchlists/{watchlist_id}/tickers."""

    ticker: str


# --- Responses -------------------------------------------------------------


class WatchlistSummary(BaseModel):
    """Summary of a watchlist — returned by the list endpoint."""

    id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    ticker_count: int


class WatchlistDetail(BaseModel):
    """Full watchlist with its tickers — returned by single-item endpoints."""

    id: int
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    tickers: list[str]


class DeleteResponse(BaseModel):
    """Confirmation body for DELETE /api/watchlists/{watchlist_id}."""

    status: str = "deleted"
    id: int
