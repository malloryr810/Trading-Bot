"""
Unit tests for app/analysis/fundamentals_analysis.py.

All tests use locally constructed CompanyFundamentals objects — no network calls.
"""

from datetime import datetime, timezone

import pytest

from app.analysis.fundamentals_analysis import (
    FundamentalAnalysisError,
    build_fundamental_signals,
)
from app.models.fundamentals import CompanyFundamentals
from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TS = datetime(2024, 6, 1, tzinfo=timezone.utc)

_SIGNAL_NAMES = {
    "Valuation",
    "Profitability",
    "Growth",
    "Debt Levels",
    "Free Cash Flow",
}


def _make_fundamentals(**overrides) -> CompanyFundamentals:
    """Return a CompanyFundamentals with healthy defaults and optional overrides."""
    defaults: dict = dict(
        ticker="AAPL",
        company_name="Apple Inc.",
        sector="Technology",
        industry="Consumer Electronics",
        market_cap=3_000_000_000_000,
        trailing_pe=22.0,
        forward_pe=20.0,
        price_to_book=10.0,
        profit_margin=0.25,
        revenue_growth=0.15,
        earnings_growth=0.15,
        debt_to_equity=40.0,
        free_cash_flow=90_000_000_000,
        dividend_yield=0.005,
        beta=1.2,
        data_timestamp=_TS,
    )
    defaults.update(overrides)
    return CompanyFundamentals(**defaults)


def _signal_by_name(signals: list[Signal], name: str) -> Signal:
    for s in signals:
        if s.name == name:
            return s
    raise KeyError(f"No signal named '{name}' in result.")


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

class TestStructure:
    def test_returns_list(self):
        result = build_fundamental_signals(_make_fundamentals())
        assert isinstance(result, list)

    def test_returns_exactly_5_signals(self):
        result = build_fundamental_signals(_make_fundamentals())
        assert len(result) == 5

    def test_all_items_are_signal_instances(self):
        result = build_fundamental_signals(_make_fundamentals())
        assert all(isinstance(s, Signal) for s in result)

    def test_all_signals_are_fundamental_category(self):
        result = build_fundamental_signals(_make_fundamentals())
        assert all(s.category == SignalCategory.FUNDAMENTAL for s in result)

    def test_signal_names_are_stable(self):
        result = build_fundamental_signals(_make_fundamentals())
        assert {s.name for s in result} == _SIGNAL_NAMES

    def test_all_descriptions_are_non_empty(self):
        result = build_fundamental_signals(_make_fundamentals())
        assert all(isinstance(s.description, str) and s.description.strip() for s in result)


# ---------------------------------------------------------------------------
# Valuation signal
# ---------------------------------------------------------------------------

