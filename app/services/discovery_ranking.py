"""
Discovery ranking strategies.

Pure, deterministic ordering over ``Rating`` objects that the existing scoring
engine already produced. Each mode is a sort key plus a plain-text explanation
of why a candidate surfaced.

This module **does not score**. It never recomputes a score, sub-score,
category, or confidence level — it only reads the values on the Rating and
decides an order. Ties are always broken by ticker so runs are reproducible.

Sub-score semantics come from ``app/analysis/scoring.py``: every sub-score is
0–100 and higher is better, including ``risk_score`` (a high risk score means
*favorable* risk signals — low volatility, mild drawdown — not high danger).
"""

from __future__ import annotations

from app.models.discovery import DiscoveryMode, DiscoveryModeInfo
from app.models.rating import ConfidenceLevel, Rating
from app.models.signal import Signal, SignalCategory

# Name of the fundamental signal that carries valuation evidence. Produced by
# app/analysis/fundamentals_analysis.py; used by the `value` mode only.
VALUATION_SIGNAL_NAME = "Valuation"

_CONFIDENCE_RANK: dict[ConfidenceLevel, int] = {
    ConfidenceLevel.HIGH: 2,
    ConfidenceLevel.MEDIUM: 1,
    ConfidenceLevel.LOW: 0,
}

_MODE_INFO: dict[DiscoveryMode, tuple[str, str, str]] = {
    DiscoveryMode.OVERALL: (
        "Overall",
        "Best general research candidates across all four signal categories.",
        "Highest composite score first, then confidence.",
    ),
    DiscoveryMode.MOMENTUM: (
        "Momentum",
        "Names whose technical setup and trend evidence are strongest right now.",
        "Highest technical sub-score first, then composite score.",
    ),
    DiscoveryMode.QUALITY: (
        "Quality",
        "Names with the stronger fundamental profile (profitability, growth, "
        "debt, cash flow).",
        "Highest fundamental sub-score first, then composite score.",
    ),
    DiscoveryMode.VALUE: (
        "Value",
        "Names whose valuation signal is favorable, backed by the wider "
        "fundamental profile.",
        "Most favorable valuation signal first, then fundamental sub-score, "
        "then composite score.",
    ),
    DiscoveryMode.DEFENSIVE: (
        "Defensive",
        "Lower-risk, steadier names — favorable volatility, drawdown, and "
        "liquidity signals.",
        "Highest risk sub-score (most favorable risk signals) first, then "
        "confidence, then composite score.",
    ),
    DiscoveryMode.AVOID: (
        "Avoid / caution",
        "Weakest names in the screened shortlist, surfaced as warnings rather "
        "than as opportunities.",
        "Negative-rated names first, then lowest composite score, then least "
        "favorable risk signals.",
    ),
}


def list_mode_info() -> list[DiscoveryModeInfo]:
    """Return descriptions of every supported discovery mode, in enum order."""
    return [
        DiscoveryModeInfo(
            key=mode,
            label=_MODE_INFO[mode][0],
            description=_MODE_INFO[mode][1],
            ranking=_MODE_INFO[mode][2],
        )
        for mode in DiscoveryMode
    ]


def rank_ratings(mode: DiscoveryMode, ratings: list[Rating]) -> list[Rating]:
    """Order fully analyzed ratings according to a discovery mode.

    Args:
        mode: The discovery mode whose sort key should be applied.
        ratings: Ratings produced by the existing analysis pipeline.

    Returns:
        A new list ordered best-match-first for the mode. The input list is
        never mutated.
    """
    return sorted(ratings, key=lambda rating: _sort_key(mode, rating))


def match_reason(mode: DiscoveryMode, rating: Rating) -> str:
    """Explain, in plain text, why a candidate surfaced for this mode.

    Uses only values already present on the Rating — no new judgements are
    introduced and no data is invented.
    """
    if mode is DiscoveryMode.OVERALL:
        return (
            f"Composite score {rating.score:.1f}/100 with {rating.confidence.value} "
            f"confidence — rated {rating.final_category.value} by the scoring engine."
        )
    if mode is DiscoveryMode.MOMENTUM:
        return (
            f"Technical sub-score {rating.technical_score:.1f}/100 "
            f"(composite {rating.score:.1f}) — ranked on trend and momentum "
            "evidence within the screened shortlist."
        )
    if mode is DiscoveryMode.QUALITY:
        return (
            f"Fundamental sub-score {rating.fundamental_score:.1f}/100 "
            f"(composite {rating.score:.1f}) — ranked on the strength of the "
            "fundamental profile within the screened shortlist."
        )
    if mode is DiscoveryMode.VALUE:
        return _value_reason(rating)
    if mode is DiscoveryMode.DEFENSIVE:
        return (
            f"Risk sub-score {rating.risk_score:.1f}/100 (higher is calmer) with "
            f"{rating.confidence.value} confidence — ranked on favorable risk "
            f"signals within the screened shortlist (composite {rating.score:.1f})."
        )
    return (
        f"Composite score {rating.score:.1f}/100, rated "
        f"{rating.final_category.value} with risk sub-score "
        f"{rating.risk_score:.1f}/100 — surfaced as a caution, not an opportunity."
    )


def valuation_lean(rating: Rating) -> float:
    """Return the valuation signal's score impact (-1.0…1.0), or 0.0 if absent.

    Reads the existing fundamental "Valuation" signal. When fundamentals are
    unavailable the analysis layer emits a neutral signal (impact 0.0), so a
    missing or no-data valuation ranks between favorable and unfavorable rather
    than being treated as either.
    """
    signal = _valuation_signal(rating)
    return signal.score_impact if signal is not None else 0.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sort_key(mode: DiscoveryMode, rating: Rating) -> tuple:
    """Build the deterministic sort key for a mode (ascending sort)."""
    confidence = _CONFIDENCE_RANK[rating.confidence]

    if mode is DiscoveryMode.MOMENTUM:
        return (-rating.technical_score, -rating.score, rating.ticker)
    if mode is DiscoveryMode.QUALITY:
        return (-rating.fundamental_score, -rating.score, rating.ticker)
    if mode is DiscoveryMode.VALUE:
        return (
            -valuation_lean(rating),
            -rating.fundamental_score,
            -rating.score,
            rating.ticker,
        )
    if mode is DiscoveryMode.DEFENSIVE:
        return (-rating.risk_score, -confidence, -rating.score, rating.ticker)
    if mode is DiscoveryMode.AVOID:
        return (
            0 if rating.is_negative_rating else 1,
            rating.score,
            rating.risk_score,
            rating.ticker,
        )
    return (-rating.score, -confidence, rating.ticker)


def _valuation_signal(rating: Rating) -> Signal | None:
    """Return the fundamental Valuation signal, or None when it is absent."""
    for signal in rating.signals_used:
        if (
            signal.category == SignalCategory.FUNDAMENTAL
            and signal.name == VALUATION_SIGNAL_NAME
        ):
            return signal
    return None


def _value_reason(rating: Rating) -> str:
    """Build the value-mode explanation, quoting the valuation signal if present."""
    signal = _valuation_signal(rating)
    base = (
        f"Fundamental sub-score {rating.fundamental_score:.1f}/100 "
        f"(composite {rating.score:.1f})."
    )
    if signal is None:
        return f"No valuation signal was available; ranked on fundamentals. {base}"
    return f"Valuation signal: {signal.description} {base}"
