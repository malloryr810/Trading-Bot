"""
Entry point for the Investment Bot.

Runs a full single-ticker analysis pipeline from the terminal:

    python -m app.main <TICKER>

Fetches historical OHLCV data and company fundamentals, computes technical,
fundamental, and risk signals, scores them with composite weights, and prints
a plain-text research report.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from app.analysis.fundamentals_analysis import (
    FundamentalAnalysisError,
    build_fundamental_signals,
)
from app.analysis.news_analysis import analyze_news
from app.analysis.risk_analysis import RiskAnalysisError, analyze_risk_conditions
from app.analysis.scoring import ScoringError, score_signals
from app.analysis.technicals import (
    TechnicalAnalysisError,
    build_technical_signals,
    calculate_technical_indicators,
    summarize_technical_signals,
)
from app.data.fundamentals import FundamentalDataFetchError, get_company_fundamentals
from app.data.market_data import DataFetchError, get_price_history
from app.data.news_data import get_recent_news
from app.models.rating import Rating
from app.reports.stock_report import generate_stock_report


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def analyze_ticker(ticker: str) -> Rating:
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

    return score_signals(
        ticker=ticker,
        signals=tech_signals + fund_signals + risk_signals + news_signals,
        data_timestamp=datetime.now(tz=timezone.utc),
        data_sources_used=["yfinance"],
    )


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_rating_output(rating: Rating) -> str:
    """Render a Rating as a human-readable terminal string."""

    def _list_items(items: list[str]) -> str:
        return "\n".join(f"  - {item}" for item in items) if items else "  - None"

    lines = [
        "Investment Bot Technical Analysis",
        "=================================",
        f"Ticker:           {rating.ticker}",
        f"Final Category:   {rating.final_category.value}",
        f"Score:            {rating.score:.1f}/100",
        f"Confidence:       {rating.confidence.value}",
        f"Technical Score:  {rating.technical_score:.1f}/100",
        "",
        "Explanation:",
        f"  {rating.explanation}",
        "",
        "Technical Summary:",
        f"  {rating.technical_summary or 'N/A'}",
        "",
        "Key Positive Factors:",
        _list_items(rating.key_positive_factors),
        "",
        "Key Risks:",
        _list_items(rating.key_risks),
        "",
        "Buy Trigger:",
        f"  {rating.buy_trigger or 'N/A'}",
        "",
        "Sell / Avoid Trigger:",
        f"  {rating.sell_or_avoid_trigger or 'N/A'}",
        "",
        "Note:",
        "  This is a decision-support output.",
        "  It is not financial advice and does not place trades.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        0 on success, 1 on any handled error.
    """
    args = argv if argv is not None else sys.argv[1:]

    if not args:
        print("Usage: python -m app.main <TICKER>", file=sys.stderr)
        return 1

    ticker = args[0]

    try:
        rating = analyze_ticker(ticker)
    except DataFetchError as exc:
        print(f"Error fetching market data: {exc}", file=sys.stderr)
        return 1
    except FundamentalDataFetchError as exc:
        print(f"Error fetching fundamental data: {exc}", file=sys.stderr)
        return 1
    except TechnicalAnalysisError as exc:
        print(f"Error running technical analysis: {exc}", file=sys.stderr)
        return 1
    except FundamentalAnalysisError as exc:
        print(f"Error running fundamental analysis: {exc}", file=sys.stderr)
        return 1
    except RiskAnalysisError as exc:
        print(f"Error running risk analysis: {exc}", file=sys.stderr)
        return 1
    except ScoringError as exc:
        print(f"Error scoring signals: {exc}", file=sys.stderr)
        return 1

    report = generate_stock_report(
        ticker=rating.ticker,
        rating=rating,
        signals=rating.signals_used,
    )
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
