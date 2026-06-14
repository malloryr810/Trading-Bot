"""
Saved watchlist analysis snapshot service.

Persists historical records of explicitly user-triggered on-demand watchlist
analysis runs, and reads them back. All database I/O uses SQLAlchemy Core; no
ORM is used. This layer adds no analysis or scoring logic — it saves an
already-produced analysis result (from ``watchlist_analysis_service``).

**Not a scheduled scan.** Snapshots are only written when the user invokes the
analyze-and-save flow. Nothing here runs on a timer or in the background.

Public functions::

    analyze_and_save_snapshot(watchlist_id, *, engine=None)
        — run the on-demand analysis once and persist the result (one explicit
          user action). Returns the saved snapshot detail.
    save_watchlist_analysis_snapshot(analysis, *, engine=None)
        — persist an already-produced analysis-result dict. Returns the detail.
    list_watchlist_snapshots(watchlist_id, *, engine=None)
        — list saved snapshot summaries for a watchlist, newest first.
    get_watchlist_snapshot(snapshot_id, *, engine=None)
        — return one snapshot's full detail (results + errors), or None.

Errors (reused from watchlist_service so the API maps them consistently):
    WatchlistNotFoundError — the watchlist id does not exist (HTTP 404).
    WatchlistValidationError — the watchlist exists but has no tickers (HTTP 400).
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.engine import Engine

from app.data.database import (
    build_engine,
    watchlist_analysis_snapshot_results,
    watchlist_analysis_snapshots,
)
from app.services.watchlist_analysis_service import analyze_watchlist
from app.services.watchlist_service import get_watchlist

_engine: Engine | None = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine


def _as_utc(value: datetime) -> datetime:
    """Return a timezone-aware UTC datetime (SQLite stores naive datetimes)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def analyze_and_save_snapshot(
    watchlist_id: int,
    *,
    engine: Engine | None = None,
) -> dict:
    """Run the on-demand analysis once and persist it as a snapshot.

    This is the single explicit "analyze & save" user action. It is distinct
    from the analyze-only flow, which never writes to the database.

    Raises:
        WatchlistNotFoundError: If the watchlist id does not exist.
        WatchlistValidationError: If the watchlist has no tickers to analyze.
    """
    _e = engine or _get_engine()
    analysis = analyze_watchlist(watchlist_id, engine=_e)
    return save_watchlist_analysis_snapshot(analysis, engine=_e)


