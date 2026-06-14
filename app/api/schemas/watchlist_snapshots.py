"""
Response schemas for saved watchlist analysis snapshot endpoints.

A snapshot is a historical record of an explicitly user-triggered on-demand
watchlist analysis run. These models describe the HTTP response contract; the
service owns all persistence logic. The per-ticker result/error shapes are
reused from the live analysis schemas so the frontend can render a saved run
the same way it renders a fresh one.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.api.schemas.watchlists import (
    WatchlistAnalysisError,
    WatchlistAnalysisResult,
)


class WatchlistSnapshotSummary(BaseModel):
    """One saved snapshot, without its per-ticker rows (list endpoint)."""

    id: int
    watchlist_id: int
    watchlist_name: str
    analyzed_at: datetime
    total_tickers: int
    success_count: int
    failure_count: int
    created_at: datetime


class WatchlistSnapshotDetail(WatchlistSnapshotSummary):
    """A saved snapshot with its successful results and failed-ticker errors."""

    results: list[WatchlistAnalysisResult]
    errors: list[WatchlistAnalysisError]
