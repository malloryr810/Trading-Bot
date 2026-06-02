"""
SQLite persistence layer — table schema and engine factory.

Uses SQLAlchemy Core (no ORM). The ``analysis_reports`` table stores a full
JSON snapshot of each StockReport alongside indexed summary columns so the
history endpoint can query without unpacking the full JSON blob.

Usage::

    from app.data.database import build_engine, analysis_reports

    engine = build_engine()           # production (data/investment_bot.db)
    engine = build_engine(":memory:") # in-memory (tests)
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Column, DateTime, Float, Integer, MetaData, String, Table, Text, create_engine
from sqlalchemy.engine import Engine

metadata = MetaData()

analysis_reports = Table(
    "analysis_reports",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ticker", String, nullable=False),
    Column("company_name", String, nullable=True),
    Column("category", String, nullable=False),
    Column("score", Float, nullable=False),
    Column("confidence", String, nullable=False),
    Column("report_json", Text, nullable=False),
    Column("created_at", DateTime, nullable=False),
)


def build_engine(db_path: Path | str | None = None) -> Engine:
    """Create a SQLite engine and ensure the schema exists.

    Args:
        db_path: Path to the SQLite file, or ``":memory:"`` for an in-memory
            database.  Defaults to the value of ``DATABASE_PATH`` in config
            (``data/investment_bot.db`` unless overridden by the environment).

    Returns:
        A configured :class:`Engine` with the ``analysis_reports`` table created.
    """
    if db_path is None:
        from app.config import DATABASE_PATH
        db_path = DATABASE_PATH

    if str(db_path) == ":memory:":
        url = "sqlite:///:memory:"
    else:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{path}"

    engine = create_engine(url, connect_args={"check_same_thread": False})
    metadata.create_all(engine)
    return engine
