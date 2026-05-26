"""
Report generator.

Assembles a StockReport from completed pipeline outputs (Rating + optional
metadata), then delegates to templates.py for plain-text rendering.

This module does not fetch data, run analysis, or perform scoring.
"""

from __future__ import annotations

from app.models.rating import Rating
from app.models.signal import SignalCategory
from app.models.stock_report import StockReport
from app.reports.templates import format_plain_text_report


def build_stock_report(
    rating: Rating,
    company_name: str | None = None,
    current_price: float | None = None,
) -> StockReport:
    """Assemble a StockReport from a completed Rating.

    Partitions rating.signals_used into per-category lists and maps
    Rating fields onto the StockReport contract. Does not re-score or
    re-analyse — it only reorganises already-computed results.

    Args:
        rating: A Rating produced by the scoring engine.
        company_name: Optional human-readable company name.
        current_price: Optional latest price in USD.

    Returns:
        A fully populated StockReport ready for formatting.
    """
    resolved_name  = company_name  if company_name  is not None else rating.company_name
    resolved_price = current_price if current_price is not None else rating.current_price
    signals = rating.signals_used
    return StockReport(
        ticker=rating.ticker,
        company_name=resolved_name,
        current_price=resolved_price,
        final_category=rating.final_category,
        score=rating.score,
        confidence_level=rating.confidence,
        technical_summary=rating.technical_summary,
        fundamental_summary=rating.fundamental_summary,
        news_summary=rating.news_summary,
        risk_summary=rating.risk_summary,
        key_positive_factors=list(rating.key_positive_factors),
        key_risks=list(rating.key_risks),
        buy_trigger=rating.buy_trigger,
        sell_or_avoid_trigger=rating.sell_or_avoid_trigger,
        data_timestamp=rating.data_timestamp,
        data_sources_used=list(rating.data_sources_used),
        confidence_diagnostics=rating.confidence_diagnostics,
        technical_signals=[s for s in signals if s.category == SignalCategory.TECHNICAL],
        fundamental_signals=[s for s in signals if s.category == SignalCategory.FUNDAMENTAL],
        news_signals=[s for s in signals if s.category == SignalCategory.NEWS],
        risk_signals=[s for s in signals if s.category == SignalCategory.RISK],
    )


def generate_plain_text_report(report: StockReport) -> str:
    """Render a StockReport as a plain-text string.

    Args:
        report: A completed StockReport produced by build_stock_report.

    Returns:
        A single formatted plain-text string.
    """
    return format_plain_text_report(report)
