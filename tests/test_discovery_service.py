"""
Tests for app/services/discovery_service.py.

The pre-screen and the analysis pipeline are injected as fakes, so no test
touches yfinance or the network. The committed starter universe is used as the
ticker source because it is static repository data.
"""

from __future__ import annotations

import pytest

from app.data.universe_loader import STARTER_LARGE_CAP, load_universe
from app.models.discovery import DiscoveryMode, DiscoveryStage
from app.models.rating import ConfidenceLevel, Rating, RatingCategory
from app.services.discovery_screening import PrescreenResult
from app.services.discovery_service import (
    MAX_FULL_ANALYSIS_CEILING,
    MAX_LIMIT,
    DiscoveryValidationError,
    list_discovery_modes,
    list_discovery_universes,
    run_discovery,
)

UNIVERSE_TICKERS = [entry.ticker for entry in load_universe(STARTER_LARGE_CAP)]


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def _rating(
    ticker: str,
    *,
    score: float = 60.0,
    technical: float = 50.0,
    fundamental: float = 50.0,
    news: float = 50.0,
    risk: float = 50.0,
) -> Rating:
    return Rating(
        ticker=ticker,
        final_category=RatingCategory.WATCHLIST,
        score=score,
        confidence=ConfidenceLevel.MEDIUM,
        explanation=f"Rating for {ticker}.",
        technical_score=technical,
        fundamental_score=fundamental,
        news_score=news,
        risk_score=risk,
        company_name=f"{ticker} Inc.",
        current_price=100.0,
        data_sources_used=["yfinance"],
    )


def _pass_all(ticker: str) -> PrescreenResult:
    return PrescreenResult(ticker, True)


def _fail_all(ticker: str) -> PrescreenResult:
    return PrescreenResult(ticker, False, "No usable price history.")


def _prescreen_except(*blocked: str):
    """Pre-screen that fails only for the named tickers."""
    blocked_set = set(blocked)

    def _prescreen(ticker: str) -> PrescreenResult:
        if ticker in blocked_set:
            return PrescreenResult(ticker, False, "No usable price history.")
        return PrescreenResult(ticker, True)

    return _prescreen


def _analyze_ok(ticker: str) -> Rating:
    return _rating(ticker)


def _analyze_failing(*failing: str):
    """Analysis fake that raises only for the named tickers."""
    failing_set = set(failing)

    def _analyze(ticker: str) -> Rating:
        if ticker in failing_set:
            raise RuntimeError(f"no data for {ticker}")
        return _rating(ticker)

    return _analyze


def _analyze_scored(scores: dict[str, dict[str, float]]):
    """Analysis fake returning per-ticker sub-scores; others get defaults."""

    def _analyze(ticker: str) -> Rating:
        return _rating(ticker, **scores.get(ticker, {}))

    return _analyze


def _run(**kwargs):
    """run_discovery with fakes wired in by default."""
    kwargs.setdefault("analyze", _analyze_ok)
    kwargs.setdefault("prescreen", _pass_all)
    return run_discovery(**kwargs)


# ---------------------------------------------------------------------------
# Metadata endpoints
# ---------------------------------------------------------------------------


class TestDiscoveryMetadata:
    def test_lists_every_mode(self):
        assert {info.key for info in list_discovery_modes()} == set(DiscoveryMode)

    def test_lists_the_starter_universe(self):
        keys = [info.key for info in list_discovery_universes()]
        assert STARTER_LARGE_CAP in keys


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_unknown_mode_raises(self):
        with pytest.raises(DiscoveryValidationError, match="Unknown discovery mode"):
            _run(mode="moonshot")

    def test_blank_mode_raises(self):
        with pytest.raises(DiscoveryValidationError):
            _run(mode="")

    def test_unknown_universe_raises(self):
        with pytest.raises(DiscoveryValidationError, match="Unknown universe"):
            _run(universe="sp500")

    def test_zero_limit_raises(self):
        with pytest.raises(DiscoveryValidationError, match="limit must be at least 1"):
            _run(limit=0)

    def test_negative_limit_raises(self):
        with pytest.raises(DiscoveryValidationError):
            _run(limit=-5)

    def test_limit_above_ceiling_raises(self):
        with pytest.raises(DiscoveryValidationError, match="at most"):
            _run(limit=MAX_LIMIT + 1, max_full_analysis=MAX_FULL_ANALYSIS_CEILING)

    def test_zero_max_full_analysis_raises(self):
        with pytest.raises(DiscoveryValidationError, match="max_full_analysis"):
            _run(max_full_analysis=0)

    def test_max_full_analysis_above_ceiling_raises(self):
        with pytest.raises(DiscoveryValidationError, match="max_full_analysis"):
            _run(max_full_analysis=MAX_FULL_ANALYSIS_CEILING + 1)

    def test_limit_greater_than_max_full_analysis_raises(self):
        with pytest.raises(DiscoveryValidationError, match="cannot exceed"):
            _run(limit=10, max_full_analysis=5)

    def test_non_integer_limit_raises(self):
        with pytest.raises(DiscoveryValidationError, match="must be an integer"):
            _run(limit="ten")

    def test_validation_runs_before_any_analysis(self):
        calls: list[str] = []

        def _tracking_analyze(ticker: str) -> Rating:
            calls.append(ticker)
            return _rating(ticker)

        with pytest.raises(DiscoveryValidationError):
            _run(mode="nonsense", analyze=_tracking_analyze)
        assert calls == []

    def test_mode_accepts_enum_instance(self):
        assert _run(mode=DiscoveryMode.MOMENTUM, limit=1, max_full_analysis=1).mode is (
            DiscoveryMode.MOMENTUM
        )

    def test_mode_is_case_insensitive(self):
        assert _run(mode="OVERALL", limit=1, max_full_analysis=1).mode is (
            DiscoveryMode.OVERALL
        )


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


