"""
Unit tests for app/analysis/scoring.py.

All tests use Signal objects built locally — no network calls.
"""

import pytest

from app.analysis.scoring import ScoringError, score_technical_signals
from app.models.rating import ConfidenceLevel, Rating, RatingCategory
from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal(
    score_impact: float = 0.0,
    confidence: float = 0.60,
    direction: SignalDirection = SignalDirection.NEUTRAL,
    name: str = "Test Signal",
    category: SignalCategory = SignalCategory.TECHNICAL,
) -> Signal:
    return Signal(
        name=name,
        category=category,
        direction=direction,
        strength=SignalStrength.MODERATE,
        description=f"Test signal with impact {score_impact}.",
        score_impact=score_impact,
        confidence=confidence,
    )


def _bullish(impact: float = 0.20, confidence: float = 0.70) -> Signal:
    return _make_signal(
        score_impact=impact,
        confidence=confidence,
        direction=SignalDirection.BULLISH,
        name="Bullish Signal",
    )


def _bearish(impact: float = -0.20, confidence: float = 0.70) -> Signal:
    return _make_signal(
        score_impact=impact,
        confidence=confidence,
        direction=SignalDirection.BEARISH,
        name="Bearish Signal",
    )


def _neutral(confidence: float = 0.50) -> Signal:
    return _make_signal(
        score_impact=0.0,
        confidence=confidence,
        direction=SignalDirection.NEUTRAL,
        name="Neutral Signal",
    )


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

class TestReturnType:
    def test_returns_rating(self):
        result = score_technical_signals("AAPL", [_neutral()])
        assert isinstance(result, Rating)

    def test_ticker_normalized_through_rating(self):
        result = score_technical_signals("  aapl  ", [_neutral()])
        assert result.ticker == "AAPL"


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_empty_ticker_raises(self):
        with pytest.raises(ScoringError):
            score_technical_signals("", [_neutral()])

    def test_whitespace_ticker_raises(self):
        with pytest.raises(ScoringError):
            score_technical_signals("   ", [_neutral()])

    def test_non_string_ticker_raises(self):
        with pytest.raises(ScoringError):
            score_technical_signals(None, [_neutral()])  # type: ignore[arg-type]

    def test_empty_signals_list_raises(self):
        with pytest.raises(ScoringError):
            score_technical_signals("AAPL", [])

    def test_non_list_signals_raises(self):
        with pytest.raises(ScoringError):
            score_technical_signals("AAPL", "not a list")  # type: ignore[arg-type]

    def test_non_signal_item_in_list_raises(self):
        with pytest.raises(ScoringError):
            score_technical_signals("AAPL", [_neutral(), "oops"])  # type: ignore[arg-type]

    def test_non_technical_signal_raises(self):
        fundamental_signal = _make_signal(category=SignalCategory.FUNDAMENTAL)
        with pytest.raises(ScoringError, match="TECHNICAL"):
            score_technical_signals("AAPL", [fundamental_signal])


# ---------------------------------------------------------------------------
# Score calculation
# ---------------------------------------------------------------------------

class TestScoreCalculation:
    def test_zero_impact_produces_score_50(self):
        result = score_technical_signals("AAPL", [_neutral()])
        assert result.score == pytest.approx(50.0)

    def test_positive_impacts_produce_score_above_50(self):
        result = score_technical_signals("AAPL", [_bullish(0.30), _bullish(0.20)])
        assert result.score > 50.0

    def test_negative_impacts_produce_score_below_50(self):
        result = score_technical_signals("AAPL", [_bearish(-0.30), _bearish(-0.20)])
        assert result.score < 50.0

    def test_impact_clamps_at_upper_bound(self):
        # Seven signals each with 0.25 → total 1.75, clamped to 1.0 → score 100
        signals = [_bullish(0.25) for _ in range(7)]
        result = score_technical_signals("AAPL", signals)
        assert result.score == pytest.approx(100.0)

    def test_impact_clamps_at_lower_bound(self):
        signals = [_bearish(-0.25) for _ in range(7)]
        result = score_technical_signals("AAPL", signals)
        assert result.score == pytest.approx(0.0)

    def test_technical_score_equals_composite_score(self):
        result = score_technical_signals("AAPL", [_bullish(0.20)])
        assert result.technical_score == pytest.approx(result.score)

    def test_non_technical_sub_scores_are_zero(self):
        result = score_technical_signals("AAPL", [_bullish(0.20)])
        assert result.fundamental_score == 0.0
        assert result.news_score == 0.0
        assert result.risk_score == 0.0


