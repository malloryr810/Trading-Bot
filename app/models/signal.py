"""
Signal model.

Represents a single analytical signal produced by any analysis module
(technical, fundamental, news, or risk). All analysis modules produce Signal
objects that the scoring engine consumes — this is the shared typed contract
across the analysis layer.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class SignalCategory(str, Enum):
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    NEWS = "news"
    RISK = "risk"


class SignalDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class SignalStrength(str, Enum):
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class Signal(BaseModel):
    """A typed analytical signal produced by an analysis module."""

    name: str
    category: SignalCategory
    direction: SignalDirection
    strength: SignalStrength
    description: str

    value: float | int | str | bool | None = None
    score_impact: float = Field(default=0.0, ge=-1.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    source: str | None = None
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be empty or whitespace.")
        return v

    @field_validator("description")
    @classmethod
    def description_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("description must not be empty or whitespace.")
        return v

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def is_bullish(self) -> bool:
        return self.direction == SignalDirection.BULLISH

    @property
    def is_bearish(self) -> bool:
        return self.direction == SignalDirection.BEARISH

    @property
    def is_neutral(self) -> bool:
        return self.direction == SignalDirection.NEUTRAL
