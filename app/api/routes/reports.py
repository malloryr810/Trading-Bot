"""
Report persistence routes.

  POST /api/reports/analyze      — analyze a ticker and save the snapshot
  GET  /api/reports/history      — list saved report summaries
  GET  /api/reports/{report_id}  — retrieve one full saved report

All routes delegate to the service layer; no pipeline or persistence logic
lives here.  ``POST /api/analyze`` (the analysis-only endpoint) is unaffected.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.errors import KNOWN_ANALYSIS_ERRORS
from app.api.schemas.analysis import AnalyzeRequest
from app.api.schemas.reports import SavedReportDetail, SavedReportSummary
from app.services.report_persistence_service import (
    get_saved_report,
    list_saved_reports,
    save_stock_report,
)
from app.services.stock_analysis_service import analyze_stock

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/analyze", response_model=SavedReportDetail)
async def analyze_and_save(request: AnalyzeRequest) -> dict:
    """Analyze a ticker and persist the resulting StockReport snapshot."""
    try:
        report = analyze_stock(request.ticker)
    except KNOWN_ANALYSIS_ERRORS as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc

    try:
        return save_stock_report(report)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to save report") from exc


@router.get("/history", response_model=list[SavedReportSummary])
async def get_report_history(limit: int = 50) -> list[dict]:
    """Return saved report summaries, newest first."""
    return list_saved_reports(limit=limit)


@router.get("/{report_id}", response_model=SavedReportDetail)
async def get_report(report_id: int) -> dict:
    """Return one full saved StockReport snapshot by id."""
    result = get_saved_report(report_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return result