class TestValuationSignal:
    def _get(self, **overrides) -> Signal:
        return _signal_by_name(
            build_fundamental_signals(_make_fundamentals(**overrides)), "Valuation"
        )

    def test_attractive_forward_pe_is_bullish(self):
        s = self._get(forward_pe=18.0)
        assert s.direction == SignalDirection.BULLISH
        assert s.score_impact > 0

    def test_attractive_trailing_pe_used_when_no_forward(self):
        s = self._get(forward_pe=None, trailing_pe=15.0)
        assert s.direction == SignalDirection.BULLISH

    def test_forward_pe_preferred_over_trailing_pe(self):
        # forward_pe is attractive, trailing_pe is expensive — forward wins
        s = self._get(forward_pe=20.0, trailing_pe=50.0)
        assert s.direction == SignalDirection.BULLISH

    def test_elevated_pe_is_neutral(self):
        s = self._get(forward_pe=32.0)
        assert s.direction == SignalDirection.NEUTRAL
        assert s.score_impact == pytest.approx(0.0)

    def test_expensive_pe_is_bearish(self):
        s = self._get(forward_pe=55.0)
        assert s.direction == SignalDirection.BEARISH
        assert s.score_impact < 0

    def test_negative_pe_is_bearish(self):
        s = self._get(forward_pe=-5.0, trailing_pe=-5.0)
        assert s.direction == SignalDirection.BEARISH
        assert s.score_impact < 0

    def test_zero_pe_is_bearish(self):
        s = self._get(forward_pe=0.0, trailing_pe=0.0)
        assert s.direction == SignalDirection.BEARISH

    def test_very_low_pe_is_neutral(self):
        s = self._get(forward_pe=2.0, trailing_pe=2.0)
        assert s.direction == SignalDirection.NEUTRAL

    def test_missing_both_pe_is_neutral_with_low_confidence(self):
        s = self._get(forward_pe=None, trailing_pe=None)
        assert s.direction == SignalDirection.NEUTRAL
        assert s.confidence == pytest.approx(0.30)
        assert s.score_impact == pytest.approx(0.0)

    def test_value_is_pe_used(self):
        s = self._get(forward_pe=20.0)
        assert s.value == pytest.approx(20.0)

    def test_value_is_none_when_pe_missing(self):
        s = self._get(forward_pe=None, trailing_pe=None)
        assert s.value is None

    def test_boundary_pe_25_is_bullish(self):
        s = self._get(forward_pe=25.0, trailing_pe=25.0)
        assert s.direction == SignalDirection.BULLISH

    def test_boundary_pe_just_above_25_is_neutral(self):
        s = self._get(forward_pe=25.1, trailing_pe=25.1)
        assert s.direction == SignalDirection.NEUTRAL

    def test_boundary_pe_40_is_neutral(self):
        s = self._get(forward_pe=40.0, trailing_pe=40.0)
        assert s.direction == SignalDirection.NEUTRAL

    def test_boundary_pe_just_above_40_is_bearish(self):
        s = self._get(forward_pe=40.1, trailing_pe=40.1)
        assert s.direction == SignalDirection.BEARISH


# ---------------------------------------------------------------------------
# Profitability signal
# ---------------------------------------------------------------------------

class TestProfitabilitySignal:
    def _get(self, **overrides) -> Signal:
        return _signal_by_name(
            build_fundamental_signals(_make_fundamentals(**overrides)), "Profitability"
        )

    def test_strong_margin_is_bullish_strong(self):
        s = self._get(profit_margin=0.25)
        assert s.direction == SignalDirection.BULLISH
        assert s.strength == SignalStrength.STRONG
        assert s.score_impact == pytest.approx(0.20)

    def test_moderate_margin_is_bullish_weak(self):
        s = self._get(profit_margin=0.10)
        assert s.direction == SignalDirection.BULLISH
        assert s.strength == SignalStrength.WEAK
        assert s.score_impact == pytest.approx(0.10)

    def test_thin_margin_is_neutral(self):
        s = self._get(profit_margin=0.02)
        assert s.direction == SignalDirection.NEUTRAL
        assert s.score_impact == pytest.approx(0.0)

    def test_zero_margin_is_neutral(self):
        s = self._get(profit_margin=0.0)
        assert s.direction == SignalDirection.NEUTRAL

    def test_negative_margin_is_bearish(self):
        s = self._get(profit_margin=-0.10)
        assert s.direction == SignalDirection.BEARISH
        assert s.score_impact < 0

    def test_missing_margin_is_neutral_low_confidence(self):
        s = self._get(profit_margin=None)
        assert s.direction == SignalDirection.NEUTRAL
        assert s.confidence == pytest.approx(0.30)

    def test_value_is_profit_margin(self):
        s = self._get(profit_margin=0.20)
        assert s.value == pytest.approx(0.20)

    def test_boundary_15pct_is_strong(self):
        s = self._get(profit_margin=0.15)
        assert s.strength == SignalStrength.STRONG

    def test_boundary_just_below_15pct_is_weak(self):
        s = self._get(profit_margin=0.149)
        assert s.strength == SignalStrength.WEAK


# ---------------------------------------------------------------------------
# Growth signal
# ---------------------------------------------------------------------------

