"""
Stock analysis service layer.

Provides reusable analysis functions that can be called by both the CLI
(app/main.py) and a future UI without importing from app.main.

Functions:
    _analyze_ticker — internal; run the full pipeline; return a Rating.
    analyze_stock   — run the full pipeline; return a StockReport.
    analyze_stock_rating — run the full pipeline; return the raw Rating.
    analyze_watchlist_file — load a watchlist file and analyze all tickers.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.analysis.fundamentals_analysis import build_fundamental_signals
from app.analysis.news_analysis import analyze_news
from app.analysis.risk_analysis import analyze_risk_conditions
from app.analysis.scoring import score_signals
from app.analysis.technicals import (
    build_technical_signals,
    calculate_technical_indicators,
    summarize_technical_signals,
)
from app.data.fundamentals import get_company_fundamentals
from app.data.market_data import get_price_history, latest_valid_close
from app.data.news_data import get_recent_news
from app.models.rating import Rating
from app.models.stock_report import StockReport
from app.reports.report_generator import build_stock_report
from app.watchlist import WatchlistResult, load_watchlist, scan_watchlist


def _analyze_ticker(ticker: str) -> Rating:
    """Run the full analysis pipeline for a single ticker.

    Fetches market data, company fundamentals, and recent news, then computes
    technical, fundamental, risk, and news signals and scores them with
    composite weights. News fetch failures are non-fatal: the pipeline
    continues with neutral no-data news signals.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL").

    Returns:
        A composite Rating covering technical, fundamental, risk, and news signals.

    Raises:
        DataFetchError: If market data cannot be fetched or validated.
        FundamentalDataFetchError: If fundamental data cannot be fetched.
        TechnicalAnalysisError: If technical indicators or signals cannot be computed.
        FundamentalAnalysisError: If fundamental signals cannot be computed.
        RiskAnalysisError: If risk signals cannot be computed.
        ScoringError: If the signals cannot be scored.
    """
    price_data   = get_price_history(ticker)
    fundamentals = get_company_fundamentals(ticker)

    try:
        news_items = get_recent_news(ticker)
    except Exception:
        news_items = []

    indicator_data    = calculate_technical_indicators(price_data)
    indicator_summary = summarize_technical_signals(indicator_data)
    tech_signals      = build_technical_signals(indicator_summary)
    fund_signals      = build_fundamental_signals(fundamentals)
    risk_signals      = analyze_risk_conditions(price_data, beta=fundamentals.beta)
    news_signals      = analyze_news(news_items)

    rating = score_signals(
        ticker=ticker,
        signals=tech_signals + fund_signals + risk_signals + news_signals,
        data_timestamp=datetime.now(tz=timezone.utc),
        data_sources_used=["yfinance"],
    )
    return rating.model_copy(update={
        "company_name": fundamentals.company_name,
        # Latest *valid* close — an in-progress session can leave the final row's
        # OHLC null, which must not read as "no price".
        "current_price": latest_valid_close(price_data),
    })


def analyze_stock(ticker: str) -> StockReport:
    """Run the full analysis pipeline and return a StockReport.

    Convenience function for callers (e.g. a future UI) that want a
    fully assembled, report-ready object rather than the raw Rating.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL").

    Returns:
        A fully populated StockReport ready for rendering.

    Raises:
        Same exceptions as _analyze_ticker.
    """
    rating = _analyze_ticker(ticker)
    return build_stock_report(rating)


def analyze_stock_rating(ticker: str) -> Rating:
    """Run the full analysis pipeline and return the raw Rating.

    Same pipeline as ``analyze_stock`` — this is simply the entry point for
    callers that need the scoring engine's per-category sub-scores (which the
    StockReport contract does not carry), such as the discovery service's mode
    ranking. It performs no analysis or scoring of its own.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL").

    Returns:
        The composite Rating produced by the scoring engine.

    Raises:
        Same exceptions as _analyze_ticker.
    """
    return _analyze_ticker(ticker)


def analyze_watchlist_file(path: str) -> list[WatchlistResult]:
    """Load a watchlist file and analyze every ticker in it.

    Delegates to load_watchlist for file I/O and to scan_watchlist for
    per-ticker analysis. Per-ticker failures are captured as WatchlistResult
    entries with error_message set; they do not abort the scan.

    Args:
        path: Path to a plain-text watchlist file (one ticker per line).

    Returns:
        List of WatchlistResult: successes sorted by score descending,
        then failures in encounter order.

    Raises:
        WatchlistLoadError: If the file does not exist or contains no valid
            tickers. Callers should catch this to display a user-friendly
            error before the scan begins.
    """
    tickers = load_watchlist(path)
    return scan_watchlist(tickers, analyze_stock)
