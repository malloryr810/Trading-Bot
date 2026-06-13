"""
Tests for app/services/watchlist_service.py.

Uses a temporary SQLite database via the ``engine`` fixture — no writes to the
real project database.  All inputs are built locally; no live API calls.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from app.data.database import build_engine, watchlist_tickers
from app.services.watchlist_service import (
    WatchlistNotFoundError,
    WatchlistValidationError,
    add_ticker_to_watchlist,
    create_watchlist,
    delete_watchlist,
    get_watchlist,
    list_watchlists,
    remove_ticker_from_watchlist,
    update_watchlist,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine(tmp_path) -> Engine:
    return build_engine(tmp_path / "test.db")


# ---------------------------------------------------------------------------
# create_watchlist
# ---------------------------------------------------------------------------


class TestCreateWatchlist:
    def test_returns_dict(self, engine):
        result = create_watchlist("Tech", engine=engine)
        assert isinstance(result, dict)

    def test_stores_name(self, engine):
        result = create_watchlist("Tech", engine=engine)
        assert result["name"] == "Tech"

    def test_strips_name(self, engine):
        result = create_watchlist("  Tech  ", engine=engine)
        assert result["name"] == "Tech"

    def test_stores_description(self, engine):
        result = create_watchlist("Tech", "Big tech names", engine=engine)
        assert result["description"] == "Big tech names"

    def test_description_defaults_to_none(self, engine):
        result = create_watchlist("Tech", engine=engine)
        assert result["description"] is None

    def test_blank_description_normalized_to_none(self, engine):
        result = create_watchlist("Tech", "   ", engine=engine)
        assert result["description"] is None

    def test_id_is_positive_integer(self, engine):
        result = create_watchlist("Tech", engine=engine)
        assert isinstance(result["id"], int) and result["id"] > 0

    def test_timestamps_present(self, engine):
        result = create_watchlist("Tech", engine=engine)
        assert result["created_at"] is not None
        assert result["updated_at"] is not None

    def test_timestamps_are_utc_aware(self, engine):
        result = create_watchlist("Tech", engine=engine)
        assert result["created_at"].tzinfo is not None
        assert result["created_at"].utcoffset().total_seconds() == 0

    def test_tickers_start_empty(self, engine):
        result = create_watchlist("Tech", engine=engine)
        assert result["tickers"] == []

    def test_rejects_blank_name(self, engine):
        with pytest.raises(WatchlistValidationError):
            create_watchlist("   ", engine=engine)

    def test_rejects_empty_name(self, engine):
        with pytest.raises(WatchlistValidationError):
            create_watchlist("", engine=engine)


# ---------------------------------------------------------------------------
# list_watchlists
# ---------------------------------------------------------------------------


class TestListWatchlists:
    def test_returns_list(self, engine):
        assert isinstance(list_watchlists(engine=engine), list)

    def test_empty_when_none(self, engine):
        assert list_watchlists(engine=engine) == []

    def test_returns_created(self, engine):
        create_watchlist("Tech", engine=engine)
        create_watchlist("Energy", engine=engine)
        assert len(list_watchlists(engine=engine)) == 2

    def test_newest_first(self, engine):
        first = create_watchlist("Tech", engine=engine)
        second = create_watchlist("Energy", engine=engine)
        results = list_watchlists(engine=engine)
        assert results[0]["id"] == second["id"]
        assert results[1]["id"] == first["id"]

    def test_summary_has_ticker_count(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        add_ticker_to_watchlist(wl["id"], "AAPL", engine=engine)
        add_ticker_to_watchlist(wl["id"], "MSFT", engine=engine)
        assert list_watchlists(engine=engine)[0]["ticker_count"] == 2

    def test_summary_omits_full_ticker_list(self, engine):
        create_watchlist("Tech", engine=engine)
        assert "tickers" not in list_watchlists(engine=engine)[0]


# ---------------------------------------------------------------------------
# get_watchlist
# ---------------------------------------------------------------------------


class TestGetWatchlist:
    def test_returns_detail(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        result = get_watchlist(wl["id"], engine=engine)
        assert result["id"] == wl["id"]

    def test_includes_tickers(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        add_ticker_to_watchlist(wl["id"], "AAPL", engine=engine)
        result = get_watchlist(wl["id"], engine=engine)
        assert result["tickers"] == ["AAPL"]

    def test_tickers_in_insertion_order(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        add_ticker_to_watchlist(wl["id"], "AAPL", engine=engine)
        add_ticker_to_watchlist(wl["id"], "MSFT", engine=engine)
        add_ticker_to_watchlist(wl["id"], "NVDA", engine=engine)
        result = get_watchlist(wl["id"], engine=engine)
        assert result["tickers"] == ["AAPL", "MSFT", "NVDA"]

    def test_raises_not_found_for_missing(self, engine):
        with pytest.raises(WatchlistNotFoundError):
            get_watchlist(999, engine=engine)

    def test_not_found_is_lookup_error(self, engine):
        # WatchlistNotFoundError subclasses LookupError for broad catching.
        with pytest.raises(LookupError):
            get_watchlist(999, engine=engine)


# ---------------------------------------------------------------------------
# update_watchlist
# ---------------------------------------------------------------------------


class TestUpdateWatchlist:
    def test_changes_name(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        result = update_watchlist(wl["id"], name="Technology", engine=engine)
        assert result["name"] == "Technology"

    def test_changes_description(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        result = update_watchlist(wl["id"], description="Updated", engine=engine)
        assert result["description"] == "Updated"

    def test_clear_description_with_empty_string(self, engine):
        wl = create_watchlist("Tech", "original", engine=engine)
        result = update_watchlist(wl["id"], description="", engine=engine)
        assert result["description"] is None

    def test_partial_update_leaves_name(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        result = update_watchlist(wl["id"], description="x", engine=engine)
        assert result["name"] == "Tech"

    def test_advances_updated_at(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        result = update_watchlist(wl["id"], name="Technology", engine=engine)
        assert result["updated_at"] >= wl["updated_at"]

    def test_rejects_blank_name(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        with pytest.raises(WatchlistValidationError):
            update_watchlist(wl["id"], name="   ", engine=engine)

    def test_raises_not_found_for_missing(self, engine):
        with pytest.raises(WatchlistNotFoundError):
            update_watchlist(999, name="X", engine=engine)


# ---------------------------------------------------------------------------
# delete_watchlist
# ---------------------------------------------------------------------------


class TestDeleteWatchlist:
    def test_removes_watchlist(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        delete_watchlist(wl["id"], engine=engine)
        with pytest.raises(WatchlistNotFoundError):
            get_watchlist(wl["id"], engine=engine)

    def test_removes_associated_ticker_rows(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        add_ticker_to_watchlist(wl["id"], "AAPL", engine=engine)
        add_ticker_to_watchlist(wl["id"], "MSFT", engine=engine)
        delete_watchlist(wl["id"], engine=engine)
        with engine.connect() as conn:
            remaining = conn.execute(
                select(watchlist_tickers).where(
                    watchlist_tickers.c.watchlist_id == wl["id"]
                )
            ).all()
        assert remaining == []

    def test_raises_not_found_for_missing(self, engine):
        with pytest.raises(WatchlistNotFoundError):
            delete_watchlist(999, engine=engine)

    def test_does_not_affect_other_watchlists(self, engine):
        keep = create_watchlist("Keep", engine=engine)
        drop = create_watchlist("Drop", engine=engine)
        add_ticker_to_watchlist(keep["id"], "AAPL", engine=engine)
        delete_watchlist(drop["id"], engine=engine)
        assert get_watchlist(keep["id"], engine=engine)["tickers"] == ["AAPL"]


# ---------------------------------------------------------------------------
# add_ticker_to_watchlist
# ---------------------------------------------------------------------------


class TestAddTicker:
    def test_adds_ticker(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        result = add_ticker_to_watchlist(wl["id"], "AAPL", engine=engine)
        assert result["tickers"] == ["AAPL"]

    def test_normalizes_lowercase(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        result = add_ticker_to_watchlist(wl["id"], "aapl", engine=engine)
        assert result["tickers"] == ["AAPL"]

    def test_normalizes_whitespace(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        result = add_ticker_to_watchlist(wl["id"], "  msft  ", engine=engine)
        assert result["tickers"] == ["MSFT"]

    def test_rejects_blank_ticker(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        with pytest.raises(WatchlistValidationError):
            add_ticker_to_watchlist(wl["id"], "   ", engine=engine)

    def test_rejects_empty_ticker(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        with pytest.raises(WatchlistValidationError):
            add_ticker_to_watchlist(wl["id"], "", engine=engine)

    def test_rejects_nonexistent_watchlist(self, engine):
        with pytest.raises(WatchlistNotFoundError):
            add_ticker_to_watchlist(999, "AAPL", engine=engine)

    def test_does_not_create_watchlist_on_missing(self, engine):
        with pytest.raises(WatchlistNotFoundError):
            add_ticker_to_watchlist(999, "AAPL", engine=engine)
        assert list_watchlists(engine=engine) == []

    def test_duplicate_add_no_duplicate_row(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        add_ticker_to_watchlist(wl["id"], "AAPL", engine=engine)
        result = add_ticker_to_watchlist(wl["id"], "AAPL", engine=engine)
        assert result["tickers"] == ["AAPL"]

    def test_duplicate_add_case_insensitive(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        add_ticker_to_watchlist(wl["id"], "AAPL", engine=engine)
        result = add_ticker_to_watchlist(wl["id"], "aapl", engine=engine)
        assert result["tickers"] == ["AAPL"]

    def test_advances_updated_at(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        result = add_ticker_to_watchlist(wl["id"], "AAPL", engine=engine)
        assert result["updated_at"] >= wl["updated_at"]


# ---------------------------------------------------------------------------
# remove_ticker_from_watchlist
# ---------------------------------------------------------------------------


class TestRemoveTicker:
    def test_removes_ticker(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        add_ticker_to_watchlist(wl["id"], "AAPL", engine=engine)
        result = remove_ticker_from_watchlist(wl["id"], "AAPL", engine=engine)
        assert result["tickers"] == []

    def test_normalizes_input(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        add_ticker_to_watchlist(wl["id"], "AAPL", engine=engine)
        result = remove_ticker_from_watchlist(wl["id"], "  aapl ", engine=engine)
        assert result["tickers"] == []

    def test_leaves_other_tickers(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        add_ticker_to_watchlist(wl["id"], "AAPL", engine=engine)
        add_ticker_to_watchlist(wl["id"], "MSFT", engine=engine)
        result = remove_ticker_from_watchlist(wl["id"], "AAPL", engine=engine)
        assert result["tickers"] == ["MSFT"]

    def test_missing_ticker_is_idempotent(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        add_ticker_to_watchlist(wl["id"], "AAPL", engine=engine)
        # Removing a ticker that is not present is a no-op, not an error.
        result = remove_ticker_from_watchlist(wl["id"], "MSFT", engine=engine)
        assert result["tickers"] == ["AAPL"]

    def test_rejects_blank_ticker(self, engine):
        wl = create_watchlist("Tech", engine=engine)
        with pytest.raises(WatchlistValidationError):
            remove_ticker_from_watchlist(wl["id"], "  ", engine=engine)

    def test_rejects_nonexistent_watchlist(self, engine):
        with pytest.raises(WatchlistNotFoundError):
            remove_ticker_from_watchlist(999, "AAPL", engine=engine)
