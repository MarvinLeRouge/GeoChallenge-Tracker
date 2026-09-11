# backend/app/api/routes/admin_geo.py
# Admin-only endpoints for managing GeoJSON coverage of administrative zones.

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.api.dto.geo_admin import MissingCountriesResponse
from app.services.zones.geo_admin_service import get_missing_countries

router = APIRouter(
    prefix="/admin/geo",
    tags=["Admin - Geo"],
    dependencies=[Depends(require_admin)],
)


@router.get(
    "/missing-countries",
    response_model=MissingCountriesResponse,
    summary="List countries with found caches but no GeoJSON coverage",
)
async def list_missing_countries() -> MissingCountriesResponse:
    """Returns countries that need their GeoJSON files uploaded.

    Returns:
        MissingCountriesResponse: Countries with found caches but no `{code}/` directory
            under the GeoJSON data root, sorted by found-cache count descending.
    """
    items = await get_missing_countries()
    return MissingCountriesResponse(items=items)  # type: ignore[arg-type]
