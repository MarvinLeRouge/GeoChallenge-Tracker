# backend/app/services/zones/zone_service.py
# MongoDB aggregation service for administrative zone statistics.
# Powers the /api/zones endpoints used by the choropleth map.
# All counts are scoped to a specific user's found caches.

from __future__ import annotations

import logging

from bson import ObjectId

from app.api.dto.zones import (
    CacheInZone,
    ZoneDetail,
    ZoneListItem,
    ZoneTypeStatItem,
    ZoneTypeStatsResponse,
)
from app.db.mongodb import get_collection

log = logging.getLogger(__name__)

POPOVER_CACHE_LIMIT = 10


async def _resolve_type_id(type_code: str) -> ObjectId | None:
    """Resolves a cache type code to its ObjectId.

    Args:
        type_code (str): Type code, e.g. "traditional".

    Returns:
        ObjectId | None: Matching ObjectId, or None if not found.
    """
    col = await get_collection("cache_types")
    doc = await col.find_one({"code": type_code}, {"_id": 1})
    return doc["_id"] if doc else None


async def get_zones_with_counts(
    country: str,
    level: int,
    user_id: ObjectId,
    type_code: str | None = None,
) -> list[ZoneListItem]:
    """Returns administrative zones with the current user's found-cache counts.

    Description:
        Starts from `found_caches` (filtered by user), joins `caches` via $lookup,
        then groups by zone code at the requested level.
        Joins with `administrative_zones` to get zone names.
        Zones where the user has found zero caches are excluded.

    Args:
        country (str): ISO country code, e.g. "FR".
        level (int): Administrative level — 1 (region) or 2 (department).
        user_id (ObjectId): Authenticated user's ObjectId.
        type_code (str | None): Optional single cache type code filter.

    Returns:
        list[ZoneListItem]: Zones with counts, sorted by name.
    """
    level_field = f"zones.level{level}"

    type_id: ObjectId | None = None
    if type_code:
        type_id = await _resolve_type_id(type_code)
        if type_id is None:
            return []

    cache_match: dict = {
        "cache.zones.country": country,
        f"cache.{level_field}": {"$ne": None},
    }
    if type_id is not None:
        cache_match["cache.type_id"] = type_id

    found_col = await get_collection("found_caches")
    pipeline = [
        {"$match": {"user_id": user_id}},
        {
            "$lookup": {
                "from": "caches",
                "localField": "cache_id",
                "foreignField": "_id",
                "as": "cache",
            }
        },
        {"$unwind": "$cache"},
        {"$match": cache_match},
        {"$group": {"_id": f"$cache.{level_field}", "cache_count": {"$sum": 1}}},
    ]

    raw = await found_col.aggregate(pipeline).to_list(length=None)  # type: ignore[arg-type]
    code_to_count = {doc["_id"]: doc["cache_count"] for doc in raw}

    if not code_to_count:
        return []

    zones_col = await get_collection("administrative_zones")
    zone_docs = await zones_col.find(
        {"code": {"$in": list(code_to_count.keys())}, "level": level}
    ).to_list(length=None)

    items = [
        ZoneListItem(
            code=z["code"],
            name=z["name"],
            cache_count=code_to_count[z["code"]],
        )
        for z in zone_docs
    ]
    items.sort(key=lambda x: x.name)
    return items


