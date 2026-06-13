"""
Watchlist persistence service.

Public boundary for managing named lists of tickers in SQLite.  All database
I/O uses SQLAlchemy Core; no ORM is used.  This layer is storage only — it does
not run analysis, scoring, or any trading logic.  See
docs/watchlist_management_plan.md.

Public functions::

    create_watchlist(name, description=None)        — create a list, return its detail.
    list_watchlists()                               — return all list summaries.
    get_watchlist(watchlist_id)                     — return one list with its tickers.
    update_watchlist(watchlist_id, name, description) — rename / edit metadata.
    delete_watchlist(watchlist_id)                  — delete a list and its tickers.
    add_ticker_to_watchlist(watchlist_id, ticker)   — add a ticker (idempotent).
    remove_ticker_from_watchlist(watchlist_id, ticker) — remove a ticker (idempotent).

Each function accepts an optional keyword-only ``engine`` parameter for
dependency injection in tests.  Production callers omit it; a shared engine is
lazily initialised on the first call.

Errors:
    WatchlistValidationError — invalid input (blank name, blank ticker).
    WatchlistNotFoundError   — the requested watchlist id does not exist.
Both subclass the matching builtin (``ValueError`` / ``LookupError``) so callers
may catch either the specific class or the broad builtin.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Engine

from app.data.database import build_engine, watchlist_tickers, watchlists
from app.utils.helpers import normalize_ticker

_engine: Engine | None = None


class WatchlistError(Exception):
    """Base class for watchlist service errors."""


class WatchlistValidationError(WatchlistError, ValueError):
    """Raised when watchlist input fails validation."""


class WatchlistNotFoundError(WatchlistError, LookupError):
    """Raised when a watchlist id does not exist."""


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine


def _as_utc(value: datetime) -> datetime:
    """Return a timezone-aware UTC datetime.

    SQLite stores naive datetimes; this re-attaches UTC so every returned
    datetime is consistent regardless of code path.  Mirrors the helper in
    report_persistence_service.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _clean_name(name: object) -> str:
    """Validate and strip a watchlist name."""
    if not isinstance(name, str):
        raise WatchlistValidationError(
            f"Watchlist name must be a string, got {type(name).__name__}."
        )
    stripped = name.strip()
    if not stripped:
        raise WatchlistValidationError("Watchlist name must not be empty or whitespace.")
    return stripped


def _clean_description(description: object) -> str | None:
    """Normalize a description; blank/None collapses to None."""
    if description is None:
        return None
    if not isinstance(description, str):
        raise WatchlistValidationError(
            f"Description must be a string or None, got {type(description).__name__}."
        )
    stripped = description.strip()
    return stripped or None


def _clean_ticker(ticker: object) -> str:
    """Validate and normalize a ticker to uppercase, stripped.

    Reuses ``normalize_ticker`` so behavior matches the rest of the pipeline,
    but re-raises as a WatchlistValidationError for a consistent service API.
    """
    try:
        return normalize_ticker(ticker)
    except ValueError as exc:
        raise WatchlistValidationError(str(exc)) from exc


def _tickers_for(conn: Any, watchlist_id: int) -> list[str]:
    """Return the ordered ticker symbols for a watchlist on an open connection."""
    stmt = (
        select(watchlist_tickers.c.ticker)
        .where(watchlist_tickers.c.watchlist_id == watchlist_id)
        .order_by(watchlist_tickers.c.id.asc())
    )
    return [row.ticker for row in conn.execute(stmt).all()]


def _detail_for(conn: Any, watchlist_id: int) -> dict | None:
    """Build the full watchlist detail dict, or None if the id is missing."""
    row = conn.execute(
        select(watchlists).where(watchlists.c.id == watchlist_id)
    ).one_or_none()
    if row is None:
        return None
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "created_at": _as_utc(row.created_at),
        "updated_at": _as_utc(row.updated_at),
        "tickers": _tickers_for(conn, watchlist_id),
    }


def _require_exists(conn: Any, watchlist_id: int) -> None:
    """Raise WatchlistNotFoundError if the watchlist does not exist."""
    exists = conn.execute(
        select(watchlists.c.id).where(watchlists.c.id == watchlist_id)
    ).one_or_none()
    if exists is None:
        raise WatchlistNotFoundError(f"Watchlist {watchlist_id} not found.")


def create_watchlist(
    name: str,
    description: str | None = None,
    *,
    engine: Engine | None = None,
) -> dict:
    """Create a new watchlist and return its detail.

    Args:
        name: Human-readable list name (required, stripped).
        description: Optional description; blank collapses to None.
        engine: Optional engine for dependency injection in tests.

    Returns:
        Watchlist detail dict with id, name, description, created_at,
        updated_at, and an empty ``tickers`` list.

    Raises:
        WatchlistValidationError: If the name is blank.
    """
    _e = engine or _get_engine()
    clean_name = _clean_name(name)
    clean_description = _clean_description(description)
    now = datetime.now(tz=timezone.utc)

    stmt = insert(watchlists).values(
        name=clean_name,
        description=clean_description,
        created_at=now,
        updated_at=now,
    )
    with _e.begin() as conn:
        new_id = conn.execute(stmt).lastrowid
        return _detail_for(conn, new_id)


def list_watchlists(*, engine: Engine | None = None) -> list[dict]:
    """Return all watchlists, newest first, each with its ticker count.

    Args:
        engine: Optional engine for dependency injection in tests.

    Returns:
        List of summary dicts — id, name, description, created_at, updated_at,
        ticker_count.  The full ticker list is not included here.
    """
    _e = engine or _get_engine()
    stmt = select(watchlists).order_by(watchlists.c.id.desc())
    with _e.connect() as conn:
        rows = conn.execute(stmt).all()
        return [
            {
                "id": row.id,
                "name": row.name,
                "description": row.description,
                "created_at": _as_utc(row.created_at),
                "updated_at": _as_utc(row.updated_at),
                "ticker_count": len(_tickers_for(conn, row.id)),
            }
            for row in rows
        ]


