# backend/app/services/elevation_retrieval.py
# Async interface for retrieving elevations via a provider (OpenTopoData by default).

from __future__ import annotations

from collections.abc import Awaitable
from typing import Callable

from app.core.settings import get_settings

# Provider registry (can be extended later)
from app.services.providers.elevation_opentopo import fetch as fetch_opentopo

settings = get_settings()


DEFAULT_PROVIDER = (settings.elevation_provider or "").lower()
_PROVIDERS: dict[str, Callable[[list[tuple[float, float]]], Awaitable[list[int | None]]]] = {
    "opentopo": fetch_opentopo,
    "opentopodata": fetch_opentopo,
}


async def fetch(points: list[tuple[float, float]]) -> list[int | None]:
    """Retrieve elevations for a list of points.

    Description:
        Uses the configured provider (`settings.elevation_provider`, e.g. "opentopo") to query
        elevations for a list of `(lat, lon)` points. The response is index-aligned with `points`.
        If no provider is available, returns a list of `None`.

    Args:
        points (list[tuple[float, float]]): List of coordinates (latitude, longitude).

    Returns:
        list[int | None]: Elevations in meters (or `None` on unavailability/failure), aligned with `points`.
    """
    if not DEFAULT_PROVIDER:
        return [None] * len(points)
    provider_fn = _PROVIDERS.get(DEFAULT_PROVIDER)
    if not provider_fn:
        # depending on preference: raise HTTPException(422, ...) if called from a route
        return [None] * len(points)
    return await provider_fn(points)