class TestResponseShape:
    def test_echoes_requested_parameters(self):
        run = _run(mode="quality", limit=3, max_full_analysis=4)
        assert run.mode is DiscoveryMode.QUALITY
        assert run.universe == STARTER_LARGE_CAP
        assert run.limit == 3
        assert run.max_full_analysis == 4

    def test_reports_universe_size_and_name(self):
        run = _run(limit=2, max_full_analysis=2)
        assert run.universe_size == len(UNIVERSE_TICKERS)
        assert run.universe_name

    def test_reports_run_timestamps(self):
        run = _run(limit=1, max_full_analysis=1)
        assert run.completed_at >= run.started_at

    def test_reports_data_sources_used(self):
        assert _run(limit=1, max_full_analysis=1).data_sources_used == ["yfinance"]

    def test_ranks_results_from_one(self):
        run = _run(limit=5, max_full_analysis=5)
        assert [c.rank for c in run.results] == [1, 2, 3, 4, 5]

    def test_candidates_carry_the_requested_mode(self):
        run = _run(mode="defensive", limit=3, max_full_analysis=3)
        assert all(c.mode is DiscoveryMode.DEFENSIVE for c in run.results)

    def test_candidates_include_a_match_reason(self):
        for candidate in _run(limit=3, max_full_analysis=3).results:
            assert candidate.match_reason.strip()

    def test_candidates_carry_universe_metadata(self):
        candidate = _run(limit=1, max_full_analysis=1).results[0]
        entry = next(e for e in load_universe(STARTER_LARGE_CAP) if e.ticker == candidate.ticker)
        assert candidate.sector == entry.sector
        assert candidate.industry == entry.industry

    def test_candidate_scores_are_copied_verbatim(self):
        run = _run(
            limit=1,
            max_full_analysis=1,
            analyze=_analyze_scored(
                {UNIVERSE_TICKERS[0]: {"score": 71.5, "technical": 82.0, "risk": 44.0}}
            ),
        )
        candidate = run.results[0]
        assert candidate.score == 71.5
        assert candidate.technical_score == 82.0
        assert candidate.risk_score == 44.0
        assert candidate.final_category is RatingCategory.WATCHLIST
        assert candidate.confidence_level is ConfidenceLevel.MEDIUM


# ---------------------------------------------------------------------------
# Bounding
# ---------------------------------------------------------------------------


class TestBounding:
    def test_full_analysis_is_capped(self):
        calls: list[str] = []

        def _tracking_analyze(ticker: str) -> Rating:
            calls.append(ticker)
            return _rating(ticker)

        _run(limit=3, max_full_analysis=3, analyze=_tracking_analyze)
        assert len(calls) == 3

    def test_cap_holds_even_for_a_larger_universe(self):
        run = _run(limit=5, max_full_analysis=5)
        assert run.analyzed_count == 5
        assert run.universe_size > 5

    def test_prescreen_stops_once_the_shortlist_is_full(self):
        calls: list[str] = []

        def _tracking_prescreen(ticker: str) -> PrescreenResult:
            calls.append(ticker)
            return PrescreenResult(ticker, True)

        _run(limit=2, max_full_analysis=2, prescreen=_tracking_prescreen)
        assert len(calls) == 2

    def test_prescreen_failures_do_not_shrink_the_shortlist(self):
        run = _run(
            limit=3,
            max_full_analysis=3,
            prescreen=_prescreen_except(UNIVERSE_TICKERS[0], UNIVERSE_TICKERS[1]),
        )
        assert run.shortlist_count == 3
        assert run.prescreened_count == 5

    def test_results_are_truncated_to_limit(self):
        run = _run(limit=2, max_full_analysis=6)
        assert len(run.results) == 2
        assert run.analyzed_count == 6


