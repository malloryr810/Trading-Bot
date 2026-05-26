"""
Entry point for the Investment Bot.

Single-ticker mode:

    python -m app.main <TICKER>
    python -m app.main <TICKER> --save-report
    python -m app.main <TICKER> --save-json
    python -m app.main <TICKER> --save-markdown
    python -m app.main <TICKER> --save-report --save-json

Watchlist mode:

    python -m app.main --watchlist <file>
    python -m app.main --watchlist <file> --save-report
    python -m app.main --watchlist <file> --save-json
    python -m app.main --watchlist <file> --save-markdown
    python -m app.main --watchlist <file> --save-report --save-json

Fetches historical OHLCV data and company fundamentals, computes technical,
fundamental, risk, and news signals, scores them with composite weights, and
prints a plain-text research report. Optionally saves the report as a .txt
file, a .md Markdown file, and/or a structured .json result when the
respective flags are provided.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from app.analysis.fundamentals_analysis import (
    FundamentalAnalysisError,
    build_fundamental_signals,
)
from app.analysis.news_analysis import NewsAnalysisError, analyze_news
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
from app.data.storage import StorageError, save_json_result, save_markdown_report, save_text_report
from app.models.rating import Rating
from app.utils.helpers import safe_float
from app.reports.report_generator import build_stock_report, generate_plain_text_report
from app.reports.templates import format_report_markdown, format_watchlist_markdown


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

    rating = score_signals(
        ticker=ticker,
        signals=tech_signals + fund_signals + risk_signals + news_signals,
        data_timestamp=datetime.now(tz=timezone.utc),
        data_sources_used=["yfinance"],
    )
    return rating.model_copy(update={
        "company_name": fundamentals.company_name,
        "current_price": safe_float(price_data["close"].iloc[-1]),
    })


# ---------------------------------------------------------------------------
# Watchlist mode
# ---------------------------------------------------------------------------

def _run_watchlist(
    watchlist_path: str,
    do_save_report: bool = False,
    do_save_json: bool = False,
    do_save_markdown: bool = False,
) -> int:
    """Run watchlist scan mode, print a ranked summary table, and optionally save."""
    from app.watchlist import (
        WatchlistLoadError,
        format_watchlist_summary,
        load_watchlist,
        scan_watchlist,
        serialize_watchlist_results,
    )

    try:
        tickers = load_watchlist(watchlist_path)
    except WatchlistLoadError as exc:
        print(f"Error loading watchlist: {exc}", file=sys.stderr)
        return 1

    results = scan_watchlist(
        tickers,
        lambda ticker: build_stock_report(analyze_ticker(ticker)),
    )
    summary = format_watchlist_summary(results)
    print(summary)

    if do_save_report:
        try:
            path = save_text_report(summary, "WATCHLIST")
            print(f"Saved text report to: {path}")
        except StorageError as exc:
            print(f"Warning: failed to save text report: {exc}", file=sys.stderr)

    if do_save_markdown:
        try:
            md_text = format_watchlist_markdown(results)
            path = save_markdown_report(md_text, "WATCHLIST")
            print(f"Saved Markdown report to: {path}")
        except StorageError as exc:
            print(f"Warning: failed to save Markdown report: {exc}", file=sys.stderr)

    if do_save_json:
        try:
            data = {"results": serialize_watchlist_results(results)}
            path = save_json_result(data, "WATCHLIST")
            print(f"Saved JSON result to: {path}")
        except StorageError as exc:
            print(f"Warning: failed to save JSON result: {exc}", file=sys.stderr)

    return 0


# ---------------------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m app.main",
        description="Stock research and analysis tool. Prints a scored research report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python -m app.main AAPL\n"
            "  python -m app.main AAPL --save-report --save-json\n"
            "  python -m app.main --watchlist watchlists/default.txt\n"
            "  python -m app.main --watchlist watchlists/default.txt --save-report\n"
        ),
    )
    parser.add_argument(
        "ticker",
        nargs="?",
        help="Stock ticker symbol to analyze (e.g. AAPL).",
    )
    parser.add_argument(
        "--watchlist",
        metavar="FILE",
        help="Path to a plain-text watchlist file (one ticker per line).",
    )
    parser.add_argument(
        "--save-report",
        action="store_true",
        help="Save a plain-text report to outputs/reports/.",
    )
    parser.add_argument(
        "--save-json",
        action="store_true",
        help="Save a structured JSON result to outputs/results/.",
    )
    parser.add_argument(
        "--save-markdown",
        action="store_true",
        help="Save a Markdown report to outputs/reports/.",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments and return a Namespace.

    Args:
        argv: Argument list. If None, uses sys.argv[1:].

    Returns:
        Parsed Namespace with fields: ticker, watchlist, save_report, save_json, save_markdown.

    Raises:
        SystemExit: On parse errors or --help.
    """
    return build_parser().parse_args(argv)


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
    parser = build_parser()

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        return 0 if code == 0 else 1

    if args.ticker and args.watchlist:
        parser.print_usage(sys.stderr)
        print(
            "error: provide either a ticker or --watchlist, not both.",
            file=sys.stderr,
        )
        return 1

    if not args.ticker and not args.watchlist:
        parser.print_usage(sys.stderr)
        print(
            "error: provide a ticker symbol or --watchlist file.",
            file=sys.stderr,
        )
        return 1

    if args.watchlist:
        return _run_watchlist(args.watchlist, args.save_report, args.save_json, args.save_markdown)

    ticker = args.ticker

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
    except NewsAnalysisError as exc:
        print(f"Error running news analysis: {exc}", file=sys.stderr)
        return 1
    except ScoringError as exc:
        print(f"Error scoring signals: {exc}", file=sys.stderr)
        return 1

    stock_report = build_stock_report(rating)
    report = generate_plain_text_report(stock_report)
    print(report)

    if args.save_report:
        try:
            path = save_text_report(report, rating.ticker)
            print(f"Saved text report to: {path}")
        except StorageError as exc:
            print(f"Warning: failed to save text report: {exc}", file=sys.stderr)

    if args.save_markdown:
        try:
            md_text = format_report_markdown(stock_report)
            path = save_markdown_report(md_text, rating.ticker)
            print(f"Saved Markdown report to: {path}")
        except StorageError as exc:
            print(f"Warning: failed to save Markdown report: {exc}", file=sys.stderr)

    if args.save_json:
        try:
            path = save_json_result(rating, rating.ticker)
            print(f"Saved JSON result to: {path}")
        except StorageError as exc:
            print(f"Warning: failed to save JSON result: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
