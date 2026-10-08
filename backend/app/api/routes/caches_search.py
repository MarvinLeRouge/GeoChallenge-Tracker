# backend/app/api/routes/caches_search.py
# Routes related to geocache search by filter criteria.

from __future__ import annotations

import math
from typing import Annotated, Any

from bson import ObjectId
from fastapi import Body, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pymongo import ASCENDING, DESCENDING

from app.api.dto.cache_query import CacheFilterIn
from app.db.mongodb import get_collection

from .caches import router


def _doc(d: dict[str, Any]) -> dict[str, Any]:
    """Encodes a MongoDB document (ObjectId -> str)."""
    return jsonable_encoder(d, custom_encoder={ObjectId: str})


def _oid(v: str | ObjectId | None) -> ObjectId | None:
    """Converts a value to a MongoDB ObjectId, or raises HTTP 400 if invalid."""
    if v is None:
        return None
    if isinstance(v, ObjectId):
        return v
    try:
        return ObjectId(v)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid ObjectId: {v}") from e


# ------------------------- compact helpers -------------------------

# Collections and label fields (adjust "name" if your schema differs)
TYPE_COLLECTION = "cache_types"
SIZE_COLLECTION = "cache_sizes"


TYPE_LABEL_FIELD = "name"
TYPE_CODE_FIELD = "code"
SIZE_LABEL_FIELD = "name"
SIZE_CODE_FIELD = "code"

# Fields to return in "compact" mode
COMPACT_FIELDS = {
    "_id": 1,
    "GC": 1,
    "title": 1,
    "type_id": 1,
    "size_id": 1,
    "difficulty": 1,
    "terrain": 1,
    "lat": 1,
    "lon": 1,
}


def _compact_lookups_and_project():
    """$lookup/$project stages to enrich type/size (label+code) and project compact fields."""
    return [
        {
            "$lookup": {
                "from": TYPE_COLLECTION,
                "localField": "type_id",
                "foreignField": "_id",
                "as": "_type",
            }
        },
        {
            "$lookup": {
                "from": SIZE_COLLECTION,
                "localField": "size_id",
                "foreignField": "_id",
                "as": "_size",
            }
        },
        # take the first elements and build {label, code} objects
        {
            "$addFields": {
                "type": {
                    "label": {
                        "$ifNull": [
                            {"$arrayElemAt": [f"$_type.{TYPE_LABEL_FIELD}", 0]},
                            None,
                        ]
                    },
                    "code": {
                        "$ifNull": [
                            {"$arrayElemAt": [f"$_type.{TYPE_CODE_FIELD}", 0]},
                            None,
                        ]
                    },
                },
                "size": {
                    "label": {
                        "$ifNull": [
                            {"$arrayElemAt": [f"$_size.{SIZE_LABEL_FIELD}", 0]},
                            None,
                        ]
                    },
                    "code": {
                        "$ifNull": [
                            {"$arrayElemAt": [f"$_size.{SIZE_CODE_FIELD}", 0]},
                            None,
                        ]
                    },
                },
            }
        },
        # remove temporary arrays
        {"$project": {**COMPACT_FIELDS, "type": 1, "size": 1}},
    ]


def _apply_simple_equality_filters(q: dict[str, Any], payload: CacheFilterIn) -> None:
    """Apply the text search and simple id-equality filters onto q, mutating it in place.

    Args:
        q: Mongo query being built, mutated.
        payload (CacheFilterIn): Filtering criteria.
    """
    if payload.q:
        q["$text"] = {"$search": payload.q}
    if payload.type_id:
        q["type_id"] = payload.type_id
    if payload.size_id:
        q["size_id"] = payload.size_id
    if payload.country_id:
        q["country_id"] = payload.country_id
    if payload.state_id:
        q["state_id"] = payload.state_id


