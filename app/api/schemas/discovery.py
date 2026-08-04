"""
Response schemas for /api/discovery* endpoints.

The discovery service already returns typed domain models, so this module only
names them for the HTTP layer rather than redefining their fields — keeping one
source of truth for the discovery contract.

Source of truth: app/models/discovery.py, app/models/universe.py
"""

from __future__ import annotations

from app.models.discovery import (
    DiscoveryCandidate,
    DiscoveryMode,
    DiscoveryModeInfo,
    DiscoveryRun,
    DiscoveryStage,
    DiscoveryWarning,
)
from app.models.universe import UniverseInfo

# The full discovery run is the response body of GET /api/discovery.
DiscoveryResponse = DiscoveryRun

# Listing endpoints.
DiscoveryModeResponse = DiscoveryModeInfo
DiscoveryUniverseResponse = UniverseInfo

__all__ = [
    "DiscoveryCandidate",
    "DiscoveryMode",
    "DiscoveryModeResponse",
    "DiscoveryResponse",
    "DiscoveryStage",
    "DiscoveryUniverseResponse",
    "DiscoveryWarning",
]