class TestGrowthSignal:
    def _get(self, **overrides) -> Signal:
        return _signal_by_name(
            build_fundamental_signals(_make_fundamentals(**overrides)), "Growth"
        )

    def test_strong_growth_both_above_10pct_is_bullish_moderate(self):
        s = self._get(revenue_growth=0.15, earnings_growth=0.12)
        assert s.direction == SignalDirection.BULLISH
        assert s.strength == SignalStrength.MODERATE
        assert s.score_impact == pytest.approx(0.20)

    def test_both_positive_under_10pct_is_bullish_weak(self):
        s = self._get(revenue_growth=0.05, earnings_growth=0.07)
        assert s.direction == SignalDirection.BULLISH
        assert s.strength == SignalStrength.WEAK
        assert s.score_impact == pytest.approx(0.10)

    def test_mixed_one_positive_one_negative_is_neutral(self):
        s = self._get(revenue_growth=0.08, earnings_growth=-0.03)
        assert s.direction == SignalDirection.NEUTRAL
        assert s.score_impact == pytest.approx(0.0)

    def test_both_negative_growth_is_bearish(self):
        s = self._get(revenue_growth=-0.05, earnings_growth=-0.10)
        assert s.direction == SignalDirection.BEARISH
        assert s.score_impact < 0

    def test_one_missing_one_positive_is_neutral_partial(self):
        s = self._get(revenue_growth=0.10, earnings_growth=None)
        assert s.direction == SignalDirection.NEUTRAL
        assert s.confidence == pytest.approx(0.45)

    def test_one_missing_one_negative_is_neutral_partial(self):
        s = self._get(revenue_growth=None, earnings_growth=-0.05)
        assert s.direction == SignalDirection.NEUTRAL

    def test_both_missing_growth_is_neutral_low_confidence(self):
        s = self._get(revenue_growth=None, earnings_growth=None)
        assert s.direction == SignalDirection.NEUTRAL
        assert s.confidence == pytest.approx(0.30)
        assert s.score_impact == pytest.approx(0.0)

    def test_boundary_both_exactly_10pct_is_bullish_moderate(self):
        s = self._get(revenue_growth=0.101, earnings_growth=0.101)
        assert s.direction == SignalDirection.BULLISH
        assert s.strength == SignalStrength.MODERATE

    def test_value_is_revenue_growth(self):
        s = self._get(revenue_growth=0.15, earnings_growth=0.15)
        assert s.value == pytest.approx(0.15)


# ---------------------------------------------------------------------------
# Debt signal
# ---------------------------------------------------------------------------

class TestDebtSignal:
    def _get(self, **overrides) -> Signal:
        return _signal_by_name(
            build_fundamental_signals(_make_fundamentals(**overrides)), "Debt Levels"
        )

    def test_low_dte_is_bullish(self):
        s = self._get(debt_to_equity=30.0)
        assert s.direction == SignalDirection.BULLISH
        assert s.score_impact > 0

    def test_zero_dte_is_bullish(self):
        s = self._get(debt_to_equity=0.0)
        assert s.direction == SignalDirection.BULLISH

    def test_moderate_dte_is_neutral(self):
        s = self._get(debt_to_equity=100.0)
        assert s.direction == SignalDirection.NEUTRAL
        assert s.score_impact == pytest.approx(0.0)

    def test_high_dte_is_bearish(self):
        s = self._get(debt_to_equity=200.0)
        assert s.direction == SignalDirection.BEARISH
        assert s.score_impact < 0

    def test_negative_dte_is_neutral_with_lower_confidence(self):
        s = self._get(debt_to_equity=-10.0)
        assert s.direction == SignalDirection.NEUTRAL
        assert s.confidence == pytest.approx(0.40)

    def test_missing_dte_is_neutral_low_confidence(self):
        s = self._get(debt_to_equity=None)
        assert s.direction == SignalDirection.NEUTRAL
        assert s.confidence == pytest.approx(0.30)

    def test_boundary_50_is_bullish(self):
        s = self._get(debt_to_equity=50.0)
        assert s.direction == SignalDirection.BULLISH

    def test_boundary_just_above_50_is_neutral(self):
        s = self._get(debt_to_equity=50.1)
        assert s.direction == SignalDirection.NEUTRAL

    def test_boundary_150_is_neutral(self):
        s = self._get(debt_to_equity=150.0)
        assert s.direction == SignalDirection.NEUTRAL

    def test_boundary_just_above_150_is_bearish(self):
        s = self._get(debt_to_equity=150.1)
        assert s.direction == SignalDirection.BEARISH

    def test_value_is_debt_to_equity(self):
        s = self._get(debt_to_equity=75.0)
        assert s.value == pytest.approx(75.0)


