"""
Portfolio persistence service.

Public boundary for managing manually entered portfolios and their holdings in
SQLite.  All database I/O uses SQLAlchemy Core; no ORM is used.  This layer is
storage only — it never fetches market data, runs analysis, connects to a
broker, executes orders, or performs any trading logic.  Current-price
enrichment and portfolio calculations live in
``app.services.portfolio_summary_service`` and run only when the summary is
requested.

Public functions::

    create_portfolio(name, description=None)          — create a portfolio.
    list_portfolios()                                 — all portfolio summaries.
    get_portfolio(portfolio_id)                       — one portfolio + holdings.
    update_portfolio(portfolio_id, name, description) — edit metadata.
    delete_portfolio(portfolio_id)                    — delete a portfolio + holdings.
    add_holding(portfolio_id, ticker, shares, average_cost, ...)  — add a holding.
    update_holding(portfolio_id, holding_id, ...)     — edit a holding (partial).
    remove_holding(portfolio_id, holding_id)          — delete one holding.

Each function accepts an optional keyword-only ``engine`` parameter for
dependency injection in tests.  Production callers omit it; a shared engine is
lazily initialised on the first call.

Decimal safety: ``shares`` and ``average_cost`` are validated and stored as
exact ``Decimal`` values (persisted as canonical strings).  ``shares`` must be
greater than zero; ``average_cost`` must be zero or greater.

Errors:
    PortfolioValidationError — invalid input (blank name, bad number, bad ticker).
    PortfolioNotFoundError   — the requested portfolio id does not exist.
    HoldingNotFoundError     — the requested holding id does not exist.
    DuplicateHoldingError    — a holding for that ticker already exists.
The first three subclass the matching builtin (``ValueError`` / ``LookupError``)
so callers may catch either the specific class or the broad builtin.
``DuplicateHoldingError`` subclasses ``ValueError`` but is caught first at the
API layer so it can map to HTTP 409 rather than 400.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Engine

from app.data.database import build_engine, portfolio_holdings, portfolios
from app.utils.helpers import normalize_ticker

_engine: Engine | None = None


class PortfolioError(Exception):
    """Base class for portfolio service errors."""


class PortfolioValidationError(PortfolioError, ValueError):
    """Raised when portfolio or holding input fails validation."""


class PortfolioNotFoundError(PortfolioError, LookupError):
    """Raised when a portfolio id does not exist."""


class HoldingNotFoundError(PortfolioError, LookupError):
    """Raised when a holding id does not exist within a portfolio."""


class DuplicateHoldingError(PortfolioError, ValueError):
    """Raised when a portfolio already holds the given ticker."""


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine


def _as_utc(value: datetime) -> datetime:
    """Return a timezone-aware UTC datetime.

    SQLite stores naive datetimes; this re-attaches UTC so every returned
    datetime is consistent regardless of code path.  Mirrors the helper in
    watchlist_service / report_persistence_service.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Input cleaners
# ---------------------------------------------------------------------------

def _clean_name(name: object) -> str:
    if not isinstance(name, str):
        raise PortfolioValidationError(
            f"Portfolio name must be a string, got {type(name).__name__}."
        )
    stripped = name.strip()
    if not stripped:
        raise PortfolioValidationError("Portfolio name must not be empty or whitespace.")
    return stripped


def _clean_description(description: object) -> str | None:
    if description is None:
        return None
    if not isinstance(description, str):
        raise PortfolioValidationError(
            f"Description must be a string or None, got {type(description).__name__}."
        )
    stripped = description.strip()
    return stripped or None


def _clean_notes(notes: object) -> str | None:
    if notes is None:
        return None
    if not isinstance(notes, str):
        raise PortfolioValidationError(
            f"Notes must be a string or None, got {type(notes).__name__}."
        )
    stripped = notes.strip()
    return stripped or None


def _clean_ticker(ticker: object) -> str:
    """Validate and normalize a ticker, reusing the shared normalizer."""
    try:
        return normalize_ticker(ticker)
    except ValueError as exc:
        raise PortfolioValidationError(str(exc)) from exc


