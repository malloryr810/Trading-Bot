"""
Saved watchlist analysis snapshot routes.

  POST /api/watchlists/{watchlist_id}/analysis-snapshots
      — run an on-demand analysis once and save the result (explicit user action)
  GET  /api/watchlists/{watchlist_id}/analysis-snapshots
      — list saved snapshots for a watchlist (newest first)
  GET  /api/watchlist-analysis-snapshots/{snapshot_id}
      — get one snapshot's full detail (results + errors)

All routes delegate to watchlist_analysis_snapshot_service; no persistence or
analysis logic lives here. This is distinct from the analyze-only endpoint
(`POST /api/watchlists/{id}/analyze`), which never saves. No scheduled scans.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas.watchlist_snapshots import (
    WatchlistSnapshotDetail,
    WatchlistSnapshotSummary,
)
from app.services.watchlist_analysis_snapshot_service import (
    analyze_and_save_snapshot,
    get_watchlist_snapshot,
    list_watchlist_snapshots,
)
from app.services.watchlist_service import (
    WatchlistNotFoundError,
    WatchlistValidationError,
)

router = APIRouter(tags=["watchlist-snapshots"])


@router.post(
    "/watchlists/{watchlist_id}/analysis-snapshots",
    response_model=WatchlistSnapshotDetail,
    status_code=201,
)
async def post_analysis_snapshot(watchlist_id: int) -> dict:
    """Analyze every ticker once and save the run as a snapshot.

    Explicit save action. Per-ticker failures are recorded in the snapshot;
    the request fails only when the watchlist is missing (404) or empty (400).
    """
    try:
        return analyze_and_save_snapshot(watchlist_id)
    except (WatchlistNotFoundError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (WatchlistValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/watchlists/{watchlist_id}/analysis-snapshots",
    response_model=list[WatchlistSnapshotSummary],
)
async def get_analysis_snapshots(watchlist_id: int) -> list[dict]:
    """List saved snapshots for a watchlist, newest first."""
    try:
        return list_watchlist_snapshots(watchlist_id)
    except (WatchlistNotFoundError, LookupError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/watchlist-analysis-snapshots/{snapshot_id}",
    response_model=WatchlistSnapshotDetail,
)
async def get_analysis_snapshot(snapshot_id: int) -> dict:
    """Return one snapshot's full detail by id."""
    detail = get_watchlist_snapshot(snapshot_id)
    if detail is None:
        raise HTTPException(
            status_code=404, detail=f"Snapshot {snapshot_id} not found"
        )
    return detail