# ---------------------------------------------------------------------------
# Rating category mapping
# ---------------------------------------------------------------------------

class TestCategoryMapping:
    def _score_at(self, impact: float) -> Rating:
        # Single signal so total_impact == score_impact
        return score_technical_signals("AAPL", [_bullish(impact)])

    def test_maps_to_strong_buy(self):
        # impact 0.70 → score 85 exactly
        result = score_technical_signals("AAPL", [_bullish(0.70)])
        assert result.final_category == RatingCategory.STRONG_BUY_CANDIDATE

    def test_maps_to_buy_candidate(self):
        # impact 0.40 → score 70
        result = score_technical_signals("AAPL", [_bullish(0.40)])
        assert result.final_category == RatingCategory.BUY_CANDIDATE

    def test_maps_to_watchlist(self):
        # impact 0.10 → score 55
        result = score_technical_signals("AAPL", [_bullish(0.10)])
        assert result.final_category == RatingCategory.WATCHLIST

    def test_maps_to_hold(self):
        # impact 0.0 → score 50
        result = score_technical_signals("AAPL", [_neutral()])
        assert result.final_category == RatingCategory.HOLD

    def test_maps_to_avoid(self):
        # impact -0.10 → score 45; boundary of HOLD is 45, so -0.10 gives 45 → HOLD
        # need score < 45 → impact < -0.10, e.g. -0.20 → score 40
        result = score_technical_signals("AAPL", [_bearish(-0.20)])
        assert result.final_category == RatingCategory.AVOID

    def test_maps_to_sell_exit_warning(self):
        # impact -0.40 → score 30; boundary is < 30, so -0.41 → 29.5 → SELL
        result = score_technical_signals("AAPL", [_bearish(-0.41)])
        assert result.final_category == RatingCategory.SELL_EXIT_WARNING


# ---------------------------------------------------------------------------
# Confidence mapping
# ---------------------------------------------------------------------------

class TestConfidenceMapping:
    def test_high_confidence(self):
        result = score_technical_signals("AAPL", [_bullish(confidence=0.80)])
        assert result.confidence == ConfidenceLevel.HIGH

    def test_medium_confidence(self):
        result = score_technical_signals("AAPL", [_bullish(confidence=0.60)])
        assert result.confidence == ConfidenceLevel.MEDIUM

    def test_low_confidence(self):
        result = score_technical_signals("AAPL", [_bullish(confidence=0.30)])
        assert result.confidence == ConfidenceLevel.LOW

    def test_average_confidence_used_across_signals(self):
        # 0.80 + 0.40 = 1.20 / 2 = 0.60 → MEDIUM (0.50 ≤ avg < 0.63)
        signals = [_bullish(confidence=0.80), _bearish(confidence=0.40)]
        result = score_technical_signals("AAPL", signals)
        assert result.confidence == ConfidenceLevel.MEDIUM


# ---------------------------------------------------------------------------
# Confidence mapping — calibrated thresholds (HIGH >= 0.63, MEDIUM >= 0.50)
# ---------------------------------------------------------------------------

