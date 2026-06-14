"""
Market-data route: GET /api/market-data/{ticker}/history.

Read-only. Delegates to ``market_data_service.get_price_history_response`` —
no pipeline, persistence, or DataFrame logic lives here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas.market_data import PriceHistoryResponse
from app.data.market_data import DataFetchError
from app.services.market_data_service import (
    DEFAULT_INTERVAL,
    DEFAULT_PERIOD,
    get_price_history_response,
)

router = APIRouter(prefix="/market-data", tags=["market-data"])


@router.get("/{ticker}/history", response_model=PriceHistoryResponse)
async def get_history(
    ticker: str,
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
) -> PriceHistoryResponse:
    """Return daily historical OHLCV price data for a ticker."""
    try:
        return get_price_history_response(ticker, period=period, interval=interval)
    except (ValueError, DataFetchError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc
