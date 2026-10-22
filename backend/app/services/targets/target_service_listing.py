# backend/app/services/targets/target_service_listing.py
# Target listing/pagination helpers for TargetService.

from __future__ import annotations

import logging
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

log = logging.getLogger(__name__)


async def list_targets_with_pagination(
    db: AsyncIOMotorDatabase,
    filters: dict[str, Any],
    page: int,
    page_size: int,
    sort: str,
) -> dict[str, Any]:
    """Generic pagination utility for targets."""
    coll_targets = db.targets

    # Count total
    total_count = await coll_targets.count_documents(filters)

    # Pagination
    skip = (page - 1) * page_size
    nb_pages = (total_count + page_size - 1) // page_size

    # Build sort spec
    sort_spec = []
    for sort_key in sort.split(","):
        sort_key = sort_key.strip()
        if sort_key.startswith("-"):
            sort_spec.append((sort_key[1:], -1))
        else:
            sort_spec.append((sort_key, 1))

    # Retrieve items
    cursor = coll_targets.find(filters).sort(sort_spec).skip(skip).limit(page_size)
    items = await cursor.to_list(length=None)

    return {
        "items": items,
        "nb_items": total_count,
        "page": page,
        "page_size": page_size,
        "nb_pages": nb_pages,
    }


async def list_targets_nearby(
    db: AsyncIOMotorDatabase,
    base_filters: dict[str, Any],
    lat: float,
    lon: float,
    radius_km: float,
    page: int,
    page_size: int,
    sort: str,
) -> dict[str, Any]:
    """List targets within a geographic radius using $geoNear.

    Uses the 2dsphere index on the ``loc`` field to filter and compute
    live distance from the provided coordinates.
    """
    coll_targets = db.targets

    geo_stage: dict[str, Any] = {
        "$geoNear": {
            "near": {"type": "Point", "coordinates": [lon, lat]},
            "distanceField": "distance_m",
            "maxDistance": radius_km * 1000,
            "spherical": True,
            "query": base_filters,
        }
    }

    # Build sort document for the aggregation pipeline
    if sort == "distance":
        sort_doc: dict[str, Any] = {"distance_m": 1}
    else:
        sort_doc = {}
        for key in sort.split(","):
            key = key.strip()
            if key.startswith("-"):
                sort_doc[key[1:]] = -1
            else:
                sort_doc[key] = 1

    skip = (page - 1) * page_size

    # Count matching documents
    count_result = await coll_targets.aggregate([geo_stage, {"$count": "total"}]).to_list(length=1)
    total_count: int = count_result[0]["total"] if count_result else 0
    nb_pages = (total_count + page_size - 1) // page_size if total_count else 0

    # Fetch page
    pipeline: list[dict[str, Any]] = [
        geo_stage,
        {"$sort": sort_doc},
        {"$skip": skip},
        {"$limit": page_size},
    ]
    items = await coll_targets.aggregate(pipeline).to_list(length=None)

    log.debug(
        "[targets] nearby lat=%s lon=%s r=%skm — %d result(s)", lat, lon, radius_km, total_count
    )

    return {
        "items": items,
        "nb_items": total_count,
        "page": page,
        "page_size": page_size,
        "nb_pages": nb_pages,
    }


async def _resolve_user_target_filters(
    db: AsyncIOMotorDatabase,
    user_id: ObjectId,
    status_filter: str | None,
    page: int,
    page_size: int,
    log_suffix: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Build base target filters for a user, resolving status_filter to UC ids.

    Args:
        db: Database handle.
        user_id: Target user.
        status_filter: Optional UserChallenge status filter.
        page: Requested page (echoed back in the early-empty-result shape).
        page_size: Requested page size (echoed back likewise).
        log_suffix: Appended to the debug log message to distinguish callers
            (e.g. "" for the plain listing, "nearby " for the geo one).

    Returns:
        tuple: `(base_filters, empty_result)`. When `status_filter` resolves
            to no matching UserChallenge, `empty_result` is a ready-to-return
            empty page and `base_filters` should be ignored by the caller.
    """
    base_filters: dict[str, Any] = {"user_id": user_id}

    if status_filter:
        coll_uc = db.user_challenges
        uc_docs = await coll_uc.find(
            {"user_id": user_id, "status": status_filter},
            {"_id": 1},
        ).to_list(length=None)
        uc_ids = [doc["_id"] for doc in uc_docs]

        log.debug(
            "[targets] %sstatus_filter=%s — %d UC(s) matched",
            log_suffix,
            status_filter,
            len(uc_ids),
        )

        if not uc_ids:
            return base_filters, {
                "items": [],
                "nb_items": 0,
                "page": page,
                "page_size": page_size,
                "nb_pages": 0,
            }

        base_filters["user_challenge_id"] = {"$in": uc_ids}

    return base_filters, None


async def list_targets_for_user_with_status_filter(
    db: AsyncIOMotorDatabase,
    user_id: ObjectId,
    status_filter: str | None,
    page: int,
    page_size: int,
    sort: str,
) -> dict[str, Any]:
    """List targets with an optional UC status filter.

    When ``status_filter`` is provided, resolves the matching
    UserChallenge ids first, then filters targets accordingly.
    """
    base_filters, empty_result = await _resolve_user_target_filters(
        db, user_id, status_filter, page, page_size, log_suffix=""
    )
    if empty_result is not None:
        return empty_result

    return await list_targets_with_pagination(
        db,
        filters=base_filters,
        page=page,
        page_size=page_size,
        sort=sort,
    )


async def list_targets_nearby_for_user_with_status_filter(
    db: AsyncIOMotorDatabase,
    user_id: ObjectId,
    lat: float,
    lon: float,
    radius_km: float,
    status_filter: str | None,
    page: int,
    page_size: int,
    sort: str,
) -> dict[str, Any]:
    """List nearby targets with an optional UC status filter.

    Resolves matching UC ids when a status filter is provided,
    then delegates to ``list_targets_nearby``.
    """
    base_filters, empty_result = await _resolve_user_target_filters(
        db, user_id, status_filter, page, page_size, log_suffix="nearby "
    )
    if empty_result is not None:
        return empty_result

    return await list_targets_nearby(
        db,
        base_filters=base_filters,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        page=page,
        page_size=page_size,
        sort=sort,
    )
