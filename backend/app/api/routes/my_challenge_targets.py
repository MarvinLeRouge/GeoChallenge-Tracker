# backend/app/api/routes/my_challenge_targets.py
# "Targets" routes: evaluation/refresh of targets per challenge, paginated listings (global/nearby), deletion.

from __future__ import annotations

from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import CurrentUserId
from app.api.dto.target import TargetListResponse
from app.core.security import get_current_user
from app.core.utils import utcnow
from app.db.mongodb import get_db
from app.services.targets_service import (
    delete_targets_for_user_challenge,
    evaluate_all_for_user,
    evaluate_targets_for_user_challenge,
    get_targets_refresh_status,
    list_targets_for_user,
    list_targets_for_user_challenge,
    list_targets_nearby_for_user,
    list_targets_nearby_for_user_challenge,
)
from app.services.user_profile_service import UserProfileService

router = APIRouter(
    prefix="/my", tags=["My challenge targets"], dependencies=[Depends(get_current_user)]
)


# ---------------------------
# Helpers
# ---------------------------


def _as_objid(v: Any) -> ObjectId:
    """Converts a value to ObjectId (preserving it if already typed as ObjectId).

    Args:
        v (Any): Value to convert.

    Returns:
        ObjectId: MongoDB identifier.
    """
    if isinstance(v, ObjectId):
        return v
    return ObjectId(str(v))


def _current_user_id(current_user: dict) -> ObjectId:
    """Extracts the ObjectId of the current user, or raises 401 if absent.

    Args:
        current_user (dict): Authenticated user.

    Returns:
        ObjectId: User identifier.
    """
    uid = current_user.get("_id")
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthenticated.")
    return _as_objid(uid)


# ---------------------------
# Evaluate / refresh (per UserChallenge)
# ---------------------------


# TODO: [BACKLOG] Route /my/challenges/{uc_id}/targets/evaluate (POST) to verify
@router.post(
    "/challenges/{uc_id}/targets/evaluate",
    status_code=status.HTTP_200_OK,
    summary="Evaluate and persist targets for a UserChallenge",
    description=(
        "Computes **targets** for a UserChallenge by aggregating unfound caches that satisfy ≥1 task,\n"
        "deduplicates, scores, then upserts to the database.\n\n"
        "- Controllable caps (`limit_per_task`, `hard_limit_total`)\n"
        "- Optional geographic filter (`include_geo_filter` + `lat`/`lon`/`radius_km`)\n"
        "- `force` option to recalculate even if targets already exist"
    ),
)
async def evaluate_targets(
    user_id: CurrentUserId,
    uc_id: str = Path(..., description="UserChallenge identifier."),
    limit_per_task: int = Query(500, ge=1, le=5000, description="Computation cap per task."),
    hard_limit_total: int = Query(
        2000, ge=1, le=20000, description="Global cap before merging/scoring."
    ),
    include_geo_filter: bool = Query(
        False, description="Enable a geographic filter during evaluation."
    ),
    lat: float | None = Query(
        None, ge=-90, le=90, description="Latitude for geo filter (if enabled)."
    ),
    lon: float | None = Query(
        None, ge=-180, le=180, description="Longitude for geo filter (if enabled)."
    ),
    radius_km: float | None = Query(
        None, gt=0, description="Radius (km) required if `include_geo_filter=true`."
    ),
    force: bool = Query(False, description="Force recalculation even if targets already exist."),
):
    """Evaluate and persist targets for a UserChallenge.

    Description:
        Builds the list of target caches based on the challenge tasks, applies scoring, and
        saves the result. Can restrict evaluation to a geographic area.

    Args:
        uc_id (str): UserChallenge identifier.
        limit_per_task (int): Per-task cap during evaluation.
        hard_limit_total (int): Global cap before merging/scoring.
        include_geo_filter (bool): Enable geographic filter.
        lat (float | None): Latitude for geo filter.
        lon (float | None): Longitude for geo filter.
        radius_km (float | None): Radius (km) required if geo filter is active.
        force (bool): Recalculate even if targets already exist.

    Returns:
        dict: Report `{ok, inserted, updated, total}`.
    """
    uc_oid = _as_objid(uc_id)

    geo_ctx = None
    if include_geo_filter:
        # if lat/lon not provided, try to retrieve from user profile
        if lat is None or lon is None:
            db = get_db()
            user_profile_service = UserProfileService(db)
            location_data = await user_profile_service.get_user_location(user_id)
            if not location_data:
                raise HTTPException(
                    status_code=422,
                    detail="No user location found; provide lat/lon or save your location first.",
                )
            lon, lat = location_data["coordinates"][0], location_data["coordinates"][1]
        if radius_km is None:
            raise HTTPException(
                status_code=422,
                detail="radius_km is required when include_geo_filter=true.",
            )
        geo_ctx = {"lat": lat, "lon": lon, "radius_km": radius_km}

    result = await evaluate_targets_for_user_challenge(
        user_id=user_id,
        uc_id=uc_oid,
        limit_per_task=int(limit_per_task),
        hard_limit_total=int(hard_limit_total),
        geo_ctx=geo_ctx,
        evaluated_at=utcnow(),
        force=force,
    )
    # expected result: {"ok": True, "inserted": int, "updated": int, "total": int}
    return result


