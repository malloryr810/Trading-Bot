"""
Watchlist scanning.

Provides functions to load a watchlist from a plain-text file, run the
existing single-stock pipeline across every ticker, format a ranked
summary table, and serialize results for export. Adds no trading, order
execution, or broker connectivity.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.models.rating import ConfidenceLevel, RatingCategory
from app.models.stock_report import StockReport


class WatchlistLoadError(Exception):
    """Raised when a watchlist file cannot be loaded or contains no valid tickers."""


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

@dataclass
class WatchlistResult:
    """Result of analyzing a single ticker during a watchlist scan."""

    ticker: str
    company_name: str | None = None
    final_category: RatingCategory | None = None
    score: float | None = None
    confidence_level: ConfidenceLevel | None = None
    current_price: float | None = None
    error_message: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error_message is None


# ---------------------------------------------------------------------------
# File loading
# ---------------------------------------------------------------------------

def load_watchlist(path: str | Path) -> list[str]:
    """Load ticker symbols from a plain-text watchlist file.

    Rules applied to each line:
    - Whitespace is stripped.
    - Blank lines are ignored.
    - Lines starting with # are ignored.
    - Tickers are normalized to uppercase.
    - Duplicates are removed while preserving first-seen order.

    Args:
        path: Path to the watchlist file.

    Returns:
        Ordered, deduplicated list of uppercase ticker symbols.

    Raises:
        WatchlistLoadError: If the file does not exist or contains no valid tickers.
    """
    p = Path(path)
    if not p.exists():
        raise WatchlistLoadError(f"Watchlist file not found: {p}")

    text = p.read_text(encoding="utf-8")
    seen: set[str] = set()
    tickers: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        normalized = stripped.upper()
        if normalized not in seen:
            seen.add(normalized)
            tickers.append(normalized)

    if not tickers:
        raise WatchlistLoadError(f"Watchlist file contains no valid tickers: {p}")

    return tickers


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def scan_watchlist(
    tickers: list[str],
    analyze_func: Callable[[str], StockReport],
) -> list[WatchlistResult]:
    """Analyze multiple tickers and return ranked results.

    Each ticker is analyzed using analyze_func. Failures are captured as
    WatchlistResult entries with error_message set — they do not stop the scan.

    Successful results are sorted by score descending. Failed results appear
    after all successful ones, in the order they were encountered.

    Args:
        tickers: Ordered list of ticker symbols to analyze.
        analyze_func: Callable accepting a ticker string and returning a StockReport.
                      Inject a mock here in tests to avoid live API calls.

    Returns:
        List of WatchlistResult: successes sorted by score desc, then failures.
    """
    successes: list[WatchlistResult] = []
    failures: list[WatchlistResult] = []

    for ticker in tickers:
        try:
            report = analyze_func(ticker)
            successes.append(WatchlistResult(
                ticker=report.ticker,
                company_name=report.company_name,
                final_category=report.final_category,
                score=report.score,
                confidence_level=report.confidence_level,
                current_price=report.current_price,
            ))
        except Exception as exc:
            failures.append(WatchlistResult(
                ticker=ticker,
                error_message=str(exc) or type(exc).__name__,
            ))

    successes.sort(key=lambda r: r.score or 0.0, reverse=True)
    return successes + failures


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

_WIDTH = 100
_SEP = "=" * _WIDTH
_TICKER_W = 8
_COMPANY_W = 18
_CATEGORY_W = 22
_SCORE_W = 6
_CONF_W = 10
_PRICE_W = 12
_MAX_ERR = 70  # truncate long error messages so rows stay within _WIDTH


def format_watchlist_summary(results: list[WatchlistResult]) -> str:
    """Format watchlist scan results as a plain-text aligned terminal table.

    Args:
        results: List of WatchlistResult as returned by scan_watchlist.

    Returns:
        A multi-line string suitable for printing to the terminal.
    """
    n = len(results)
    n_success = sum(1 for r in results if r.succeeded)
    n_fail = n - n_success

    title = f"WATCHLIST SCAN — {n} ticker{'s' if n != 1 else ''} scanned"
    col_header = (
        f"  {'TICKER':<{_TICKER_W}}  {'COMPANY':<{_COMPANY_W}}"
        f"  {'CATEGORY':<{_CATEGORY_W}}"
        f"  {'SCORE':>{_SCORE_W}}  {'CONFIDENCE':<{_CONF_W}}"
        f"  {'PRICE':>{_PRICE_W}}"
    )
    col_divider = (
        f"  {'-' * _TICKER_W}  {'-' * _COMPANY_W}"
        f"  {'-' * _CATEGORY_W}"
        f"  {'-' * _SCORE_W}  {'-' * _CONF_W}"
        f"  {'-' * _PRICE_W}"
    )

    lines = [
        _SEP,
        title.center(_WIDTH),
        _SEP,
        col_header,
        col_divider,
    ]

    for result in results:
        ticker_col = result.ticker[:_TICKER_W]
        if result.succeeded:
            company_str = (result.company_name or "—")[:_COMPANY_W]
            cat_str = result.final_category.value if result.final_category else "--"
            score_str = f"{result.score:.1f}" if result.score is not None else "--"
            conf_str = result.confidence_level.value.capitalize() if result.confidence_level else "--"
            price_str = f"${result.current_price:,.2f}" if result.current_price is not None else "—"
            lines.append(
                f"  {ticker_col:<{_TICKER_W}}  {company_str:<{_COMPANY_W}}"
                f"  {cat_str:<{_CATEGORY_W}}"
                f"  {score_str:>{_SCORE_W}}  {conf_str:<{_CONF_W}}"
                f"  {price_str:>{_PRICE_W}}"
            )
        else:
            err = (result.error_message or "unknown error")[:_MAX_ERR]
            lines.append(f"  {ticker_col:<{_TICKER_W}}  ERROR: {err}")

    status = f"Scanned: {n}   Success: {n_success}   Failed: {n_fail}"
    lines += [_SEP, f"  {status}", _SEP]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def serialize_watchlist_results(results: list[WatchlistResult]) -> list[dict[str, Any]]:
    """Convert a list of WatchlistResult to JSON-serializable dicts.

    Enum fields (final_category, confidence_level) are serialized to their
    string values. None values are preserved as null. The list order is
    preserved so callers can guarantee sorted output in exported JSON.

    Args:
        results: List of WatchlistResult as returned by scan_watchlist.

    Returns:
        List of plain dicts safe to pass to json.dumps or save_json_result.
    """
    return [_result_to_dict(r) for r in results]


def _result_to_dict(result: WatchlistResult) -> dict[str, Any]:
    return {
        "ticker": result.ticker,
        "company_name": result.company_name,
        "final_category": result.final_category.value if result.final_category else None,
        "score": result.score,
        "confidence_level": result.confidence_level.value if result.confidence_level else None,
        "current_price": result.current_price,
        "error_message": result.error_message,
        "succeeded": result.succeeded,
    }
