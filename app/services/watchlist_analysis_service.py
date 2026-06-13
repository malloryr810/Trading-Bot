"""
Watchlist analysis service.

Runs the existing single-ticker analysis pipeline across every ticker in a
saved watchlist and returns a structured, frontend-ready summary.

This layer adds no new analysis or scoring logic — it reuses ``analyze_stock``
(the same entry point the CLI and ``/api/analyze`` use) and ``get_watchlist``
from the watchlist persistence service. Analysis-only: it does not save the
generated reports (see the development log for the saving-as-future-work note).

Public function::

    analyze_watchlist(watchlist_id, *, engine=None) -> dict

Errors (reused from watchlist_service so the API maps them consistently):
    WatchlistNotFoundError — the watchlist id does not exist (HTTP 404).
    WatchlistValidationError — the watchlist exists but has no tickers (HTTP 400).

Partial success: a single ticker failing is captured in the ``errors`` list and
does not abort the run. The request only fails outright when the watchlist is
missing or empty.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.engine import Engine

from app.models.stock_report import StockReport
from app.services.stock_analysis_service import analyze_stock
from app.services.watchlist_service import (
    WatchlistValidationError,
    get_watchlist,
)


def _success_item(report: StockReport) -> dict:
    """Build a success result item from a StockReport (no recomputation)."""
    return {
        "ticker": report.ticker,
        "company_name": report.company_name,
        "category": report.final_category.value,
        "score": report.score,
        "confidence": report.confidence_level.value,
        "current_price": report.current_price,
        "report": report.model_dump(mode="json"),
    }


def analyze_watchlist(
    watchlist_id: int,
    *,
    engine: Engine | None = None,
) -> dict:
    """Analyze every ticker in a saved watchlist; return a structured summary.

    Args:
        watchlist_id: Integer primary key of the watchlist.
        engine: Optional engine for dependency injection in tests (passed
            through to the watchlist lookup).

    Returns:
        Dict with watchlist_id, watchlist_name, analyzed_at (UTC), total_tickers,
        successful_count, failed_count, results (list of success items, each
        including the full StockReport under ``report``), and errors (list of
        ``{ticker, error}``).

    Raises:
        WatchlistNotFoundError: If the watchlist id does not exist.
        WatchlistValidationError: If the watchlist has no tickers to analyze.
    """
    watchlist = get_watchlist(watchlist_id, engine=engine)
    tickers: list[str] = watchlist["tickers"]

    if not tickers:
        raise WatchlistValidationError(
            f"Watchlist {watchlist_id} has no tickers to analyze."
        )

    results: list[dict] = []
    errors: list[dict] = []

    for ticker in tickers:
        try:
            report = analyze_stock(ticker)
        except Exception as exc:
            # Partial success: one ticker's failure never aborts the run.
            errors.append({"ticker": ticker, "error": str(exc) or type(exc).__name__})
            continue
        results.append(_success_item(report))

    return {
        "watchlist_id": watchlist["id"],
        "watchlist_name": watchlist["name"],
        "analyzed_at": datetime.now(tz=timezone.utc),
        "total_tickers": len(tickers),
        "successful_count": len(results),
        "failed_count": len(errors),
        "results": results,
        "errors": errors,
    }