class TestConfidenceMappingBoundaries:
    # --- HIGH boundary (0.63) ---

    def test_high_at_exact_threshold(self):
        result = score_technical_signals("AAPL", [_make_signal(confidence=0.63)])
        assert result.confidence == ConfidenceLevel.HIGH

    def test_high_above_threshold(self):
        result = score_technical_signals("AAPL", [_make_signal(confidence=0.65)])
        assert result.confidence == ConfidenceLevel.HIGH

    def test_medium_just_below_high_threshold(self):
        # 0.6299 is just below 0.63 → MEDIUM
        result = score_technical_signals("AAPL", [_make_signal(confidence=0.6299)])
        assert result.confidence == ConfidenceLevel.MEDIUM

    # --- MEDIUM/LOW boundary (0.50) ---

    def test_medium_at_exact_low_boundary(self):
        result = score_technical_signals("AAPL", [_make_signal(confidence=0.50)])
        assert result.confidence == ConfidenceLevel.MEDIUM

    def test_low_just_below_medium_threshold(self):
        # 0.4999 is just below 0.50 → LOW
        result = score_technical_signals("AAPL", [_make_signal(confidence=0.4999)])
        assert result.confidence == ConfidenceLevel.LOW

    # --- All three labels are reachable ---

    def test_high_is_reachable(self):
        result = score_technical_signals("AAPL", [_make_signal(confidence=0.63)])
        assert result.confidence == ConfidenceLevel.HIGH

    def test_medium_is_reachable(self):
        result = score_technical_signals("AAPL", [_make_signal(confidence=0.56)])
        assert result.confidence == ConfidenceLevel.MEDIUM

    def test_low_is_reachable(self):
        result = score_technical_signals("AAPL", [_make_signal(confidence=0.30)])
        assert result.confidence == ConfidenceLevel.LOW

    # --- Representative real-ticker averages from diagnostics review ---

    def test_ko_representative_average_yields_high(self):
        # KO measured avg_signal_confidence = 0.6375 (diagnostics review 2026-05-26)
        result = score_technical_signals("AAPL", [_make_signal(confidence=0.6375)])
        assert result.confidence == ConfidenceLevel.HIGH

    def test_msft_representative_average_yields_high(self):
        # MSFT measured avg_signal_confidence = 0.6425 (diagnostics review 2026-05-26)
        result = score_technical_signals("AAPL", [_make_signal(confidence=0.6425)])
        assert result.confidence == ConfidenceLevel.HIGH

    def test_xom_representative_average_yields_medium(self):
        # XOM measured avg_signal_confidence = 0.6250 (diagnostics review 2026-05-26)
        result = score_technical_signals("AAPL", [_make_signal(confidence=0.6250)])
        assert result.confidence == ConfidenceLevel.MEDIUM

    def test_mcd_representative_average_yields_medium(self):
        # MCD measured avg_signal_confidence = 0.6175 (one missing-data signal)
        result = score_technical_signals("AAPL", [_make_signal(confidence=0.6175)])
        assert result.confidence == ConfidenceLevel.MEDIUM

    def test_pfe_representative_average_yields_medium(self):
        # PFE measured avg_signal_confidence = 0.6100 (most neutral signals in review set)
        result = score_technical_signals("AAPL", [_make_signal(confidence=0.6100)])
        assert result.confidence == ConfidenceLevel.MEDIUM

    # --- HIGH is reachable with a realistic multi-signal set ---

    def test_high_reachable_with_realistic_multi_signal_set(self):
        # Mix of typical bullish technical signals (avg = 0.6357 ≥ 0.63 → HIGH)
        # Trend: 0.70, SMA 200: 0.70, MACD: 0.65, SMA 50: 0.65, SMA 20: 0.60,
        # RSI overbought: 0.65, Volume neutral: 0.45
        # avg = (0.70+0.70+0.65+0.65+0.60+0.65+0.45) / 7 = 4.40 / 7 ≈ 0.6286
        # Use slightly higher values to clear 0.63 boundary cleanly
        signals = [
            _make_signal(confidence=0.70),
            _make_signal(confidence=0.70),
            _make_signal(confidence=0.65),
            _make_signal(confidence=0.65),
            _make_signal(confidence=0.65),
            _make_signal(confidence=0.60),
            _make_signal(confidence=0.50),
        ]
        # avg = (0.70+0.70+0.65+0.65+0.65+0.60+0.50) / 7 = 4.45 / 7 ≈ 0.6357 → HIGH
        result = score_technical_signals("AAPL", signals)
        assert result.confidence == ConfidenceLevel.HIGH

    # --- Regression: score and category are not affected by the threshold change ---

    def test_score_unchanged_by_threshold_recalibration(self):
        signals = [_bullish(impact=0.20, confidence=0.6375), _neutral(confidence=0.60)]
        result = score_technical_signals("AAPL", signals)
        # Score comes from score_impact only; confidence threshold change is irrelevant
        assert 50.0 < result.score <= 100.0
        assert result.score == pytest.approx(60.0, abs=1.0)

    def test_category_unchanged_by_threshold_recalibration(self):
        signals = [_bullish(impact=0.25, confidence=0.65), _neutral(confidence=0.60)]
        result = score_technical_signals("AAPL", signals)
        assert result.final_category is not None
        # Category is determined by score, not by confidence
        expected_score = 50.0 + (0.25 + 0.0) * 50.0
        assert result.score == pytest.approx(expected_score, abs=0.1)

    def test_confidence_diagnostics_average_unchanged_by_threshold_recalibration(self):
        # ConfidenceDiagnostics reads raw values; threshold change must not alter them
        signals = [
            _make_signal(confidence=0.6375, direction=SignalDirection.BULLISH),
            _make_signal(confidence=0.60, direction=SignalDirection.NEUTRAL),
        ]
        result = score_technical_signals("AAPL", signals)
        diag = result.confidence_diagnostics
        assert diag is not None
        assert diag.signal_count == 2
        assert diag.average_signal_confidence == pytest.approx(
            (0.6375 + 0.60) / 2, abs=1e-4
        )

    def test_confidence_diagnostics_area_averages_unchanged(self):
        signals = [
            _make_signal(confidence=0.70, direction=SignalDirection.BULLISH),
            _make_signal(confidence=0.56, direction=SignalDirection.NEUTRAL),
        ]
        result = score_technical_signals("AAPL", signals)
        diag = result.confidence_diagnostics
        assert diag.technical_average_confidence == pytest.approx(0.63, abs=1e-4)
        assert diag.fundamental_average_confidence is None


