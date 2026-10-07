# backend/app/api/routes/caches_geo_search.py
# Geo-search routes: bounding-box and radius search.

from __future__ import annotations

import math
from typing import Any, Literal

from fastapi import HTTPException, Query
from pymongo import ASCENDING, DESCENDING

from app.db.mongodb import get_collection

from .caches import router
from .caches_search import _compact_lookups_and_project, _doc, _oid


# DONE: [BACKLOG] Route /caches/within-bbox (GET) verified
@router.get(
    "/within-bbox",
    summary="Caches within a bounding box",
    description=(
        "Paginated list of caches within a BBox.\n"
        "- Optional filter by `type_id` and `size_id`\n"
        "- Sort: `-placed_at`, `-favorites`, `difficulty`, `terrain`\n"
        "- Pagination via `page` and `page_size` (max 200)"
    ),
)
async def within_bbox(
    min_lat: float = Query(..., description="Minimum BBox latitude."),
    min_lon: float = Query(..., description="Minimum BBox longitude."),
    max_lat: float = Query(..., description="Maximum BBox latitude."),
    max_lon: float = Query(..., description="Maximum BBox longitude."),
    type_id: str | None = Query(None, description="Optional filter: type identifier (ObjectId)."),
    size_id: str | None = Query(None, description="Optional filter: size identifier (ObjectId)."),
    page: int = Query(1, ge=1, description="Page number (≥1)."),
    page_size: int = Query(100, ge=1, le=200, description="Page size (1–200)."),
    sort: Literal["-placed_at", "-favorites", "difficulty", "terrain"] = Query(
        "-placed_at",
        description="Sort key: ‘-placed_at’ (default), ‘-favorites’, ‘difficulty’, ‘terrain’.",
    ),
    compact: bool = Query(
        True,
        description="Returns an abbreviated version (_id, GC, title, type_id, type, size_id, size, difficulty, terrain).",
    ),
):
    """Lists caches within a BBox.

    Description:
        Applies a rectangular spatial filter (BBox) with sorting and pagination options.
        Can be restricted by cache type and/or size.

    Args:
        min_lat (float): Minimum latitude.
        min_lon (float): Minimum longitude.
        max_lat (float): Maximum latitude.
        max_lon (float): Maximum longitude.
        type_id (str | None): Cache type identifier (ObjectId).
        size_id (str | None): Cache size identifier (ObjectId).
        page (int): Page number.
        page_size (int): Page size.
        sort (Literal): Sort key.

    Returns:
        dict: Paginated results `{items, total, page, page_size}`.
    """
    coll = await get_collection("caches")
    q: dict[str, Any] = {
        "loc": {
            "$geoWithin": {
                "$geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [min_lon, min_lat],
                            [max_lon, min_lat],
                            [max_lon, max_lat],
                            [min_lon, max_lat],
                            [min_lon, min_lat],
                        ]
                    ],
                }
            }
        }
    }
    if type_id:
        q["type_id"] = _oid(type_id)
    if size_id:
        q["size_id"] = _oid(size_id)

    sort_map = {
        "-placed_at": [("placed_at", DESCENDING)],
        "-favorites": [("favorites", DESCENDING)],
        "difficulty": [("difficulty", ASCENDING)],
        "terrain": [("terrain", ASCENDING)],
    }
    order = sort_map[sort]

    page_size = min(max(1, page_size), 200)
    page = max(1, page)
    skip = (page - 1) * page_size

    if compact:
        pipeline = [
            {"$match": q},
            {"$sort": dict(order)},
            {"$skip": skip},
            {"$limit": page_size},
            *_compact_lookups_and_project(),
        ]
        docs = [_doc(d) async for d in coll.aggregate(pipeline)]
    else:
        docs = [_doc(d) async for d in (coll.find(q).sort(order).skip(skip).limit(page_size))]

    total = await coll.count_documents(q)
    nb_pages = math.ceil(total / page_size)

    return {
        "items": docs,
        "total": total,
        "page": page,
        "nb_pages": nb_pages,
        "page_size": page_size,
    }


# DONE: [BACKLOG] Route /caches/within-radius (GET) verified
@router.get(
    "/within-radius",
    summary="Caches around a point (radius)",
    description=(
        "Distance search (geoNear) around a point (lat, lon).\n"
        "- Requires a 2dsphere index on `caches.loc`\n"
        "- Optional filter by `type_id` and `size_id`\n"
        "- Pagination via `page`/`page_size` (max 200)"
    ),
)
async def within_radius(
    lat: float = Query(..., description="Center latitude."),
    lon: float = Query(..., description="Center longitude."),
    radius_km: float = Query(
        10.0,
        ge=0.1,
        le=100.0,
        description="Search radius in kilometers (0.1–100).",
    ),
    type_id: str | None = Query(None, description="Optional filter: type identifier (ObjectId)."),
    size_id: str | None = Query(None, description="Optional filter: size identifier (ObjectId)."),
    page: int = Query(1, ge=1, description="Page number (≥1)."),
    page_size: int = Query(100, ge=1, le=200, description="Page size (1–200)."),
    compact: bool = Query(
        True,
        description="Returns an abbreviated version (_id, GC, title, type_id, type, size_id, size, difficulty, terrain).",
    ),
):
    """Search by radius around a point.

    Description:
        Performs a `$geoNear` aggregation centered on (lat, lon) with a maximum distance,
        then applies ascending distance sorting, pagination, and an estimated count.

    Args:
        lat (float): Center latitude.
        lon (float): Center longitude.
        radius_km (float): Search radius in kilometers.
        type_id (str | None): Cache type identifier (ObjectId).
        size_id (str | None): Cache size identifier (ObjectId).
        page (int): Page number.
        page_size (int): Page size.

    Returns:
        dict: Paginated results `{items, total, page, nb_pages, page_size}`.

    Raises:
        HTTPException: 400 if the required `2dsphere` index on `caches.loc` is missing.
    """
    coll = await get_collection("caches")
    geo = {"type": "Point", "coordinates": [lon, lat]}
    q: dict[str, Any] = {}
    if type_id:
        q["type_id"] = _oid(type_id)
    if size_id:
        q["size_id"] = _oid(size_id)

    page_size = min(max(1, page_size), 200)
    page = max(1, page)
    skip = (page - 1) * page_size

    pipeline: list[dict[str, Any]] = [
        {
            "$geoNear": {
                "near": geo,
                "distanceField": "dist_meters",
                "spherical": True,
                "maxDistance": radius_km * 1000.0,
                "query": q,
            }
        },
        {"$sort": {"dist_meters": 1}},
        {"$skip": skip},
        {"$limit": page_size},
    ]
    if compact:
        pipeline += _compact_lookups_and_project()

    try:
        cur = coll.aggregate(pipeline)
        docs = [_doc(d) async for d in cur]
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"2dsphere index required on caches.loc: {e}"
        ) from e
    # count with same query (rough, not exact geo count but OK for paging UI)
    radius_radians = radius_km / 6378.1  # Earth radius in km
    total = await coll.count_documents(
        {"loc": {"$geoWithin": {"$centerSphere": [[lon, lat], radius_radians]}}, **q}
    )
    nb_pages = math.ceil(total / page_size)
    return {
        "items": docs,
        "total": total,
        "page": page,
        "nb_pages": nb_pages,
        "page_size": page_size,
    }
