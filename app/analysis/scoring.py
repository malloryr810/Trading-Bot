"""
Scoring engine.

Implements technical-only scoring (score_technical_signals) and composite
scoring across technical, fundamental, news, and risk signals (score_signals).
Base weights: Technical 35%, Fundamental 25%, News 25%, Risk 15%; sum to 1.00;
re-normalised to active categories when any category is absent.
"""

from __future__ import annotations

from datetime import datetime

from app.models.confidence_diagnostics import ConfidenceDiagnostics
from app.models.rating import ConfidenceLevel, Rating, RatingCategory
from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength


class ScoringError(Exception):
    """Raised when stock signals cannot be scored."""


# Supported categories and their base weights (sum to 1.00; re-normalised when
# a category is absent).
_WEIGHTS: dict[SignalCategory, float] = {
    SignalCategory.TECHNICAL:   0.35,
    SignalCategory.FUNDAMENTAL: 0.25,
    SignalCategory.NEWS:        0.25,
    SignalCategory.RISK:        0.15,
}

_STRENGTH_ORDER: dict[SignalStrength, int] = {
    SignalStrength.STRONG:   0,
    SignalStrength.MODERATE: 1,
    SignalStrength.WEAK:     2,
}

_CATEGORY_LABELS: dict[SignalCategory, str] = {
    SignalCategory.TECHNICAL:   "technical",
    SignalCategory.FUNDAMENTAL: "fundamental",
    SignalCategory.NEWS:        "news sentiment",
    SignalCategory.RISK:        "risk",
}

