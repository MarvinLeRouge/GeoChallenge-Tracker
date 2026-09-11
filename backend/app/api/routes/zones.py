# backend/app/api/routes/zones.py
# Endpoints for administrative zone statistics (choropleth map).

from __future__ import annotations

from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUserId
from app.api.dto.zones import ZoneDetail, ZoneListResponse
from app.services.zones.zone_service import (
    get_zone_detail,
    get_zones_with_counts,
)

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
    level: int = Query(
        ..., ge=0, le=2, description="Administrative level: 0=country, 1=region, 2=department"
    ),
    country: str | None = Query(
        default=None, description="ISO country code, e.g. 'FR'. Required for level 1/2."
    ),
    type: Annotated[list[str] | None, Query(description="Filter by cache type code(s)")] = None,
) -> ZoneListResponse:
    """Returns administrative zones with found-cache counts for the current user.

    Description:
        Used by the choropleth map to color polygons according to the density of caches
        the authenticated user has found.  Only zones where the user found at least one
        cache are returned.
        Optionally filtered by one or more cache type codes (e.g. 'traditional', 'mystery').

    Args:
        current_user_id: Injected authenticated user ObjectId.
        level (int): Administrative level (0=country, 1=region, 2=department).
        country (str | None): ISO country code. Required for level 1/2, ignored at level 0.
        type (list[str] | None): Optional cache type filter.

    Returns:
        ZoneListResponse: List of zones with counts, sorted by name.

    Raises:
        422: If level is 1 or 2 and country is missing.
    """
    if level != 0 and not country:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="country is required for level 1 and 2.",
        )
    items = await get_zones_with_counts(
        level=level,
        user_id=ObjectId(current_user_id),
        country=country,
        type_codes=type,
    )
    return ZoneListResponse(items=items)


@router.get(
    "/{code}",
    response_model=ZoneDetail,
    summary="Get zone detail with per-type cache breakdown",
)
async def get_zone(
    code: str,
    current_user_id: CurrentUserId,
    level: int | None = Query(
        default=None,
        ge=1,
        le=2,
        description="Level hint to disambiguate codes shared between levels",
    ),
) -> ZoneDetail:
    """Returns zone detail with total found-cache count and per-type breakdown.

    Description:
        All cache types are always included in the breakdown (count=0 for types with no
        found caches in this zone), ordered by canonical GC.com type order.

    Args:
        code (str): Zone code, e.g. 'FR-84' or 'FR-38'.
        current_user_id: Injected authenticated user ObjectId.
        level (int | None): Level hint (1 or 2) to disambiguate codes that exist at both levels.

    Returns:
        ZoneDetail: Zone name, total count, and per-type cache counts.

    Raises:
        404: If the zone code is not found in administrative_zones.
    """
    detail = await get_zone_detail(
        code=code,
        user_id=ObjectId(current_user_id),
        level=level,
    )
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone '{code}' not found.",
        )
    return detail
