"""
Tests for app/data/database.py — the watchlist id-reuse guard.

SQLite reuses the highest deleted rowid unless a table is declared
AUTOINCREMENT.  Snapshots deliberately outlive their watchlist, so a reused id
would hand a deleted watchlist's history to a new one.  These tests cover both
fresh databases and the one-time upgrade of a database created before the fix.
All databases are temporary files; no network access.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.engine import Connection

from app.data.database import build_engine
from app.services.watchlist_analysis_snapshot_service import (
    get_watchlist_snapshot,
    list_watchlist_snapshots,
)
from app.services.watchlist_service import create_watchlist, get_watchlist

# The watchlist schema exactly as metadata.create_all() emitted it before the
# fix: an INTEGER PRIMARY KEY without AUTOINCREMENT.
_LEGACY_SCHEMA = """
CREATE TABLE watchlists (
    id INTEGER NOT NULL,
    name VARCHAR NOT NULL,
    description VARCHAR,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id)
);
CREATE TABLE watchlist_tickers (
    id INTEGER NOT NULL,
    watchlist_id INTEGER NOT NULL,
    ticker VARCHAR NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_watchlist_ticker UNIQUE (watchlist_id, ticker),
    FOREIGN KEY(watchlist_id) REFERENCES watchlists (id)
);
CREATE TABLE watchlist_analysis_snapshots (
    id INTEGER NOT NULL,
    watchlist_id INTEGER NOT NULL,
    watchlist_name VARCHAR NOT NULL,
    analyzed_at DATETIME NOT NULL,
    total_tickers INTEGER NOT NULL,
    success_count INTEGER NOT NULL,
    failure_count INTEGER NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(watchlist_id) REFERENCES watchlists (id)
);
"""

_TS = "2026-01-01 00:00:00.000000"


def _table_sql(path: Path, name: str) -> str:
    with sqlite3.connect(path) as conn:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
    return row[0]


@pytest.fixture()
def legacy_db(tmp_path) -> Path:
    """A pre-fix database: watchlist 1 (with a ticker) is live, and a
    snapshot survives from watchlist 2, which was deleted."""
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(_LEGACY_SCHEMA)
        conn.execute(
            "INSERT INTO watchlists VALUES (1, 'Live', 'kept', ?, ?)", (_TS, _TS)
        )
        conn.execute(
            "INSERT INTO watchlist_tickers VALUES (1, 1, 'AAPL', ?)", (_TS,)
        )
        conn.execute(
            "INSERT INTO watchlist_analysis_snapshots "
            "VALUES (1, 2, 'Deleted', ?, 1, 1, 0, ?)",
            (_TS, _TS),
        )
    return path


class TestFreshDatabase:
    def test_watchlists_table_uses_autoincrement(self, tmp_path):
        path = tmp_path / "fresh.db"
        build_engine(path)
        assert "AUTOINCREMENT" in _table_sql(path, "watchlists").upper()


class TestLegacyDatabaseUpgrade:
    def test_upgrades_watchlists_table_to_autoincrement(self, legacy_db):
        assert "AUTOINCREMENT" not in _table_sql(legacy_db, "watchlists").upper()
        build_engine(legacy_db)
        assert "AUTOINCREMENT" in _table_sql(legacy_db, "watchlists").upper()

    def test_preserves_existing_watchlists_and_tickers(self, legacy_db):
        engine = build_engine(legacy_db)
        detail = get_watchlist(1, engine=engine)
        assert detail["name"] == "Live"
        assert detail["description"] == "kept"
        assert detail["tickers"] == ["AAPL"]

    def test_new_watchlist_skips_orphaned_snapshot_ids(self, legacy_db):
        engine = build_engine(legacy_db)

        created = create_watchlist("New", engine=engine)

        # Plain rowid would give 2 — the deleted watchlist's id.
        assert created["id"] == 3
        assert list_watchlist_snapshots(created["id"], engine=engine) == []
        assert get_watchlist_snapshot(1, engine=engine)["watchlist_id"] == 2

    def test_upgrade_is_idempotent(self, legacy_db):
        build_engine(legacy_db)
        engine = build_engine(legacy_db)
        assert get_watchlist(1, engine=engine)["tickers"] == ["AAPL"]
        assert create_watchlist("New", engine=engine)["id"] == 3

    def test_upgrades_empty_legacy_table(self, tmp_path):
        path = tmp_path / "empty.db"
        with sqlite3.connect(path) as conn:
            conn.executescript(_LEGACY_SCHEMA)
        engine = build_engine(path)
        assert create_watchlist("First", engine=engine)["id"] == 1

    def test_failed_upgrade_rolls_back_and_retry_succeeds(self, legacy_db):
        real_exec = Connection.exec_driver_sql

        def _fail_on_rename(self, statement, *args, **kwargs):
            if statement.startswith("ALTER TABLE"):
                raise RuntimeError("simulated crash after DROP TABLE")
            return real_exec(self, statement, *args, **kwargs)

        with patch.object(Connection, "exec_driver_sql", _fail_on_rename):
            with pytest.raises(RuntimeError):
                build_engine(legacy_db)

        # The DROP was rolled back: the legacy table and its row survive.
        assert "AUTOINCREMENT" not in _table_sql(legacy_db, "watchlists").upper()
        engine = build_engine(legacy_db)
        assert get_watchlist(1, engine=engine)["name"] == "Live"
        assert create_watchlist("New", engine=engine)["id"] == 3

    def test_clears_leftover_rebuild_table(self, legacy_db):
        with sqlite3.connect(legacy_db) as conn:
            conn.execute(
                "CREATE TABLE watchlists_autoincrement_rebuild (id INTEGER)"
            )
        engine = build_engine(legacy_db)
        assert get_watchlist(1, engine=engine)["tickers"] == ["AAPL"]
        with sqlite3.connect(legacy_db) as conn:
            leftover = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE name='watchlists_autoincrement_rebuild'"
            ).fetchone()
        assert leftover is None


class TestConcurrentEngineBuild:
    def test_parallel_first_builds_do_not_race_on_create_table(self, tmp_path):
        # Each persistence service lazily builds its own engine and API
        # handlers run in a threadpool, so first requests can arrive together.
        path = tmp_path / "fresh.db"
        errors: list[Exception] = []

        def _build() -> None:
            try:
                build_engine(path)
            except Exception as exc:  # noqa: BLE001 — collected for the assert
                errors.append(exc)

        threads = [threading.Thread(target=_build) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert errors == []
