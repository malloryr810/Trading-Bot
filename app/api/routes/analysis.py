"""
Analysis route: POST /api/analyze.

Delegates to app.services.stock_analysis_service.analyze_stock — the
sole public entry point for the analysis engine. No pipeline logic lives here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.analysis.fundamentals_analysis import FundamentalAnalysisError
from app.analysis.news_analysis import NewsAnalysisError
from app.analysis.risk_analysis import RiskAnalysisError
from app.analysis.scoring import ScoringError
from app.analysis.technicals import TechnicalAnalysisError
from app.api.schemas.analysis import AnalyzeRequest
from app.data.fundamentals import FundamentalDataFetchError
from app.data.market_data import DataFetchError
from app.models.stock_report import StockReport
from app.services.stock_analysis_service import analyze_stock

_KNOWN_ERRORS = (
    DataFetchError,
    FundamentalDataFetchError,
    TechnicalAnalysisError,
    FundamentalAnalysisError,
    RiskAnalysisError,
    NewsAnalysisError,
    ScoringError,
)

router = APIRouter()


@router.post("/analyze", response_model=StockReport)
async def analyze(request: AnalyzeRequest) -> StockReport:
    # analyze_stock is synchronous; acceptable for a single-user personal tool.
    # Wrap in asyncio.to_thread if concurrent request handling is needed later.
    try:
        return analyze_stock(request.ticker)
    except _KNOWN_ERRORS as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc
