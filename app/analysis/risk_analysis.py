"""
Risk analysis module.

Evaluates downside conditions from historical OHLCV price data and optional
beta. Returns typed Signal objects consumed by the scoring engine.
Does not fetch data — accepts a DataFrame from the data layer.
"""

from __future__ import annotations

import math
from math import sqrt

import pandas as pd

from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength


REQUIRED_COLUMNS = {"close", "volume"}

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

_VOL_HIGH = 0.45    # annualized volatility
_VOL_LOW  = 0.25

_DD_SEVERE = -0.35  # maximum drawdown
_DD_MILD   = -0.15

_TREND_DOWN     = -0.10  # 30-day price return
_TREND_UP       =  0.05
_TREND_MIN_ROWS =  31    # minimum rows needed for the 30-day lookback

_LIQ_LOW  = 500_000    # average daily volume
_LIQ_HIGH = 1_000_000

_BETA_HIGH = 1.5
_BETA_LOW  = 0.8


class RiskAnalysisError(Exception):
    """Raised when risk signals cannot be computed from the provided input."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_risk_conditions(
    price_history: pd.DataFrame,
    beta: float | None = None,
) -> list[Signal]:
    """Evaluate downside risk conditions from OHLCV price history.

    Args:
        price_history: DataFrame with lowercase columns including at least
            'close' and 'volume', as returned by get_price_history().
        beta: Optional stock beta (market sensitivity measure). When provided,
            a beta signal is added to the output.

    Returns:
        A list of 4 Signal objects (or 5 when beta is provided), each using
        SignalCategory.RISK.

    Raises:
        RiskAnalysisError: If price_history is not a non-empty DataFrame with
            the required columns, or if beta is provided but is not a finite number.
    """
    _validate_price_history(price_history)
    if beta is not None:
        _validate_beta(beta)

    close  = price_history["close"].dropna()
    volume = price_history["volume"].dropna()

    signals: list[Signal] = [
        _volatility_signal(close),
        _max_drawdown_signal(close),
        _recent_trend_signal(close),
        _liquidity_signal(volume),
    ]

    if beta is not None:
        signals.append(_beta_signal(beta))

    return signals


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_price_history(df: object) -> None:
    if not isinstance(df, pd.DataFrame):
        raise RiskAnalysisError(
            f"Expected a DataFrame, got {type(df).__name__}."
        )
    if df.empty:
        raise RiskAnalysisError("price_history is empty.")
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise RiskAnalysisError(
            f"price_history is missing required columns: {sorted(missing)}."
        )


def _validate_beta(beta: object) -> None:
    try:
        f = float(beta)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise RiskAnalysisError(f"beta must be a finite number, got {beta!r}.")
    if not math.isfinite(f):
        raise RiskAnalysisError(f"beta must be finite, got {beta!r}.")


# ---------------------------------------------------------------------------
# Signal builders
# ---------------------------------------------------------------------------

def _volatility_signal(close: pd.Series) -> Signal:
    """Annualized volatility from daily returns."""
    vol_daily = _safe_float(close.pct_change().dropna().std())

    if vol_daily is None:
        return _insufficient_data_signal(
            "Volatility Risk",
            "Insufficient price data to compute volatility.",
            {"annualized_volatility": None},
        )

    annualized = vol_daily * sqrt(252)

    if annualized >= _VOL_HIGH:
        direction, strength = SignalDirection.BEARISH, SignalStrength.STRONG
        score_impact, confidence = -0.20, 0.75
        description = (
            f"High annualized volatility of {annualized:.1%} indicates elevated price risk."
        )
    elif annualized >= _VOL_LOW:
        direction, strength = SignalDirection.NEUTRAL, SignalStrength.WEAK
        score_impact, confidence = 0.0, 0.60
        description = (
            f"Moderate annualized volatility of {annualized:.1%}; within a normal range."
        )
    else:
        direction, strength = SignalDirection.BULLISH, SignalStrength.WEAK
        score_impact, confidence = 0.10, 0.65
        description = (
            f"Low annualized volatility of {annualized:.1%} indicates relatively stable pricing."
        )

    return Signal(
        name="Volatility Risk",
        category=SignalCategory.RISK,
        direction=direction,
        strength=strength,
        score_impact=score_impact,
        confidence=confidence,
        description=description,
        value=round(annualized, 4),
        metadata={"annualized_volatility": round(annualized, 4)},
    )


def _max_drawdown_signal(close: pd.Series) -> Signal:
    """Peak-to-trough maximum drawdown over the full price history."""
    if len(close) < 2:
        return _insufficient_data_signal(
            "Maximum Drawdown Risk",
            "Insufficient price data to compute maximum drawdown.",
            {"max_drawdown": None},
        )

    drawdown = (close / close.cummax()) - 1
    max_dd = _safe_float(drawdown.min())

    if max_dd is None:
        return _insufficient_data_signal(
            "Maximum Drawdown Risk",
            "Maximum drawdown could not be computed.",
            {"max_drawdown": None},
        )

    if max_dd <= _DD_SEVERE:
        direction, strength = SignalDirection.BEARISH, SignalStrength.STRONG
        score_impact, confidence = -0.25, 0.75
        description = (
            f"Severe maximum drawdown of {max_dd:.1%} indicates significant historical losses."
        )
    elif max_dd <= _DD_MILD:
        direction, strength = SignalDirection.NEUTRAL, SignalStrength.MODERATE
        score_impact, confidence = 0.0, 0.65
        description = (
            f"Moderate maximum drawdown of {max_dd:.1%}; some historical price weakness."
        )
    else:
        direction, strength = SignalDirection.BULLISH, SignalStrength.WEAK
        score_impact, confidence = 0.10, 0.60
        description = (
            f"Mild maximum drawdown of {max_dd:.1%}; price has been relatively resilient."
        )

    return Signal(
        name="Maximum Drawdown Risk",
        category=SignalCategory.RISK,
        direction=direction,
        strength=strength,
        score_impact=score_impact,
        confidence=confidence,
        description=description,
        value=round(max_dd, 4),
        metadata={"max_drawdown": round(max_dd, 4)},
    )


def _recent_trend_signal(close: pd.Series) -> Signal:
    """30-trading-day price return as a short-term trend risk signal."""
    if len(close) < _TREND_MIN_ROWS:
        return _insufficient_data_signal(
            "Recent Trend Risk",
            (
                f"Fewer than {_TREND_MIN_ROWS} data points available; "
                "30-day trend cannot be assessed."
            ),
            {"return_30d": None, "rows_available": len(close)},
        )

    return_30d = _safe_float((close.iloc[-1] / close.iloc[-31]) - 1)

    if return_30d is None:
        return _insufficient_data_signal(
            "Recent Trend Risk",
            "30-day trend could not be computed.",
            {"return_30d": None},
        )

    if return_30d <= _TREND_DOWN:
        direction, strength = SignalDirection.BEARISH, SignalStrength.MODERATE
        score_impact, confidence = -0.15, 0.65
        description = (
            f"Recent 30-day return of {return_30d:.1%} indicates recent price weakness."
        )
    elif return_30d >= _TREND_UP:
        direction, strength = SignalDirection.BULLISH, SignalStrength.WEAK
        score_impact, confidence = 0.10, 0.60
        description = (
            f"Recent 30-day return of {return_30d:.1%} indicates recent price strength."
        )
    else:
        direction, strength = SignalDirection.NEUTRAL, SignalStrength.WEAK
        score_impact, confidence = 0.0, 0.55
        description = (
            f"Recent 30-day return of {return_30d:.1%}; no strong directional signal."
        )

    return Signal(
        name="Recent Trend Risk",
        category=SignalCategory.RISK,
        direction=direction,
        strength=strength,
        score_impact=score_impact,
        confidence=confidence,
        description=description,
        value=round(return_30d, 4),
        metadata={"return_30d": round(return_30d, 4)},
    )


def _liquidity_signal(volume: pd.Series) -> Signal:
    """Average daily volume as a proxy for liquidity."""
    avg_vol = _safe_float(volume.mean())

    if avg_vol is None:
        return _insufficient_data_signal(
            "Liquidity Risk",
            "Volume data is unavailable; liquidity cannot be assessed.",
            {"average_volume": None},
        )

    if avg_vol < _LIQ_LOW:
        direction, strength = SignalDirection.BEARISH, SignalStrength.MODERATE
        score_impact, confidence = -0.15, 0.65
        description = (
            f"Low average daily volume ({avg_vol:,.0f} shares) may indicate liquidity risk."
        )
    elif avg_vol < _LIQ_HIGH:
        direction, strength = SignalDirection.NEUTRAL, SignalStrength.WEAK
        score_impact, confidence = 0.0, 0.55
        description = f"Moderate average daily volume ({avg_vol:,.0f} shares)."
    else:
        direction, strength = SignalDirection.BULLISH, SignalStrength.WEAK
        score_impact, confidence = 0.10, 0.60
        description = (
            f"Adequate average daily volume ({avg_vol:,.0f} shares) suggests good liquidity."
        )

    return Signal(
        name="Liquidity Risk",
        category=SignalCategory.RISK,
        direction=direction,
        strength=strength,
        score_impact=score_impact,
        confidence=confidence,
        description=description,
        value=round(avg_vol, 0),
        metadata={"average_volume": round(avg_vol, 0)},
    )


def _beta_signal(beta: float) -> Signal:
    """Market sensitivity signal derived from the stock's beta coefficient."""
    if beta >= _BETA_HIGH:
        direction, strength = SignalDirection.BEARISH, SignalStrength.MODERATE
        score_impact, confidence = -0.15, 0.70
        description = (
            f"High beta of {beta:.2f} indicates elevated sensitivity to market moves."
        )
    elif beta >= _BETA_LOW:
        direction, strength = SignalDirection.NEUTRAL, SignalStrength.WEAK
        score_impact, confidence = 0.0, 0.65
        description = f"Beta of {beta:.2f} is within a normal market-sensitivity range."
    else:
        direction, strength = SignalDirection.BULLISH, SignalStrength.WEAK
        score_impact, confidence = 0.10, 0.65
        description = (
            f"Low beta of {beta:.2f} indicates lower sensitivity to market moves."
        )

    return Signal(
        name="Beta Risk",
        category=SignalCategory.RISK,
        direction=direction,
        strength=strength,
        score_impact=score_impact,
        confidence=confidence,
        description=description,
        value=beta,
        metadata={"beta": beta},
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_float(value: object) -> float | None:
    """Return float if value is a finite number, else None."""
    try:
        f = float(value)  # type: ignore[arg-type]
        return None if not math.isfinite(f) else f
    except (TypeError, ValueError):
        return None


def _insufficient_data_signal(
    name: str,
    description: str,
    metadata: dict,
) -> Signal:
    """Return a neutral low-confidence Signal for when data is unavailable."""
    return Signal(
        name=name,
        category=SignalCategory.RISK,
        direction=SignalDirection.NEUTRAL,
        strength=SignalStrength.WEAK,
        score_impact=0.0,
        confidence=0.30,
        description=description,
        value=None,
        metadata=metadata,
    )