# ---------------------------
# Listing (per UserChallenge)
# ---------------------------


# TODO: [BACKLOG] Route /my/challenges/{uc_id}/targets (GET) to verify
@router.get(
    "/challenges/{uc_id}/targets",
    response_model=TargetListResponse,
    summary="List targets for a UserChallenge",
    description=(
        "Returns the **paginated** list of targets for a UserChallenge.\n"
        "- Configurable sort (e.g. `-score`, `distance`, `GC`)\n"
        "- Pagination via `page`/`limit` (max 200)"
    ),
)
async def list_targets_uc(
    user_id: CurrentUserId,
    uc_id: str = Path(..., description="UserChallenge identifier."),
    page: int = Query(1, ge=1, description="Page number."),
    page_size: int = Query(50, ge=1, le=200, description="Page size (1–200)."),
    sort: str = Query("-score", description="Sort key (e.g. ‘-score’, ‘distance’, ‘GC’)."),
):
    """List targets for a UserChallenge (paginated).

    Description:
        Displays targets associated with the UserChallenge with pagination and sorting.

    Args:
        uc_id (str): UserChallenge identifier.
        page (int): Page (≥1).
        page_size (int): Page size (1–200).
        sort (str): Sort key.

    Returns:
        TargetListResponse: Items and pagination.
    """
    uc_oid = _as_objid(uc_id)
    return await list_targets_for_user_challenge(
        user_id=user_id, uc_id=uc_oid, page=page, page_size=page_size, sort=sort
    )


# TODO: [BACKLOG] Route /my/challenges/{uc_id}/targets/nearby (GET) to verify
@router.get(
    "/challenges/{uc_id}/targets/nearby",
    response_model=TargetListResponse,
    summary="List targets near a point (per UC)",
    description=(
        "**Paginated** list of targets for a UserChallenge near a point (`lat`/`lon`) within a radius (km).\n"
        "- If `lat`/`lon` are absent, uses the user’s **last saved location**\n"
        "- Default sort: `distance`"
    ),
)
async def list_targets_uc_nearby(
    user_id: CurrentUserId,
    uc_id: str = Path(..., description="UserChallenge identifier."),
    radius_km: float = Query(50.0, gt=0, description="Search radius (km)."),
    lat: float | None = Query(
        None, ge=-90, le=90, description="Latitude; falls back to saved location."
    ),
    lon: float | None = Query(
        None, ge=-180, le=180, description="Longitude; falls back to saved location."
    ),
    page: int = Query(1, ge=1, description="Page number."),
    page_size: int = Query(50, ge=1, le=200, description="Page size (1–200)."),
    sort: str = Query("distance", description="Sort key (default: ‘distance’)."),
):
    """List targets near a point (per UC).

    Description:
        Returns targets for the UserChallenge located near a given point, with pagination and sorting.

    Args:
        uc_id (str): UserChallenge identifier.
        radius_km (float): Radius (km).
        lat (float | None): Latitude or saved location.
        lon (float | None): Longitude or saved location.
        page (int): Page (≥1).
        page_size (int): Page size (1–200).
        sort (str): Sort key.

    Returns:
        TargetListResponse: Items and pagination.
    """
    uc_oid = _as_objid(uc_id)

    final_lat: float
    final_lon: float

    if lat is None or lon is None:
        db = get_db()
        user_profile_service = UserProfileService(db)
        location_data = await user_profile_service.get_user_location(user_id)
        if not location_data:
            raise HTTPException(
                status_code=422,
                detail="No user location found; provide lat/lon or save your location first.",
            )
        final_lon, final_lat = location_data["coordinates"][0], location_data["coordinates"][1]
    else:
        final_lat = lat
        final_lon = lon

    return await list_targets_nearby_for_user_challenge(
        user_id=user_id,
        uc_id=uc_oid,
        lat=final_lat,
        lon=final_lon,
        radius_km=radius_km,
        page=int(page),
        page_size=int(page_size),
        sort=sort,
    )


# ---------------------------
# Global listing (all accepted challenges of the user)
# ---------------------------


# TODO: [BACKLOG] Route /my/targets (GET) to verify
@router.get(
    "/targets",
    response_model=TargetListResponse,
    summary="List all my targets (all challenges)",
    description=(
        "**Paginated** list of targets across all of the user’s challenges.\n"
        "- Optional `status_filter` (e.g. ‘accepted’)\n"
        "- Sort (e.g. `-score`, `distance`, `GC`)"
    ),
)
async def list_targets_all(
    user_id: CurrentUserId,
    status_filter: str | None = Query(None, description="Filter by UC status (e.g. ‘accepted’)."),
    page: int = Query(1, ge=1, description="Page number."),
    page_size: int = Query(50, ge=1, le=200, description="Page size (1–200)."),
    sort: str = Query("-score", description="Sort key (e.g. ‘-score’, ‘distance’, ‘GC’)."),
):
    """List all my targets (paginated).

    Description:
        Returns aggregated targets from all of the user’s challenges, with pagination and sorting.

    Args:
        status_filter (str | None): UC status filter.
        page (int): Page (≥1).
        page_size (int): Page size (1–200).
        sort (str): Sort key.

    Returns:
        TargetListResponse: Items and pagination.
    """
    return await list_targets_for_user(
        user_id=user_id,
        status_filter=(status_filter or None),
        page=int(page),
        page_size=int(page_size),
        sort=sort,
    )


