# backend/app/services/elevation_retrieval.py
# Interface d’appel asynchrone pour récupérer les altitudes via un provider (OpenTopoData par défaut).

from __future__ import annotations

from app.core.settings import get_settings
settings = get_settings()

# Provider registry (can be extended later)
from app.services.providers.elevation_opentopo import fetch as fetch_opentopo

DEFAULT_PROVIDER = settings.elevation_provider


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
    provider = DEFAULT_PROVIDER.lower()
    if provider in ("opentopo", "opentopodata"):
        return await fetch_opentopo(points)
    # Fallback: no provider -> all None
    return [None] * len(points)
