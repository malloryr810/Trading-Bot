"""
Stock discovery service.

Turns a controlled ticker universe into a ranked, explainable shortlist of
research candidates. This is the discovery layer built *around* the existing
analysis engine — it introduces no new scoring, weights, thresholds, or
categories, and it never trades, saves, or schedules anything.

Pipeline::

    universe file  ->  stage-1 pre-screen  ->  bounded shortlist
                   ->  existing analyze_stock_rating pipeline
                   ->  mode ranking  ->  DiscoveryRun

Bounding rules (deliberate, because every analyzed ticker costs provider calls):
    * ``max_full_analysis`` caps how many tickers reach the full pipeline.
    * The pre-screen stops as soon as the shortlist is full.
    * ``limit`` caps how many ranked results are returned and can never exceed
      ``max_full_analysis``.

Failure tolerance: a ticker that fails the pre-screen or the analysis pipeline
is recorded as a ``DiscoveryWarning`` and skipped. A run only fails outright on
invalid parameters or an unloadable universe.

Results are rule-based research candidates, not financial advice.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from app.data.universe_loader import (
    STARTER_LARGE_CAP,
    UniverseLoadError,
    list_universes,
    load_universe,
)
from app.models.discovery import (
    DiscoveryCandidate,
    DiscoveryMode,
    DiscoveryModeInfo,
    DiscoveryRun,
    DiscoveryStage,
    DiscoveryWarning,
)
from app.models.rating import Rating
from app.models.universe import UniverseEntry, UniverseInfo
from app.services.discovery_ranking import list_mode_info, match_reason, rank_ratings
from app.services.discovery_screening import PrescreenResult, prescreen_ticker
from app.services.stock_analysis_service import analyze_stock_rating

DEFAULT_MODE = DiscoveryMode.OVERALL
DEFAULT_UNIVERSE = STARTER_LARGE_CAP
DEFAULT_LIMIT = 10
DEFAULT_MAX_FULL_ANALYSIS = 25

# Hard ceilings. A single synchronous request must never be able to trigger
# hundreds of provider round-trips.
MAX_LIMIT = 50
MAX_FULL_ANALYSIS_CEILING = 50

AnalyzeFn = Callable[[str], Rating]
PrescreenFn = Callable[[str], PrescreenResult]


class DiscoveryValidationError(Exception):
    """Raised when discovery parameters are invalid (maps to HTTP 400)."""


def list_discovery_modes() -> list[DiscoveryModeInfo]:
    """Return every supported discovery mode with its ranking explanation."""
    return list_mode_info()


def list_discovery_universes() -> list[UniverseInfo]:
    """Return every registered stock universe with its size."""
    return list_universes()


def run_discovery(
    mode: str | DiscoveryMode = DEFAULT_MODE,
    universe: str = DEFAULT_UNIVERSE,
    limit: int = DEFAULT_LIMIT,
    max_full_analysis: int = DEFAULT_MAX_FULL_ANALYSIS,
    *,
    analyze: AnalyzeFn | None = None,
    prescreen: PrescreenFn | None = None,
) -> DiscoveryRun:
    """Screen a universe, analyze a bounded shortlist, and rank the results.

    Args:
        mode: Discovery mode key (see ``DiscoveryMode``).
        universe: Registered universe key (e.g. ``"starter_large_cap"``).
        limit: Maximum ranked results to return (1…``MAX_LIMIT``); may not
            exceed ``max_full_analysis``.
        max_full_analysis: Maximum tickers to run the full pipeline on
            (1…``MAX_FULL_ANALYSIS_CEILING``).
        analyze: Injection point for the analysis pipeline (tests).
            Defaults to ``analyze_stock_rating``.
        prescreen: Injection point for the stage-1 check (tests).
            Defaults to ``prescreen_ticker``.

    Returns:
        A DiscoveryRun with ranked candidates, per-ticker warnings, and run
        metadata.

    Raises:
        DiscoveryValidationError: If any parameter is invalid or the universe
            cannot be loaded.
    """
    resolved_mode = _validate_mode(mode)
    resolved_limit = _validate_bound(limit, "limit", MAX_LIMIT)
    resolved_max = _validate_bound(
        max_full_analysis, "max_full_analysis", MAX_FULL_ANALYSIS_CEILING
    )
    if resolved_limit > resolved_max:
        raise DiscoveryValidationError(
            f"limit ({resolved_limit}) cannot exceed max_full_analysis "
            f"({resolved_max})."
        )

    entries, universe_key, universe_name = _load_universe_entries(universe)
    analyze_fn = analyze if analyze is not None else analyze_stock_rating
    prescreen_fn = prescreen if prescreen is not None else prescreen_ticker

    started_at = datetime.now(tz=timezone.utc)
    warnings: list[DiscoveryWarning] = []

    shortlist, prescreened_count = _build_shortlist(
        entries, resolved_max, prescreen_fn, warnings
    )
    ratings, by_ticker = _analyze_shortlist(shortlist, analyze_fn, warnings)

    ranked = rank_ratings(resolved_mode, ratings)[:resolved_limit]
    results = [
        _build_candidate(rating, by_ticker[rating.ticker], resolved_mode, rank)
        for rank, rating in enumerate(ranked, start=1)
    ]

    return DiscoveryRun(
        mode=resolved_mode,
        universe=universe_key,
        universe_name=universe_name,
        limit=resolved_limit,
        max_full_analysis=resolved_max,
        universe_size=len(entries),
        prescreened_count=prescreened_count,
        shortlist_count=len(shortlist),
        analyzed_count=len(ratings),
        results=results,
        warnings=warnings,
        started_at=started_at,
        completed_at=datetime.now(tz=timezone.utc),
        data_sources_used=_collect_sources(ratings),
    )


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------

def _build_shortlist(
    entries: tuple[UniverseEntry, ...],
    max_full_analysis: int,
    prescreen_fn: PrescreenFn,
    warnings: list[DiscoveryWarning],
) -> tuple[list[UniverseEntry], int]:
    """Stage 1 — pre-screen universe entries until the shortlist is full.

    Walks the universe in file order and stops as soon as ``max_full_analysis``
    tickers have passed, so a healthy universe costs one pre-screen per
    shortlisted ticker rather than one per universe member.

    Returns:
        The shortlist and the number of tickers actually pre-screened.
    """
    shortlist: list[UniverseEntry] = []
    prescreened_count = 0

    for entry in entries:
        if len(shortlist) >= max_full_analysis:
            break
        prescreened_count += 1
        result = prescreen_fn(entry.ticker)
        if result.passed:
            shortlist.append(entry)
            continue
        warnings.append(
            DiscoveryWarning(
                ticker=entry.ticker,
                stage=DiscoveryStage.PRESCREEN,
                message=result.reason or "Failed the pre-screen.",
            )
        )

    return shortlist, prescreened_count


def _analyze_shortlist(
    shortlist: list[UniverseEntry],
    analyze_fn: AnalyzeFn,
    warnings: list[DiscoveryWarning],
) -> tuple[list[Rating], dict[str, UniverseEntry]]:
    """Stage 2 — run the existing pipeline over the shortlist.

    Per-ticker failures are captured as warnings and never abort the run.

    Returns:
        The successful ratings and a ticker -> universe entry lookup for them.
    """
    ratings: list[Rating] = []
    by_ticker: dict[str, UniverseEntry] = {}

    for entry in shortlist:
        try:
            rating = analyze_fn(entry.ticker)
        except Exception as exc:
            warnings.append(
                DiscoveryWarning(
                    ticker=entry.ticker,
                    stage=DiscoveryStage.ANALYSIS,
                    message=str(exc) or type(exc).__name__,
                )
            )
            continue
        ratings.append(rating)
        by_ticker[rating.ticker] = entry

    return ratings, by_ticker


def _build_candidate(
    rating: Rating,
    entry: UniverseEntry,
    mode: DiscoveryMode,
    rank: int,
) -> DiscoveryCandidate:
    """Copy an existing Rating into a ranked DiscoveryCandidate.

    Every scored field is carried over verbatim; discovery only adds ``rank``
    and ``match_reason``, plus sector/industry metadata from the universe file.
    """
    return DiscoveryCandidate(
        ticker=rating.ticker,
        company_name=rating.company_name or entry.company_name,
        sector=entry.sector,
        industry=entry.industry,
        mode=mode,
        rank=rank,
        match_reason=match_reason(mode, rating),
        final_category=rating.final_category,
        score=rating.score,
        confidence_level=rating.confidence,
        current_price=rating.current_price,
        technical_score=rating.technical_score,
        fundamental_score=rating.fundamental_score,
        news_score=rating.news_score,
        risk_score=rating.risk_score,
        technical_summary=rating.technical_summary,
        fundamental_summary=rating.fundamental_summary,
        news_summary=rating.news_summary,
        risk_summary=rating.risk_summary,
        key_positive_factors=list(rating.key_positive_factors),
        key_risks=list(rating.key_risks),
        buy_trigger=rating.buy_trigger,
        sell_or_avoid_trigger=rating.sell_or_avoid_trigger,
        data_timestamp=rating.data_timestamp,
        data_sources_used=list(rating.data_sources_used),
    )


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_mode(mode: str | DiscoveryMode) -> DiscoveryMode:
    """Resolve a mode key to the enum; raise DiscoveryValidationError if unknown."""
    if isinstance(mode, DiscoveryMode):
        return mode
    normalized = mode.strip().lower() if isinstance(mode, str) else ""
    try:
        return DiscoveryMode(normalized)
    except ValueError as exc:
        raise DiscoveryValidationError(
            f"Unknown discovery mode {mode!r}. Supported modes: "
            f"{[m.value for m in DiscoveryMode]}."
        ) from exc


def _validate_bound(value: object, name: str, ceiling: int) -> int:
    """Validate a positive integer bound within an inclusive ceiling."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise DiscoveryValidationError(f"{name} must be an integer, got {value!r}.")
    if value < 1:
        raise DiscoveryValidationError(f"{name} must be at least 1, got {value}.")
    if value > ceiling:
        raise DiscoveryValidationError(f"{name} must be at most {ceiling}, got {value}.")
    return value


def _load_universe_entries(
    universe: str,
) -> tuple[tuple[UniverseEntry, ...], str, str]:
    """Load a universe and its display name; map load failures to validation errors."""
    key = universe.strip().lower() if isinstance(universe, str) else ""
    try:
        entries = load_universe(key)
    except UniverseLoadError as exc:
        raise DiscoveryValidationError(str(exc)) from exc

    name = next(
        (info.name for info in list_universes() if info.key == key),
        key,
    )
    return entries, key, name


def _collect_sources(ratings: list[Rating]) -> list[str]:
    """Union of the data sources reported by the analyzed ratings, sorted."""
    sources: set[str] = set()
    for rating in ratings:
        sources.update(rating.data_sources_used)
    return sorted(sources)
