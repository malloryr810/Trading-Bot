"""
Request schemas for the analysis API routes.
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator


class AnalyzeRequest(BaseModel):
    """Request body for POST /api/analyze."""

    ticker: str

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        normalized = v.strip().upper()
        if not normalized:
            raise ValueError("ticker must not be empty or whitespace")
        return normalized
