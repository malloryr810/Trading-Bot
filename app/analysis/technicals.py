"""
Technical analysis module.

Computes price-based indicators from a cleaned OHLCV DataFrame produced by
the data layer. Returns a new DataFrame with indicator columns appended.
Does not fetch data directly — accepts input from app/data/market_data.py.
"""

import pandas as pd


REQUIRED_OHLCV = {"open", "high", "low", "close", "volume"}

REQUIRED_INDICATOR_COLUMNS = {
    "sma_20", "sma_50", "rsi_14", "macd", "macd_signal", "volume_sma_20",
}


class TechnicalAnalysisError(Exception):
    """Raised when technical indicators cannot be calculated."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def calculate_technical_indicators(price_data: pd.DataFrame) -> pd.DataFrame:
    """Compute technical indicators from a cleaned OHLCV DataFrame.

    Args:
        price_data: DataFrame with columns open, high, low, close, volume
                    and a DatetimeIndex, as returned by get_price_history().

    Returns:
        A new DataFrame containing the original columns plus:
        sma_20, sma_50, sma_200, rsi_14, macd, macd_signal,
        macd_histogram, volume_sma_20, daily_return.
        Rows where a window has not yet filled will contain NaN.

    Raises:
        TechnicalAnalysisError: If input is not a DataFrame, is empty,
            or is missing required OHLCV columns.
    """
    _validate_ohlcv_input(price_data)
    df = price_data.copy()

    close = df["close"]
    volume = df["volume"]

    # Simple moving averages
    df["sma_20"] = close.rolling(window=20).mean()
    df["sma_50"] = close.rolling(window=50).mean()
    df["sma_200"] = close.rolling(window=200).mean()

    # RSI 14
    df["rsi_14"] = _calculate_rsi(close, period=14)

    # MACD
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema_12 - ema_26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_histogram"] = df["macd"] - df["macd_signal"]

    # Volume SMA
    df["volume_sma_20"] = volume.rolling(window=20).mean()

    # Daily return
    df["daily_return"] = close.pct_change()

    return df


def summarize_technical_signals(indicator_data: pd.DataFrame) -> dict:
    """Build a human-readable signal summary from the latest indicator row.

    Args:
        indicator_data: DataFrame returned by calculate_technical_indicators().

    Returns:
        Dictionary with latest values and derived signal labels.

    Raises:
        TechnicalAnalysisError: If input is invalid, empty, or missing
            required indicator columns.
    """
    if not isinstance(indicator_data, pd.DataFrame):
        raise TechnicalAnalysisError(
            f"Expected a DataFrame, got {type(indicator_data).__name__}."
        )
    if indicator_data.empty:
        raise TechnicalAnalysisError("indicator_data is empty.")

    missing = REQUIRED_INDICATOR_COLUMNS - set(indicator_data.columns)
    if missing:
        raise TechnicalAnalysisError(
            f"indicator_data is missing required columns: {sorted(missing)}."
        )

    row = indicator_data.iloc[-1]

    close = float(row["close"])
    sma_20 = _maybe_float(row.get("sma_20"))
    sma_50 = _maybe_float(row.get("sma_50"))
    sma_200 = _maybe_float(row.get("sma_200"))
    rsi = _maybe_float(row.get("rsi_14"))
    macd = _maybe_float(row.get("macd"))
    macd_signal = _maybe_float(row.get("macd_signal"))

    return {
        "latest_close": close,
        "sma_20": sma_20,
        "sma_50": sma_50,
        "sma_200": sma_200,
        "rsi_14": rsi,
        "macd": macd,
        "macd_signal": macd_signal,
        "volume": float(row["volume"]),
        "volume_sma_20": _maybe_float(row.get("volume_sma_20")),
        "trend": _classify_trend(close, sma_20, sma_50),
        "price_above_sma_20": _above(close, sma_20),
        "price_above_sma_50": _above(close, sma_50),
        "price_above_sma_200": _above(close, sma_200),
        "rsi_condition": _classify_rsi(rsi),
        "macd_condition": _classify_macd(macd, macd_signal),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_ohlcv_input(df: object) -> None:
    if not isinstance(df, pd.DataFrame):
        raise TechnicalAnalysisError(
            f"Expected a DataFrame, got {type(df).__name__}."
        )
    if isinstance(df, pd.DataFrame) and df.empty:
        raise TechnicalAnalysisError("price_data is empty.")
    missing = REQUIRED_OHLCV - set(df.columns)  # type: ignore[union-attr]
    if missing:
        raise TechnicalAnalysisError(
            f"price_data is missing required OHLCV columns: {sorted(missing)}."
        )


def _calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    # Avoid division by zero: where avg_loss is 0, RS is effectively infinite → RSI = 100
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    # When avg_loss is 0 and avg_gain > 0, RSI is 100
    rsi = rsi.fillna(100)
    return rsi


def _maybe_float(value: object) -> float | None:
    """Return float if value is a finite number, else None."""
    try:
        f = float(value)  # type: ignore[arg-type]
        return None if f != f else f  # NaN check: NaN != NaN
    except (TypeError, ValueError):
        return None


def _above(price: float, level: float | None) -> bool | None:
    if level is None:
        return None
    return price > level


def _classify_trend(
    close: float, sma_20: float | None, sma_50: float | None
) -> str:
    if sma_20 is None or sma_50 is None:
        return "mixed"
    if close > sma_20 > sma_50:
        return "bullish"
    if close < sma_20 < sma_50:
        return "bearish"
    return "mixed"


def _classify_rsi(rsi: float | None) -> str:
    if rsi is None:
        return "neutral"
    if rsi >= 70:
        return "overbought"
    if rsi <= 30:
        return "oversold"
    return "neutral"


def _classify_macd(macd: float | None, signal: float | None) -> str:
    if macd is None or signal is None:
        return "neutral"
    if macd > signal:
        return "bullish"
    if macd < signal:
        return "bearish"
    return "neutral"
