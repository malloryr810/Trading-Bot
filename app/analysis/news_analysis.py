"""
News analysis module.

Converts a list of NewsItem objects into typed Signal objects using
transparent, rule-based keyword matching. Does not fetch data — accepts
the output of app/data/news_data.py. All returned signals use
SignalCategory.NEWS.
"""

from __future__ import annotations

from app.models.news import NewsItem
from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength


class NewsAnalysisError(Exception):
    """Raised when news signals cannot be computed from the provided input."""


# ---------------------------------------------------------------------------
# Keyword lists
# ---------------------------------------------------------------------------

_POSITIVE_KEYWORDS: frozenset[str] = frozenset({
    "beat", "beats", "earnings beat", "raises guidance", "raised guidance",
    "revenue growth", "profit growth", "upgrade", "upgraded", "outperform",
    "strong demand", "record revenue", "expansion", "partnership", "acquisition",
    "approval", "launches", "buyback", "dividend increase",
})

_NEGATIVE_KEYWORDS: frozenset[str] = frozenset({
    "miss", "misses", "earnings miss", "cuts guidance", "cut guidance",
    "revenue decline", "profit decline", "downgrade", "downgraded", "underperform",
    "weak demand", "layoffs", "lawsuit", "investigation", "sec probe", "recall",
    "loss widens", "bankruptcy", "restructuring", "data breach",
})

_RISK_KEYWORDS: frozenset[str] = frozenset({
    "lawsuit", "investigation", "probe", "sec probe", "doj", "antitrust", "recall",
    "regulatory", "fraud", "restatement", "accounting issue", "data breach",
    "cybersecurity", "bankruptcy", "default", "debt concern",
})

_MAX_EXAMPLE_TERMS = 3


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_news(news_items: list[NewsItem]) -> list[Signal]:
    """Convert a list of NewsItem objects into typed Signal objects.

    Applies rule-based keyword matching across each article's title and summary
    to produce three signals: sentiment, risk headlines, and coverage.

    Args:
        news_items: A list of NewsItem objects produced by the data layer.
            An empty list is valid — it produces three neutral no-data signals.

    Returns:
        A list of exactly 3 Signal objects: News Sentiment, News Risk
        Headlines, and News Coverage. All signals use SignalCategory.NEWS.

    Raises:
        NewsAnalysisError: If news_items is not a list, or if any element
            is not a NewsItem instance.
    """
    if not isinstance(news_items, list):
        raise NewsAnalysisError(
            f"Expected a list of NewsItem objects, got {type(news_items).__name__}."
        )
    for i, item in enumerate(news_items):
        if not isinstance(item, NewsItem):
            raise NewsAnalysisError(
                f"news_items[{i}] is not a NewsItem instance "
                f"(got {type(item).__name__})."
            )

    if not news_items:
        return [
            _no_data_signal(
                "News Sentiment",
                "No recent news items were available, so news sentiment is neutral.",
            ),
            _no_data_signal(
                "News Risk Headlines",
                "No recent news items were available; risk headlines could not be assessed.",
            ),
            _no_data_signal(
                "News Coverage",
                "No recent news items were available for analysis.",
            ),
        ]

    texts = [_extract_news_text(item) for item in news_items]
    full_text = " ".join(texts)

    pos_matches  = _unique_matches(full_text, _POSITIVE_KEYWORDS)
    neg_matches  = _unique_matches(full_text, _NEGATIVE_KEYWORDS)
    risk_matches = _unique_matches(full_text, _RISK_KEYWORDS)

    article_count = len(news_items)
    coverage_conf = min(0.40 + article_count * 0.04, 0.70)

    return [
        _sentiment_signal(pos_matches, neg_matches, coverage_conf),
        _risk_headline_signal(risk_matches, coverage_conf),
        _coverage_signal(article_count, coverage_conf),
    ]


# ---------------------------------------------------------------------------
# Signal builders
# ---------------------------------------------------------------------------

def _no_data_signal(name: str, description: str) -> Signal:
    """Return a neutral low-confidence Signal for when no news is available."""
    return Signal(
        name=name,
        category=SignalCategory.NEWS,
        direction=SignalDirection.NEUTRAL,
        strength=SignalStrength.WEAK,
        score_impact=0.0,
        confidence=0.30,
        description=description,
        value=None,
        metadata={},
    )


