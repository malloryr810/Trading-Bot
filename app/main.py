"""
Entry point for the Investment Bot.

Runs a technical-only single-ticker analysis pipeline from the terminal:

    python -m app.main <TICKER>

Fetches historical OHLCV data, calculates technical indicators, builds
typed Signal objects, scores them, and prints a readable summary.
Fundamentals, news, risk, and report file generation are not yet implemented.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from app.analysis.scoring import ScoringError, score_technical_signals
from app.analysis.technicals import (
    TechnicalAnalysisError,
    build_technical_signals,
    calculate_technical_indicators,
    summarize_technical_signals,
)
from app.data.market_data import DataFetchError, get_price_history
from app.models.rating import Rating


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def analyze_ticker(ticker: str) -> Rating:
    """Run the full technical analysis pipeline for a single ticker.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL").

    Returns:
        A Rating produced by the technical scoring engine.

    Raises:
        DataFetchError: If market data cannot be fetched or validated.
        TechnicalAnalysisError: If indicators or signals cannot be computed.
        ScoringError: If the signals cannot be scored.
    """
    price_data = get_price_history(ticker)
    indicator_data = calculate_technical_indicators(price_data)
    indicator_summary = summarize_technical_signals(indicator_data)
    signals = build_technical_signals(indicator_summary)
    return score_technical_signals(
        ticker=ticker,
        signals=signals,
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
        "  This is a technical-only decision-support output.",
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
    except TechnicalAnalysisError as exc:
        print(f"Error running technical analysis: {exc}", file=sys.stderr)
        return 1
    except ScoringError as exc:
        print(f"Error scoring signals: {exc}", file=sys.stderr)
        return 1

    print(format_rating_output(rating))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
