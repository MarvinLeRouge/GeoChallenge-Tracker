# backend/app/services/elevation_retrieval.py
# Interface d’appel asynchrone pour récupérer les altitudes via un provider (OpenTopoData par défaut).

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
    """Récupérer les altitudes pour une liste de points.

    Description:
        Utilise le provider configuré (`settings.elevation_provider`, ex. "opentopo") pour interroger
        les altitudes d’une liste de points `(lat, lon)`. La réponse est alignée en index sur `points`.
        Si aucun provider n’est disponible, retourne une liste de `None`.

    Args:
        points (list[tuple[float, float]]): Liste de coordonnées (latitude, longitude).

    Returns:
        list[int | None]: Altitudes en mètres (ou `None` en cas d’indisponibilité/échec), alignées sur `points`.
    """
    if not DEFAULT_PROVIDER:
        return [None] * len(points)
    provider_fn = _PROVIDERS.get(DEFAULT_PROVIDER)
    if not provider_fn:
        # selon ta préférence: raise HTTPException(422, ...) si appelé depuis une route
        return [None] * len(points)
    return await provider_fn(points)
