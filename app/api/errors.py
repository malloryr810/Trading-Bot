"""
Shared analysis error types for API route error handling.

Both /api/analyze and /api/reports/analyze map these errors to HTTP 422.
Centralising them here means a new pipeline error type only needs to be
added in one place.
"""

from __future__ import annotations

from app.analysis.fundamentals_analysis import FundamentalAnalysisError
from app.analysis.news_analysis import NewsAnalysisError
from app.analysis.risk_analysis import RiskAnalysisError
from app.analysis.scoring import ScoringError
from app.analysis.technicals import TechnicalAnalysisError
from app.data.fundamentals import FundamentalDataFetchError
from app.data.market_data import DataFetchError

KNOWN_ANALYSIS_ERRORS = (
    DataFetchError,
    FundamentalDataFetchError,
    TechnicalAnalysisError,
    FundamentalAnalysisError,
    RiskAnalysisError,
    NewsAnalysisError,
    ScoringError,
)
