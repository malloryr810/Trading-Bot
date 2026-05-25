"""
Fundamentals data fetcher.

Responsible for retrieving basic company information and key financial metrics
from yfinance. Returns a typed CompanyFundamentals model consumed by the
analysis layer. Does not perform scoring or signal generation.
"""

from __future__ import annotations

from datetime import datetime, timezone

import yfinance as yf

from app.models.fundamentals import CompanyFundamentals
from app.utils.helpers import normalize_ticker, safe_float


class FundamentalDataFetchError(Exception):
    """Raised when fundamental company data cannot be fetched or validated."""


def get_company_fundamentals(ticker: str) -> CompanyFundamentals:
    """Fetch and return basic fundamental data for a ticker.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL"). Case-insensitive.

    Returns:
        A CompanyFundamentals instance with available metrics populated.
        Fields missing from yfinance are returned as None.

    Raises:
        FundamentalDataFetchError: If the ticker is invalid, yfinance raises
            an error, or the returned data does not identify a valid company.
    """
    try:
        symbol = normalize_ticker(ticker)
    except ValueError as exc:
        raise FundamentalDataFetchError(str(exc)) from exc

    try:
        info = yf.Ticker(symbol).info
    except Exception as exc:
        raise FundamentalDataFetchError(
            f"yfinance raised an error while fetching fundamentals for '{symbol}': {exc}"
        ) from exc

    if not isinstance(info, dict) or not info:
        raise FundamentalDataFetchError(
            f"No data returned by yfinance for ticker '{symbol}'. "
            "The symbol may be invalid or delisted."
        )

    company_name = _extract_company_name(info)
    if company_name is None:
        raise FundamentalDataFetchError(
            f"yfinance returned data for '{symbol}' but could not identify the company. "
            "The symbol may be invalid."
        )

    return CompanyFundamentals(
        ticker=symbol,
        company_name=company_name,
        sector=info.get("sector") or None,
        industry=info.get("industry") or None,
        market_cap=safe_float(info.get("marketCap")),
        trailing_pe=safe_float(info.get("trailingPE")),
        forward_pe=safe_float(info.get("forwardPE")),
        price_to_book=safe_float(info.get("priceToBook")),
        profit_margin=safe_float(info.get("profitMargins")),
        revenue_growth=safe_float(info.get("revenueGrowth")),
        earnings_growth=safe_float(info.get("earningsGrowth")),
        debt_to_equity=safe_float(info.get("debtToEquity")),
        free_cash_flow=safe_float(info.get("freeCashflow")),
        dividend_yield=safe_float(info.get("dividendYield")),
        beta=safe_float(info.get("beta")),
        data_timestamp=datetime.now(tz=timezone.utc),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_company_name(info: dict) -> str | None:
    """Return the best available company name from yfinance info, or None."""
    return info.get("longName") or info.get("shortName") or None
