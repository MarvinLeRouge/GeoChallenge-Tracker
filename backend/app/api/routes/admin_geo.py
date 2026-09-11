# backend/app/api/routes/admin_geo.py
# Admin-only endpoints for managing GeoJSON coverage of administrative zones.

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile, status

from app.api.deps import require_admin
from app.api.dto.geo_admin import GeoUploadResponse, MissingCountriesResponse
from app.core.middleware import read_upload_file_with_limit
from app.core.settings import get_settings
from app.services.zones.geo_admin_service import get_missing_countries, upload_zone_level

_COUNTRY_CODE_RE = re.compile(r"^[A-Z]{2}$")

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


@router.post(
    "/{country_code}/upload",
    response_model=GeoUploadResponse,
    summary="Upload a normalized GeoJSON file for one administrative level",
)
async def upload_geo_file(
    country_code: Annotated[str, Path(description="ISO 3166-1 alpha-2 code, e.g. 'FR'.")],
    level: Annotated[int, Query(ge=0, le=2, description="Administrative level: 0, 1 or 2.")],
    file: Annotated[UploadFile, File(..., description="Normalized adm{level}.geojson file.")],
) -> GeoUploadResponse:
    """Uploads and ingests a normalized GeoJSON file for one country/level.

    Description:
        See ~/projets/geo_json/CONTRACT.md for the expected feature schema
        (`code`, `nom`, `feature_code`, `parent_code` for level 2, `bbox`).

    Args:
        country_code (str): ISO 3166-1 alpha-2 code, uppercase.
        level (int): Administrative level - 0, 1 or 2.
        file (UploadFile): The normalized GeoJSON FeatureCollection.

    Returns:
        GeoUploadResponse: Ingestion summary.

    Raises:
        422: If country_code is not a 2-letter uppercase code, or the file violates the contract.
        413: If the file exceeds the configured upload size limit.
    """
    if not _COUNTRY_CODE_RE.match(country_code):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="country_code must be a 2-letter uppercase ISO code, e.g. 'FR'.",
        )

    settings = get_settings()
    content = await read_upload_file_with_limit(file, settings.max_upload_bytes)

    try:
        result = await upload_zone_level(country_code, level, content)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return GeoUploadResponse(**result)