# TODO: [BACKLOG] Route /my/targets/nearby (GET) to verify
@router.get(
    "/targets/nearby",
    response_model=TargetListResponse,
    summary="List targets near a point (all challenges)",
    description=(
        "**Paginated** list of targets near a point (`lat`/`lon`) for **all** challenges.\n"
        "- If `lat`/`lon` are absent, uses the saved location\n"
        "- UC status filter available (`status_filter`)"
    ),
)
async def list_targets_all_nearby(
    user_id: CurrentUserId,
    radius_km: float = Query(50.0, gt=0, description="Radius (km)."),
    lat: float | None = Query(
        None, ge=-90, le=90, description="Latitude; falls back to saved location."
    ),
    lon: float | None = Query(
        None, ge=-180, le=180, description="Longitude; falls back to saved location."
    ),
    status_filter: str | None = Query(None, description="Filter by UC status (e.g. ‘accepted’)."),
    page: int = Query(1, ge=1, description="Page number."),
    page_size: int = Query(50, ge=1, le=200, description="Page size (1–200)."),
    sort: str = Query("distance", description="Sort key (default: ‘distance’)."),
):
    """List nearby targets (all challenges).

    Description:
        Aggregates targets near a point across all of the user’s challenges.

    Args:
        radius_km (float): Radius (km).
        lat (float | None): Latitude or saved location.
        lon (float | None): Longitude or saved location.
        status_filter (str | None): UC status filter.
        page (int): Page (≥1).
        page_size (int): Page size (1–200).
        sort (str): Sort key.

    Returns:
        TargetListResponse: Items and pagination.
    """
    final_lat: float
    final_lon: float

    if lat is None or lon is None:
        db = get_db()
        user_profile_service = UserProfileService(db)
        location_data = await user_profile_service.get_user_location(user_id)
        if not location_data:
            raise HTTPException(
                status_code=422,
                detail="No user location found; provide lat/lon or save your location first.",
            )
        final_lon, final_lat = location_data["coordinates"][0], location_data["coordinates"][1]
    else:
        final_lat = lat
        final_lon = lon

    return await list_targets_nearby_for_user(
        user_id=user_id,
        lat=final_lat,
        lon=final_lon,
        radius_km=radius_km,
        status_filter=(status_filter or None),
        page=int(page),
        page_size=int(page_size),
        sort=sort,
    )


# ---------------------------
# Global evaluate / refresh status
# ---------------------------


@router.get(
    "/targets/refresh-status",
    summary="Check whether targets need a refresh",
    description=(
        "Returns `needs_refresh=true` if unfound caches have been imported since the last\n"
        "target evaluation, meaning the targets list may be stale."
    ),
)
async def targets_refresh_status(user_id: CurrentUserId):
    """Return the targets refresh status for the current user.

    Returns:
        dict: {needs_refresh, last_not_found_import_at, last_targets_evaluated_at}.
    """
    return await get_targets_refresh_status(user_id=user_id)


@router.post(
    "/targets/evaluate-all",
    status_code=status.HTTP_200_OK,
    summary="Evaluate targets for all accepted challenges",
    description=(
        "Runs target evaluation for **all** accepted UserChallenges of the current user\n"
        "and updates `last_targets_evaluated_at` on the user profile."
    ),
)
async def evaluate_all_targets(user_id: CurrentUserId):
    """Evaluate targets for all accepted UCs of the current user.

    Returns:
        dict: {ok, evaluated, total_inserted, total_updated, last_targets_evaluated_at}.
    """
    return await evaluate_all_for_user(user_id=user_id, force=False)


# ---------------------------
# Maintenance
# ---------------------------


# TODO: [BACKLOG] Route /my/challenges/{uc_id}/targets (DELETE) to verify
@router.delete(
    "/challenges/{uc_id}/targets",
    status_code=status.HTTP_200_OK,
    summary="Delete all targets for a UserChallenge",
    description="Removes all targets associated with the given UserChallenge.",
)
async def clear_targets_uc(
    user_id: CurrentUserId,
    uc_id: str = Path(..., description="UserChallenge identifier."),
):
    """Delete targets for a UserChallenge.

    Description:
        Removes all targets linked to the UserChallenge for the current user.

    Args:
        uc_id (str): UserChallenge identifier.

    Returns:
        dict: Result `{ok, deleted}`.
    """
    uc_oid = _as_objid(uc_id)
    result = await delete_targets_for_user_challenge(user_id=user_id, uc_id=uc_oid)
    # expected result: {"ok": True, "deleted": n}
    return result
