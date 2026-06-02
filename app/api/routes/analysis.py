"""
Analysis route: POST /api/analyze.

Delegates to app.services.stock_analysis_service.analyze_stock — the
sole public entry point for the analysis engine. No pipeline logic lives here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.errors import KNOWN_ANALYSIS_ERRORS
from app.api.schemas.analysis import AnalyzeRequest
from app.models.stock_report import StockReport
from app.services.stock_analysis_service import analyze_stock

router = APIRouter()


@router.post("/analyze", response_model=StockReport)
async def analyze(request: AnalyzeRequest) -> StockReport:
    # analyze_stock is synchronous; acceptable for a single-user personal tool.
    # Wrap in asyncio.to_thread if concurrent request handling is needed later.
    try:
        return analyze_stock(request.ticker)
    except KNOWN_ANALYSIS_ERRORS as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc
