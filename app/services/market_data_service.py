"""
Market-data service: assemble a JSON-safe historical price series.

Thin orchestration over the existing data layer (``app.data.market_data``).
It validates request parameters, fetches the validated OHLCV DataFrame, and
converts it into a transport-ready ``PriceHistoryResponse``. It performs no
analysis, scoring, or persistence — and never stores chart data.
"""

from __future__ import annotations

import pandas as pd

from app.api.schemas.market_data import PriceHistoryResponse, PricePoint
from app.data.market_data import get_price_history
from app.utils.helpers import normalize_ticker, safe_float

# Conservative, daily-or-coarser windows for now. Intraday intervals are
# intentionally excluded — real-time/intraday charting is a later phase.
ALLOWED_PERIODS: frozenset[str] = frozenset(
    {"1mo", "3mo", "6mo", "1y", "2y", "5y", "max"}
)
ALLOWED_INTERVALS: frozenset[str] = frozenset({"1d", "1wk", "1mo"})

DEFAULT_PERIOD = "1y"
DEFAULT_INTERVAL = "1d"


def get_price_history_response(
    ticker: str,
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
) -> PriceHistoryResponse:
    """Fetch daily price history and return a JSON-safe response model.

    Args:
        ticker: Stock ticker symbol (case-insensitive).
        period: Look-back window; must be one of ``ALLOWED_PERIODS``.
        interval: Bar interval; must be one of ``ALLOWED_INTERVALS``.

    Returns:
        A ``PriceHistoryResponse`` with chronological price points.

    Raises:
        ValueError: If the ticker is empty or the period/interval is unsupported.
        DataFetchError: If the data layer cannot fetch or validate the data.
    """
    symbol = normalize_ticker(ticker)
    period = _validate_choice(period, ALLOWED_PERIODS, "period")
    interval = _validate_choice(interval, ALLOWED_INTERVALS, "interval")

    df = get_price_history(symbol, period=period, interval=interval)

    prices = [_row_to_point(index, row) for index, row in df.iterrows()]
    data_timestamp = _to_iso(df.index[-1]) if len(df.index) else None

    return PriceHistoryResponse(
        ticker=symbol,
        period=period,
        interval=interval,
        data_timestamp=data_timestamp,
        prices=prices,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_choice(value: str, allowed: frozenset[str], name: str) -> str:
    """Normalize and validate a query choice; raise ValueError if unsupported."""
    normalized = value.strip().lower()
    if normalized not in allowed:
        raise ValueError(
            f"Invalid {name} {value!r}. Allowed values: {sorted(allowed)}."
        )
    return normalized


def _row_to_point(index: object, row: pd.Series) -> PricePoint:
    """Convert one DataFrame row into a JSON-safe PricePoint."""
    return PricePoint(
        date=_to_date(index),
        open=safe_float(row.get("open")),
        high=safe_float(row.get("high")),
        low=safe_float(row.get("low")),
        close=safe_float(row.get("close")),
        volume=safe_float(row.get("volume")),
    )


def _to_date(index: object) -> str:
    """Render a DatetimeIndex entry as an ISO date string (YYYY-MM-DD)."""
    return pd.Timestamp(index).date().isoformat()


def _to_iso(index: object) -> str:
    """Render a DatetimeIndex entry as a full ISO timestamp string."""
    return pd.Timestamp(index).isoformat()
