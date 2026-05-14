"""
Scoring engine.

Currently implements technical-only scoring from typed Signal objects.
Full multi-category scoring (Technical 35%, Fundamental 25%, News 25%, Risk 15%)
will be added once those analysis modules are implemented.
"""

from __future__ import annotations

from datetime import datetime

from app.models.rating import ConfidenceLevel, Rating, RatingCategory
from app.models.signal import Signal, SignalCategory


class ScoringError(Exception):
    """Raised when stock signals cannot be scored."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_technical_signals(
    ticker: str,
    signals: list[Signal],
    data_timestamp: datetime | None = None,
    data_sources_used: list[str] | None = None,
) -> Rating:
    """Score a list of technical signals and return a typed Rating.

    Only technical signals (SignalCategory.TECHNICAL) are accepted.
    Fundamental, news, and risk sub-scores are set to 0.0 because those
    analysis modules have not been implemented yet.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL").
        signals: Non-empty list of technical Signal objects.
        data_timestamp: Optional timestamp of the underlying price data.
        data_sources_used: Optional list of data source names.

    Returns:
        A Rating with technical_score == score, all other sub-scores 0.0.

    Raises:
        ScoringError: If ticker is invalid, signals is not a non-empty list
            of technical Signal objects.
    """
    _validate_scoring_inputs(ticker, signals)
    sources = list(data_sources_used) if data_sources_used is not None else []

    technical_score = _calculate_technical_score(signals)
    category = _map_score_to_category(technical_score)
    confidence = _map_confidence(signals)

    positive_factors = _build_positive_factors(signals)
    risk_factors = _build_risk_factors(signals)

    n = len(signals)
    explanation = (
        f"Technical-only rating for {ticker.strip().upper()} based on {n} technical "
        "signals. Fundamentals, news, and risk analysis are not included yet."
    )
    technical_summary = (
        f"Technical score: {technical_score:.1f}/100 based on trend, RSI, MACD, "
        "moving-average, and volume signals."
    )
    buy_trigger = _build_buy_trigger(category)
    sell_or_avoid_trigger = _build_sell_avoid_trigger(category)

    return Rating(
        ticker=ticker,
        final_category=category,
        score=technical_score,
        confidence=confidence,
        explanation=explanation,
        technical_score=technical_score,
        fundamental_score=0.0,
        news_score=0.0,
        risk_score=0.0,
        technical_summary=technical_summary,
        key_positive_factors=positive_factors,
        key_risks=risk_factors,
        buy_trigger=buy_trigger,
        sell_or_avoid_trigger=sell_or_avoid_trigger,
        data_timestamp=data_timestamp,
        data_sources_used=sources,
        signals_used=list(signals),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_scoring_inputs(ticker: object, signals: object) -> None:
    if not isinstance(ticker, str) or not ticker.strip():
        raise ScoringError(
            f"ticker must be a non-empty string, got {ticker!r}."
        )
    if not isinstance(signals, list):
        raise ScoringError(
            f"signals must be a list, got {type(signals).__name__}."
        )
    if not signals:
        raise ScoringError("signals must not be empty.")
    for i, item in enumerate(signals):
        if not isinstance(item, Signal):
            raise ScoringError(
                f"signals[{i}] is not a Signal instance (got {type(item).__name__})."
            )
        if item.category != SignalCategory.TECHNICAL:
            raise ScoringError(
                f"signals[{i}] has category '{item.category.value}'; "
                "score_technical_signals only accepts TECHNICAL signals."
            )


def _calculate_technical_score(signals: list[Signal]) -> float:
    """Sum score_impacts, clamp to [-1, 1], then scale to [0, 100]."""
    total_impact = sum(s.score_impact for s in signals)
    clamped = max(-1.0, min(1.0, total_impact))
    return round(50.0 + clamped * 50.0, 10)


def _map_score_to_category(score: float) -> RatingCategory:
    if score >= 85:
        return RatingCategory.STRONG_BUY_CANDIDATE
    if score >= 70:
        return RatingCategory.BUY_CANDIDATE
    if score >= 55:
        return RatingCategory.WATCHLIST
    if score >= 45:
        return RatingCategory.HOLD
    if score >= 30:
        return RatingCategory.AVOID
    return RatingCategory.SELL_EXIT_WARNING


def _map_confidence(signals: list[Signal]) -> ConfidenceLevel:
    avg = sum(s.confidence for s in signals) / len(signals)
    if avg >= 0.70:
        return ConfidenceLevel.HIGH
    if avg >= 0.45:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def _build_positive_factors(signals: list[Signal]) -> list[str]:
    return [
        s.description
        for s in signals
        if s.score_impact > 0
    ]


def _build_risk_factors(signals: list[Signal]) -> list[str]:
    return [
        s.description
        for s in signals
        if s.score_impact < 0
    ]


def _build_buy_trigger(category: RatingCategory) -> str:
    if category in {RatingCategory.STRONG_BUY_CANDIDATE, RatingCategory.BUY_CANDIDATE}:
        return (
            "Already showing positive technical conditions; consider waiting for "
            "confirmation from fundamentals and risk analysis."
        )
    return (
        "Consider only if technical score improves above 70 and future "
        "fundamentals/risk checks support the setup."
    )


def _build_sell_avoid_trigger(category: RatingCategory) -> str:
    if category in {RatingCategory.AVOID, RatingCategory.SELL_EXIT_WARNING}:
        return (
            "Technical conditions are weak; avoid or review for exit unless "
            "future analysis provides a strong counterargument."
        )
    return (
        "Reassess if technical score falls below 45 or bearish signals strengthen."
    )