async def get_zone_detail(
    code: str,
    user_id: ObjectId,
    type_code: str | None = None,
    level: int | None = None,
) -> ZoneDetail | None:
    """Returns zone detail with the user's found-cache count and first 10 found caches.

    Description:
        Resolves the zone document (using the optional level hint to disambiguate),
        then queries `found_caches` joined with `caches` to count and list matches.

    Args:
        code (str): Zone code, e.g. "FR-84" or "FR-38".
        user_id (ObjectId): Authenticated user's ObjectId.
        type_code (str | None): Optional single cache type code filter.
        level (int | None): Level hint (1 or 2) to disambiguate codes shared between levels.

    Returns:
        ZoneDetail | None: Zone detail, or None if the zone code is unknown.
    """
    zones_col = await get_collection("administrative_zones")

    if level is not None:
        zone_doc = await zones_col.find_one({"code": code, "level": level})
    else:
        zone_doc = await zones_col.find_one({"code": code, "level": 2})
        if not zone_doc:
            zone_doc = await zones_col.find_one({"code": code, "level": 1})

    if not zone_doc:
        return None

    zone_level = zone_doc["level"]
    level_field = f"zones.level{zone_level}"

    type_id: ObjectId | None = None
    if type_code:
        type_id = await _resolve_type_id(type_code)
        if type_id is None:
            return ZoneDetail(code=code, name=zone_doc["name"], cache_count=0, caches=[])

    cache_match: dict = {f"cache.{level_field}": code}
    if type_id is not None:
        cache_match["cache.type_id"] = type_id

    found_col = await get_collection("found_caches")

    count_pipeline = [
        {"$match": {"user_id": user_id}},
        {
            "$lookup": {
                "from": "caches",
                "localField": "cache_id",
                "foreignField": "_id",
                "as": "cache",
            }
        },
        {"$unwind": "$cache"},
        {"$match": cache_match},
        {"$count": "total"},
    ]
    count_result = await found_col.aggregate(count_pipeline).to_list(length=1)  # type: ignore[arg-type]
    total = count_result[0]["total"] if count_result else 0

    detail_pipeline = [
        {"$match": {"user_id": user_id}},
        {
            "$lookup": {
                "from": "caches",
                "localField": "cache_id",
                "foreignField": "_id",
                "as": "cache",
            }
        },
        {"$unwind": "$cache"},
        {"$match": cache_match},
        {"$limit": POPOVER_CACHE_LIMIT},
        {
            "$lookup": {
                "from": "cache_types",
                "localField": "cache.type_id",
                "foreignField": "_id",
                "as": "type_doc",
            }
        },
        {
            "$project": {
                "GC": "$cache.GC",
                "title": "$cache.title",
                "difficulty": "$cache.difficulty",
                "terrain": "$cache.terrain",
                "type_code": {"$arrayElemAt": ["$type_doc.code", 0]},
            }
        },
    ]

    raw_caches = await found_col.aggregate(detail_pipeline).to_list(length=None)  # type: ignore[arg-type]
    caches = [
        CacheInZone(
            GC=c["GC"],
            title=c["title"],
            type_code=c.get("type_code"),
            difficulty=c.get("difficulty"),
            terrain=c.get("terrain"),
        )
        for c in raw_caches
    ]

    return ZoneDetail(
        code=code,
        name=zone_doc["name"],
        cache_count=total,
        caches=caches,
    )


async def get_zone_type_stats(
    code: str,
    user_id: ObjectId,
    level: int | None = None,
) -> ZoneTypeStatsResponse | None:
    """Returns per-type found-cache counts for a zone, including types with zero caches.

    Description:
        Resolves the zone document then aggregates found_caches by cache type for that zone.
        All cache types are always returned (count=0 for types with no matches), in canonical
        GC.com order (sorted by cache_type_id ascending).

    Args:
        code (str): Zone code, e.g. "FR-84".
        user_id (ObjectId): Authenticated user's ObjectId.
        level (int | None): Level hint (1 or 2) to disambiguate codes shared between levels.

    Returns:
        ZoneTypeStatsResponse | None: Zone type stats, or None if the zone code is unknown.
    """
    zones_col = await get_collection("administrative_zones")

    if level is not None:
        zone_doc = await zones_col.find_one({"code": code, "level": level})
    else:
        zone_doc = await zones_col.find_one({"code": code, "level": 2})
        if not zone_doc:
            zone_doc = await zones_col.find_one({"code": code, "level": 1})

    if not zone_doc:
        return None

    zone_level = zone_doc["level"]
    level_field = f"zones.level{zone_level}"

    found_col = await get_collection("found_caches")
    pipeline = [
        {"$match": {"user_id": user_id}},
        {
            "$lookup": {
                "from": "caches",
                "localField": "cache_id",
                "foreignField": "_id",
                "as": "cache",
            }
        },
        {"$unwind": "$cache"},
        {"$match": {f"cache.{level_field}": code}},
        {"$group": {"_id": "$cache.type_id", "count": {"$sum": 1}}},
    ]
    raw = await found_col.aggregate(pipeline).to_list(length=None)  # type: ignore[arg-type]
    type_id_to_count: dict[ObjectId, int] = {
        doc["_id"]: doc["count"] for doc in raw if doc["_id"] is not None
    }

    types_col = await get_collection("cache_types")
    all_types = await types_col.find({}, {"_id": 1, "code": 1, "name": 1, "sort_order": 1}).to_list(
        length=None
    )
    all_types.sort(key=lambda t: t.get("sort_order") or 999)

    type_counts = [
        ZoneTypeStatItem(
            type_code=t["code"],
            type_name=t["name"],
            count=type_id_to_count.get(t["_id"], 0),
        )
        for t in all_types
    ]

    return ZoneTypeStatsResponse(
        code=code,
        name=zone_doc["name"],
        type_counts=type_counts,
    )