# ---------------------------------------------------------------------------
# Failure tolerance
# ---------------------------------------------------------------------------


class TestFailureTolerance:
    def test_partial_analysis_failure_does_not_abort_the_run(self):
        run = _run(
            limit=3,
            max_full_analysis=3,
            analyze=_analyze_failing(UNIVERSE_TICKERS[0]),
        )
        assert run.analyzed_count == 2
        assert len(run.results) == 2

    def test_failed_ticker_is_reported_as_a_warning(self):
        run = _run(
            limit=3,
            max_full_analysis=3,
            analyze=_analyze_failing(UNIVERSE_TICKERS[1]),
        )
        warning = next(w for w in run.warnings if w.ticker == UNIVERSE_TICKERS[1])
        assert warning.stage is DiscoveryStage.ANALYSIS
        assert "no data" in warning.message

    def test_prescreen_failure_is_reported_as_a_warning(self):
        run = _run(
            limit=2,
            max_full_analysis=2,
            prescreen=_prescreen_except(UNIVERSE_TICKERS[0]),
        )
        warning = next(w for w in run.warnings if w.ticker == UNIVERSE_TICKERS[0])
        assert warning.stage is DiscoveryStage.PRESCREEN
        assert warning.message

    def test_failed_tickers_are_excluded_from_results(self):
        run = _run(
            limit=3,
            max_full_analysis=3,
            analyze=_analyze_failing(UNIVERSE_TICKERS[0]),
        )
        assert UNIVERSE_TICKERS[0] not in [c.ticker for c in run.results]

    def test_every_ticker_failing_prescreen_yields_no_candidates(self):
        run = _run(limit=5, max_full_analysis=5, prescreen=_fail_all)
        assert run.results == []
        assert run.shortlist_count == 0
        assert run.analyzed_count == 0
        assert len(run.warnings) == run.universe_size

    def test_every_ticker_failing_analysis_yields_no_candidates(self):
        run = _run(
            limit=3,
            max_full_analysis=3,
            analyze=_analyze_failing(*UNIVERSE_TICKERS),
        )
        assert run.results == []
        assert run.analyzed_count == 0
        assert len(run.warnings) == 3

    def test_no_candidates_still_returns_a_complete_run(self):
        run = _run(limit=3, max_full_analysis=3, prescreen=_fail_all)
        assert run.universe_size > 0
        assert run.completed_at >= run.started_at


# ---------------------------------------------------------------------------
# Mode ranking wired end to end
# ---------------------------------------------------------------------------


class TestModeRankingIntegration:
    def _run_with_scores(self, mode: str, scores: dict[str, dict[str, float]]):
        return _run(mode=mode, limit=3, max_full_analysis=3, analyze=_analyze_scored(scores))

    def test_overall_puts_the_highest_score_first(self):
        run = self._run_with_scores("overall", {UNIVERSE_TICKERS[2]: {"score": 95.0}})
        assert run.results[0].ticker == UNIVERSE_TICKERS[2]

    def test_momentum_puts_the_strongest_technical_first(self):
        run = self._run_with_scores(
            "momentum", {UNIVERSE_TICKERS[1]: {"score": 40.0, "technical": 95.0}}
        )
        assert run.results[0].ticker == UNIVERSE_TICKERS[1]

    def test_quality_puts_the_strongest_fundamental_first(self):
        run = self._run_with_scores(
            "quality", {UNIVERSE_TICKERS[2]: {"score": 40.0, "fundamental": 92.0}}
        )
        assert run.results[0].ticker == UNIVERSE_TICKERS[2]

    def test_value_falls_back_to_fundamentals_without_valuation_signals(self):
        run = self._run_with_scores("value", {UNIVERSE_TICKERS[0]: {"fundamental": 90.0}})
        assert run.results[0].ticker == UNIVERSE_TICKERS[0]

    def test_defensive_puts_the_most_favorable_risk_first(self):
        run = self._run_with_scores(
            "defensive", {UNIVERSE_TICKERS[1]: {"score": 40.0, "risk": 91.0}}
        )
        assert run.results[0].ticker == UNIVERSE_TICKERS[1]

    def test_avoid_puts_the_weakest_score_first(self):
        run = self._run_with_scores("avoid", {UNIVERSE_TICKERS[2]: {"score": 11.0}})
        assert run.results[0].ticker == UNIVERSE_TICKERS[2]