def get_watchlist(watchlist_id: int, *, engine: Engine | None = None) -> dict:
    """Return one watchlist with its tickers.

    Args:
        watchlist_id: Integer primary key of the watchlist.
        engine: Optional engine for dependency injection in tests.

    Returns:
        Watchlist detail dict including the ordered ``tickers`` list.

    Raises:
        WatchlistNotFoundError: If the id does not exist.
    """
    _e = engine or _get_engine()
    with _e.connect() as conn:
        detail = _detail_for(conn, watchlist_id)
    if detail is None:
        raise WatchlistNotFoundError(f"Watchlist {watchlist_id} not found.")
    return detail


def update_watchlist(
    watchlist_id: int,
    name: str | None = None,
    description: str | None = None,
    *,
    engine: Engine | None = None,
) -> dict:
    """Update a watchlist's metadata (partial update) and return its detail.

    Only provided fields change.  ``name=None`` leaves the name untouched;
    ``description=None`` also leaves it untouched (pass an empty string to
    clear a description).

    Args:
        watchlist_id: Integer primary key of the watchlist.
        name: New name, if provided (must not be blank).
        description: New description, if provided (blank collapses to None).
        engine: Optional engine for dependency injection in tests.

    Returns:
        The updated watchlist detail dict.

    Raises:
        WatchlistNotFoundError: If the id does not exist.
        WatchlistValidationError: If ``name`` is provided but blank.
    """
    _e = engine or _get_engine()

    values: dict[str, Any] = {}
    if name is not None:
        values["name"] = _clean_name(name)
    if description is not None:
        values["description"] = _clean_description(description)

    with _e.begin() as conn:
        _require_exists(conn, watchlist_id)
        if values:
            values["updated_at"] = datetime.now(tz=timezone.utc)
            conn.execute(
                update(watchlists)
                .where(watchlists.c.id == watchlist_id)
                .values(**values)
            )
        return _detail_for(conn, watchlist_id)


def delete_watchlist(watchlist_id: int, *, engine: Engine | None = None) -> None:
    """Delete a watchlist and all of its ticker rows.

    Ticker rows are deleted explicitly rather than relying on SQLite cascade
    behavior, which is off by default in this project.

    Args:
        watchlist_id: Integer primary key of the watchlist.
        engine: Optional engine for dependency injection in tests.

    Raises:
        WatchlistNotFoundError: If the id does not exist.
    """
    _e = engine or _get_engine()
    with _e.begin() as conn:
        _require_exists(conn, watchlist_id)
        conn.execute(
            delete(watchlist_tickers).where(
                watchlist_tickers.c.watchlist_id == watchlist_id
            )
        )
        conn.execute(delete(watchlists).where(watchlists.c.id == watchlist_id))


def add_ticker_to_watchlist(
    watchlist_id: int,
    ticker: str,
    *,
    engine: Engine | None = None,
) -> dict:
    """Add a ticker to a watchlist and return the updated detail.

    Tickers are normalized (trimmed + uppercased).  Adding a ticker that is
    already present is an idempotent no-op — no duplicate row is created.

    Args:
        watchlist_id: Integer primary key of the watchlist.
        ticker: Ticker symbol to add.
        engine: Optional engine for dependency injection in tests.

    Returns:
        The updated watchlist detail dict.

    Raises:
        WatchlistNotFoundError: If the watchlist does not exist.
        WatchlistValidationError: If the ticker is blank.
    """
    _e = engine or _get_engine()
    clean = _clean_ticker(ticker)

    with _e.begin() as conn:
        _require_exists(conn, watchlist_id)
        already = conn.execute(
            select(watchlist_tickers.c.id).where(
                watchlist_tickers.c.watchlist_id == watchlist_id,
                watchlist_tickers.c.ticker == clean,
            )
        ).one_or_none()
        if already is None:
            now = datetime.now(tz=timezone.utc)
            conn.execute(
                insert(watchlist_tickers).values(
                    watchlist_id=watchlist_id,
                    ticker=clean,
                    created_at=now,
                )
            )
            conn.execute(
                update(watchlists)
                .where(watchlists.c.id == watchlist_id)
                .values(updated_at=now)
            )
        return _detail_for(conn, watchlist_id)


def remove_ticker_from_watchlist(
    watchlist_id: int,
    ticker: str,
    *,
    engine: Engine | None = None,
) -> dict:
    """Remove a ticker from a watchlist and return the updated detail.

    Tickers are normalized before matching.  Removing a ticker that is not
    present is an idempotent no-op (no error).

    Args:
        watchlist_id: Integer primary key of the watchlist.
        ticker: Ticker symbol to remove.
        engine: Optional engine for dependency injection in tests.

    Returns:
        The updated watchlist detail dict.

    Raises:
        WatchlistNotFoundError: If the watchlist does not exist.
        WatchlistValidationError: If the ticker is blank.
    """
    _e = engine or _get_engine()
    clean = _clean_ticker(ticker)

    with _e.begin() as conn:
        _require_exists(conn, watchlist_id)
        result = conn.execute(
            delete(watchlist_tickers).where(
                watchlist_tickers.c.watchlist_id == watchlist_id,
                watchlist_tickers.c.ticker == clean,
            )
        )
        if result.rowcount:
            conn.execute(
                update(watchlists)
                .where(watchlists.c.id == watchlist_id)
                .values(updated_at=datetime.now(tz=timezone.utc))
            )
        return _detail_for(conn, watchlist_id)
