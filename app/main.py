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

from app.analysis.fundamentals_analysis import FundamentalAnalysisError
from app.analysis.news_analysis import NewsAnalysisError
from app.analysis.risk_analysis import RiskAnalysisError
from app.analysis.scoring import ScoringError
from app.analysis.technicals import TechnicalAnalysisError
from app.data.fundamentals import FundamentalDataFetchError
from app.data.market_data import DataFetchError
from app.data.storage import StorageError, save_json_result, save_markdown_report, save_text_report
from app.reports.report_generator import build_stock_report, generate_plain_text_report
from app.reports.templates import format_report_markdown, format_watchlist_markdown
from app.services.stock_analysis_service import analyze_ticker, analyze_watchlist_file


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
        serialize_watchlist_results,
    )

    try:
        results = analyze_watchlist_file(watchlist_path)
    except WatchlistLoadError as exc:
        print(f"Error loading watchlist: {exc}", file=sys.stderr)
        return 1

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
