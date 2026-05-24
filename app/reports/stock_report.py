"""
Stock report generator.

Converts a Rating and its associated Signal list into a formatted
plain-text research report string. Returns the report as a single string;
callers are responsible for printing or writing it to a file.

No external dependencies beyond the standard library and the project's
own models.
"""

from __future__ import annotations

from datetime import date

from app.models.rating import Rating
from app.models.signal import Signal, SignalDirection


_WIDTH = 80
_SEP = "=" * _WIDTH


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_stock_report(
    ticker: str,
    rating: Rating,
    signals: list[Signal],
    company_name: str | None = None,
    current_price: float | None = None,
    data_sources: list[str] | None = None,
) -> str:
    """Generate a plain-text stock research report.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL").
        rating: Completed Rating produced by the scoring engine.
        signals: Signal list used in the analysis (may be empty).
        company_name: Optional human-readable company name.
        current_price: Optional latest price in USD.
        data_sources: Optional list of data-source labels. Falls back to
            rating.data_sources_used when not provided.

    Returns:
        A single formatted plain-text string.

    Raises:
        ValueError: If ticker is empty or whitespace.
    """
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValueError(f"ticker must be a non-empty string, got {ticker!r}.")

    t = ticker.strip().upper()
    sources = list(data_sources) if data_sources is not None else list(rating.data_sources_used)

    parts = [
        _header(t, company_name, current_price, sources),
        _recommendation(rating),
        _score_breakdown(rating),
        _analysis_summaries(rating),
        _signals_section(signals),
        _key_strengths(rating),
        _key_risks(rating),
        _triggers(rating),
        _disclaimer(),
    ]
    return "\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _header(
    ticker: str,
    company_name: str | None,
    current_price: float | None,
    sources: list[str],
) -> str:
    name_label = f"{ticker}  ({company_name})" if company_name else ticker
    lines = [
        _SEP,
        "INVESTMENT BOT — STOCK RESEARCH REPORT".center(_WIDTH),
        _SEP,
        f"  Ticker:  {name_label}",
        f"  Date:    {date.today().isoformat()}",
    ]
    if current_price is not None:
        lines.append(f"  Price:   ${current_price:,.2f}")
    if sources:
        lines.append(f"  Data:    {', '.join(sources)}")
    return "\n".join(lines)


def _recommendation(rating: Rating) -> str:
    lines = [
        "",
        _SEP,
        "RECOMMENDATION".center(_WIDTH),
        _SEP,
        f"  Rating:      {rating.final_category.value}",
        f"  Score:       {rating.score:.1f} / 100",
        f"  Confidence:  {rating.confidence.value.capitalize()}",
        "",
        f"  {rating.explanation}",
    ]
    return "\n".join(lines)


def _score_breakdown(rating: Rating) -> str:
    def _row(label: str, score: float) -> str:
        tag = "  (not scored)" if score == 0.0 else ""
        return f"  {label:<15} {score:>5.1f} / 100{tag}"

    lines = [
        "",
        _SEP,
        "SCORE BREAKDOWN".center(_WIDTH),
        _SEP,
        _row("Technical:", rating.technical_score),
        _row("Fundamental:", rating.fundamental_score),
        _row("News:", rating.news_score),
        _row("Risk:", rating.risk_score),
    ]
    return "\n".join(lines)


def _analysis_summaries(rating: Rating) -> str:
    risk_text = rating.risk_summary or "Risk conditions were not assessed for this report."
    present = [
        ("TECHNICAL ANALYSIS",   rating.technical_summary),
        ("FUNDAMENTAL ANALYSIS", rating.fundamental_summary),
        ("NEWS / SENTIMENT",     rating.news_summary),
        ("RISK CONDITIONS",      risk_text),
    ]
    active = [(title, summary) for title, summary in present if summary]
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
    bullish = sum(1 for s in signals if s.is_bullish)
    bearish = sum(1 for s in signals if s.is_bearish)
    neutral = n - bullish - bearish

    lines = [
        "",
        _SEP,
        "SIGNALS".center(_WIDTH),
        _SEP,
        f"  {n} signal{'s' if n != 1 else ''}   "
        f"{bullish} bullish   {bearish} bearish   {neutral} neutral",
    ]
    if signals:
        lines.append("")
        for sig in signals:
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


def _key_strengths(rating: Rating) -> str:
    lines = [
        "",
        _SEP,
        "KEY STRENGTHS".center(_WIDTH),
        _SEP,
    ]
    if rating.key_positive_factors:
        for factor in rating.key_positive_factors:
            lines.append(f"  + {factor}")
    else:
        lines.append("  (none identified)")
    return "\n".join(lines)


def _key_risks(rating: Rating) -> str:
    lines = [
        "",
        _SEP,
        "KEY RISKS".center(_WIDTH),
        _SEP,
    ]
    if rating.key_risks:
        for risk in rating.key_risks:
            lines.append(f"  - {risk}")
    else:
        lines.append("  (none identified)")
    return "\n".join(lines)


def _triggers(rating: Rating) -> str:
    has_buy = bool(rating.buy_trigger)
    has_sell = bool(rating.sell_or_avoid_trigger)

    lines = [
        "",
        _SEP,
        "TRIGGERS".center(_WIDTH),
        _SEP,
    ]
    if has_buy:
        lines.append("  Buy Trigger:")
        lines.append(f"    {rating.buy_trigger}")
    if has_sell:
        if has_buy:
            lines.append("")
        lines.append("  Sell / Avoid Trigger:")
        lines.append(f"    {rating.sell_or_avoid_trigger}")
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
