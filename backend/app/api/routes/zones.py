# backend/app/api/routes/zones.py
# Endpoints for administrative zone statistics (choropleth map).

from __future__ import annotations

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUserId
from app.api.dto.zones import ZoneDetail, ZoneListResponse
from app.services.zones.zone_service import get_zone_detail, get_zones_with_counts

router = APIRouter(
    prefix="/zones",
    tags=["Zones"],
)


@router.get(
    "",
    response_model=ZoneListResponse,
    summary="List administrative zones with cache counts",
)
async def list_zones(
    current_user_id: CurrentUserId,
    country: str = Query(..., description="ISO country code, e.g. 'FR'"),
    level: int = Query(..., ge=1, le=2, description="Administrative level: 1=region, 2=department"),
    type: str | None = Query(default=None, description="Filter by cache type code"),
) -> ZoneListResponse:
    """Returns administrative zones with found-cache counts for the current user.

    Description:
        Used by the choropleth map to color polygons according to the density of caches
        the authenticated user has found.  Only zones where the user found at least one
        cache are returned.
        Optionally filtered by cache type code (e.g. 'traditional', 'mystery').

    Args:
        current_user_id: Injected authenticated user ObjectId.
        country (str): ISO country code.
        level (int): Administrative level (1 or 2).
        type (list[str] | None): Optional cache type filter.

    Returns:
        ZoneListResponse: List of zones with counts, sorted by name.
    """
    items = await get_zones_with_counts(
        country=country,
        level=level,
        user_id=ObjectId(current_user_id),
        type_code=type,
    )
    return ZoneListResponse(items=items)


@router.get(
    "/{code}",
    response_model=ZoneDetail,
    summary="Get zone detail with top found caches",
)
async def get_zone(
    code: str,
    current_user_id: CurrentUserId,
    type: str | None = Query(default=None, description="Filter by cache type code"),
    level: int | None = Query(
        default=None,
        ge=1,
        le=2,
        description="Level hint to disambiguate codes shared between levels",
    ),
) -> ZoneDetail:
    """Returns zone detail with total found-cache count and first 10 found caches.

    Args:
        code (str): Zone code, e.g. 'FR-84' or 'FR-38'.
        current_user_id: Injected authenticated user ObjectId.
        type (list[str] | None): Optional cache type filter.
        level (int | None): Level hint (1 or 2) to disambiguate codes that exist at both levels.

    Returns:
        ZoneDetail: Zone name, total count, and first 10 caches.

    Raises:
        404: If the zone code is not found in administrative_zones.
    """
    detail = await get_zone_detail(
        code=code,
        user_id=ObjectId(current_user_id),
        type_code=type,
        level=level,
    )
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone '{code}' not found.",
        )
    return detail
