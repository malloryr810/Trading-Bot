"""
Stock discovery routes.

  GET /api/discovery            — ranked candidates from a controlled universe
  GET /api/discovery/modes      — supported discovery modes
  GET /api/discovery/universes  — registered stock universes

All routes delegate to app.services.discovery_service; no screening, analysis,
ranking, or persistence logic lives here. Invalid parameters map to HTTP 400.
Per-ticker failures do not fail the request — they are returned in the run's
``warnings`` list with a 200.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas.discovery import (
    DiscoveryModeResponse,
    DiscoveryResponse,
    DiscoveryUniverseResponse,
)
from app.data.universe_loader import UniverseLoadError
from app.services.discovery_service import (
    DEFAULT_LIMIT,
    DEFAULT_MAX_FULL_ANALYSIS,
    DEFAULT_MODE,
    DEFAULT_UNIVERSE,
    DiscoveryValidationError,
    list_discovery_modes,
    list_discovery_universes,
    run_discovery,
)

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.get("/modes", response_model=list[DiscoveryModeResponse])
async def get_modes() -> list[DiscoveryModeResponse]:
    """Return every supported discovery mode and how it ranks candidates."""
    return list_discovery_modes()


@router.get("/universes", response_model=list[DiscoveryUniverseResponse])
async def get_universes() -> list[DiscoveryUniverseResponse]:
    """Return every registered stock universe with its size."""
    try:
        return list_discovery_universes()
    except UniverseLoadError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("", response_model=DiscoveryResponse)
async def get_discovery(
    mode: str = DEFAULT_MODE.value,
    universe: str = DEFAULT_UNIVERSE,
    limit: int = DEFAULT_LIMIT,
    max_full_analysis: int = DEFAULT_MAX_FULL_ANALYSIS,
) -> DiscoveryResponse:
    """Run a bounded discovery scan and return ranked research candidates."""
    try:
        return run_discovery(
            mode=mode,
            universe=universe,
            limit=limit,
            max_full_analysis=max_full_analysis,
        )
    except DiscoveryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc
