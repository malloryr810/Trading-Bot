"""
Response schemas for the market-data history endpoint.

Display/transport shapes only — no analysis or scoring logic. All numeric
fields are nullable so non-finite values (NaN/inf) can be safely serialized as
JSON ``null`` instead of producing invalid JSON.
"""

from __future__ import annotations

from pydantic import BaseModel


class PricePoint(BaseModel):
    """One OHLCV bar for a single date."""

    date: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None


class PriceHistoryResponse(BaseModel):
    """Historical daily price series for one ticker."""

    ticker: str
    period: str
    interval: str
    data_timestamp: str | None
    prices: list[PricePoint]