def _sentiment_signal(
    pos_matches: frozenset[str],
    neg_matches: frozenset[str],
    coverage_conf: float,
) -> Signal:
    """Build a sentiment Signal from positive vs negative keyword match counts."""
    pos_count = len(pos_matches)
    neg_count = len(neg_matches)
    net = pos_count - neg_count

    metadata = {
        "positive_matches": sorted(pos_matches),
        "negative_matches": sorted(neg_matches),
        "net_sentiment": net,
    }

    if net > 0:
        strength = SignalStrength.MODERATE if pos_count >= 3 else SignalStrength.WEAK
        score_impact = min(0.05 * net, 0.20)
        examples = _format_sample(pos_matches)
        return Signal(
            name="News Sentiment",
            category=SignalCategory.NEWS,
            direction=SignalDirection.BULLISH,
            strength=strength,
            score_impact=score_impact,
            confidence=coverage_conf,
            description=(
                f"Recent news appears positive: found positive terms such as {examples}."
            ),
            value=net,
            metadata=metadata,
        )

    if net < 0:
        strength = SignalStrength.MODERATE if neg_count >= 3 else SignalStrength.WEAK
        score_impact = -min(0.05 * abs(net), 0.20)
        examples = _format_sample(neg_matches)
        return Signal(
            name="News Sentiment",
            category=SignalCategory.NEWS,
            direction=SignalDirection.BEARISH,
            strength=strength,
            score_impact=score_impact,
            confidence=coverage_conf,
            description=(
                f"Recent news appears negative: found negative terms such as {examples}."
            ),
            value=net,
            metadata=metadata,
        )

    # Neutral: tied counts or no matches at all
    if pos_count == 0:
        description = (
            "No positive or negative news terms were found; sentiment is neutral."
        )
    else:
        description = (
            "Positive and negative news terms are evenly balanced; sentiment is neutral."
        )
    return Signal(
        name="News Sentiment",
        category=SignalCategory.NEWS,
        direction=SignalDirection.NEUTRAL,
        strength=SignalStrength.WEAK,
        score_impact=0.0,
        confidence=coverage_conf,
        description=description,
        value=0,
        metadata=metadata,
    )


def _risk_headline_signal(
    risk_matches: frozenset[str],
    coverage_conf: float,
) -> Signal:
    """Build a risk headline Signal from risk keyword matches."""
    if not risk_matches:
        return Signal(
            name="News Risk Headlines",
            category=SignalCategory.NEWS,
            direction=SignalDirection.NEUTRAL,
            strength=SignalStrength.WEAK,
            score_impact=0.0,
            confidence=coverage_conf,
            description="No risk-related terms found in recent news.",
            value=0,
            metadata={"risk_matches": []},
        )

    risk_count = len(risk_matches)
    strength = SignalStrength.MODERATE if risk_count >= 2 else SignalStrength.WEAK
    score_impact = -min(0.05 * risk_count, 0.20)
    examples = _format_sample(risk_matches)
    return Signal(
        name="News Risk Headlines",
        category=SignalCategory.NEWS,
        direction=SignalDirection.BEARISH,
        strength=strength,
        score_impact=score_impact,
        confidence=coverage_conf,
        description=(
            f"Recent news contains risk-related terms such as {examples}."
        ),
        value=risk_count,
        metadata={"risk_matches": sorted(risk_matches)},
    )


def _coverage_signal(article_count: int, coverage_conf: float) -> Signal:
    """Build a coverage Signal reflecting how many news items were analyzed."""
    plural = "item" if article_count == 1 else "items"
    return Signal(
        name="News Coverage",
        category=SignalCategory.NEWS,
        direction=SignalDirection.NEUTRAL,
        strength=SignalStrength.WEAK,
        score_impact=0.0,
        confidence=coverage_conf,
        description=f"{article_count} recent news {plural} were available for analysis.",
        value=article_count,
        metadata={"article_count": article_count},
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_news_text(item: NewsItem) -> str:
    """Combine title and summary into a single text block for keyword matching."""
    parts = [item.title]
    if item.summary:
        parts.append(item.summary)
    return " ".join(parts)


def _normalize_text(text: str) -> str:
    """Return text lowercased for case-insensitive matching."""
    return text.lower()


def _unique_matches(text: str, keywords: frozenset[str]) -> frozenset[str]:
    """Return the subset of keywords found in text via case-insensitive substring match."""
    normalized = _normalize_text(text)
    return frozenset(kw for kw in keywords if kw in normalized)


def _format_sample(matches: frozenset[str], limit: int = _MAX_EXAMPLE_TERMS) -> str:
    """Return a quoted, comma-separated string of up to `limit` example terms."""
    sample = sorted(matches)[:limit]
    return ", ".join(f"'{m}'" for m in sample)
