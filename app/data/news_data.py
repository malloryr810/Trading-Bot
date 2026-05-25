"""
News data fetcher.

Responsible for retrieving recent news headlines for a ticker from yfinance.
Returns a list of typed NewsItem objects consumed by the news analysis layer.
Does not perform sentiment scoring or signal generation.
"""

from __future__ import annotations

from datetime import datetime, timezone

import yfinance as yf

from app.models.news import NewsItem
from app.utils.helpers import normalize_ticker


class NewsFetchError(Exception):
    """Raised when news data cannot be fetched or validated."""


def get_recent_news(ticker: str, limit: int = 10) -> list[NewsItem]:
    """Fetch and return recent news headlines for a ticker.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL"). Case-insensitive.
        limit: Maximum number of items to return. Must be a positive integer.

    Returns:
        A list of up to ``limit`` NewsItem objects. Returns an empty list when
        yfinance returns no news or all items lack a usable title.

    Raises:
        NewsFetchError: If the ticker is invalid, limit is invalid, or yfinance
            raises an error during the fetch.
    """
    try:
        symbol = normalize_ticker(ticker)
    except ValueError as exc:
        raise NewsFetchError(str(exc)) from exc
    _validate_limit(limit)

    try:
        raw_news = yf.Ticker(symbol).news
    except Exception as exc:
        raise NewsFetchError(
            f"yfinance raised an error while fetching news for '{symbol}': {exc}"
        ) from exc

    if not raw_news:
        return []

    items: list[NewsItem] = []
    for raw in raw_news:
        if len(items) >= limit:
            break
        item = _parse_news_item(raw)
        if item is not None:
            items.append(item)

    return items


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_limit(limit: object) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise NewsFetchError(
            f"Limit must be a positive integer, got {type(limit).__name__}."
        )
    if limit < 1:
        raise NewsFetchError(
            f"Limit must be a positive integer, got {limit}."
        )


def _parse_news_item(raw: object) -> NewsItem | None:
    """Parse a single raw yfinance news dict into a NewsItem.

    Returns None if the item has no usable title, so the caller can skip it.
    Handles both flat (older yfinance) and nested-content (newer yfinance) shapes.
    """
    if not isinstance(raw, dict):
        return None

    content = raw.get("content") or {}
    if not isinstance(content, dict):
        content = {}

    # Title — required; no title means we skip this item
    title = _str_or_none(raw.get("title"))
    if title is None:
        title = _str_or_none(content.get("title"))
    if title is None:
        return None

    # Publisher
    publisher = _str_or_none(raw.get("publisher"))
    if publisher is None:
        provider = content.get("provider") or {}
        if isinstance(provider, dict):
            publisher = _str_or_none(provider.get("displayName"))

    # Link
    link = _str_or_none(raw.get("link"))
    if link is None:
        canonical = content.get("canonicalUrl") or {}
        if isinstance(canonical, dict):
            link = _str_or_none(canonical.get("url"))

    # Published at — Unix timestamp (int) → timezone-aware UTC datetime
    published_at: datetime | None = None
    ts = raw.get("providerPublishTime")
    if ts is not None:
        try:
            published_at = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        except (ValueError, TypeError, OSError):
            published_at = None

    # Summary
    summary = _str_or_none(raw.get("summary"))
    if summary is None:
        summary = _str_or_none(content.get("summary"))
    if summary is None:
        summary = _str_or_none(content.get("description"))

    # Related tickers
    related_raw = raw.get("relatedTickers")
    related_tickers = (
        [t for t in related_raw if isinstance(t, str)]
        if isinstance(related_raw, list)
        else []
    )

    return NewsItem(
        title=title,
        publisher=publisher,
        link=link,
        published_at=published_at,
        summary=summary,
        related_tickers=related_tickers,
    )


def _str_or_none(value: object) -> str | None:
    """Return the stripped string if non-empty, else None."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped if stripped else None
