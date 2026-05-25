"""
News item model.

Defines the typed output of the news data layer. A NewsItem holds a single
headline or article returned by a news provider (e.g. yfinance). Sentiment
fields are intentionally absent — the news analysis layer adds those later.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class NewsItem(BaseModel):
    """A single news headline or article for a ticker."""

    title: str
    publisher: str | None = None
    link: str | None = None
    published_at: datetime | None = None
    summary: str | None = None
    related_tickers: list[str] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("title must not be empty or whitespace.")
        return stripped