def _build_min_max_range(min_value: Any, max_value: Any) -> dict[str, Any]:
    """Build a Mongo $gte/$lte range filter from optional min/max bounds.

    Args:
        min_value: Lower bound (inclusive), or None.
        max_value: Upper bound (inclusive), or None.

    Returns:
        dict: Range filter, empty if both bounds are None.
    """
    rng: dict[str, Any] = {}
    if min_value is not None:
        rng["$gte"] = min_value
    if max_value is not None:
        rng["$lte"] = max_value
    return rng


def _apply_difficulty_terrain_filters(q: dict[str, Any], payload: CacheFilterIn) -> None:
    """Apply the difficulty and terrain range filters onto q, mutating it in place.

    Args:
        q: Mongo query being built, mutated.
        payload (CacheFilterIn): Filtering criteria.
    """
    if payload.difficulty:
        rng = _build_min_max_range(payload.difficulty.min, payload.difficulty.max)
        if rng:
            q["difficulty"] = rng
    if payload.terrain:
        rng = _build_min_max_range(payload.terrain.min, payload.terrain.max)
        if rng:
            q["terrain"] = rng


def _apply_placed_date_filter(q: dict[str, Any], payload: CacheFilterIn) -> None:
    """Apply the placed_at date range filter onto q, mutating it in place.

    Args:
        q: Mongo query being built, mutated.
        payload (CacheFilterIn): Filtering criteria.
    """
    if payload.placed_after or payload.placed_before:
        rng_dt: dict[str, Any] = {}
        if payload.placed_after:
            rng_dt["$gte"] = payload.placed_after
        if payload.placed_before:
            rng_dt["$lte"] = payload.placed_before
        q["placed_at"] = rng_dt


def _build_attribute_elem_match(attribute_ids: list[Any], is_positive: bool) -> dict[str, Any]:
    """Build an $elemMatch clause for a positive or negative attribute filter.

    Args:
        attribute_ids: Attribute document ids to match.
        is_positive: Whether to match the positive or negative occurrence.

    Returns:
        dict: `$elemMatch` clause on the `attributes` field.
    """
    return {
        "attributes": {
            "$elemMatch": {
                "attribute_doc_id": {"$in": attribute_ids},
                "is_positive": is_positive,
            }
        }
    }


def _apply_attribute_filters(q: dict[str, Any], payload: CacheFilterIn) -> None:
    """Apply the positive and negative attribute filters onto q, mutating it in place.

    Args:
        q: Mongo query being built, mutated.
        payload (CacheFilterIn): Filtering criteria.
    """
    if payload.attr_pos:
        q.setdefault("$and", []).append(_build_attribute_elem_match(payload.attr_pos, True))
    if payload.attr_neg:
        q.setdefault("$and", []).append(_build_attribute_elem_match(payload.attr_neg, False))


def _build_bbox_geo_filter(bb: Any) -> dict[str, Any]:
    """Build a $geoWithin polygon filter from a bounding box.

    Args:
        bb: Bounding box with min_lon/min_lat/max_lon/max_lat.

    Returns:
        dict: `$geoWithin` polygon filter.
    """
    return {
        "$geoWithin": {
            "$geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [bb.min_lon, bb.min_lat],
                        [bb.max_lon, bb.min_lat],
                        [bb.max_lon, bb.max_lat],
                        [bb.min_lon, bb.max_lat],
                        [bb.min_lon, bb.min_lat],
                    ]
                ],
            }
        }
    }


def _build_cache_filter_query(payload: CacheFilterIn) -> dict[str, Any]:
    """Build the Mongo filter query from the cache-filter payload.

    Args:
        payload (CacheFilterIn): Filtering criteria.

    Returns:
        dict: Mongo query matching `caches`.
    """
    q: dict[str, Any] = {}

    _apply_simple_equality_filters(q, payload)
    _apply_difficulty_terrain_filters(q, payload)
    _apply_placed_date_filter(q, payload)
    _apply_attribute_filters(q, payload)
    if payload.bbox:
        q["loc"] = _build_bbox_geo_filter(payload.bbox)

    return q


