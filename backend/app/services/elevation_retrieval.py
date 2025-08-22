# backend/app/services/elevation_retrieval.py

from __future__ import annotations
from typing import List, Optional, Tuple
import os

# Provider registry (can be extended later)
from app.services.providers.elevation_opentopo import fetch as fetch_opentopo
from app.core.settings import settings

DEFAULT_PROVIDER = settings.elevation_provider

async def fetch(points: List[Tuple[float, float]]) -> List[Optional[int]]:
    """
    Fetch elevations for a list of (lat, lon) points.
    Returns a list aligned to 'points' with altitude in meters or None.
    """
    provider = DEFAULT_PROVIDER.lower()
    if provider in ("opentopo", "opentopodata"):
        return await fetch_opentopo(points)
    # Fallback: no provider -> all None
    return [None] * len(points)
