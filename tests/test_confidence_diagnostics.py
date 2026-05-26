"""
Unit tests for ConfidenceDiagnostics and its integration with the scoring /
report pipeline.

All inputs are built locally — no network calls.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile

import pytest

from app.analysis.scoring import _build_confidence_diagnostics, score_signals
from app.models.confidence_diagnostics import ConfidenceDiagnostics
from app.models.rating import ConfidenceLevel, Rating, RatingCategory
from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength
from app.models.stock_report import StockReport
from app.reports.report_generator import build_stock_report
from app.reports.templates import format_report_markdown


# ---------------------------------------------------------------------------
# Signal factory helpers
# ---------------------------------------------------------------------------

def _sig(
    name: str = "Test",
    category: SignalCategory = SignalCategory.TECHNICAL,
    direction: SignalDirection = SignalDirection.NEUTRAL,
    confidence: float = 0.60,
    score_impact: float = 0.0,
) -> Signal:
    return Signal(
        name=name,
        category=category,
        direction=direction,
        strength=SignalStrength.MODERATE,
        description=f"Description for {name}.",
        score_impact=score_impact,
        confidence=confidence,
    )


def _bullish(confidence: float = 0.70, category: SignalCategory = SignalCategory.TECHNICAL) -> Signal:
    return _sig("Bullish", category, SignalDirection.BULLISH, confidence, score_impact=0.20)


def _bearish(confidence: float = 0.65, category: SignalCategory = SignalCategory.TECHNICAL) -> Signal:
    return _sig("Bearish", category, SignalDirection.BEARISH, confidence, score_impact=-0.20)


def _neutral(confidence: float = 0.50, category: SignalCategory = SignalCategory.TECHNICAL) -> Signal:
    return _sig("Neutral", category, SignalDirection.NEUTRAL, confidence, score_impact=0.0)


def _missing(category: SignalCategory = SignalCategory.TECHNICAL) -> Signal:
    return _sig("Missing", category, SignalDirection.NEUTRAL, confidence=0.30, score_impact=0.0)


# ---------------------------------------------------------------------------
# _build_confidence_diagnostics — empty input
# ---------------------------------------------------------------------------

class TestBuildDiagnosticsEmpty:
    def test_empty_list_returns_diagnostics_object(self):
        result = _build_confidence_diagnostics([])
        assert isinstance(result, ConfidenceDiagnostics)

    def test_empty_list_signal_count_zero(self):
        assert _build_confidence_diagnostics([]).signal_count == 0

    def test_empty_list_average_is_none(self):
        assert _build_confidence_diagnostics([]).average_signal_confidence is None

    def test_empty_list_min_is_none(self):
        assert _build_confidence_diagnostics([]).min_signal_confidence is None

    def test_empty_list_max_is_none(self):
        assert _build_confidence_diagnostics([]).max_signal_confidence is None

    def test_empty_list_direction_counts_all_zero(self):
        d = _build_confidence_diagnostics([])
        assert d.bullish_count == 0
        assert d.bearish_count == 0
        assert d.neutral_count == 0

    def test_empty_list_missing_count_zero(self):
        assert _build_confidence_diagnostics([]).missing_count == 0

    def test_empty_list_area_averages_all_none(self):
        d = _build_confidence_diagnostics([])
        assert d.technical_average_confidence is None
        assert d.fundamental_average_confidence is None
        assert d.news_average_confidence is None
        assert d.risk_average_confidence is None


# ---------------------------------------------------------------------------
# _build_confidence_diagnostics — signal_count
# ---------------------------------------------------------------------------

class TestSignalCount:
    def test_single_signal(self):
        assert _build_confidence_diagnostics([_bullish()]).signal_count == 1

    def test_multiple_signals(self):
        signals = [_bullish(), _bearish(), _neutral(), _missing()]
        assert _build_confidence_diagnostics(signals).signal_count == 4

    def test_twenty_signals(self):
        signals = [_bullish()] * 20
        assert _build_confidence_diagnostics(signals).signal_count == 20


# ---------------------------------------------------------------------------
# _build_confidence_diagnostics — average_signal_confidence
# ---------------------------------------------------------------------------

class TestAverageConfidence:
    def test_single_signal_average_equals_its_confidence(self):
        d = _build_confidence_diagnostics([_bullish(confidence=0.70)])
        assert d.average_signal_confidence == pytest.approx(0.70, abs=1e-4)

    def test_two_signals_average(self):
        signals = [_bullish(confidence=0.80), _bearish(confidence=0.60)]
        d = _build_confidence_diagnostics(signals)
        assert d.average_signal_confidence == pytest.approx(0.70, abs=1e-4)

    def test_mixed_average(self):
        # 0.70 + 0.50 + 0.30 = 1.50 / 3 = 0.50
        signals = [_bullish(confidence=0.70), _neutral(confidence=0.50), _missing()]
        d = _build_confidence_diagnostics(signals)
        assert d.average_signal_confidence == pytest.approx(0.50, abs=1e-4)

    def test_average_rounded_to_four_decimal_places(self):
        # 0.70 + 0.65 + 0.60 = 1.95 / 3 = 0.65 exactly
        signals = [
            _sig(confidence=0.70),
            _sig(confidence=0.65),
            _sig(confidence=0.60),
        ]
        d = _build_confidence_diagnostics(signals)
        assert d.average_signal_confidence == pytest.approx(0.65, abs=1e-4)


# ---------------------------------------------------------------------------
# _build_confidence_diagnostics — min / max
# ---------------------------------------------------------------------------

class TestMinMaxConfidence:
    def test_min_equals_lowest_confidence(self):
        signals = [_sig(confidence=0.70), _sig(confidence=0.30), _sig(confidence=0.55)]
        d = _build_confidence_diagnostics(signals)
        assert d.min_signal_confidence == pytest.approx(0.30, abs=1e-4)

    def test_max_equals_highest_confidence(self):
        signals = [_sig(confidence=0.70), _sig(confidence=0.30), _sig(confidence=0.55)]
        d = _build_confidence_diagnostics(signals)
        assert d.max_signal_confidence == pytest.approx(0.70, abs=1e-4)

    def test_single_signal_min_and_max_equal(self):
        d = _build_confidence_diagnostics([_sig(confidence=0.65)])
        assert d.min_signal_confidence == pytest.approx(0.65, abs=1e-4)
        assert d.max_signal_confidence == pytest.approx(0.65, abs=1e-4)

    def test_uniform_confidence_min_equals_max(self):
        signals = [_sig(confidence=0.60)] * 5
        d = _build_confidence_diagnostics(signals)
        assert d.min_signal_confidence == pytest.approx(0.60, abs=1e-4)
        assert d.max_signal_confidence == pytest.approx(0.60, abs=1e-4)


# ---------------------------------------------------------------------------
# _build_confidence_diagnostics — direction counts
# ---------------------------------------------------------------------------

class TestDirectionCounts:
    def test_all_bullish(self):
        signals = [_bullish()] * 3
        d = _build_confidence_diagnostics(signals)
        assert d.bullish_count == 3
        assert d.bearish_count == 0
        assert d.neutral_count == 0

    def test_all_bearish(self):
        signals = [_bearish()] * 2
        d = _build_confidence_diagnostics(signals)
        assert d.bullish_count == 0
        assert d.bearish_count == 2
        assert d.neutral_count == 0

    def test_all_neutral(self):
        signals = [_neutral()] * 4
        d = _build_confidence_diagnostics(signals)
        assert d.bullish_count == 0
        assert d.bearish_count == 0
        assert d.neutral_count == 4

    def test_mixed_directions(self):
        signals = [
            _bullish(), _bullish(),
            _bearish(),
            _neutral(), _neutral(), _neutral(),
        ]
        d = _build_confidence_diagnostics(signals)
        assert d.bullish_count == 2
        assert d.bearish_count == 1
        assert d.neutral_count == 3

    def test_direction_counts_sum_to_signal_count(self):
        signals = [_bullish(), _bearish(), _neutral(), _missing()]
        d = _build_confidence_diagnostics(signals)
        assert d.bullish_count + d.bearish_count + d.neutral_count == d.signal_count


# ---------------------------------------------------------------------------
# _build_confidence_diagnostics — missing_count
# ---------------------------------------------------------------------------

class TestMissingCount:
    def test_no_missing_signals(self):
        signals = [_sig(confidence=0.60), _sig(confidence=0.70)]
        assert _build_confidence_diagnostics(signals).missing_count == 0

    def test_one_missing_signal(self):
        signals = [_sig(confidence=0.60), _missing()]
        assert _build_confidence_diagnostics(signals).missing_count == 1

    def test_all_missing_signals(self):
        signals = [_missing()] * 3
        assert _build_confidence_diagnostics(signals).missing_count == 3

    def test_exactly_0_30_counts_as_missing(self):
        assert _build_confidence_diagnostics([_sig(confidence=0.30)]).missing_count == 1

    def test_above_0_30_not_counted_as_missing(self):
        assert _build_confidence_diagnostics([_sig(confidence=0.31)]).missing_count == 0


# ---------------------------------------------------------------------------
# _build_confidence_diagnostics — per-area averages
# ---------------------------------------------------------------------------

class TestAreaAverages:
    def test_technical_only(self):
        signals = [
            _sig(confidence=0.70, category=SignalCategory.TECHNICAL),
            _sig(confidence=0.60, category=SignalCategory.TECHNICAL),
        ]
        d = _build_confidence_diagnostics(signals)
        assert d.technical_average_confidence == pytest.approx(0.65, abs=1e-4)
        assert d.fundamental_average_confidence is None
        assert d.news_average_confidence is None
        assert d.risk_average_confidence is None

    def test_fundamental_only(self):
        signals = [_sig(confidence=0.70, category=SignalCategory.FUNDAMENTAL)]
        d = _build_confidence_diagnostics(signals)
        assert d.fundamental_average_confidence == pytest.approx(0.70, abs=1e-4)
        assert d.technical_average_confidence is None

    def test_news_only(self):
        signals = [_sig(confidence=0.68, category=SignalCategory.NEWS)] * 3
        d = _build_confidence_diagnostics(signals)
        assert d.news_average_confidence == pytest.approx(0.68, abs=1e-4)

    def test_risk_only(self):
        signals = [
            _sig(confidence=0.65, category=SignalCategory.RISK),
            _sig(confidence=0.75, category=SignalCategory.RISK),
        ]
        d = _build_confidence_diagnostics(signals)
        assert d.risk_average_confidence == pytest.approx(0.70, abs=1e-4)

    def test_all_four_areas(self):
        signals = [
            _sig(confidence=0.60, category=SignalCategory.TECHNICAL),
            _sig(confidence=0.70, category=SignalCategory.FUNDAMENTAL),
            _sig(confidence=0.68, category=SignalCategory.NEWS),
            _sig(confidence=0.65, category=SignalCategory.RISK),
        ]
        d = _build_confidence_diagnostics(signals)
        assert d.technical_average_confidence == pytest.approx(0.60, abs=1e-4)
        assert d.fundamental_average_confidence == pytest.approx(0.70, abs=1e-4)
        assert d.news_average_confidence == pytest.approx(0.68, abs=1e-4)
        assert d.risk_average_confidence == pytest.approx(0.65, abs=1e-4)

    def test_area_avg_matches_overall_when_single_area(self):
        signals = [_sig(confidence=0.64, category=SignalCategory.TECHNICAL)] * 4
        d = _build_confidence_diagnostics(signals)
        assert d.technical_average_confidence == pytest.approx(
            d.average_signal_confidence, abs=1e-4
        )

    def test_area_averages_rounded_to_four_places(self):
        # 0.70 + 0.65 + 0.60 = 1.95 / 3 = 0.65 exactly
        signals = [
            _sig(confidence=0.70, category=SignalCategory.TECHNICAL),
            _sig(confidence=0.65, category=SignalCategory.TECHNICAL),
            _sig(confidence=0.60, category=SignalCategory.TECHNICAL),
        ]
        d = _build_confidence_diagnostics(signals)
        assert d.technical_average_confidence == pytest.approx(0.65, abs=1e-4)


# ---------------------------------------------------------------------------
# Integration: score_signals attaches diagnostics to Rating
# ---------------------------------------------------------------------------

def _make_composite_signals() -> list[Signal]:
    return [
        _sig("T1", SignalCategory.TECHNICAL, SignalDirection.BULLISH, 0.70, 0.20),
        _sig("T2", SignalCategory.TECHNICAL, SignalDirection.NEUTRAL, 0.50, 0.0),
        _sig("F1", SignalCategory.FUNDAMENTAL, SignalDirection.BULLISH, 0.65, 0.20),
        _sig("N1", SignalCategory.NEWS, SignalDirection.NEUTRAL, 0.60, 0.0),
        _sig("R1", SignalCategory.RISK, SignalDirection.NEUTRAL, 0.55, 0.0),
    ]


class TestScoreSignalsIntegration:
    def test_rating_has_confidence_diagnostics(self):
        rating = score_signals("AAPL", _make_composite_signals())
        assert rating.confidence_diagnostics is not None

    def test_diagnostics_signal_count_matches_input(self):
        signals = _make_composite_signals()
        rating = score_signals("AAPL", signals)
        assert rating.confidence_diagnostics.signal_count == len(signals)

    def test_diagnostics_average_is_correct(self):
        signals = _make_composite_signals()
        # avg of [0.70, 0.50, 0.65, 0.60, 0.55] = 3.00 / 5 = 0.60
        rating = score_signals("AAPL", signals)
        assert rating.confidence_diagnostics.average_signal_confidence == pytest.approx(0.60, abs=1e-4)

    def test_diagnostics_bullish_count_correct(self):
        signals = _make_composite_signals()
        rating = score_signals("AAPL", signals)
        assert rating.confidence_diagnostics.bullish_count == 2

    def test_diagnostics_neutral_count_correct(self):
        signals = _make_composite_signals()
        rating = score_signals("AAPL", signals)
        assert rating.confidence_diagnostics.neutral_count == 3

    def test_diagnostics_does_not_change_confidence_label(self):
        signals = _make_composite_signals()
        rating = score_signals("AAPL", signals)
        # avg 0.60 → MEDIUM (0.45 ≤ avg < 0.70)
        assert rating.confidence == ConfidenceLevel.MEDIUM

    def test_diagnostics_does_not_change_score(self):
        signals = _make_composite_signals()
        rating_a = score_signals("AAPL", signals)
        # score must be deterministic and unchanged
        assert isinstance(rating_a.score, float)
        assert 0.0 <= rating_a.score <= 100.0

    def test_diagnostics_area_technical_average_present(self):
        signals = _make_composite_signals()
        rating = score_signals("AAPL", signals)
        assert rating.confidence_diagnostics.technical_average_confidence is not None

    def test_diagnostics_area_news_average_present(self):
        signals = _make_composite_signals()
        rating = score_signals("AAPL", signals)
        assert rating.confidence_diagnostics.news_average_confidence is not None

    def test_diagnostics_area_absent_when_category_not_in_signals(self):
        # Only TECHNICAL signals — no FUNDAMENTAL, NEWS, RISK
        signals = [_sig("T1", SignalCategory.TECHNICAL, confidence=0.65, score_impact=0.10)]
        rating = score_signals("AAPL", signals)
        assert rating.confidence_diagnostics.fundamental_average_confidence is None
        assert rating.confidence_diagnostics.news_average_confidence is None
        assert rating.confidence_diagnostics.risk_average_confidence is None

    def test_high_confidence_signals_still_yield_correct_label(self):
        signals = [
            _sig("T1", SignalCategory.TECHNICAL, SignalDirection.BULLISH, 0.80, 0.30),
            _sig("T2", SignalCategory.TECHNICAL, SignalDirection.BULLISH, 0.75, 0.20),
        ]
        rating = score_signals("AAPL", signals)
        assert rating.confidence == ConfidenceLevel.HIGH
        assert rating.confidence_diagnostics.average_signal_confidence == pytest.approx(0.775, abs=1e-4)

    def test_low_confidence_signals_still_yield_correct_label(self):
        signals = [
            _sig("T1", SignalCategory.TECHNICAL, confidence=0.30, score_impact=0.10),
            _sig("T2", SignalCategory.TECHNICAL, confidence=0.30, score_impact=0.10),
        ]
        rating = score_signals("AAPL", signals)
        assert rating.confidence == ConfidenceLevel.LOW
        assert rating.confidence_diagnostics.missing_count == 2


# ---------------------------------------------------------------------------
# Integration: build_stock_report passes diagnostics through
# ---------------------------------------------------------------------------

def _make_rating_with_diag(confidence_diagnostics=None) -> Rating:
    signals = _make_composite_signals()
    return Rating(
        ticker="AAPL",
        final_category=RatingCategory.WATCHLIST,
        score=60.0,
        confidence=ConfidenceLevel.MEDIUM,
        confidence_diagnostics=confidence_diagnostics,
        explanation="Rating for AAPL.",
        technical_score=60.0,
        data_sources_used=["yfinance"],
        signals_used=signals,
    )


class TestBuildStockReportDiagnostics:
    def test_diagnostics_passed_through_when_present(self):
        from app.models.confidence_diagnostics import ConfidenceDiagnostics
        diag = ConfidenceDiagnostics(signal_count=5, average_signal_confidence=0.60)
        rating = _make_rating_with_diag(confidence_diagnostics=diag)
        report = build_stock_report(rating)
        assert report.confidence_diagnostics is diag

    def test_diagnostics_is_none_when_rating_has_none(self):
        rating = _make_rating_with_diag(confidence_diagnostics=None)
        report = build_stock_report(rating)
        assert report.confidence_diagnostics is None

    def test_diagnostics_from_score_signals_survives_to_report(self):
        signals = _make_composite_signals()
        rating = score_signals("AAPL", signals)
        report = build_stock_report(rating)
        assert report.confidence_diagnostics is not None
        assert report.confidence_diagnostics.signal_count == len(signals)

    def test_existing_fields_unchanged(self):
        signals = _make_composite_signals()
        rating = score_signals("AAPL", signals)
        report = build_stock_report(rating)
        assert report.score == rating.score
        assert report.final_category == rating.final_category
        assert report.confidence_level == rating.confidence


# ---------------------------------------------------------------------------
# Integration: JSON serialization includes diagnostics
# ---------------------------------------------------------------------------

class TestJsonSerializationWithDiagnostics:
    def test_stock_report_json_includes_confidence_diagnostics(self):
        signals = _make_composite_signals()
        rating = score_signals("AAPL", signals)
        report = build_stock_report(rating)
        data = report.model_dump(mode="json")
        assert "confidence_diagnostics" in data

    def test_confidence_diagnostics_json_not_null(self):
        signals = _make_composite_signals()
        rating = score_signals("AAPL", signals)
        report = build_stock_report(rating)
        data = report.model_dump(mode="json")
        assert data["confidence_diagnostics"] is not None

    def test_confidence_diagnostics_json_has_signal_count(self):
        signals = _make_composite_signals()
        rating = score_signals("AAPL", signals)
        report = build_stock_report(rating)
        data = report.model_dump(mode="json")
        assert data["confidence_diagnostics"]["signal_count"] == len(signals)

    def test_confidence_diagnostics_json_has_average(self):
        signals = _make_composite_signals()
        rating = score_signals("AAPL", signals)
        report = build_stock_report(rating)
        data = report.model_dump(mode="json")
        assert "average_signal_confidence" in data["confidence_diagnostics"]

    def test_confidence_diagnostics_json_has_direction_counts(self):
        signals = _make_composite_signals()
        rating = score_signals("AAPL", signals)
        report = build_stock_report(rating)
        data = report.model_dump(mode="json")
        diag = data["confidence_diagnostics"]
        assert "bullish_count" in diag
        assert "bearish_count" in diag
        assert "neutral_count" in diag

    def test_confidence_diagnostics_json_has_area_averages(self):
        signals = _make_composite_signals()
        rating = score_signals("AAPL", signals)
        report = build_stock_report(rating)
        data = report.model_dump(mode="json")
        diag = data["confidence_diagnostics"]
        assert "technical_average_confidence" in diag
        assert "fundamental_average_confidence" in diag
        assert "news_average_confidence" in diag
        assert "risk_average_confidence" in diag

    def test_json_dumps_round_trips_without_error(self):
        signals = _make_composite_signals()
        rating = score_signals("AAPL", signals)
        report = build_stock_report(rating)
        data = report.model_dump(mode="json")
        json_str = json.dumps(data)
        restored = json.loads(json_str)
        assert restored["confidence_diagnostics"]["signal_count"] == len(signals)

    def test_confidence_diagnostics_null_when_none(self):
        rating = _make_rating_with_diag(confidence_diagnostics=None)
        report = build_stock_report(rating)
        data = report.model_dump(mode="json")
        assert data["confidence_diagnostics"] is None

    def test_save_json_result_writes_diagnostics(self):
        from app.data.storage import save_json_result
        signals = _make_composite_signals()
        rating = score_signals("AAPL", signals)
        report = build_stock_report(rating)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_json_result(report, "AAPL", output_dir=tmpdir)
            text = path.read_text(encoding="utf-8")
            parsed = json.loads(text)
        assert "confidence_diagnostics" in parsed
        assert parsed["confidence_diagnostics"]["signal_count"] == len(signals)


# ---------------------------------------------------------------------------
# Report templates — Markdown section
# ---------------------------------------------------------------------------

class TestMarkdownDiagnosticsSection:
    def _report_with_diag(self) -> StockReport:
        signals = _make_composite_signals()
        rating = score_signals("AAPL", signals)
        return build_stock_report(rating)

    def test_markdown_contains_confidence_diagnostics_heading(self):
        report = self._report_with_diag()
        md = format_report_markdown(report)
        assert "## Confidence Diagnostics" in md

    def test_markdown_contains_avg_confidence(self):
        report = self._report_with_diag()
        md = format_report_markdown(report)
        assert "Avg confidence" in md

    def test_markdown_contains_signal_count(self):
        report = self._report_with_diag()
        md = format_report_markdown(report)
        assert "Signals" in md

    def test_markdown_contains_direction_counts(self):
        report = self._report_with_diag()
        md = format_report_markdown(report)
        assert "bullish" in md

    def test_markdown_contains_missing_count(self):
        report = self._report_with_diag()
        md = format_report_markdown(report)
        assert "Missing-data" in md

    def test_markdown_diagnostics_absent_when_none(self):
        rating = _make_rating_with_diag(confidence_diagnostics=None)
        report = build_stock_report(rating)
        md = format_report_markdown(report)
        assert "## Confidence Diagnostics" not in md

    def test_existing_recommendation_section_still_present(self):
        report = self._report_with_diag()
        md = format_report_markdown(report)
        assert "## Recommendation" in md

    def test_existing_score_unchanged_in_markdown(self):
        report = self._report_with_diag()
        md = format_report_markdown(report)
        assert f"{report.score:.1f}" in md

    def test_disclaimer_still_present(self):
        report = self._report_with_diag()
        md = format_report_markdown(report)
        assert "not financial advice" in md