def _resolve_sort_and_pagination(
    payload: CacheFilterIn,
) -> tuple[list[tuple[str, int]], int, int, int]:
    """Resolve the sort order and pagination bounds from the payload.

    Args:
        payload (CacheFilterIn): Filtering, sorting, and pagination parameters.

    Returns:
        tuple: `(sort, page, page_size, skip)`.
    """
    sort_map = {
        "-placed_at": [("placed_at", DESCENDING)],
        "-favorites": [("favorites", DESCENDING)],
        "difficulty": [("difficulty", ASCENDING)],
        "terrain": [("terrain", ASCENDING)],
    }
    sort = sort_map.get(payload.sort or "-placed_at", [("placed_at", DESCENDING)])

    page_size = min(max(1, payload.page_size), 200)
    page = max(1, payload.page)
    skip = (page - 1) * page_size
    return sort, page, page_size, skip


async def _fetch_filtered_caches(
    coll: Any,
    q: dict[str, Any],
    sort: list[tuple[str, int]],
    skip: int,
    page_size: int,
    compact: bool,
) -> list[dict[str, Any]]:
    """Fetch the matching, paginated cache documents.

    Args:
        coll (Any): `caches` collection.
        q (dict): Mongo filter query.
        sort (list): Sort order.
        skip (int): Number of documents to skip.
        page_size (int): Page size (max documents to return).
        compact (bool): Whether to use the abbreviated aggregation projection.

    Returns:
        list[dict]: Matching documents (already passed through `_doc`).
    """
    if compact:
        pipeline = [
            {"$match": q},
            {"$sort": dict(sort)},
            {"$skip": skip},
            {"$limit": page_size},
            *_compact_lookups_and_project(),
        ]
        return [_doc(d) async for d in coll.aggregate(pipeline)]
    return [_doc(d) async for d in coll.find(q).sort(sort).skip(skip).limit(page_size)]


# DONE: [BACKLOG] Route /caches/by-filter (POST) verified
@router.post(
    "/by-filter",
    summary="Search caches by filters",
    description=(
        "Returns a paginated list of geocaches based on combinable filters:\n"
        "- Text (`$text`), type, size, country/state\n"
        "- Difficulty/terrain (min/max ranges)\n"
        "- Placement period (after/before)\n"
        "- Positive/negative attributes\n"
        "- Optional BBox and sort (-placed_at, -favorites, difficulty, terrain)"
    ),
)
async def by_filter(
    payload: Annotated[
        CacheFilterIn,
        Body(
            ...,
            description=(
                "Filtering and pagination object:\n"
                "- `q`: full-text search\n"
                "- `type_id`, `size_id`, `country_id`, `state_id`\n"
                "- `difficulty`, `terrain`: `Range {min,max}` objects\n"
                "- `placed_after`, `placed_before`: time bounds\n"
                "- `attr_pos`, `attr_neg`: attribute lists (ObjectId)\n"
                "- `bbox`: `{min_lat,min_lon,max_lat,max_lon}`\n"
                "- `sort`, `page`, `page_size`"
            ),
        ),
    ],
    compact: bool = Query(
        True,
        description="Returns an abbreviated version (_id, GC, title, type_id, type, size_id, size, difficulty, terrain).",
    ),
):
    """Multi-criteria geocache search.

    Description:
        Filters caches using multiple combinable criteria, applies sorting, and returns paginated results.

    Args:
        payload (CacheFilterIn): Filtering, sorting, and pagination parameters.

    Returns:
        dict: Paginated results `{items, total, page, page_size}`.
    """
    coll = await get_collection("caches")
    q = _build_cache_filter_query(payload)
    sort, page, page_size, skip = _resolve_sort_and_pagination(payload)

    docs = await _fetch_filtered_caches(coll, q, sort, skip, page_size, compact)

    total = await coll.count_documents(q)
    nb_pages = math.ceil(total / page_size)

    return {
        "items": docs,
        "total": total,
        "page": page,
        "nb_pages": nb_pages,
        "page_size": page_size,
    }
