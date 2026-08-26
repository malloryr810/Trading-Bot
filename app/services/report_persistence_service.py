"""
StockReport persistence service.

Public boundary for saving and retrieving StockReport snapshots in SQLite.
All database I/O uses SQLAlchemy Core; no ORM is used.

Public functions::

    save_stock_report(report)     — persist a StockReport; return its summary + report dict.
    list_saved_reports(limit)     — return recent summaries (no full JSON blob).
    get_saved_report(report_id)   — return one full snapshot by id, or None.

Each function accepts an optional keyword-only ``engine`` parameter for
dependency injection in tests.  Production callers omit it; a shared engine
is lazily initialised on the first call.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.engine import Engine

from app.data.database import analysis_reports, as_utc, build_engine
from app.models.stock_report import StockReport

_engine: Engine | None = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine


def _summary_from_row(row: Any) -> dict:
    return {
        "id": row.id,
        "ticker": row.ticker,
        "company_name": row.company_name,
        "category": row.category,
        "score": row.score,
        "confidence": row.confidence,
        "created_at": as_utc(row.created_at),
    }


def save_stock_report(
    report: StockReport,
    *,
    engine: Engine | None = None,
) -> dict:
    """Persist a StockReport snapshot and return its saved summary plus report.

    Args:
        report: The fully populated StockReport to save.
        engine: Optional engine for dependency injection in tests.

    Returns:
        Dict with id, ticker, company_name, category, score, confidence,
        created_at, and the full report serialised as a nested dict under
        ``"report"``.
    """
    _e = engine or _get_engine()
    now = datetime.now(tz=timezone.utc)
    report_json = report.model_dump_json()

    stmt = insert(analysis_reports).values(
        ticker=report.ticker,
        company_name=report.company_name,
        category=report.final_category.value,
        score=report.score,
        confidence=report.confidence_level.value,
        report_json=report_json,
        created_at=now,
    )

    with _e.begin() as conn:
        result = conn.execute(stmt)
        new_id = result.lastrowid

    return {
        "id": new_id,
        "ticker": report.ticker,
        "company_name": report.company_name,
        "category": report.final_category.value,
        "score": report.score,
        "confidence": report.confidence_level.value,
        "created_at": now,
        "report": report.model_dump(mode="json"),
    }


def list_saved_reports(
    limit: int = 50,
    *,
    engine: Engine | None = None,
) -> list[dict]:
    """Return saved report summaries, newest first.

    Args:
        limit: Maximum number of rows to return.
        engine: Optional engine for dependency injection in tests.

    Returns:
        List of summary dicts — id, ticker, company_name, category, score,
        confidence, created_at.  The full report JSON is not included.
    """
    _e = engine or _get_engine()

    stmt = (
        select(
            analysis_reports.c.id,
            analysis_reports.c.ticker,
            analysis_reports.c.company_name,
            analysis_reports.c.category,
            analysis_reports.c.score,
            analysis_reports.c.confidence,
            analysis_reports.c.created_at,
        )
        .order_by(analysis_reports.c.id.desc())
        .limit(limit)
    )

    with _e.connect() as conn:
        rows = conn.execute(stmt).all()

    return [_summary_from_row(row) for row in rows]


def get_saved_report(
    report_id: int,
    *,
    engine: Engine | None = None,
) -> dict | None:
    """Return one full StockReport snapshot by id.

    Args:
        report_id: Integer primary key of the saved report.
        engine: Optional engine for dependency injection in tests.

    Returns:
        Dict with summary fields plus ``"report"`` (the full StockReport as a
        JSON-compatible dict), or ``None`` if the id does not exist.
    """
    _e = engine or _get_engine()

    stmt = select(analysis_reports).where(analysis_reports.c.id == report_id)

    with _e.connect() as conn:
        row = conn.execute(stmt).one_or_none()

    if row is None:
        return None

    report = StockReport.model_validate_json(row.report_json)

    return {
        "id": row.id,
        "ticker": row.ticker,
        "company_name": row.company_name,
        "category": row.category,
        "score": row.score,
        "confidence": row.confidence,
        "created_at": as_utc(row.created_at),
        "report": report.model_dump(mode="json"),
    }
