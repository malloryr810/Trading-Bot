"""
Discovery models.

Typed output of the stock discovery engine: a ranked, explainable list of
candidate tickers drawn from a controlled universe.

Discovery adds **no scoring of its own**. Every score, sub-score, category,
confidence level, summary, factor list, and trigger on a ``DiscoveryCandidate``
is copied verbatim from the ``Rating`` produced by ``app/analysis/scoring.py``.
The only thing discovery contributes is *ordering* (``rank``) and a plain-text
``match_reason`` explaining why a candidate surfaced for the requested mode.

These are research candidates, not financial advice.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.models.rating import ConfidenceLevel, RatingCategory


class DiscoveryMode(str, Enum):
    """Deterministic ranking strategies applied to fully analyzed candidates."""

    OVERALL = "overall"
    MOMENTUM = "momentum"
    QUALITY = "quality"
    VALUE = "value"
    DEFENSIVE = "defensive"
    AVOID = "avoid"


class DiscoveryModeInfo(BaseModel):
    """Human-readable description of one discovery mode."""

    key: DiscoveryMode
    label: str
    description: str
    ranking: str


class DiscoveryCandidate(BaseModel):
    """One ranked discovery result.

    All rating fields mirror the existing analysis pipeline output. ``rank`` and
    ``match_reason`` are the only discovery-owned fields.
    """

    # Identity (ticker/company from the pipeline; sector/industry from the universe file)
    ticker: str
    company_name: str | None = None
    sector: str | None = None
    industry: str | None = None

    # Discovery-owned
    mode: DiscoveryMode
    rank: int = Field(..., ge=1)
    match_reason: str

    # Existing rating output — copied, never recomputed
    final_category: RatingCategory
    score: float = Field(..., ge=0.0, le=100.0)
    confidence_level: ConfidenceLevel
    current_price: float | None = None

    technical_score: float = Field(default=0.0, ge=0.0, le=100.0)
    fundamental_score: float = Field(default=0.0, ge=0.0, le=100.0)
    news_score: float = Field(default=0.0, ge=0.0, le=100.0)
    risk_score: float = Field(default=0.0, ge=0.0, le=100.0)

    technical_summary: str | None = None
    fundamental_summary: str | None = None
    news_summary: str | None = None
    risk_summary: str | None = None

    key_positive_factors: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    buy_trigger: str | None = None
    sell_or_avoid_trigger: str | None = None

    # Provenance
    data_timestamp: datetime | None = None
    data_sources_used: list[str] = Field(default_factory=list)

    @field_validator("ticker")
    @classmethod
    def ticker_normalized(cls, v: str) -> str:
        normalized = v.strip().upper()
        if not normalized:
            raise ValueError("ticker must not be empty or whitespace.")
        return normalized


class DiscoveryStage(str, Enum):
    """Pipeline stage a per-ticker failure occurred in."""

    PRESCREEN = "prescreen"
    ANALYSIS = "analysis"


class DiscoveryWarning(BaseModel):
    """One ticker that was skipped or failed; failures never abort a run."""

    ticker: str
    stage: DiscoveryStage
    message: str


class DiscoveryRun(BaseModel):
    """Full result of one bounded discovery run."""

    mode: DiscoveryMode
    universe: str
    universe_name: str

    # Requested bounds (echoed back so the caller can see what actually applied)
    limit: int = Field(..., ge=1)
    max_full_analysis: int = Field(..., ge=1)

    # Run accounting
    universe_size: int = Field(..., ge=0)
    prescreened_count: int = Field(default=0, ge=0)
    shortlist_count: int = Field(default=0, ge=0)
    analyzed_count: int = Field(default=0, ge=0)

    results: list[DiscoveryCandidate] = Field(default_factory=list)
    warnings: list[DiscoveryWarning] = Field(default_factory=list)

    started_at: datetime
    completed_at: datetime
    data_sources_used: list[str] = Field(default_factory=list)
