"""
Unit tests for app/data/news_data.py.

All tests mock yfinance so no network calls are made.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.data.news_data import NewsFetchError, get_recent_news
from app.models.news import NewsItem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_raw_item(**overrides) -> dict:
    """Return a realistic raw yfinance news dict with optional field overrides."""
    defaults: dict = {
        "uuid": "abc-123",
        "title": "Apple Reports Record Earnings",
        "publisher": "Reuters",
        "link": "https://example.com/article",
        "providerPublishTime": 1_716_320_000,
        "type": "STORY",
        "relatedTickers": ["AAPL", "MSFT"],
    }
    defaults.update(overrides)
    return defaults


TICKER_PATH = "app.data.news_data.yf.Ticker"


def _mock_ticker(news: list):
    """Return a patch context manager that makes yf.Ticker(...).news return news."""
    mock = MagicMock()
    mock.return_value.news = news
    return patch(TICKER_PATH, mock)


# ---------------------------------------------------------------------------
# Return type and structure
# ---------------------------------------------------------------------------

class TestReturnType:
    def test_returns_a_list(self):
        with _mock_ticker([_make_raw_item()]):
            result = get_recent_news("AAPL")
        assert isinstance(result, list)

    def test_list_contains_news_items(self):
        with _mock_ticker([_make_raw_item()]):
            result = get_recent_news("AAPL")
        assert all(isinstance(item, NewsItem) for item in result)

    def test_single_item_returned(self):
        with _mock_ticker([_make_raw_item()]):
            result = get_recent_news("AAPL")
        assert len(result) == 1

    def test_multiple_items_returned(self):
        raw = [_make_raw_item(title=f"Headline {i}") for i in range(3)]
        with _mock_ticker(raw):
            result = get_recent_news("AAPL")
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Field mapping — successful fetch
# ---------------------------------------------------------------------------

class TestFieldMapping:
    def _fetch_one(self, **overrides) -> NewsItem:
        with _mock_ticker([_make_raw_item(**overrides)]):
            return get_recent_news("AAPL")[0]

    def test_title_populated(self):
        assert self._fetch_one().title == "Apple Reports Record Earnings"

    def test_publisher_populated(self):
        assert self._fetch_one().publisher == "Reuters"

    def test_link_populated(self):
        assert self._fetch_one().link == "https://example.com/article"

    def test_published_at_populated(self):
        assert self._fetch_one().published_at is not None

    def test_related_tickers_populated(self):
        assert self._fetch_one().related_tickers == ["AAPL", "MSFT"]


# ---------------------------------------------------------------------------
# Ticker normalization
# ---------------------------------------------------------------------------

class TestTickerNormalization:
    def test_lowercase_ticker_normalized_to_uppercase(self):
        mock = MagicMock()
        mock.return_value.news = [_make_raw_item()]
        with patch(TICKER_PATH, mock):
            get_recent_news("aapl")
        mock.assert_called_once_with("AAPL")

    def test_whitespace_stripped_before_calling_yfinance(self):
        mock = MagicMock()
        mock.return_value.news = [_make_raw_item()]
        with patch(TICKER_PATH, mock):
            get_recent_news("  aapl  ")
        mock.assert_called_once_with("AAPL")

    def test_mixed_case_normalized(self):
        mock = MagicMock()
        mock.return_value.news = [_make_raw_item()]
        with patch(TICKER_PATH, mock):
            get_recent_news("AaPl")
        mock.assert_called_once_with("AAPL")


# ---------------------------------------------------------------------------
# Limit behavior
# ---------------------------------------------------------------------------

class TestLimitBehavior:
    def test_limit_caps_returned_items(self):
        raw = [_make_raw_item(title=f"Headline {i}") for i in range(10)]
        with _mock_ticker(raw):
            result = get_recent_news("AAPL", limit=3)
        assert len(result) == 3

    def test_limit_of_one_returns_one_item(self):
        raw = [_make_raw_item(title=f"Headline {i}") for i in range(5)]
        with _mock_ticker(raw):
            result = get_recent_news("AAPL", limit=1)
        assert len(result) == 1

    def test_limit_larger_than_available_returns_all(self):
        raw = [_make_raw_item(title=f"Headline {i}") for i in range(2)]
        with _mock_ticker(raw):
            result = get_recent_news("AAPL", limit=10)
        assert len(result) == 2

    def test_default_limit_is_ten(self):
        raw = [_make_raw_item(title=f"Headline {i}") for i in range(15)]
        with _mock_ticker(raw):
            result = get_recent_news("AAPL")
        assert len(result) == 10


# ---------------------------------------------------------------------------
# Empty news
# ---------------------------------------------------------------------------

class TestEmptyNews:
    def test_empty_list_from_yfinance_returns_empty_list(self):
        with _mock_ticker([]):
            result = get_recent_news("AAPL")
        assert result == []

    def test_none_from_yfinance_returns_empty_list(self):
        mock = MagicMock()
        mock.return_value.news = None
        with patch(TICKER_PATH, mock):
            result = get_recent_news("AAPL")
        assert result == []


# ---------------------------------------------------------------------------
# Ticker input validation
# ---------------------------------------------------------------------------

class TestTickerValidation:
    def test_empty_string_raises(self):
        with pytest.raises(NewsFetchError):
            get_recent_news("")

    def test_whitespace_only_raises(self):
        with pytest.raises(NewsFetchError):
            get_recent_news("   ")

    def test_non_string_int_raises(self):
        with pytest.raises(NewsFetchError):
            get_recent_news(123)  # type: ignore[arg-type]

    def test_non_string_none_raises(self):
        with pytest.raises(NewsFetchError):
            get_recent_news(None)  # type: ignore[arg-type]

    def test_error_message_mentions_ticker_type(self):
        with pytest.raises(NewsFetchError, match="string"):
            get_recent_news(42)  # type: ignore[arg-type]

    def test_error_message_for_empty_ticker(self):
        with pytest.raises(NewsFetchError, match="empty"):
            get_recent_news("")


# ---------------------------------------------------------------------------
# Limit input validation
# ---------------------------------------------------------------------------

class TestLimitValidation:
    def test_zero_limit_raises(self):
        with pytest.raises(NewsFetchError):
            get_recent_news("AAPL", limit=0)

    def test_negative_limit_raises(self):
        with pytest.raises(NewsFetchError):
            get_recent_news("AAPL", limit=-1)

    def test_float_limit_raises(self):
        with pytest.raises(NewsFetchError):
            get_recent_news("AAPL", limit=5.0)  # type: ignore[arg-type]

    def test_string_limit_raises(self):
        with pytest.raises(NewsFetchError):
            get_recent_news("AAPL", limit="10")  # type: ignore[arg-type]

    def test_none_limit_raises(self):
        with pytest.raises(NewsFetchError):
            get_recent_news("AAPL", limit=None)  # type: ignore[arg-type]

    def test_bool_limit_raises(self):
        with pytest.raises(NewsFetchError):
            get_recent_news("AAPL", limit=True)  # type: ignore[arg-type]

    def test_positive_int_limit_is_valid(self):
        with _mock_ticker([_make_raw_item()]):
            result = get_recent_news("AAPL", limit=1)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# yfinance error handling
# ---------------------------------------------------------------------------

class TestYfinanceErrors:
    def test_yfinance_exception_wrapped_in_fetch_error(self):
        with patch(TICKER_PATH, side_effect=Exception("network timeout")):
            with pytest.raises(NewsFetchError, match="yfinance raised an error"):
                get_recent_news("AAPL")

    def test_yfinance_value_error_wrapped(self):
        with patch(TICKER_PATH, side_effect=ValueError("bad response")):
            with pytest.raises(NewsFetchError):
                get_recent_news("AAPL")

    def test_error_message_includes_symbol(self):
        with patch(TICKER_PATH, side_effect=Exception("timeout")):
            with pytest.raises(NewsFetchError, match="AAPL"):
                get_recent_news("AAPL")


# ---------------------------------------------------------------------------
# Malformed items — skip without title
# ---------------------------------------------------------------------------

class TestMalformedItems:
    def test_item_missing_title_is_skipped(self):
        raw = [{"publisher": "Reuters", "link": "https://example.com"}]
        with _mock_ticker(raw):
            result = get_recent_news("AAPL")
        assert result == []

    def test_item_with_empty_string_title_is_skipped(self):
        raw = [_make_raw_item(title="")]
        with _mock_ticker(raw):
            result = get_recent_news("AAPL")
        assert result == []

    def test_item_with_whitespace_only_title_is_skipped(self):
        raw = [_make_raw_item(title="   ")]
        with _mock_ticker(raw):
            result = get_recent_news("AAPL")
        assert result == []

    def test_non_dict_item_is_skipped(self):
        raw = ["not a dict", None, 42]
        with _mock_ticker(raw):
            result = get_recent_news("AAPL")
        assert result == []

    def test_mix_of_valid_and_invalid_items(self):
        raw = [
            {"publisher": "Reuters"},          # no title — skip
            _make_raw_item(title="Good headline"),
            _make_raw_item(title=""),           # empty title — skip
            _make_raw_item(title="Also good"),
        ]
        with _mock_ticker(raw):
            result = get_recent_news("AAPL")
        assert len(result) == 2
        assert result[0].title == "Good headline"
        assert result[1].title == "Also good"

    def test_all_malformed_returns_empty_list(self):
        raw = [{"uuid": "x"}, {"uuid": "y"}]
        with _mock_ticker(raw):
            result = get_recent_news("AAPL")
        assert result == []


# ---------------------------------------------------------------------------
# Timestamp conversion
# ---------------------------------------------------------------------------

class TestTimestampConversion:
    def test_unix_timestamp_converted_to_datetime(self):
        with _mock_ticker([_make_raw_item(providerPublishTime=1_716_320_000)]):
            result = get_recent_news("AAPL")
        assert isinstance(result[0].published_at, datetime)

    def test_published_at_is_utc(self):
        with _mock_ticker([_make_raw_item(providerPublishTime=1_716_320_000)]):
            result = get_recent_news("AAPL")
        assert result[0].published_at.tzinfo == timezone.utc

    def test_known_timestamp_value(self):
        expected = datetime.fromtimestamp(1_716_320_000, tz=timezone.utc)
        with _mock_ticker([_make_raw_item(providerPublishTime=1_716_320_000)]):
            result = get_recent_news("AAPL")
        assert result[0].published_at == expected

    def test_missing_timestamp_gives_none(self):
        raw = _make_raw_item()
        del raw["providerPublishTime"]
        with _mock_ticker([raw]):
            result = get_recent_news("AAPL")
        assert result[0].published_at is None

    def test_none_timestamp_gives_none(self):
        with _mock_ticker([_make_raw_item(providerPublishTime=None)]):
            result = get_recent_news("AAPL")
        assert result[0].published_at is None

    def test_invalid_timestamp_string_gives_none(self):
        with _mock_ticker([_make_raw_item(providerPublishTime="not-a-number")]):
            result = get_recent_news("AAPL")
        assert result[0].published_at is None


# ---------------------------------------------------------------------------
# Optional fields — missing or None does not crash
# ---------------------------------------------------------------------------

class TestOptionalFields:
    def _fetch_minimal(self) -> NewsItem:
        with _mock_ticker([{"title": "Minimal headline"}]):
            return get_recent_news("AAPL")[0]

    def test_missing_publisher_is_none(self):
        assert self._fetch_minimal().publisher is None

    def test_missing_link_is_none(self):
        assert self._fetch_minimal().link is None

    def test_missing_published_at_is_none(self):
        assert self._fetch_minimal().published_at is None

    def test_missing_summary_is_none(self):
        assert self._fetch_minimal().summary is None

    def test_empty_string_publisher_becomes_none(self):
        with _mock_ticker([_make_raw_item(publisher="")]):
            result = get_recent_news("AAPL")
        assert result[0].publisher is None

    def test_empty_string_link_becomes_none(self):
        with _mock_ticker([_make_raw_item(link="")]):
            result = get_recent_news("AAPL")
        assert result[0].link is None

    def test_summary_field_populated_when_present(self):
        with _mock_ticker([_make_raw_item(summary="A brief summary of the article.")]):
            result = get_recent_news("AAPL")
        assert result[0].summary == "A brief summary of the article."

    def test_none_publisher_is_none(self):
        with _mock_ticker([_make_raw_item(publisher=None)]):
            result = get_recent_news("AAPL")
        assert result[0].publisher is None


# ---------------------------------------------------------------------------
# Related tickers
# ---------------------------------------------------------------------------

class TestRelatedTickers:
    def test_related_tickers_populated_from_raw(self):
        with _mock_ticker([_make_raw_item(relatedTickers=["AAPL", "GOOG"])]):
            result = get_recent_news("AAPL")
        assert result[0].related_tickers == ["AAPL", "GOOG"]

    def test_missing_related_tickers_defaults_to_empty_list(self):
        raw = _make_raw_item()
        del raw["relatedTickers"]
        with _mock_ticker([raw]):
            result = get_recent_news("AAPL")
        assert result[0].related_tickers == []

    def test_none_related_tickers_defaults_to_empty_list(self):
        with _mock_ticker([_make_raw_item(relatedTickers=None)]):
            result = get_recent_news("AAPL")
        assert result[0].related_tickers == []

    def test_non_string_entries_in_related_tickers_filtered_out(self):
        with _mock_ticker([_make_raw_item(relatedTickers=["AAPL", 42, None, "MSFT"])]):
            result = get_recent_news("AAPL")
        assert result[0].related_tickers == ["AAPL", "MSFT"]


# ---------------------------------------------------------------------------
# Nested content fallback (newer yfinance format)
# ---------------------------------------------------------------------------

class TestNestedContentFallback:
    def test_title_falls_back_to_nested_content(self):
        raw = {
            "content": {
                "title": "Nested headline",
                "provider": {"displayName": "Bloomberg"},
                "canonicalUrl": {"url": "https://bloomberg.com/article"},
                "summary": "Nested summary",
            }
        }
        with _mock_ticker([raw]):
            result = get_recent_news("AAPL")
        assert len(result) == 1
        assert result[0].title == "Nested headline"

    def test_publisher_falls_back_to_nested_provider(self):
        raw = {
            "title": "Top-level title",
            "content": {
                "provider": {"displayName": "Bloomberg"},
            },
        }
        with _mock_ticker([raw]):
            result = get_recent_news("AAPL")
        assert result[0].publisher == "Bloomberg"

    def test_link_falls_back_to_nested_canonical_url(self):
        raw = {
            "title": "Top-level title",
            "content": {
                "canonicalUrl": {"url": "https://bloomberg.com/article"},
            },
        }
        with _mock_ticker([raw]):
            result = get_recent_news("AAPL")
        assert result[0].link == "https://bloomberg.com/article"

    def test_summary_falls_back_to_nested_content(self):
        raw = {
            "title": "Top-level title",
            "content": {"summary": "Nested summary text."},
        }
        with _mock_ticker([raw]):
            result = get_recent_news("AAPL")
        assert result[0].summary == "Nested summary text."

    def test_top_level_fields_take_precedence_over_nested(self):
        raw = {
            "title": "Top-level title",
            "publisher": "Reuters",
            "link": "https://reuters.com/article",
            "content": {
                "title": "Nested title",
                "provider": {"displayName": "Bloomberg"},
                "canonicalUrl": {"url": "https://bloomberg.com/article"},
            },
        }
        with _mock_ticker([raw]):
            result = get_recent_news("AAPL")
        assert result[0].title == "Top-level title"
        assert result[0].publisher == "Reuters"
        assert result[0].link == "https://reuters.com/article"
