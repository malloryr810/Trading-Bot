"""
Fundamentals model.

Defines the typed output of the fundamental data layer. A CompanyFundamentals
object holds basic company identity and key financial metrics for a single
ticker. All metric fields are optional because yfinance frequently returns
incomplete data — missing values become None rather than causing errors.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class CompanyFundamentals(BaseModel):
    """Basic company identity and financial metrics for a single ticker."""

    # Identity
    ticker: str
    company_name: str | None = None
    sector: str | None = None
    industry: str | None = None

    # Valuation
    market_cap: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    price_to_book: float | None = None

    # Profitability / growth
    profit_margin: float | None = None
    revenue_growth: float | None = None
    earnings_growth: float | None = None

    # Balance sheet / cash flow
    debt_to_equity: float | None = None
    free_cash_flow: float | None = None

    # Income / risk
    dividend_yield: float | None = None
    beta: float | None = None

    # Provenance
    data_timestamp: datetime
    source: str = "yfinance"

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("ticker")
    @classmethod
    def ticker_normalized(cls, v: str) -> str:
        normalized = v.strip().upper()
        if not normalized:
            raise ValueError("ticker must not be empty or whitespace.")
        return normalized
