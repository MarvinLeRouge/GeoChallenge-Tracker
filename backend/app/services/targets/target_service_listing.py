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
    base_filters: dict[str, Any] = {"user_id": user_id}

    if status_filter:
        coll_uc = db.user_challenges
        uc_docs = await coll_uc.find(
            {"user_id": user_id, "status": status_filter},
            {"_id": 1},
        ).to_list(length=None)
        uc_ids = [doc["_id"] for doc in uc_docs]

        log.debug("[targets] status_filter=%s — %d UC(s) matched", status_filter, len(uc_ids))

        if not uc_ids:
            return {
                "items": [],
                "nb_items": 0,
                "page": page,
                "page_size": page_size,
                "nb_pages": 0,
            }

        base_filters["user_challenge_id"] = {"$in": uc_ids}

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
    base_filters: dict[str, Any] = {"user_id": user_id}

    if status_filter:
        coll_uc = db.user_challenges
        uc_docs = await coll_uc.find(
            {"user_id": user_id, "status": status_filter},
            {"_id": 1},
        ).to_list(length=None)
        uc_ids = [doc["_id"] for doc in uc_docs]

        log.debug(
            "[targets] nearby status_filter=%s — %d UC(s) matched", status_filter, len(uc_ids)
        )

        if not uc_ids:
            return {
                "items": [],
                "nb_items": 0,
                "page": page,
                "page_size": page_size,
                "nb_pages": 0,
            }

        base_filters["user_challenge_id"] = {"$in": uc_ids}

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
