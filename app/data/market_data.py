"""
Market data fetcher.

Responsible for retrieving OHLCV price history from yfinance.
Returns a normalized, validated pandas DataFrame consumed by the analysis layer.

Also owns ``latest_valid_close`` — the single, canonical way to read a "current
price" out of a price-history DataFrame. Use it instead of indexing the final
row: while a trading session is in progress the provider can return a row for
the current day whose OHLC values are still null, and taking that row literally
turns a perfectly good price into "unavailable".

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

from app.utils.helpers import normalize_ticker, safe_float


REQUIRED_COLUMNS: frozenset[str] = frozenset({"open", "high", "low", "close", "volume"})


class DataFetchError(Exception):
    """Raised when market data cannot be fetched or validated."""


def latest_valid_close(price_data: pd.DataFrame) -> float | None:
    """Return the most recent usable close price from a price-history DataFrame.

    This is the canonical "what is it trading at right now" reader. Rows are
    scanned newest-first and the first close that is a finite number wins;
    missing, null, NaN, infinite, and non-numeric closes are skipped. That
    matters because while a session is in progress the provider commonly returns
    a row for the current day with a volume but null OHLC values — the settled
    close from the previous session is the right answer there, not "no price".

    Zero and negative closes are returned as-is rather than skipped: they are
    numerically valid, and callers that require a positive price (portfolio
    valuation, the discovery pre-screen) already check for that themselves.

    Args:
        price_data: A normalized price-history DataFrame (lowercase columns).

    Returns:
        The most recent finite close, or ``None`` when the frame is empty, has
        no ``close`` column, or contains no usable close at all. ``None`` is the
        explicit "unavailable" state used throughout this project (see
        ``safe_float``) — it is never substituted with zero.
    """
    if not isinstance(price_data, pd.DataFrame) or "close" not in price_data.columns:
        return None

    for value in reversed(price_data["close"].tolist()):
        close = safe_float(value)
        if close is not None:
            return close

    return None


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
