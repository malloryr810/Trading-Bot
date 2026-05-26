"""
ConfidenceDiagnostics model.

Captures the per-signal confidence inputs that feed into the final
ConfidenceLevel label so they can be inspected without re-running analysis.
This is a diagnostic aid only — it does not affect scores, categories, or labels.
"""

from __future__ import annotations

from pydantic import BaseModel


class ConfidenceDiagnostics(BaseModel):
    """Read-only breakdown of the confidence inputs for a single scoring run."""

    signal_count: int = 0
    average_signal_confidence: float | None = None
    min_signal_confidence: float | None = None
    max_signal_confidence: float | None = None

    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0

    # Signals with confidence <= 0.30 are the missing-data fallback case:
    # all four analysis modules assign exactly 0.30 when a data field is None.
    missing_count: int = 0

    technical_average_confidence: float | None = None
    fundamental_average_confidence: float | None = None
    news_average_confidence: float | None = None
    risk_average_confidence: float | None = None
