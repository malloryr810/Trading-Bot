"""
Universe models.

A *universe* is a controlled, static list of tickers the discovery engine is
allowed to consider. These models describe one entry in a universe file and the
metadata of a registered universe. They carry no analysis, scoring, or market
data — only identity and classification fields loaded from the repository.
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator


class UniverseEntry(BaseModel):
    """One ticker in a stock universe, as loaded from a universe CSV file."""

    ticker: str
    company_name: str | None = None
    sector: str | None = None
    industry: str | None = None

    @field_validator("ticker")
    @classmethod
    def ticker_normalized(cls, v: str) -> str:
        normalized = v.strip().upper()
        if not normalized:
            raise ValueError("ticker must not be empty or whitespace.")
        return normalized

    @field_validator("company_name", "sector", "industry")
    @classmethod
    def blank_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped or None


class UniverseInfo(BaseModel):
    """Metadata describing a registered universe (no ticker rows)."""

    key: str
    name: str
    description: str
    size: int