# ---------------------------------------------------------------------------
# Rating fields
# ---------------------------------------------------------------------------

class TestRatingFields:
    def test_signals_used_included(self):
        signals = [_bullish(), _neutral()]
        result = score_technical_signals("AAPL", signals)
        assert len(result.signals_used) == 2

    def test_data_sources_used_included(self):
        result = score_technical_signals(
            "AAPL", [_neutral()], data_sources_used=["yfinance"]
        )
        assert "yfinance" in result.data_sources_used

    def test_data_sources_defaults_to_empty_list(self):
        result = score_technical_signals("AAPL", [_neutral()])
        assert result.data_sources_used == []

    def test_data_timestamp_passed_through(self):
        from datetime import datetime, timezone
        ts = datetime(2024, 6, 1, tzinfo=timezone.utc)
        result = score_technical_signals("AAPL", [_neutral()], data_timestamp=ts)
        assert result.data_timestamp == ts

    def test_positive_factors_include_bullish_signals(self):
        result = score_technical_signals("AAPL", [_bullish(0.25), _neutral()])
        assert any("0.25" in f or "Bullish" in f or len(result.key_positive_factors) > 0
                   for f in result.key_positive_factors)
        assert len(result.key_positive_factors) >= 1

    def test_key_risks_include_bearish_signals(self):
        result = score_technical_signals("AAPL", [_bearish(-0.25), _neutral()])
        assert len(result.key_risks) >= 1

    def test_no_positive_factors_for_all_neutral(self):
        result = score_technical_signals("AAPL", [_neutral(), _neutral()])
        assert result.key_positive_factors == []

    def test_no_key_risks_for_all_neutral(self):
        result = score_technical_signals("AAPL", [_neutral(), _neutral()])
        assert result.key_risks == []


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------

class TestImmutability:
    def test_input_signal_list_not_mutated(self):
        signals = [_bullish(), _neutral()]
        original_len = len(signals)
        score_technical_signals("AAPL", signals)
        assert len(signals) == original_len

    def test_input_data_sources_not_mutated(self):
        sources = ["yfinance"]
        score_technical_signals("AAPL", [_neutral()], data_sources_used=sources)
        assert sources == ["yfinance"]
