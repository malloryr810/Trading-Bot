"""
Market data fetcher.

Responsible for retrieving OHLCV price history from yfinance.
Returns a normalized, validated pandas DataFrame consumed by the analysis layer.
"""

import yfinance as yf
import pandas as pd


REQUIRED_COLUMNS = {"open", "high", "low", "close", "volume"}


class DataFetchError(Exception):
    """Raised when market data cannot be fetched or validated."""


def get_price_history(
    ticker: str,
    period: str = "1y",
    interval: str = "1d",
) -> pd.DataFrame:
    """Fetch and return historical OHLCV price data for a ticker.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL"). Case-insensitive.
        period: yfinance period string (e.g. "1y", "6mo", "3mo").
        interval: yfinance interval string (e.g. "1d", "1wk").

    Returns:
        DataFrame with a DatetimeIndex and normalized lowercase column names.
        Always contains: open, high, low, close, volume.

    Raises:
        DataFetchError: If the ticker is invalid, data is unavailable,
            required columns are missing, or yfinance raises an error.
    """
    _validate_ticker(ticker)
    symbol = ticker.strip().upper()

    try:
        raw = yf.download(symbol, period=period, interval=interval, progress=False)
    except Exception as exc:
        raise DataFetchError(
            f"yfinance raised an error while fetching '{symbol}': {exc}"
        ) from exc

    if raw is None or raw.empty:
        raise DataFetchError(
            f"No data returned by yfinance for ticker '{symbol}'. "
            "The symbol may be invalid or delisted."
        )

    df = _normalize_columns(raw)
    _validate_columns(df, symbol)

    df = df.dropna(subset=list(REQUIRED_COLUMNS), how="all")

    if df.empty:
        raise DataFetchError(
            f"All rows for '{symbol}' contained missing OHLCV values after cleaning."
        )

    return df


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_ticker(ticker: object) -> None:
    if not isinstance(ticker, str):
        raise DataFetchError(
            f"Ticker must be a string, got {type(ticker).__name__}."
        )
    if not ticker.strip():
        raise DataFetchError("Ticker must not be empty or whitespace.")


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase column names and replace spaces with underscores."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
    return df


def _validate_columns(df: pd.DataFrame, symbol: str) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise DataFetchError(
            f"Data for '{symbol}' is missing required columns: {sorted(missing)}."
        )
