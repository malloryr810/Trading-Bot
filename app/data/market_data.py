"""
Market data fetcher.

Responsible for retrieving OHLCV price history from yfinance.
Returns a normalized, validated pandas DataFrame consumed by the analysis layer.

Validation pipeline (in order):
    1. Normalize and validate the ticker symbol.
    2. Call yfinance, wrapping any exception as DataFetchError.
    3. Verify the result is a pandas DataFrame.
    4. Verify the DataFrame is not empty.
    5. Normalize column names to lowercase.
    6. Verify all required OHLCV columns are present.
    7. Verify no required column is entirely null.
    8. Verify all required columns contain numeric data.
    9. Drop rows where all OHLCV values are null, then verify not empty.
"""

from __future__ import annotations

import pandas as pd
import yfinance as yf

from app.utils.helpers import normalize_ticker


REQUIRED_COLUMNS: frozenset[str] = frozenset({"open", "high", "low", "close", "volume"})


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
            required columns are missing, columns are non-numeric, or
            yfinance raises an error.
    """
    try:
        symbol = normalize_ticker(ticker)
    except ValueError as exc:
        raise DataFetchError(str(exc)) from exc

    try:
        raw = yf.download(symbol, period=period, interval=interval, progress=False)
    except Exception as exc:
        raise DataFetchError(
            f"yfinance raised an error fetching '{symbol}' "
            f"(period={period!r}, interval={interval!r}): {exc}"
        ) from exc

    if not isinstance(raw, pd.DataFrame):
        raise DataFetchError(
            f"yfinance returned an unexpected result type for '{symbol}': "
            f"{type(raw).__name__}. Expected a DataFrame."
        )

    if raw.empty:
        raise DataFetchError(
            f"No data returned by yfinance for '{symbol}' "
            f"(period={period!r}, interval={interval!r}). "
            "The symbol may be invalid or delisted."
        )

    df = _normalize_columns(raw)
    _validate_price_history(df, symbol)

    df = df.dropna(subset=list(REQUIRED_COLUMNS), how="all")

    if df.empty:
        raise DataFetchError(
            f"All rows for '{symbol}' contained only missing OHLCV values after cleaning."
        )

    # TODO: Add staleness detection — raise DataFetchError if the latest row date is
    # unreasonably old relative to today (e.g. >14 calendar days for short periods).
    # Requires careful handling of weekends, market holidays, and test fixture dates.
    # Deferred to avoid false failures without an exchange-calendar dependency.

    return df


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns, lowercase names, replace spaces with underscores."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
    return df


def _validate_price_history(df: pd.DataFrame, symbol: str) -> None:
    """Validate a normalized DataFrame meets all requirements for downstream analysis.

    Assumes column names have already been normalized to lowercase by
    _normalize_columns. Raises DataFetchError with a specific message on the
    first validation failure found.
    """
    _validate_required_columns(df, symbol)
    _validate_column_nullability(df, symbol)
    _validate_numeric_columns(df, symbol)


def _validate_required_columns(df: pd.DataFrame, symbol: str) -> None:
    """Raise DataFetchError if any required OHLCV column is absent."""
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise DataFetchError(
            f"Data for '{symbol}' is missing required columns: {sorted(missing)}. "
            f"Columns present: {sorted(df.columns.tolist())}."
        )


def _validate_column_nullability(df: pd.DataFrame, symbol: str) -> None:
    """Raise DataFetchError if any required column contains only null values."""
    for col in sorted(REQUIRED_COLUMNS):
        if col in df.columns and df[col].isna().all():
            raise DataFetchError(
                f"Required column '{col}' for '{symbol}' contains no usable values "
                f"(all values are null)."
            )


def _validate_numeric_columns(df: pd.DataFrame, symbol: str) -> None:
    """Raise DataFetchError if any required column has a non-numeric dtype."""
    for col in sorted(REQUIRED_COLUMNS):
        if col not in df.columns:
            continue  # already caught by _validate_required_columns
        if not pd.api.types.is_numeric_dtype(df[col]):
            raise DataFetchError(
                f"Column '{col}' for '{symbol}' has non-numeric dtype "
                f"'{df[col].dtype}'. OHLCV price data must be numeric."
            )