# ---------------------------------------------------------------------------
# Cash flow signal
# ---------------------------------------------------------------------------

class TestCashFlowSignal:
    def _get(self, **overrides) -> Signal:
        return _signal_by_name(
            build_fundamental_signals(_make_fundamentals(**overrides)), "Free Cash Flow"
        )

    def test_positive_fcf_is_bullish(self):
        s = self._get(free_cash_flow=50_000_000_000)
        assert s.direction == SignalDirection.BULLISH
        assert s.score_impact > 0

    def test_negative_fcf_is_bearish(self):
        s = self._get(free_cash_flow=-1_000_000_000)
        assert s.direction == SignalDirection.BEARISH
        assert s.score_impact < 0

    def test_zero_fcf_is_neutral(self):
        s = self._get(free_cash_flow=0)
        assert s.direction == SignalDirection.NEUTRAL
        assert s.score_impact == pytest.approx(0.0)

    def test_missing_fcf_is_neutral_low_confidence(self):
        s = self._get(free_cash_flow=None)
        assert s.direction == SignalDirection.NEUTRAL
        assert s.confidence == pytest.approx(0.30)

    def test_value_is_free_cash_flow(self):
        s = self._get(free_cash_flow=90_000_000_000)
        assert s.value == pytest.approx(90_000_000_000)

    def test_small_positive_fcf_is_bullish(self):
        s = self._get(free_cash_flow=1)
        assert s.direction == SignalDirection.BULLISH


# ---------------------------------------------------------------------------
# Minimal input — all optional fields None
# ---------------------------------------------------------------------------

class TestMinimalInput:
    def _minimal(self) -> CompanyFundamentals:
        return CompanyFundamentals(ticker="AAPL", data_timestamp=_TS)

    def test_minimal_fundamentals_returns_5_signals(self):
        result = build_fundamental_signals(self._minimal())
        assert len(result) == 5

    def test_minimal_fundamentals_all_signal_instances(self):
        result = build_fundamental_signals(self._minimal())
        assert all(isinstance(s, Signal) for s in result)

    def test_missing_all_metrics_never_crashes(self):
        f = _make_fundamentals(
            trailing_pe=None, forward_pe=None, price_to_book=None,
            profit_margin=None, revenue_growth=None, earnings_growth=None,
            debt_to_equity=None, free_cash_flow=None,
        )
        result = build_fundamental_signals(f)
        assert len(result) == 5

    def test_all_missing_signals_have_low_confidence(self):
        result = build_fundamental_signals(self._minimal())
        assert all(s.confidence == pytest.approx(0.30) for s in result)

    def test_all_missing_signals_are_neutral(self):
        result = build_fundamental_signals(self._minimal())
        assert all(s.direction == SignalDirection.NEUTRAL for s in result)

    def test_all_missing_signals_have_zero_impact(self):
        result = build_fundamental_signals(self._minimal())
        assert all(s.score_impact == pytest.approx(0.0) for s in result)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_non_fundamentals_string_raises(self):
        with pytest.raises(FundamentalAnalysisError):
            build_fundamental_signals("AAPL")  # type: ignore[arg-type]

    def test_none_raises(self):
        with pytest.raises(FundamentalAnalysisError):
            build_fundamental_signals(None)  # type: ignore[arg-type]

    def test_dict_raises(self):
        with pytest.raises(FundamentalAnalysisError):
            build_fundamental_signals({"ticker": "AAPL"})  # type: ignore[arg-type]