_CAUTION_KEYWORDS: frozenset[str] = frozenset({
    "elevated", "caution", "warning", "declining",
    "concern", "overbought", "overextended",
    "low liquidity", "thin volume", "no news", "absence",
})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_signals(
    ticker: str,
    signals: list[Signal],
    data_timestamp: datetime | None = None,
    data_sources_used: list[str] | None = None,
) -> Rating:
    """Score a mixed list of signals and return a composite Rating.

    Supported categories are TECHNICAL (35%), FUNDAMENTAL (25%), NEWS (25%),
    and RISK (15%). Weights are re-normalised to 100% when any category is
    absent.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL").
        signals: Non-empty list of Signal objects.
        data_timestamp: Optional timestamp of the underlying data.
        data_sources_used: Optional list of data source names.

    Returns:
        A Rating with composite score and per-category sub-scores.

    Raises:
        ScoringError: If ticker is invalid, signals is not a non-empty list
            of Signal objects, or no supported signal categories are present.
    """
    _validate_composite_inputs(ticker, signals)
    sources = list(data_sources_used) if data_sources_used is not None else []

    by_category: dict[SignalCategory, list[Signal]] = {}
    for sig in signals:
        if sig.category in _WEIGHTS:
            by_category.setdefault(sig.category, []).append(sig)

    if not by_category:
        raise ScoringError(
            "No supported signal categories found in the provided signals. "
            "Expected at least one TECHNICAL, FUNDAMENTAL, NEWS, or RISK signal."
        )

    total_weight = sum(_WEIGHTS[cat] for cat in by_category)

    tech_signals = by_category.get(SignalCategory.TECHNICAL, [])
    fund_signals = by_category.get(SignalCategory.FUNDAMENTAL, [])
    news_signals = by_category.get(SignalCategory.NEWS, [])
    risk_signals = by_category.get(SignalCategory.RISK, [])

    technical_score   = _signals_to_score(tech_signals) if tech_signals else 0.0
    fundamental_score = _signals_to_score(fund_signals) if fund_signals else 0.0
    news_score        = _signals_to_score(news_signals) if news_signals else 0.0
    risk_score        = _signals_to_score(risk_signals) if risk_signals else 0.0

    composite = sum(
        _signals_to_score(cat_signals) * (_WEIGHTS[cat] / total_weight)
        for cat, cat_signals in by_category.items()
    )
    composite_score = round(composite, 10)

    category = _map_score_to_category(composite_score)
    confidence = _map_confidence(signals)
    confidence_diag = _build_confidence_diagnostics(signals)
    positive_factors = _build_positive_factors(signals)
    risk_factors = _build_risk_factors(signals)

    parts = []
    if tech_signals:
        parts.append(f"{len(tech_signals)} technical")
    if fund_signals:
        parts.append(f"{len(fund_signals)} fundamental")
    if news_signals:
        parts.append(f"{len(news_signals)} news")
    if risk_signals:
        parts.append(f"{len(risk_signals)} risk")
    explanation = (
        f"Composite rating for {ticker.strip().upper()} based on "
        f"{' and '.join(parts)} signals."
    )

    technical_summary: str | None = None
    if tech_signals:
        technical_summary = (
            f"Technical score: {technical_score:.1f}/100 based on trend, RSI, MACD, "
            "moving-average, and volume signals."
        )

    fundamental_summary: str | None = None
    if fund_signals:
        fundamental_summary = (
            f"Fundamental score: {fundamental_score:.1f}/100 based on valuation, "
            "profitability, growth, debt, and cash flow signals."
        )

    news_summary: str | None = None
    if news_signals:
        if news_score >= 65:
            sentiment_label = "positive"
        elif news_score >= 55:
            sentiment_label = "moderately positive"
        elif news_score >= 45:
            sentiment_label = "mixed or neutral"
        elif news_score >= 35:
            sentiment_label = "cautionary"
        else:
            sentiment_label = "negative"
        news_summary = (
            f"News score: {news_score:.1f}/100 — sentiment is {sentiment_label} "
            "based on recent headlines, risk indicators, and coverage."
        )

    risk_summary: str | None = None
    if risk_signals:
        risk_summary = (
            f"Risk score: {risk_score:.1f}/100 based on volatility, drawdown, "
            "recent trend, liquidity, and beta signals."
        )

    active_categories = frozenset(by_category.keys())
    buy_trigger = _build_buy_trigger(
        category, technical_score, fundamental_score, news_score, risk_score,
        active_categories,
    )
    sell_or_avoid_trigger = _build_sell_avoid_trigger(
        category, technical_score, fundamental_score, news_score, risk_score,
        active_categories,
    )

    return Rating(
        ticker=ticker,
        final_category=category,
        score=composite_score,
        confidence=confidence,
        confidence_diagnostics=confidence_diag,
        explanation=explanation,
        technical_score=technical_score,
        fundamental_score=fundamental_score,
        news_score=news_score,
        risk_score=risk_score,
        technical_summary=technical_summary,
        fundamental_summary=fundamental_summary,
        news_summary=news_summary,
        risk_summary=risk_summary,
        key_positive_factors=positive_factors,
        key_risks=risk_factors,
        buy_trigger=buy_trigger,
        sell_or_avoid_trigger=sell_or_avoid_trigger,
        data_timestamp=data_timestamp,
        data_sources_used=sources,
        signals_used=list(signals),
    )


