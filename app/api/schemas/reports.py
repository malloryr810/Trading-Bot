"""
Response schemas for /api/reports/* endpoints.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.stock_report import StockReport


class SavedReportSummary(BaseModel):
    """Summary of a saved report — returned by the history endpoint."""

    id: int
    ticker: str
    company_name: str | None
    category: str
    score: float
    confidence: str
    created_at: datetime


class SavedReportDetail(SavedReportSummary):
    """Full saved report — returned by analyze-and-save and single-report endpoints."""

    report: StockReport
