"""
Rating model.

Defines the typed output produced by the future scoring engine. A Rating
aggregates numeric sub-scores, a final category, confidence, explanations,
and the Signal objects that informed it — giving consumers a complete,
inspectable record of how a recommendation was reached.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.signal import Signal


class RatingCategory(str, Enum):
    STRONG_BUY_CANDIDATE = "Strong Buy Candidate"
    BUY_CANDIDATE = "Buy Candidate"
    WATCHLIST = "Watchlist"
    HOLD = "Hold"
    AVOID = "Avoid"
    SELL_EXIT_WARNING = "Sell / Exit Warning"


class ConfidenceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


_POSITIVE_CATEGORIES = {RatingCategory.STRONG_BUY_CANDIDATE, RatingCategory.BUY_CANDIDATE}
_NEGATIVE_CATEGORIES = {RatingCategory.AVOID, RatingCategory.SELL_EXIT_WARNING}
_NEUTRAL_CATEGORIES = {RatingCategory.WATCHLIST, RatingCategory.HOLD}


class Rating(BaseModel):
    """Typed output of the scoring engine for a single ticker."""

    # Core result
    ticker: str
    final_category: RatingCategory
    score: float = Field(..., ge=0.0, le=100.0)
    confidence: ConfidenceLevel
    explanation: str

    # Sub-scores (each 0–100)
    technical_score: float = Field(default=0.0, ge=0.0, le=100.0)
    fundamental_score: float = Field(default=0.0, ge=0.0, le=100.0)
    news_score: float = Field(default=0.0, ge=0.0, le=100.0)
    risk_score: float = Field(default=0.0, ge=0.0, le=100.0)

    # Per-category narrative summaries
    technical_summary: str | None = None
    fundamental_summary: str | None = None
    news_summary: str | None = None
    risk_summary: str | None = None

    # Human-readable explanation fields
    key_positive_factors: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    buy_trigger: str | None = None
    sell_or_avoid_trigger: str | None = None

    # Provenance / metadata
    data_timestamp: datetime | None = None
    data_sources_used: list[str] = Field(default_factory=list)
    signals_used: list[Signal] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

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

    @field_validator("explanation")
    @classmethod
    def explanation_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("explanation must not be empty or whitespace.")
        return v

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def is_positive_rating(self) -> bool:
        return self.final_category in _POSITIVE_CATEGORIES

    @property
    def is_negative_rating(self) -> bool:
        return self.final_category in _NEGATIVE_CATEGORIES

    @property
    def is_neutral_rating(self) -> bool:
        return self.final_category in _NEUTRAL_CATEGORIES