def score_technical_signals(
    ticker: str,
    signals: list[Signal],
    data_timestamp: datetime | None = None,
    data_sources_used: list[str] | None = None,
) -> Rating:
    """Score a list of technical signals and return a typed Rating.

    Only technical signals (SignalCategory.TECHNICAL) are accepted.
    Fundamental, news, and risk sub-scores are set to 0.0 because this is a
    technical-only scoring path. Use score_signals() for composite scoring.

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
    confidence_diag = _build_confidence_diagnostics(signals)

    positive_factors = _build_positive_factors(signals)
    risk_factors = _build_risk_factors(signals)

    n = len(signals)
    explanation = (
        f"Technical-only rating for {ticker.strip().upper()} based on {n} technical "
        "signals. Use score_signals() to include fundamental and risk analysis."
    )
    technical_summary = (
        f"Technical score: {technical_score:.1f}/100 based on trend, RSI, MACD, "
        "moving-average, and volume signals."
    )
    active_categories = frozenset({SignalCategory.TECHNICAL})
    buy_trigger = _build_buy_trigger(
        category, technical_score, 0.0, 0.0, 0.0, active_categories,
    )
    sell_or_avoid_trigger = _build_sell_avoid_trigger(
        category, technical_score, 0.0, 0.0, 0.0, active_categories,
    )

    return Rating(
        ticker=ticker,
        final_category=category,
        score=technical_score,
        confidence=confidence,
        confidence_diagnostics=confidence_diag,
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

def _validate_composite_inputs(ticker: object, signals: object) -> None:
    if not isinstance(ticker, str) or not ticker.strip():
        raise ScoringError(f"ticker must be a non-empty string, got {ticker!r}.")
    if not isinstance(signals, list):
        raise ScoringError(f"signals must be a list, got {type(signals).__name__}.")
    if not signals:
        raise ScoringError("signals must not be empty.")
    for i, item in enumerate(signals):
        if not isinstance(item, Signal):
            raise ScoringError(
                f"signals[{i}] is not a Signal instance (got {type(item).__name__})."
            )


def _validate_scoring_inputs(ticker: object, signals: object) -> None:
    if not isinstance(ticker, str) or not ticker.strip():
        raise ScoringError(f"ticker must be a non-empty string, got {ticker!r}.")
    if not isinstance(signals, list):
        raise ScoringError(f"signals must be a list, got {type(signals).__name__}.")
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


def _signals_to_score(signals: list[Signal]) -> float:
    """Sum score_impacts, clamp to [-1, 1], then scale to [0, 100]."""
    total_impact = sum(s.score_impact for s in signals)
    clamped = max(-1.0, min(1.0, total_impact))
    return round(50.0 + clamped * 50.0, 10)


def _calculate_technical_score(signals: list[Signal]) -> float:
    return _signals_to_score(signals)


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


def _build_confidence_diagnostics(signals: list[Signal]) -> ConfidenceDiagnostics:
    """Compute a read-only breakdown of the confidence inputs for a scoring run.

    Captures the per-signal confidence values, direction counts, and per-area
    averages so they can be inspected without re-running analysis. Does not
    alter the final confidence label or any score.

    Signals with confidence <= 0.30 are counted as missing_count: all four
    analysis modules assign exactly 0.30 when a required data field is None.
    """
    if not signals:
        return ConfidenceDiagnostics()

    confs = [s.confidence for s in signals]
    avg = sum(confs) / len(confs)

    def _area_avg(cat: SignalCategory) -> float | None:
        area = [s.confidence for s in signals if s.category == cat]
        return round(sum(area) / len(area), 4) if area else None

    return ConfidenceDiagnostics(
        signal_count=len(signals),
        average_signal_confidence=round(avg, 4),
        min_signal_confidence=round(min(confs), 4),
        max_signal_confidence=round(max(confs), 4),
        bullish_count=sum(1 for s in signals if s.direction == SignalDirection.BULLISH),
        bearish_count=sum(1 for s in signals if s.direction == SignalDirection.BEARISH),
        neutral_count=sum(1 for s in signals if s.direction == SignalDirection.NEUTRAL),
        missing_count=sum(1 for s in signals if s.confidence <= 0.30),
        technical_average_confidence=_area_avg(SignalCategory.TECHNICAL),
        fundamental_average_confidence=_area_avg(SignalCategory.FUNDAMENTAL),
        news_average_confidence=_area_avg(SignalCategory.NEWS),
        risk_average_confidence=_area_avg(SignalCategory.RISK),
    )


def _build_positive_factors(signals: list[Signal]) -> list[str]:
    positives = sorted(
        (s for s in signals if s.score_impact > 0),
        key=lambda s: _STRENGTH_ORDER.get(s.strength, 1),
    )
    return [s.description for s in positives]


def _is_cautionary_neutral(signal: Signal) -> bool:
    """Return True for neutral signals whose description contains a caution keyword."""
    if signal.direction != SignalDirection.NEUTRAL or signal.score_impact < 0:
        return False
    desc_lower = signal.description.lower()
    return any(kw in desc_lower for kw in _CAUTION_KEYWORDS)


def _build_risk_factors(signals: list[Signal]) -> list[str]:
    bearish = [s.description for s in signals if s.score_impact < 0]
    cautionary = [s.description for s in signals if _is_cautionary_neutral(s)]
    return (bearish + cautionary)[:10]


def _weak_category_labels(
    active_scores: dict[SignalCategory, float],
    threshold: float,
) -> list[str]:
    """Return category labels for active categories scoring below threshold, lowest first."""
    below = [(cat, sc) for cat, sc in active_scores.items() if sc < threshold]
    below.sort(key=lambda x: x[1])
    return [_CATEGORY_LABELS[cat] for cat, _ in below]


def _build_buy_trigger(
    category: RatingCategory,
    technical_score: float,
    fundamental_score: float,
    news_score: float,
    risk_score: float,
    active_categories: frozenset[SignalCategory],
) -> str:
    active_scores = {
        cat: sc
        for cat, sc in [
            (SignalCategory.TECHNICAL,   technical_score),
            (SignalCategory.FUNDAMENTAL, fundamental_score),
            (SignalCategory.NEWS,        news_score),
            (SignalCategory.RISK,        risk_score),
        ]
        if cat in active_categories
    }

    if category in {RatingCategory.STRONG_BUY_CANDIDATE, RatingCategory.BUY_CANDIDATE}:
        weak = _weak_category_labels(active_scores, 55.0)
        if weak:
            dragging = " and ".join(weak)
            return (
                f"Setup is broadly positive. Monitor {dragging} conditions — "
                "these are the weakest active signal areas."
            )
        return (
            "All active signal categories are constructive. "
            "Confirm position sizing before entry."
        )

    if category == RatingCategory.WATCHLIST:
        weak = _weak_category_labels(active_scores, 60.0)
        if weak:
            dragging = " and ".join(weak)
            return (
                f"Near entry territory. Consider a position only once {dragging} "
                "conditions improve and the composite score exceeds 65."
            )
        return (
            "Near entry territory. Wait for the composite score to push "
            "above 65 before committing."
        )

    weak = _weak_category_labels(active_scores, 50.0)
    if weak:
        dragging = " and ".join(weak)
        return (
            f"No entry signal. {dragging.capitalize()} conditions are a headwind; "
            "wait for the composite score to recover above 65."
        )
    return (
        "No clear entry signal. Wait for the composite score to improve "
        "above 65 across multiple signal categories."
    )


def _build_sell_avoid_trigger(
    category: RatingCategory,
    technical_score: float,
    fundamental_score: float,
    news_score: float,
    risk_score: float,
    active_categories: frozenset[SignalCategory],
) -> str:
    active_scores = {
        cat: sc
        for cat, sc in [
            (SignalCategory.TECHNICAL,   technical_score),
            (SignalCategory.FUNDAMENTAL, fundamental_score),
            (SignalCategory.NEWS,        news_score),
            (SignalCategory.RISK,        risk_score),
        ]
        if cat in active_categories
    }

    if category in {RatingCategory.AVOID, RatingCategory.SELL_EXIT_WARNING}:
        strong = [
            _CATEGORY_LABELS[cat]
            for cat, sc in active_scores.items()
            if sc >= 55.0
        ]
        if strong:
            holding_up = " and ".join(strong)
            return (
                f"Conditions are weak. {holding_up.capitalize()} signals "
                "are holding up but overall analysis does not support entry."
            )
        return (
            "Conditions are broadly weak across all signal categories. "
            "Avoid until a clear recovery pattern emerges."
        )

    weak = _weak_category_labels(active_scores, 55.0)
    if weak:
        dragging = " and ".join(weak)
        return (
            f"Reassess if {dragging} conditions deteriorate further "
            "or the composite score falls below 45."
        )
    return (
        "Reassess if the composite score falls below 45 or "
        "bearish signals accumulate across multiple categories."
    )
