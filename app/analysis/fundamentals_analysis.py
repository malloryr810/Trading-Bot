"""
Fundamentals analysis module.

Converts a CompanyFundamentals object into typed Signal objects using
transparent, rule-based logic. Signals are consumed by the scoring engine.
Does not fetch data — accepts a CompanyFundamentals model from the data layer.
"""

from __future__ import annotations

from app.models.fundamentals import CompanyFundamentals
from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength


class FundamentalAnalysisError(Exception):
    """Raised when fundamental signals cannot be built from the provided input."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_fundamental_signals(fundamentals: CompanyFundamentals) -> list[Signal]:
    """Convert a CompanyFundamentals object into typed Signal objects.

    Args:
        fundamentals: A CompanyFundamentals instance produced by the data layer.

    Returns:
        A list of 5 Signal objects covering valuation, profitability, growth,
        debt, and cash flow. Fields that are None produce neutral Signals with
        low confidence rather than raising exceptions.

    Raises:
        FundamentalAnalysisError: If fundamentals is not a CompanyFundamentals instance.
    """
    if not isinstance(fundamentals, CompanyFundamentals):
        raise FundamentalAnalysisError(
            f"Expected a CompanyFundamentals instance, got {type(fundamentals).__name__}."
        )

    return [
        _valuation_signal(fundamentals),
        _profitability_signal(fundamentals),
        _growth_signal(fundamentals),
        _debt_signal(fundamentals),
        _cash_flow_signal(fundamentals),
    ]


# ---------------------------------------------------------------------------
# Signal builders
# ---------------------------------------------------------------------------

def _valuation_signal(fundamentals: CompanyFundamentals) -> Signal:
    """Build a valuation Signal from P/E ratios (forward preferred, trailing fallback)."""
    pe = (
        fundamentals.forward_pe
        if fundamentals.forward_pe is not None
        else fundamentals.trailing_pe
    )
    pe_source = "forward P/E" if fundamentals.forward_pe is not None else "trailing P/E"
    pb = fundamentals.price_to_book

    if pe is None:
        return Signal(
            name="Valuation",
            category=SignalCategory.FUNDAMENTAL,
            direction=SignalDirection.NEUTRAL,
            strength=SignalStrength.WEAK,
            score_impact=0.0,
            confidence=0.30,
            description="Insufficient valuation data; no P/E ratio is available.",
            value=None,
            metadata={
                "trailing_pe": fundamentals.trailing_pe,
                "forward_pe": fundamentals.forward_pe,
                "price_to_book": pb,
            },
        )

    if pe <= 0:
        direction, strength = SignalDirection.BEARISH, SignalStrength.MODERATE
        score_impact, confidence = -0.20, 0.65
        description = (
            f"Negative or zero {pe_source} ({pe:.1f}) indicates the company "
            "is not currently profitable."
        )
    elif pe < 5:
        direction, strength = SignalDirection.NEUTRAL, SignalStrength.WEAK
        score_impact, confidence = 0.0, 0.50
        description = (
            f"Very low {pe_source} ({pe:.1f}) may indicate cyclical earnings "
            "or other unusual circumstances."
        )
    elif pe <= 25:
        direction, strength = SignalDirection.BULLISH, SignalStrength.MODERATE
        score_impact, confidence = 0.20, 0.65
        description = f"{pe_source.capitalize()} of {pe:.1f} is in an attractive valuation range."
    elif pe <= 40:
        direction, strength = SignalDirection.NEUTRAL, SignalStrength.WEAK
        score_impact, confidence = 0.0, 0.60
        description = f"{pe_source.capitalize()} of {pe:.1f} is elevated but not extreme."
    else:
        direction, strength = SignalDirection.BEARISH, SignalStrength.MODERATE
        score_impact, confidence = -0.20, 0.60
        description = (
            f"{pe_source.capitalize()} of {pe:.1f} suggests the stock is expensively valued."
        )

    return Signal(
        name="Valuation",
        category=SignalCategory.FUNDAMENTAL,
        direction=direction,
        strength=strength,
        score_impact=score_impact,
        confidence=confidence,
        description=description,
        value=pe,
        metadata={
            "pe_used": pe,
            "pe_source": pe_source,
            "trailing_pe": fundamentals.trailing_pe,
            "forward_pe": fundamentals.forward_pe,
            "price_to_book": pb,
        },
    )


def _profitability_signal(fundamentals: CompanyFundamentals) -> Signal:
    """Build a profitability Signal from profit margin."""
    margin = fundamentals.profit_margin

    if margin is None:
        return Signal(
            name="Profitability",
            category=SignalCategory.FUNDAMENTAL,
            direction=SignalDirection.NEUTRAL,
            strength=SignalStrength.WEAK,
            score_impact=0.0,
            confidence=0.30,
            description="Profit margin data is unavailable.",
            value=None,
            metadata={"profit_margin": None},
        )

    if margin >= 0.15:
        direction, strength = SignalDirection.BULLISH, SignalStrength.STRONG
        score_impact, confidence = 0.20, 0.70
        description = f"Strong profit margin of {margin:.1%} indicates robust profitability."
    elif margin >= 0.05:
        direction, strength = SignalDirection.BULLISH, SignalStrength.WEAK
        score_impact, confidence = 0.10, 0.60
        description = f"Positive profit margin of {margin:.1%}, though moderate."
    elif margin >= 0:
        direction, strength = SignalDirection.NEUTRAL, SignalStrength.WEAK
        score_impact, confidence = 0.0, 0.55
        description = f"Thin profit margin of {margin:.1%} indicates limited profitability."
    else:
        direction, strength = SignalDirection.BEARISH, SignalStrength.MODERATE
        score_impact, confidence = -0.20, 0.70
        description = (
            f"Negative profit margin of {margin:.1%} indicates the company "
            "is operating at a loss."
        )

    return Signal(
        name="Profitability",
        category=SignalCategory.FUNDAMENTAL,
        direction=direction,
        strength=strength,
        score_impact=score_impact,
        confidence=confidence,
        description=description,
        value=margin,
        metadata={"profit_margin": margin},
    )


def _growth_signal(fundamentals: CompanyFundamentals) -> Signal:
    """Build a growth Signal from revenue and earnings growth rates."""
    rev = fundamentals.revenue_growth
    earn = fundamentals.earnings_growth

    if rev is None and earn is None:
        return Signal(
            name="Growth",
            category=SignalCategory.FUNDAMENTAL,
            direction=SignalDirection.NEUTRAL,
            strength=SignalStrength.WEAK,
            score_impact=0.0,
            confidence=0.30,
            description="Revenue and earnings growth data are unavailable.",
            value=None,
            metadata={"revenue_growth": None, "earnings_growth": None},
        )

    if rev is not None and earn is not None:
        if rev > 0.10 and earn > 0.10:
            direction, strength = SignalDirection.BULLISH, SignalStrength.MODERATE
            score_impact, confidence = 0.20, 0.70
            description = (
                f"Both revenue ({rev:.1%}) and earnings ({earn:.1%}) are growing strongly."
            )
        elif rev > 0 and earn > 0:
            direction, strength = SignalDirection.BULLISH, SignalStrength.WEAK
            score_impact, confidence = 0.10, 0.60
            description = (
                f"Revenue ({rev:.1%}) and earnings ({earn:.1%}) are both growing positively."
            )
        elif rev < 0 and earn < 0:
            direction, strength = SignalDirection.BEARISH, SignalStrength.MODERATE
            score_impact, confidence = -0.20, 0.65
            description = (
                f"Both revenue ({rev:.1%}) and earnings ({earn:.1%}) are declining."
            )
        else:
            direction, strength = SignalDirection.NEUTRAL, SignalStrength.WEAK
            score_impact, confidence = 0.0, 0.50
            description = (
                f"Revenue ({rev:.1%}) and earnings ({earn:.1%}) growth signals are mixed."
            )
    else:
        direction, strength = SignalDirection.NEUTRAL, SignalStrength.WEAK
        score_impact, confidence = 0.0, 0.45
        description = "Only partial growth data is available; assessment is incomplete."

    return Signal(
        name="Growth",
        category=SignalCategory.FUNDAMENTAL,
        direction=direction,
        strength=strength,
        score_impact=score_impact,
        confidence=confidence,
        description=description,
        value=rev,
        metadata={"revenue_growth": rev, "earnings_growth": earn},
    )


def _debt_signal(fundamentals: CompanyFundamentals) -> Signal:
    """Build a debt Signal from the debt-to-equity ratio."""
    dte = fundamentals.debt_to_equity

    if dte is None:
        return Signal(
            name="Debt Levels",
            category=SignalCategory.FUNDAMENTAL,
            direction=SignalDirection.NEUTRAL,
            strength=SignalStrength.WEAK,
            score_impact=0.0,
            confidence=0.30,
            description="Debt-to-equity data is unavailable.",
            value=None,
            metadata={"debt_to_equity": None},
        )

    if dte < 0:
        direction, strength = SignalDirection.NEUTRAL, SignalStrength.WEAK
        score_impact, confidence = 0.0, 0.40
        description = (
            f"Negative debt-to-equity ({dte:.1f}) is unusual and may require further review."
        )
    elif dte <= 50:
        direction, strength = SignalDirection.BULLISH, SignalStrength.MODERATE
        score_impact, confidence = 0.15, 0.65
        description = f"Low debt-to-equity of {dte:.1f} indicates a conservative balance sheet."
    elif dte <= 150:
        direction, strength = SignalDirection.NEUTRAL, SignalStrength.WEAK
        score_impact, confidence = 0.0, 0.60
        description = f"Moderate debt-to-equity of {dte:.1f} is within an acceptable range."
    else:
        direction, strength = SignalDirection.BEARISH, SignalStrength.MODERATE
        score_impact, confidence = -0.15, 0.65
        description = f"High debt-to-equity of {dte:.1f} indicates elevated financial leverage."

    return Signal(
        name="Debt Levels",
        category=SignalCategory.FUNDAMENTAL,
        direction=direction,
        strength=strength,
        score_impact=score_impact,
        confidence=confidence,
        description=description,
        value=dte,
        metadata={"debt_to_equity": dte},
    )


def _cash_flow_signal(fundamentals: CompanyFundamentals) -> Signal:
    """Build a cash flow Signal from free cash flow."""
    fcf = fundamentals.free_cash_flow

    if fcf is None:
        return Signal(
            name="Free Cash Flow",
            category=SignalCategory.FUNDAMENTAL,
            direction=SignalDirection.NEUTRAL,
            strength=SignalStrength.WEAK,
            score_impact=0.0,
            confidence=0.30,
            description="Free cash flow data is unavailable.",
            value=None,
            metadata={"free_cash_flow": None},
        )

    if fcf > 0:
        direction, strength = SignalDirection.BULLISH, SignalStrength.MODERATE
        score_impact, confidence = 0.15, 0.65
        description = (
            "Positive free cash flow indicates the company generates cash "
            "after capital expenditures."
        )
    elif fcf < 0:
        direction, strength = SignalDirection.BEARISH, SignalStrength.MODERATE
        score_impact, confidence = -0.15, 0.65
        description = (
            "Negative free cash flow indicates the company is consuming more "
            "cash than it generates."
        )
    else:
        direction, strength = SignalDirection.NEUTRAL, SignalStrength.WEAK
        score_impact, confidence = 0.0, 0.55
        description = "Free cash flow is approximately zero."

    return Signal(
        name="Free Cash Flow",
        category=SignalCategory.FUNDAMENTAL,
        direction=direction,
        strength=strength,
        score_impact=score_impact,
        confidence=confidence,
        description=description,
        value=fcf,
        metadata={"free_cash_flow": fcf},
    )
