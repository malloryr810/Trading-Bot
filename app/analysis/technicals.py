"""
Technical analysis module.

Computes price-based indicators from a cleaned OHLCV DataFrame produced by
the data layer. Returns a new DataFrame with indicator columns appended.
Does not fetch data directly — accepts input from app/data/market_data.py.
"""

import pandas as pd

from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength


REQUIRED_OHLCV = {"open", "high", "low", "close", "volume"}

REQUIRED_INDICATOR_COLUMNS = {
    "sma_20", "sma_50", "rsi_14", "macd", "macd_signal", "volume_sma_20",
}

REQUIRED_SUMMARY_KEYS = {
    "latest_close", "sma_20", "sma_50", "sma_200",
    "rsi_14", "macd", "macd_signal",
    "volume", "volume_sma_20",
    "trend", "price_above_sma_20", "price_above_sma_50", "price_above_sma_200",
    "rsi_condition", "macd_condition",
}

# Strength, abs(score_impact), and confidence for each SMA window.
_SMA_CONFIGS: dict[int, tuple[SignalStrength, float, float]] = {
    20:  (SignalStrength.WEAK,     0.10, 0.60),
    50:  (SignalStrength.MODERATE, 0.15, 0.65),
    200: (SignalStrength.STRONG,   0.25, 0.70),
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


def build_technical_signals(indicator_summary: dict) -> list[Signal]:
    """Convert a technical summary dictionary into typed Signal objects.

    Accepts the dict returned by summarize_technical_signals() and maps each
    condition to a Signal that the scoring engine can consume.

    Args:
        indicator_summary: Dict returned by summarize_technical_signals().

    Returns:
        A list of 7 Signal objects, one per technical condition assessed.

    Raises:
        TechnicalAnalysisError: If input is not a dict, is empty, or is
            missing required summary keys.
    """
    _validate_summary_input(indicator_summary)

    return [
        _trend_signal(indicator_summary),
        _rsi_signal(indicator_summary),
        _macd_signal(indicator_summary),
        _price_vs_sma_signal(indicator_summary, window=20),
        _price_vs_sma_signal(indicator_summary, window=50),
        _price_vs_sma_signal(indicator_summary, window=200),
        _volume_signal(indicator_summary),
    ]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_ohlcv_input(df: object) -> None:
    if not isinstance(df, pd.DataFrame):
        raise TechnicalAnalysisError(
            f"Expected a DataFrame, got {type(df).__name__}."
        )
    if df.empty:
        raise TechnicalAnalysisError("price_data is empty.")
    missing = REQUIRED_OHLCV - set(df.columns)
    if missing:
        raise TechnicalAnalysisError(
            f"price_data is missing required OHLCV columns: {sorted(missing)}."
        )


def _validate_summary_input(summary: object) -> None:
    if not isinstance(summary, dict):
        raise TechnicalAnalysisError(
            f"indicator_summary must be a dict, got {type(summary).__name__}."
        )
    if not summary:
        raise TechnicalAnalysisError("indicator_summary must not be empty.")
    missing = REQUIRED_SUMMARY_KEYS - summary.keys()  # type: ignore[union-attr]
    if missing:
        raise TechnicalAnalysisError(
            f"indicator_summary is missing required keys: {sorted(missing)}."
        )


def _calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    # Where avg_loss is exactly 0 (all gains, no losses), RSI is definitionally 100.
    # Use .where() rather than .fillna() so pre-window NaN rows stay NaN.
    rsi = rsi.where(avg_loss != 0, other=100.0)
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


# ---------------------------------------------------------------------------
# Signal builder helpers
# ---------------------------------------------------------------------------

def _trend_signal(summary: dict) -> Signal:
    trend = summary["trend"]
    if trend == "bullish":
        direction, strength = SignalDirection.BULLISH, SignalStrength.MODERATE
        score_impact, confidence = 0.25, 0.70
        description = "Price is above SMA 20 which is above SMA 50, indicating an uptrend."
    elif trend == "bearish":
        direction, strength = SignalDirection.BEARISH, SignalStrength.MODERATE
        score_impact, confidence = -0.25, 0.70
        description = "Price is below SMA 20 which is below SMA 50, indicating a downtrend."
    else:
        direction, strength = SignalDirection.NEUTRAL, SignalStrength.WEAK
        score_impact, confidence = 0.0, 0.50
        description = "Price trend is mixed; no clear directional signal from SMA alignment."

    return Signal(
        name="Trend",
        category=SignalCategory.TECHNICAL,
        direction=direction,
        strength=strength,
        score_impact=score_impact,
        confidence=confidence,
        description=description,
        value=trend,
        metadata={
            "latest_close": summary["latest_close"],
            "sma_20": summary["sma_20"],
            "sma_50": summary["sma_50"],
        },
    )


def _rsi_signal(summary: dict) -> Signal:
    condition = summary["rsi_condition"]
    rsi_value = summary["rsi_14"]

    if condition == "overbought":
        direction, strength = SignalDirection.BEARISH, SignalStrength.MODERATE
        score_impact, confidence = -0.20, 0.65
        description = "RSI is above 70, suggesting the stock may be overbought."
    elif condition == "oversold":
        direction, strength = SignalDirection.BULLISH, SignalStrength.MODERATE
        score_impact, confidence = 0.20, 0.65
        description = "RSI is below 30, suggesting the stock may be oversold."
    else:
        direction, strength = SignalDirection.NEUTRAL, SignalStrength.WEAK
        score_impact, confidence = 0.0, 0.50
        description = "RSI is between 30 and 70, indicating neutral momentum."

    return Signal(
        name="RSI Condition",
        category=SignalCategory.TECHNICAL,
        direction=direction,
        strength=strength,
        score_impact=score_impact,
        confidence=confidence,
        description=description,
        value=rsi_value,
        metadata={"rsi_14": rsi_value},
    )


def _macd_signal(summary: dict) -> Signal:
    condition = summary["macd_condition"]
    macd_value = summary["macd"]

    if condition == "bullish":
        direction, strength = SignalDirection.BULLISH, SignalStrength.MODERATE
        score_impact, confidence = 0.20, 0.65
        description = "MACD line is above the signal line, indicating bullish momentum."
    elif condition == "bearish":
        direction, strength = SignalDirection.BEARISH, SignalStrength.MODERATE
        score_impact, confidence = -0.20, 0.65
        description = "MACD line is below the signal line, indicating bearish momentum."
    else:
        direction, strength = SignalDirection.NEUTRAL, SignalStrength.WEAK
        score_impact, confidence = 0.0, 0.50
        description = "MACD and signal line are aligned, indicating neutral momentum."

    return Signal(
        name="MACD Condition",
        category=SignalCategory.TECHNICAL,
        direction=direction,
        strength=strength,
        score_impact=score_impact,
        confidence=confidence,
        description=description,
        value=macd_value,
        metadata={"macd": macd_value, "macd_signal": summary["macd_signal"]},
    )


def _price_vs_sma_signal(summary: dict, window: int) -> Signal:
    above = summary[f"price_above_sma_{window}"]
    sma_value = summary[f"sma_{window}"]
    strength, impact_magnitude, conf_when_present = _SMA_CONFIGS[window]

    if above is None:
        return Signal(
            name=f"Price vs SMA {window}",
            category=SignalCategory.TECHNICAL,
            direction=SignalDirection.NEUTRAL,
            strength=SignalStrength.WEAK,
            score_impact=0.0,
            confidence=0.30,
            description=f"SMA {window} is unavailable; insufficient price history.",
            value=above,
            metadata={"latest_close": summary["latest_close"], f"sma_{window}": sma_value},
        )

    if above:
        direction = SignalDirection.BULLISH
        score_impact = impact_magnitude
        description = f"Price is above the {window}-period moving average."
    else:
        direction = SignalDirection.BEARISH
        score_impact = -impact_magnitude
        description = f"Price is below the {window}-period moving average."

    return Signal(
        name=f"Price vs SMA {window}",
        category=SignalCategory.TECHNICAL,
        direction=direction,
        strength=strength,
        score_impact=score_impact,
        confidence=conf_when_present,
        description=description,
        value=above,
        metadata={"latest_close": summary["latest_close"], f"sma_{window}": sma_value},
    )


def _volume_signal(summary: dict) -> Signal:
    volume = summary["volume"]
    volume_sma = summary["volume_sma_20"]

    if volume is None or volume_sma is None:
        return Signal(
            name="Volume vs Volume SMA 20",
            category=SignalCategory.TECHNICAL,
            direction=SignalDirection.NEUTRAL,
            strength=SignalStrength.WEAK,
            score_impact=0.0,
            confidence=0.30,
            description="Volume data is unavailable for comparison.",
            value=volume,
            metadata={"volume": volume, "volume_sma_20": volume_sma},
        )

    if volume > volume_sma:
        return Signal(
            name="Volume vs Volume SMA 20",
            category=SignalCategory.TECHNICAL,
            direction=SignalDirection.BULLISH,
            strength=SignalStrength.WEAK,
            score_impact=0.05,
            confidence=0.50,
            description="Volume is above the 20-period average, suggesting strong participation.",
            value=volume,
            metadata={"volume": volume, "volume_sma_20": volume_sma},
        )

    return Signal(
        name="Volume vs Volume SMA 20",
        category=SignalCategory.TECHNICAL,
        direction=SignalDirection.NEUTRAL,
        strength=SignalStrength.WEAK,
        score_impact=0.0,
        confidence=0.45,
        description="Volume is at or below the 20-period average.",
        value=volume,
        metadata={"volume": volume, "volume_sma_20": volume_sma},
    )
