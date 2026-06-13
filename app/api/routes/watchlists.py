"""
Watchlist management routes.

  GET    /api/watchlists                              — list saved watchlists
  POST   /api/watchlists                              — create a watchlist
  GET    /api/watchlists/{watchlist_id}               — get one watchlist + tickers
  PATCH  /api/watchlists/{watchlist_id}               — update name/description
  DELETE /api/watchlists/{watchlist_id}               — delete a watchlist
  POST   /api/watchlists/{watchlist_id}/tickers       — add a ticker
  DELETE /api/watchlists/{watchlist_id}/tickers/{ticker} — remove a ticker

All routes delegate to app.services.watchlist_service; no persistence or
business logic lives here.  Validation errors map to HTTP 400, not-found to 404.
Storage only — no analysis, scoring, or trading behavior.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas.watchlists import (
    AddTickerRequest,
    CreateWatchlistRequest,
    DeleteResponse,
    UpdateWatchlistRequest,
    WatchlistDetail,
    WatchlistSummary,
)
from app.services.watchlist_service import (
    WatchlistNotFoundError,
    WatchlistValidationError,
    add_ticker_to_watchlist,
    create_watchlist,
    delete_watchlist,
    get_watchlist,
    list_watchlists,
    remove_ticker_from_watchlist,
    update_watchlist,
)

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


@router.get("", response_model=list[WatchlistSummary])
async def get_watchlists() -> list[dict]:
    """Return all saved watchlists, newest first."""
    return list_watchlists()


@router.post("", response_model=WatchlistDetail, status_code=201)
async def post_watchlist(request: CreateWatchlistRequest) -> dict:
    """Create a new watchlist."""
    try:
        return create_watchlist(request.name, request.description)
    except (WatchlistValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{watchlist_id}", response_model=WatchlistDetail)
async def get_one_watchlist(watchlist_id: int) -> dict:
    """Return one watchlist with its tickers."""
    try:
        return get_watchlist(watchlist_id)
    except (WatchlistNotFoundError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/{watchlist_id}", response_model=WatchlistDetail)
async def patch_watchlist(watchlist_id: int, request: UpdateWatchlistRequest) -> dict:
    """Update a watchlist's name and/or description (partial update)."""
    try:
        return update_watchlist(watchlist_id, request.name, request.description)
    except (WatchlistNotFoundError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (WatchlistValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{watchlist_id}", response_model=DeleteResponse)
async def delete_one_watchlist(watchlist_id: int) -> dict:
    """Delete a watchlist and its tickers."""
    try:
        delete_watchlist(watchlist_id)
    except (WatchlistNotFoundError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"status": "deleted", "id": watchlist_id}


@router.post("/{watchlist_id}/tickers", response_model=WatchlistDetail)
async def post_ticker(watchlist_id: int, request: AddTickerRequest) -> dict:
    """Add a ticker to a watchlist (idempotent for duplicates)."""
    try:
        return add_ticker_to_watchlist(watchlist_id, request.ticker)
    except (WatchlistNotFoundError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (WatchlistValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{watchlist_id}/tickers/{ticker}", response_model=WatchlistDetail)
async def delete_ticker(watchlist_id: int, ticker: str) -> dict:
    """Remove a ticker from a watchlist (idempotent if absent)."""
    try:
        return remove_ticker_from_watchlist(watchlist_id, ticker)
    except (WatchlistNotFoundError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (WatchlistValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
