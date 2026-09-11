# backend/app/services/zones/zone_service.py
# MongoDB aggregation service for administrative zone statistics.
# Powers the /api/zones endpoints used by the choropleth map.
# All counts are scoped to a specific user's found caches.

from __future__ import annotations

import logging

from bson import ObjectId

from app.api.dto.zones import (
    ZoneDetail,
    ZoneListItem,
    ZoneTypeStatItem,
)
from app.db.mongodb import get_collection

log = logging.getLogger(__name__)


async def _resolve_type_ids(type_codes: list[str]) -> list[ObjectId]:
    """Resolves cache type codes to their ObjectIds, silently skipping unknown codes.

    Args:
        type_codes (list[str]): Type codes, e.g. ["traditional", "mystery"].

    Returns:
        list[ObjectId]: Matching ObjectIds (may be shorter than the input if some codes are unknown).
    """
    col = await get_collection("cache_types")
    docs = await col.find({"code": {"$in": type_codes}}, {"_id": 1}).to_list(length=None)
    return [doc["_id"] for doc in docs]


async def get_zones_with_counts(
    level: int,
    user_id: ObjectId,
    country: str | None = None,
    type_codes: list[str] | None = None,
) -> list[ZoneListItem]:
    """Returns administrative zones with the current user's found-cache counts.

    Description:
        Starts from `found_caches` (filtered by user), joins `caches` via $lookup,
        then groups by zone code at the requested level.
        At level 0, groups by ISO country code and joins the `countries` collection
        on its `code` field, displaying `name_fr` (falling back to `name` if unset).
        At levels 1/2, joins `administrative_zones` and requires `country` to scope
        the drill-down.
        Zones where the user has found zero caches are excluded.

    Args:
        level (int): Administrative level — 0 (country), 1 (region) or 2 (department).
        user_id (ObjectId): Authenticated user's ObjectId.
        country (str | None): ISO country code, e.g. "FR". Required for level 1/2, ignored at level 0.
        type_codes (list[str] | None): Optional cache type code filter.

    Returns:
        list[ZoneListItem]: Zones with counts, sorted by name.
    """
    type_ids: list[ObjectId] | None = None
    if type_codes:
        type_ids = await _resolve_type_ids(type_codes)
        if not type_ids:
            return []

    cache_match: dict = {}
    if level == 0:
        cache_match["cache.zones.country"] = {"$ne": None}
        group_field = "$cache.zones.country"
    else:
        level_field = f"zones.level{level}"
        cache_match["cache.zones.country"] = country
        cache_match[f"cache.{level_field}"] = {"$ne": None}
        group_field = f"$cache.{level_field}"

    if type_ids is not None:
        cache_match["cache.type_id"] = {"$in": type_ids}

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
        {"$group": {"_id": group_field, "cache_count": {"$sum": 1}}},
    ]

    raw = await found_col.aggregate(pipeline).to_list(length=None)  # type: ignore[arg-type]
    code_to_count = {doc["_id"]: doc["cache_count"] for doc in raw}

    if not code_to_count:
        return []

    if level == 0:
        ref_col = await get_collection("countries")
        ref_docs = await ref_col.find({"code": {"$in": list(code_to_count.keys())}}).to_list(
            length=None
        )
        items = [
            ZoneListItem(
                code=d["code"],
                name=d.get("name_fr") or d["name"],
                cache_count=code_to_count[d["code"]],
            )
            for d in ref_docs
        ]
    else:
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
    level: int | None = None,
) -> ZoneDetail | None:
    """Returns zone detail with the user's found-cache count and per-type breakdown.

    Description:
        Resolves the zone document (using the optional level hint to disambiguate),
        then aggregates `found_caches` joined with `caches` by cache type for that zone.
        All cache types are always returned in the breakdown (count=0 for types with no
        matches), in canonical GC.com order (sorted by sort_order). The total cache count
        is the sum of the per-type counts.

    Args:
        code (str): Zone code, e.g. "FR-84" or "FR-38".
        user_id (ObjectId): Authenticated user's ObjectId.
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

    return ZoneDetail(
        code=code,
        name=zone_doc["name"],
        cache_count=sum(item.count for item in type_counts),
        type_counts=type_counts,
    )