def _to_decimal(value: object, field: str) -> Decimal:
    """Parse a value into an exact Decimal without float artifacts.

    Numbers and numeric strings are accepted.  ``bool`` is rejected explicitly
    (it is an ``int`` subclass).  Floats are routed through ``str`` so a value
    like ``0.1`` becomes ``Decimal("0.1")`` rather than the binary-float noise
    ``Decimal(0.1)`` would produce.
    """
    if isinstance(value, bool):
        raise PortfolioValidationError(f"{field} must be a number, got bool.")
    if isinstance(value, Decimal):
        candidate = value
    elif isinstance(value, (int, str)):
        try:
            candidate = Decimal(str(value).strip())
        except (InvalidOperation, ValueError) as exc:
            raise PortfolioValidationError(f"{field} must be a valid number, got {value!r}.") from exc
    elif isinstance(value, float):
        candidate = Decimal(str(value))
    else:
        raise PortfolioValidationError(
            f"{field} must be a number, got {type(value).__name__}."
        )
    if not candidate.is_finite():
        raise PortfolioValidationError(f"{field} must be a finite number, got {value!r}.")
    return candidate


def _clean_shares(value: object) -> Decimal:
    shares = _to_decimal(value, "Shares")
    if shares <= 0:
        raise PortfolioValidationError("Shares must be greater than zero.")
    return shares


def _clean_average_cost(value: object) -> Decimal:
    cost = _to_decimal(value, "Average cost")
    if cost < 0:
        raise PortfolioValidationError("Average cost must be zero or greater.")
    return cost


