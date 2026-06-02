"""
FastAPI application factory.

Run the API server with:
    uvicorn app.api.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import analysis, health, reports


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    _app = FastAPI(
        title="Investment Bot API",
        description="Personal stock research decision-support API.",
        version="1.0.0",
    )
    _app.include_router(health.router, prefix="/api")
    _app.include_router(analysis.router, prefix="/api")
    _app.include_router(reports.router, prefix="/api")
    return _app


app = create_app()
