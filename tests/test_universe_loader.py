"""
Tests for app/data/universe_loader.py.

All tests read either the committed starter universe file or a CSV written into
tmp_path. No network calls and no dependency on provider data.
"""

from __future__ import annotations

import pytest

from app.data.universe_loader import (
    STARTER_LARGE_CAP,
    UniverseLoadError,
    UnknownUniverseError,
    available_universe_keys,
    list_universes,
    load_universe,
    load_universe_file,
)


def _write_csv(tmp_path, rows: str, header: str = "ticker,company_name,sector,industry"):
    path = tmp_path / "universe.csv"
    path.write_text(f"{header}\n{rows}", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Starter universe
# ---------------------------------------------------------------------------


class TestStarterUniverse:
    def test_loads_entries(self):
        assert len(load_universe(STARTER_LARGE_CAP)) > 0

    def test_entries_are_meaningfully_sized(self):
        # Enough names for discovery to be useful, small enough to stay bounded.
        assert 20 <= len(load_universe(STARTER_LARGE_CAP)) <= 200

    def test_all_tickers_are_unique(self):
        tickers = [entry.ticker for entry in load_universe(STARTER_LARGE_CAP)]
        assert len(tickers) == len(set(tickers))

    def test_all_tickers_are_normalized(self):
        for entry in load_universe(STARTER_LARGE_CAP):
            assert entry.ticker == entry.ticker.strip().upper()
            assert entry.ticker

    def test_entries_carry_sector_metadata(self):
        for entry in load_universe(STARTER_LARGE_CAP):
            assert entry.company_name
            assert entry.sector

    def test_repeat_loads_return_same_entries(self):
        assert load_universe(STARTER_LARGE_CAP) == load_universe(STARTER_LARGE_CAP)

    def test_key_is_case_insensitive(self):
        assert load_universe("STARTER_LARGE_CAP") == load_universe(STARTER_LARGE_CAP)


class TestUniverseRegistry:
    def test_starter_universe_is_registered(self):
        assert STARTER_LARGE_CAP in available_universe_keys()

    def test_list_universes_reports_size(self):
        infos = list_universes()
        starter = next(info for info in infos if info.key == STARTER_LARGE_CAP)
        assert starter.size == len(load_universe(STARTER_LARGE_CAP))

    def test_list_universes_includes_name_and_description(self):
        for info in list_universes():
            assert info.name
            assert info.description

    def test_unknown_universe_raises(self):
        with pytest.raises(UnknownUniverseError):
            load_universe("sp500")

    def test_unknown_universe_error_is_a_load_error(self):
        with pytest.raises(UniverseLoadError):
            load_universe("does-not-exist")

    def test_empty_key_raises(self):
        with pytest.raises(UnknownUniverseError):
            load_universe("")


# ---------------------------------------------------------------------------
# File parsing
# ---------------------------------------------------------------------------


class TestLoadUniverseFile:
    def test_parses_rows(self, tmp_path):
        path = _write_csv(tmp_path, "AAPL,Apple Inc.,Technology,Consumer Electronics\n")
        entries = load_universe_file(path)
        assert len(entries) == 1
        assert entries[0].ticker == "AAPL"
        assert entries[0].company_name == "Apple Inc."
        assert entries[0].sector == "Technology"
        assert entries[0].industry == "Consumer Electronics"

    def test_normalizes_ticker_case_and_whitespace(self, tmp_path):
        path = _write_csv(tmp_path, "  msft ,Microsoft,Technology,Software\n")
        assert load_universe_file(path)[0].ticker == "MSFT"

    def test_preserves_file_order(self, tmp_path):
        path = _write_csv(tmp_path, "MSFT,,,\nAAPL,,,\nNVDA,,,\n")
        assert [e.ticker for e in load_universe_file(path)] == ["MSFT", "AAPL", "NVDA"]

    def test_duplicate_ticker_raises(self, tmp_path):
        path = _write_csv(tmp_path, "AAPL,Apple,Technology,X\nAAPL,Apple,Technology,X\n")
        with pytest.raises(UniverseLoadError, match="Duplicate ticker"):
            load_universe_file(path)

    def test_duplicate_detection_is_case_insensitive(self, tmp_path):
        path = _write_csv(tmp_path, "AAPL,,,\naapl,,,\n")
        with pytest.raises(UniverseLoadError, match="Duplicate ticker"):
            load_universe_file(path)

    def test_blank_rows_are_skipped(self, tmp_path):
        path = _write_csv(tmp_path, "AAPL,,,\n,,,\nMSFT,,,\n")
        assert [e.ticker for e in load_universe_file(path)] == ["AAPL", "MSFT"]

    def test_blank_optional_fields_become_none(self, tmp_path):
        path = _write_csv(tmp_path, "AAPL,, ,\n")
        entry = load_universe_file(path)[0]
        assert entry.company_name is None
        assert entry.sector is None
        assert entry.industry is None

    def test_missing_ticker_column_raises(self, tmp_path):
        path = _write_csv(tmp_path, "Apple,Technology\n", header="company_name,sector")
        with pytest.raises(UniverseLoadError, match="missing required column"):
            load_universe_file(path)

    def test_file_with_no_tickers_raises(self, tmp_path):
        path = _write_csv(tmp_path, "")
        with pytest.raises(UniverseLoadError, match="contains no tickers"):
            load_universe_file(path)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(UniverseLoadError, match="not found"):
            load_universe_file(tmp_path / "nope.csv")

    def test_ticker_only_file_is_valid(self, tmp_path):
        path = _write_csv(tmp_path, "AAPL\nMSFT\n", header="ticker")
        assert [e.ticker for e in load_universe_file(path)] == ["AAPL", "MSFT"]
