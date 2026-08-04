"""
FastAPI application factory.

Run the API server with:
    uvicorn app.api.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    analysis,
    health,
    market_data,
    portfolios,
    reports,
    watchlist_snapshots,
    watchlists,
)

# Allowed origins for local frontend development (Vite default port).
# Keep this list narrow — do not use allow_origins=["*"].
_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    _app = FastAPI(
        title="Investment Bot API",
        description="Personal stock research decision-support API.",
        version="1.0.0",
    )
    _app.add_middleware(
        CORSMiddleware,
        allow_origins=_CORS_ORIGINS,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    _app.include_router(health.router, prefix="/api")
    _app.include_router(analysis.router, prefix="/api")
    _app.include_router(reports.router, prefix="/api")
    _app.include_router(watchlists.router, prefix="/api")
    _app.include_router(watchlist_snapshots.router, prefix="/api")
    _app.include_router(market_data.router, prefix="/api")
    _app.include_router(portfolios.router, prefix="/api")
    return _app


app = create_app()
