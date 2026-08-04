"""
Portfolio management routes.

  GET    /api/portfolios                                   — list portfolios
  POST   /api/portfolios                                   — create a portfolio
  GET    /api/portfolios/{portfolio_id}                    — get one + holdings
  PATCH  /api/portfolios/{portfolio_id}                    — update name/description
  DELETE /api/portfolios/{portfolio_id}                    — delete + its holdings
  POST   /api/portfolios/{portfolio_id}/holdings           — add a holding
  PATCH  /api/portfolios/{portfolio_id}/holdings/{holding_id} — update a holding
  DELETE /api/portfolios/{portfolio_id}/holdings/{holding_id} — remove a holding
  GET    /api/portfolios/{portfolio_id}/summary            — priced summary

All routes delegate to the portfolio services; no persistence, market-data, or
calculation logic lives here.  Validation errors map to HTTP 400, duplicate
tickers to 409, not-found to 404.  The summary endpoint returns 200 even on
partial (or complete) market-data failure — unavailable prices surface in the
response ``warnings`` list.  Storage + read-only enrichment only: no broker
links, order execution, or trading behavior.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas.portfolios import (
    AddHoldingRequest,
    CreatePortfolioRequest,
    DeleteResponse,
    HoldingResponse,
    PortfolioDetail,
    PortfolioSummary,
    PortfolioSummaryResponse,
    UpdateHoldingRequest,
    UpdatePortfolioRequest,
)
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
from app.services.portfolio_summary_service import get_portfolio_summary

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


@router.get("", response_model=list[PortfolioSummary])
async def get_portfolios() -> list[dict]:
    """Return all portfolios, newest first."""
    return list_portfolios()


@router.post("", response_model=PortfolioDetail, status_code=201)
async def post_portfolio(request: CreatePortfolioRequest) -> dict:
    """Create a new portfolio."""
    try:
        return create_portfolio(request.name, request.description)
    except (PortfolioValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{portfolio_id}", response_model=PortfolioDetail)
async def get_one_portfolio(portfolio_id: int) -> dict:
    """Return one portfolio with its holdings."""
    try:
        return get_portfolio(portfolio_id)
    except (PortfolioNotFoundError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/{portfolio_id}", response_model=PortfolioDetail)
async def patch_portfolio(portfolio_id: int, request: UpdatePortfolioRequest) -> dict:
    """Update a portfolio's name and/or description (partial update)."""
    try:
        return update_portfolio(portfolio_id, request.name, request.description)
    except (PortfolioNotFoundError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (PortfolioValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{portfolio_id}", response_model=DeleteResponse)
async def delete_one_portfolio(portfolio_id: int) -> dict:
    """Delete a portfolio and all of its holdings."""
    try:
        delete_portfolio(portfolio_id)
    except (PortfolioNotFoundError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"status": "deleted", "id": portfolio_id}


@router.post(
    "/{portfolio_id}/holdings",
    response_model=HoldingResponse,
    status_code=201,
)
async def post_holding(portfolio_id: int, request: AddHoldingRequest) -> dict:
    """Add a holding to a portfolio.

    Duplicate tickers within a portfolio are rejected with HTTP 409.
    """
    try:
        return add_holding(
            portfolio_id,
            request.ticker,
            request.shares,
            request.average_cost,
            request.purchase_date,
            request.notes,
        )
    except DuplicateHoldingError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (PortfolioNotFoundError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (PortfolioValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch(
    "/{portfolio_id}/holdings/{holding_id}",
    response_model=HoldingResponse,
)
async def patch_holding(
    portfolio_id: int,
    holding_id: int,
    request: UpdateHoldingRequest,
) -> dict:
    """Update a holding (partial). Duplicate-ticker validation is preserved."""
    try:
        return update_holding(
            portfolio_id,
            holding_id,
            request.ticker,
            request.shares,
            request.average_cost,
            request.purchase_date,
            request.notes,
        )
    except DuplicateHoldingError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (PortfolioNotFoundError, HoldingNotFoundError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (PortfolioValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete(
    "/{portfolio_id}/holdings/{holding_id}",
    response_model=DeleteResponse,
)
async def delete_one_holding(portfolio_id: int, holding_id: int) -> dict:
    """Remove one holding from a portfolio."""
    try:
        remove_holding(portfolio_id, holding_id)
    except (PortfolioNotFoundError, HoldingNotFoundError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"status": "deleted", "id": holding_id}


@router.get("/{portfolio_id}/summary", response_model=PortfolioSummaryResponse)
async def get_summary(portfolio_id: int) -> dict:
    """Return the portfolio with current-price calculations.

    A missing portfolio is 404.  Per-ticker market-data failures never fail the
    request: affected holdings are marked ``price_available: false`` and listed
    in ``warnings``.
    """
    try:
        return get_portfolio_summary(portfolio_id)
    except (PortfolioNotFoundError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