def _clean_purchase_date(value: object) -> str | None:
    """Validate an optional purchase date and return it as an ISO date string."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return date.fromisoformat(stripped).isoformat()
        except ValueError as exc:
            raise PortfolioValidationError(
                f"Purchase date must be an ISO date (YYYY-MM-DD), got {value!r}."
            ) from exc
    raise PortfolioValidationError(
        f"Purchase date must be a date string or None, got {type(value).__name__}."
    )


# ---------------------------------------------------------------------------
# Row builders
# ---------------------------------------------------------------------------

def _holding_from_row(row: Any) -> dict:
    """Shape a portfolio_holdings row into a JSON-friendly dict.

    ``shares`` and ``average_cost`` are stored as canonical decimal strings and
    returned as floats for the display layer; storage and validation remain
    decimal-exact.
    """
    return {
        "id": row.id,
        "portfolio_id": row.portfolio_id,
        "ticker": row.ticker,
        "shares": float(Decimal(row.shares)),
        "average_cost": float(Decimal(row.average_cost)),
        "purchase_date": row.purchase_date,
        "notes": row.notes,
        "created_at": _as_utc(row.created_at),
        "updated_at": _as_utc(row.updated_at),
    }


def _holdings_for(conn: Any, portfolio_id: int) -> list[dict]:
    stmt = (
        select(portfolio_holdings)
        .where(portfolio_holdings.c.portfolio_id == portfolio_id)
        .order_by(portfolio_holdings.c.id.asc())
    )
    return [_holding_from_row(row) for row in conn.execute(stmt).all()]


def _detail_for(conn: Any, portfolio_id: int) -> dict | None:
    row = conn.execute(
        select(portfolios).where(portfolios.c.id == portfolio_id)
    ).one_or_none()
    if row is None:
        return None
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "created_at": _as_utc(row.created_at),
        "updated_at": _as_utc(row.updated_at),
        "holdings": _holdings_for(conn, portfolio_id),
    }


def _require_portfolio(conn: Any, portfolio_id: int) -> None:
    exists = conn.execute(
        select(portfolios.c.id).where(portfolios.c.id == portfolio_id)
    ).one_or_none()
    if exists is None:
        raise PortfolioNotFoundError(f"Portfolio {portfolio_id} not found.")


def _touch_portfolio(conn: Any, portfolio_id: int, now: datetime) -> None:
    conn.execute(
        update(portfolios)
        .where(portfolios.c.id == portfolio_id)
        .values(updated_at=now)
    )


# ---------------------------------------------------------------------------
# Portfolio CRUD
# ---------------------------------------------------------------------------

def create_portfolio(
    name: str,
    description: str | None = None,
    *,
    engine: Engine | None = None,
) -> dict:
    """Create a portfolio and return its detail (with an empty holdings list)."""
    _e = engine or _get_engine()
    clean_name = _clean_name(name)
    clean_description = _clean_description(description)
    now = datetime.now(tz=timezone.utc)

    stmt = insert(portfolios).values(
        name=clean_name,
        description=clean_description,
        created_at=now,
        updated_at=now,
    )
    with _e.begin() as conn:
        new_id = conn.execute(stmt).lastrowid
        return _detail_for(conn, new_id)


def list_portfolios(*, engine: Engine | None = None) -> list[dict]:
    """Return all portfolios, newest first, each with its holdings count."""
    _e = engine or _get_engine()
    stmt = select(portfolios).order_by(portfolios.c.id.desc())
    with _e.connect() as conn:
        rows = conn.execute(stmt).all()
        return [
            {
                "id": row.id,
                "name": row.name,
                "description": row.description,
                "created_at": _as_utc(row.created_at),
                "updated_at": _as_utc(row.updated_at),
                "holdings_count": len(_holdings_for(conn, row.id)),
            }
            for row in rows
        ]


def get_portfolio(portfolio_id: int, *, engine: Engine | None = None) -> dict:
    """Return one portfolio with its holdings.

    Raises:
        PortfolioNotFoundError: If the id does not exist.
    """
    _e = engine or _get_engine()
    with _e.connect() as conn:
        detail = _detail_for(conn, portfolio_id)
    if detail is None:
        raise PortfolioNotFoundError(f"Portfolio {portfolio_id} not found.")
    return detail


def update_portfolio(
    portfolio_id: int,
    name: str | None = None,
    description: str | None = None,
    *,
    engine: Engine | None = None,
) -> dict:
    """Update a portfolio's metadata (partial update) and return its detail.

    Only provided fields change.  ``name=None`` leaves the name untouched;
    ``description=None`` also leaves it untouched (pass an empty string to clear
    a description).

    Raises:
        PortfolioNotFoundError: If the id does not exist.
        PortfolioValidationError: If ``name`` is provided but blank.
    """
    _e = engine or _get_engine()

    values: dict[str, Any] = {}
    if name is not None:
        values["name"] = _clean_name(name)
    if description is not None:
        values["description"] = _clean_description(description)

    with _e.begin() as conn:
        _require_portfolio(conn, portfolio_id)
        if values:
            values["updated_at"] = datetime.now(tz=timezone.utc)
            conn.execute(
                update(portfolios)
                .where(portfolios.c.id == portfolio_id)
                .values(**values)
            )
        return _detail_for(conn, portfolio_id)


def delete_portfolio(portfolio_id: int, *, engine: Engine | None = None) -> None:
    """Delete a portfolio and all of its holdings.

    Holdings are deleted explicitly rather than relying on SQLite cascade
    behavior, which is off by default in this project.

    Raises:
        PortfolioNotFoundError: If the id does not exist.
    """
    _e = engine or _get_engine()
    with _e.begin() as conn:
        _require_portfolio(conn, portfolio_id)
        conn.execute(
            delete(portfolio_holdings).where(
                portfolio_holdings.c.portfolio_id == portfolio_id
            )
        )
        conn.execute(delete(portfolios).where(portfolios.c.id == portfolio_id))


# ---------------------------------------------------------------------------
# Holding CRUD
# ---------------------------------------------------------------------------

def _holding_by_id(conn: Any, portfolio_id: int, holding_id: int) -> Any:
    row = conn.execute(
        select(portfolio_holdings).where(
            portfolio_holdings.c.id == holding_id,
            portfolio_holdings.c.portfolio_id == portfolio_id,
        )
    ).one_or_none()
    if row is None:
        raise HoldingNotFoundError(
            f"Holding {holding_id} not found in portfolio {portfolio_id}."
        )
    return row


def _ticker_conflict(
    conn: Any,
    portfolio_id: int,
    ticker: str,
    *,
    exclude_holding_id: int | None = None,
) -> bool:
    stmt = select(portfolio_holdings.c.id).where(
        portfolio_holdings.c.portfolio_id == portfolio_id,
        portfolio_holdings.c.ticker == ticker,
    )
    if exclude_holding_id is not None:
        stmt = stmt.where(portfolio_holdings.c.id != exclude_holding_id)
    return conn.execute(stmt).first() is not None


def add_holding(
    portfolio_id: int,
    ticker: str,
    shares: object,
    average_cost: object,
    purchase_date: object = None,
    notes: object = None,
    *,
    engine: Engine | None = None,
) -> dict:
    """Add a holding to a portfolio and return the created holding.

    Raises:
        PortfolioNotFoundError: If the portfolio does not exist.
        PortfolioValidationError: If any field fails validation.
        DuplicateHoldingError: If the portfolio already holds that ticker.
    """
    _e = engine or _get_engine()
    clean_ticker = _clean_ticker(ticker)
    clean_shares = _clean_shares(shares)
    clean_cost = _clean_average_cost(average_cost)
    clean_date = _clean_purchase_date(purchase_date)
    clean_notes = _clean_notes(notes)
    now = datetime.now(tz=timezone.utc)

    with _e.begin() as conn:
        _require_portfolio(conn, portfolio_id)
        if _ticker_conflict(conn, portfolio_id, clean_ticker):
            raise DuplicateHoldingError(
                f"Portfolio {portfolio_id} already has a holding for {clean_ticker}."
            )
        new_id = conn.execute(
            insert(portfolio_holdings).values(
                portfolio_id=portfolio_id,
                ticker=clean_ticker,
                shares=str(clean_shares),
                average_cost=str(clean_cost),
                purchase_date=clean_date,
                notes=clean_notes,
                created_at=now,
                updated_at=now,
            )
        ).lastrowid
        _touch_portfolio(conn, portfolio_id, now)
        return _holding_from_row(_holding_by_id(conn, portfolio_id, new_id))


def update_holding(
    portfolio_id: int,
    holding_id: int,
    ticker: object = None,
    shares: object = None,
    average_cost: object = None,
    purchase_date: object = None,
    notes: object = None,
    *,
    clear_purchase_date: bool = False,
    clear_notes: bool = False,
    engine: Engine | None = None,
) -> dict:
    """Update a holding (partial) and return it.

    Only provided fields change.  Duplicate-ticker validation is preserved: if
    ``ticker`` is changed to one another holding already uses, a
    ``DuplicateHoldingError`` is raised.  ``purchase_date``/``notes`` are left
    untouched when ``None``; pass ``clear_purchase_date`` / ``clear_notes`` to
    explicitly clear them.

    Raises:
        PortfolioNotFoundError: If the portfolio does not exist.
        HoldingNotFoundError: If the holding does not exist in that portfolio.
        PortfolioValidationError: If any provided field fails validation.
        DuplicateHoldingError: If the new ticker collides with another holding.
    """
    _e = engine or _get_engine()

    values: dict[str, Any] = {}
    new_ticker: str | None = None
    if ticker is not None:
        new_ticker = _clean_ticker(ticker)
        values["ticker"] = new_ticker
    if shares is not None:
        values["shares"] = str(_clean_shares(shares))
    if average_cost is not None:
        values["average_cost"] = str(_clean_average_cost(average_cost))
    if purchase_date is not None:
        values["purchase_date"] = _clean_purchase_date(purchase_date)
    elif clear_purchase_date:
        values["purchase_date"] = None
    if notes is not None:
        values["notes"] = _clean_notes(notes)
    elif clear_notes:
        values["notes"] = None

    with _e.begin() as conn:
        _require_portfolio(conn, portfolio_id)
        _holding_by_id(conn, portfolio_id, holding_id)  # 404 if missing
        if new_ticker is not None and _ticker_conflict(
            conn, portfolio_id, new_ticker, exclude_holding_id=holding_id
        ):
            raise DuplicateHoldingError(
                f"Portfolio {portfolio_id} already has a holding for {new_ticker}."
            )
        if values:
            now = datetime.now(tz=timezone.utc)
            values["updated_at"] = now
            conn.execute(
                update(portfolio_holdings)
                .where(portfolio_holdings.c.id == holding_id)
                .values(**values)
            )
            _touch_portfolio(conn, portfolio_id, now)
        return _holding_from_row(_holding_by_id(conn, portfolio_id, holding_id))


def remove_holding(
    portfolio_id: int,
    holding_id: int,
    *,
    engine: Engine | None = None,
) -> None:
    """Remove one holding from a portfolio.

    Raises:
        PortfolioNotFoundError: If the portfolio does not exist.
        HoldingNotFoundError: If the holding does not exist in that portfolio.
    """
    _e = engine or _get_engine()
    with _e.begin() as conn:
        _require_portfolio(conn, portfolio_id)
        _holding_by_id(conn, portfolio_id, holding_id)  # 404 if missing
        conn.execute(
            delete(portfolio_holdings).where(portfolio_holdings.c.id == holding_id)
        )
        _touch_portfolio(conn, portfolio_id, datetime.now(tz=timezone.utc))