def save_watchlist_analysis_snapshot(
    analysis: dict,
    *,
    engine: Engine | None = None,
) -> dict:
    """Persist an already-produced analysis-result dict as a snapshot.

    Args:
        analysis: The dict returned by ``analyze_watchlist`` — both successful
            results and failed-ticker errors are saved.
        engine: Optional engine for dependency injection in tests.

    Returns:
        The saved snapshot detail dict (see ``get_watchlist_snapshot``).

    Raises:
        WatchlistNotFoundError: If the referenced watchlist no longer exists.
    """
    _e = engine or _get_engine()
    watchlist_id = analysis["watchlist_id"]

    # Validate the referenced watchlist still exists before persisting.
    get_watchlist(watchlist_id, engine=_e)

    now = datetime.now(tz=timezone.utc)

    with _e.begin() as conn:
        snapshot_id = conn.execute(
            insert(watchlist_analysis_snapshots).values(
                watchlist_id=watchlist_id,
                watchlist_name=analysis["watchlist_name"],
                analyzed_at=analysis["analyzed_at"],
                total_tickers=analysis["total_tickers"],
                success_count=analysis["successful_count"],
                failure_count=analysis["failed_count"],
                created_at=now,
            )
        ).lastrowid

        for item in analysis["results"]:
            conn.execute(
                insert(watchlist_analysis_snapshot_results).values(
                    snapshot_id=snapshot_id,
                    ticker=item["ticker"],
                    status="success",
                    company_name=item.get("company_name"),
                    category=item.get("category"),
                    score=item.get("score"),
                    confidence=item.get("confidence"),
                    current_price=item.get("current_price"),
                    summary_json=json.dumps(item),
                    error_message=None,
                )
            )

        for err in analysis["errors"]:
            conn.execute(
                insert(watchlist_analysis_snapshot_results).values(
                    snapshot_id=snapshot_id,
                    ticker=err["ticker"],
                    status="failure",
                    summary_json=None,
                    error_message=err["error"],
                )
            )

        return _detail_for(conn, snapshot_id)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def list_watchlist_snapshots(
    watchlist_id: int,
    *,
    engine: Engine | None = None,
) -> list[dict]:
    """Return saved snapshot summaries for a watchlist, newest first.

    Raises:
        WatchlistNotFoundError: If the watchlist id does not exist.
    """
    _e = engine or _get_engine()
    # 404 if the watchlist itself is gone.
    get_watchlist(watchlist_id, engine=_e)

    stmt = (
        select(watchlist_analysis_snapshots)
        .where(watchlist_analysis_snapshots.c.watchlist_id == watchlist_id)
        .order_by(watchlist_analysis_snapshots.c.id.desc())
    )
    # One extra query collects the successful-result scores for every snapshot
    # in this watchlist so we can compute average_score without an N+1 loop.
    score_stmt = (
        select(
            watchlist_analysis_snapshot_results.c.snapshot_id,
            watchlist_analysis_snapshot_results.c.score,
        )
        .select_from(
            watchlist_analysis_snapshot_results.join(
                watchlist_analysis_snapshots,
                watchlist_analysis_snapshot_results.c.snapshot_id
                == watchlist_analysis_snapshots.c.id,
            )
        )
        .where(
            watchlist_analysis_snapshots.c.watchlist_id == watchlist_id,
            watchlist_analysis_snapshot_results.c.status == "success",
        )
    )
    with _e.connect() as conn:
        rows = conn.execute(stmt).all()
        score_rows = conn.execute(score_stmt).all()

    scores_by_snapshot: dict[int, list[float]] = {}
    for score_row in score_rows:
        scores_by_snapshot.setdefault(score_row.snapshot_id, []).append(
            score_row.score
        )

    return [
        _summary_from_row(
            row, average_score=_mean_score(scores_by_snapshot.get(row.id, []))
        )
        for row in rows
    ]


def get_watchlist_snapshot(
    snapshot_id: int,
    *,
    engine: Engine | None = None,
) -> dict | None:
    """Return one snapshot's full detail, or None if the id does not exist."""
    _e = engine or _get_engine()
    with _e.connect() as conn:
        return _detail_for(conn, snapshot_id)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _mean_score(scores: list[Any]) -> float | None:
    """Average of present numeric scores, rounded to 2 decimals.

    Failed-ticker rows carry no score and are passed in as ``None``; they are
    ignored here. Returns ``None`` when there are no successful scored rows so
    the response distinguishes "no data" from a real zero average.
    """
    valid = [
        float(s)
        for s in scores
        if isinstance(s, (int, float))
        and not isinstance(s, bool)
        and math.isfinite(s)
    ]
    if not valid:
        return None
    return round(sum(valid) / len(valid), 2)


def _summary_from_row(row: Any, *, average_score: float | None = None) -> dict:
    return {
        "id": row.id,
        "watchlist_id": row.watchlist_id,
        "watchlist_name": row.watchlist_name,
        "analyzed_at": _as_utc(row.analyzed_at),
        "total_tickers": row.total_tickers,
        "success_count": row.success_count,
        "failure_count": row.failure_count,
        "average_score": average_score,
        "created_at": _as_utc(row.created_at),
    }


def _detail_for(conn: Any, snapshot_id: int) -> dict | None:
    """Build the full snapshot detail dict, or None if the id is missing."""
    head = conn.execute(
        select(watchlist_analysis_snapshots).where(
            watchlist_analysis_snapshots.c.id == snapshot_id
        )
    ).one_or_none()
    if head is None:
        return None

    rows = conn.execute(
        select(watchlist_analysis_snapshot_results)
        .where(watchlist_analysis_snapshot_results.c.snapshot_id == snapshot_id)
        .order_by(watchlist_analysis_snapshot_results.c.id.asc())
    ).all()

    results: list[dict] = []
    errors: list[dict] = []
    success_scores: list[Any] = []
    for row in rows:
        if row.status == "success" and row.summary_json:
            results.append(json.loads(row.summary_json))
            success_scores.append(row.score)
        else:
            errors.append({"ticker": row.ticker, "error": row.error_message or ""})

    detail = _summary_from_row(head, average_score=_mean_score(success_scores))
    detail["results"] = results
    detail["errors"] = errors
    return detail
