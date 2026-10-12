"""
Response schemas for the market-data history endpoint.

The market-data service already returns typed models, so this module only names
them for the HTTP layer rather than redefining their fields.

Source of truth: app/models/market_data.py
"""

from __future__ import annotations

from app.models.market_data import PriceHistoryResponse, PricePoint

__all__ = ["PriceHistoryResponse", "PricePoint"]
