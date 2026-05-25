"""
StockReport model.

The top-level output of a full analysis run for a single ticker.
Aggregates signals, scores, ratings, and metadata into one structured
object that report_generator renders into a final report.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.rating import ConfidenceLevel, RatingCategory
from app.models.signal import Signal


class StockReport(BaseModel):
    """Top-level structured output of a single-ticker analysis run."""

    # Identity
    ticker: str
    company_name: str | None = None
    current_price: float | None = None

    # Recommendation
    final_category: RatingCategory
    score: float = Field(..., ge=0.0, le=100.0)
    confidence_level: ConfidenceLevel

    # Narrative summaries (one per analysis category)
    technical_summary: str | None = None
    fundamental_summary: str | None = None
    news_summary: str | None = None
    risk_summary: str | None = None

    # Human-readable factors and action triggers
    key_positive_factors: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    buy_trigger: str | None = None
    sell_or_avoid_trigger: str | None = None

    # Provenance
    data_timestamp: datetime | None = None
    data_sources_used: list[str] = Field(default_factory=list)

    # Signals split by category
    technical_signals: list[Signal] = Field(default_factory=list)
    fundamental_signals: list[Signal] = Field(default_factory=list)
    news_signals: list[Signal] = Field(default_factory=list)
    risk_signals: list[Signal] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("ticker")
    @classmethod
    def ticker_normalized(cls, v: str) -> str:
        normalized = v.strip().upper()
        if not normalized:
            raise ValueError("ticker must not be empty or whitespace.")
        return normalized
