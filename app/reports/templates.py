"""
Report templates.

Plain-text formatting helpers for StockReport. The single public entry
point is format_plain_text_report(report) which produces a terminal-
readable research report from a completed StockReport object.
"""

from __future__ import annotations

from datetime import date

from app.models.signal import Signal, SignalCategory, SignalDirection
from app.models.stock_report import StockReport

_WIDTH = 80
_SEP = "=" * _WIDTH

_CATEGORY_ORDER: dict[SignalCategory, int] = {
    SignalCategory.TECHNICAL:   0,
    SignalCategory.FUNDAMENTAL: 1,
    SignalCategory.NEWS:        2,
    SignalCategory.RISK:        3,
}


def format_plain_text_report(report: StockReport) -> str:
    """Render a StockReport as a plain-text terminal-readable string.

    Args:
        report: A completed StockReport produced by report_generator.

    Returns:
        A single formatted plain-text string.
    """
    all_signals = (
        report.technical_signals
        + report.fundamental_signals
        + report.news_signals
        + report.risk_signals
    )
    parts = [
        _header(report),
        _recommendation(report),
        _analysis_summaries(report),
        _signals_section(all_signals),
        _key_strengths(report),
        _key_risks(report),
        _triggers(report),
        _disclaimer(),
    ]
    return "\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _header(report: StockReport) -> str:
    name_label = (
        f"{report.ticker}  ({report.company_name})"
        if report.company_name
        else report.ticker
    )
    lines = [
        _SEP,
        "INVESTMENT BOT — STOCK RESEARCH REPORT".center(_WIDTH),
        _SEP,
        f"  Ticker:  {name_label}",
        f"  Date:    {date.today().isoformat()}",
    ]
    if report.current_price is not None:
        lines.append(f"  Price:   ${report.current_price:,.2f}")
    if report.data_timestamp is not None:
        ts = report.data_timestamp.strftime("%Y-%m-%d %H:%M UTC")
        lines.append(f"  As of:   {ts}")
    if report.data_sources_used:
        lines.append(f"  Data:    {', '.join(report.data_sources_used)}")
    return "\n".join(lines)


def _recommendation(report: StockReport) -> str:
    lines = [
        "",
        _SEP,
        "RECOMMENDATION".center(_WIDTH),
        _SEP,
        f"  Rating:      {report.final_category.value}",
        f"  Score:       {report.score:.1f} / 100",
        f"  Confidence:  {report.confidence_level.value.capitalize()}",
    ]
    return "\n".join(lines)


def _analysis_summaries(report: StockReport) -> str:
    risk_text = report.risk_summary or "Risk conditions were not assessed for this report."
    candidates = [
        ("TECHNICAL ANALYSIS",   report.technical_summary),
        ("FUNDAMENTAL ANALYSIS", report.fundamental_summary),
        ("NEWS / SENTIMENT",     report.news_summary),
        ("RISK CONDITIONS",      risk_text),
    ]
    active = [(title, summary) for title, summary in candidates if summary]
    if not active:
        return ""

    parts: list[str] = []
    for title, summary in active:
        parts.append("")
        parts.append(_SEP)
        parts.append(title.center(_WIDTH))
        parts.append(_SEP)
        parts.append(f"  {summary}")
    return "\n".join(parts)


def _signals_section(signals: list[Signal]) -> str:
    n = len(signals)
    bullish = sum(1 for s in signals if s.direction == SignalDirection.BULLISH)
    bearish = sum(1 for s in signals if s.direction == SignalDirection.BEARISH)
    neutral = n - bullish - bearish

    lines = [
        "",
        _SEP,
        "SIGNALS".center(_WIDTH),
        _SEP,
        f"  {n} signal{'s' if n != 1 else ''}   "
        f"{bullish} bullish   {bearish} bearish   {neutral} neutral",
    ]
    ordered = sorted(signals, key=lambda s: _CATEGORY_ORDER.get(s.category, 99))
    if ordered:
        lines.append("")
        for sig in ordered:
            ind = _direction_indicator(sig.direction)
            dir_str = sig.direction.value.upper()
            str_str = sig.strength.value.upper()
            lines.append(f"  {ind} {dir_str:<8}  {str_str:<10}  {sig.name}")
            lines.append(f"      {sig.description}")
    return "\n".join(lines)


def _direction_indicator(direction: SignalDirection) -> str:
    if direction == SignalDirection.BULLISH:
        return "[+]"
    if direction == SignalDirection.BEARISH:
        return "[-]"
    return "[ ]"


def _key_strengths(report: StockReport) -> str:
    lines = [
        "",
        _SEP,
        "KEY STRENGTHS".center(_WIDTH),
        _SEP,
    ]
    if report.key_positive_factors:
        for factor in report.key_positive_factors:
            lines.append(f"  + {factor}")
    else:
        lines.append("  (none identified)")
    return "\n".join(lines)


def _key_risks(report: StockReport) -> str:
    lines = [
        "",
        _SEP,
        "KEY RISKS".center(_WIDTH),
        _SEP,
    ]
    if report.key_risks:
        for risk in report.key_risks:
            lines.append(f"  - {risk}")
    else:
        lines.append("  (none identified)")
    return "\n".join(lines)


def _triggers(report: StockReport) -> str:
    has_buy = bool(report.buy_trigger)
    has_sell = bool(report.sell_or_avoid_trigger)

    lines = [
        "",
        _SEP,
        "TRIGGERS".center(_WIDTH),
        _SEP,
    ]
    if has_buy:
        lines.append("  Buy Trigger:")
        lines.append(f"    {report.buy_trigger}")
    if has_sell:
        if has_buy:
            lines.append("")
        lines.append("  Sell / Avoid Trigger:")
        lines.append(f"    {report.sell_or_avoid_trigger}")
    if not has_buy and not has_sell:
        lines.append("  (no triggers defined)")
    return "\n".join(lines)


def _disclaimer() -> str:
    lines = [
        "",
        _SEP,
        "DISCLAIMER".center(_WIDTH),
        _SEP,
        "  This report is for research and decision-support purposes only.",
        "  It is not financial advice. It does not place, recommend, or imply trades.",
        _SEP,
    ]
    return "\n".join(lines)
