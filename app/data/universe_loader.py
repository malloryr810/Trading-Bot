"""
Stock universe loader.

Loads the controlled, static ticker universes that the discovery engine screens.
Universe files are plain CSV committed to the repository under
``app/data/universes/`` — nothing is scraped or fetched over the network here,
and no analysis or scoring happens in this module.

Public API::

    list_universes()          -> list[UniverseInfo]
    load_universe(key)        -> tuple[UniverseEntry, ...]
    load_universe_file(path)  -> tuple[UniverseEntry, ...]

Adding a universe later (S&P 500, Nasdaq 100, a sector list, …) means dropping a
new CSV next to the starter file and registering it in ``_UNIVERSES``.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from app.models.universe import UniverseEntry, UniverseInfo
from app.utils.helpers import normalize_ticker

UNIVERSE_DIR: Path = Path(__file__).resolve().parent / "universes"

# Only ``ticker`` is required; company_name / sector / industry are read
# opportunistically per row and default to None when absent.
REQUIRED_COLUMNS: tuple[str, ...] = ("ticker",)

STARTER_LARGE_CAP = "starter_large_cap"


class UniverseLoadError(Exception):
    """Raised when a universe file is missing, malformed, or has duplicate tickers."""


class UnknownUniverseError(UniverseLoadError):
    """Raised when a universe key is not registered."""


# Registered universes: key -> (filename, display name, description).
# Only the starter universe exists today; the registry exists so additional
# universes can be added without touching the loading logic.
_UNIVERSES: dict[str, tuple[str, str, str]] = {
    STARTER_LARGE_CAP: (
        "starter_large_cap.csv",
        "Starter large cap (US)",
        "A small, hand-maintained set of liquid large-cap U.S. equities used as "
        "the default discovery universe. Static and versioned in the repository.",
    ),
}


def available_universe_keys() -> tuple[str, ...]:
    """Return the registered universe keys, sorted for deterministic output."""
    return tuple(sorted(_UNIVERSES))


def list_universes() -> list[UniverseInfo]:
    """Return metadata for every registered universe, including its size.

    Returns:
        List of UniverseInfo, sorted by key.

    Raises:
        UniverseLoadError: If a registered universe file cannot be read.
    """
    return [
        UniverseInfo(
            key=key,
            name=_UNIVERSES[key][1],
            description=_UNIVERSES[key][2],
            size=len(load_universe(key)),
        )
        for key in available_universe_keys()
    ]


def load_universe(key: str) -> tuple[UniverseEntry, ...]:
    """Load a registered universe by key.

    Results are cached: universe files are static repository data, so a single
    parse per process is enough.

    Args:
        key: Registered universe key (e.g. ``"starter_large_cap"``).

    Returns:
        Immutable tuple of UniverseEntry in file order.

    Raises:
        UnknownUniverseError: If the key is not registered.
        UniverseLoadError: If the file is missing, malformed, or has duplicates.
    """
    normalized = key.strip().lower() if isinstance(key, str) else ""
    if normalized not in _UNIVERSES:
        raise UnknownUniverseError(
            f"Unknown universe {key!r}. Available universes: "
            f"{list(available_universe_keys())}."
        )
    return _load_cached(normalized)


def load_universe_file(path: Path | str) -> tuple[UniverseEntry, ...]:
    """Parse and validate a universe CSV file.

    Args:
        path: Path to a CSV file with a ``ticker`` column and optional
            ``company_name``, ``sector``, and ``industry`` columns.

    Returns:
        Immutable tuple of UniverseEntry in file order.

    Raises:
        UniverseLoadError: If the file is missing, has no ``ticker`` column,
            contains an invalid ticker, has duplicate tickers, or is empty.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise UniverseLoadError(f"Universe file not found: {file_path}.")

    try:
        with file_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = [name.strip() for name in (reader.fieldnames or [])]
            rows = list(reader)
    except OSError as exc:
        raise UniverseLoadError(f"Could not read universe file {file_path}: {exc}") from exc

    missing = [col for col in REQUIRED_COLUMNS if col not in fieldnames]
    if missing:
        raise UniverseLoadError(
            f"Universe file {file_path} is missing required column(s): {missing}. "
            f"Columns present: {sorted(fieldnames)}."
        )

    entries: list[UniverseEntry] = []
    seen: set[str] = set()

    for line_number, row in enumerate(rows, start=2):  # start=2 accounts for the header
        raw_ticker = (row.get("ticker") or "").strip()
        if not raw_ticker:
            continue  # tolerate blank padding rows
        try:
            ticker = normalize_ticker(raw_ticker)
        except ValueError as exc:
            raise UniverseLoadError(
                f"Invalid ticker on line {line_number} of {file_path}: {exc}"
            ) from exc
        if ticker in seen:
            raise UniverseLoadError(
                f"Duplicate ticker {ticker!r} on line {line_number} of {file_path}. "
                "Universe tickers must be unique."
            )
        seen.add(ticker)
        entries.append(
            UniverseEntry(
                ticker=ticker,
                company_name=row.get("company_name"),
                sector=row.get("sector"),
                industry=row.get("industry"),
            )
        )

    if not entries:
        raise UniverseLoadError(f"Universe file {file_path} contains no tickers.")

    return tuple(entries)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _load_cached(key: str) -> tuple[UniverseEntry, ...]:
    """Load and cache a registered universe. Keyed by an already-validated key."""
    return load_universe_file(UNIVERSE_DIR / _UNIVERSES[key][0])
