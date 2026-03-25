# backend/app/api/routes/caches.py
# Routes related to geocaches:
# - GPX upload and import
# - Search by filters, bbox, or radius
# - Retrieval by identifier or GC code

from __future__ import annotations

import asyncio
import logging
import math
from typing import Annotated, Any, Literal

from bson import ObjectId
from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    Request,
    UploadFile,
)
from fastapi.encoders import jsonable_encoder
from pymongo import ASCENDING, DESCENDING

from app.api.deps import CurrentUserId
from app.api.dto.cache_query import CacheFilterIn
from app.core.security import get_current_user
from app.core.settings import get_settings
from app.db.mongodb import get_collection
from app.services.challenge_autocreate import create_new_challenges_from_caches
from app.services.gpx_importer_service import import_gpx_payload
from app.services.progress import evaluate_progress
from app.services.user_challenges_service import sync_user_challenges

log = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/caches", tags=["Caches"], dependencies=[Depends(get_current_user)])

# ------------------------- helpers -------------------------


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


# ------------------------- routes -------------------------


# DONE: [BACKLOG] Route /caches/upload-gpx (POST) verified
@router.post(
    "/upload-gpx",
    summary="Import caches from a GPX/ZIP file",
    description=(
        "Loads a GPX file (or a ZIP containing a GPX) and imports the associated geocaches.\n\n"
        "- Optionally marks caches as found (creates `found_caches` records)\n"
        "- Then attempts to auto-create challenges from the imported caches\n"
        f"- **Size limit**: {settings.max_upload_mb} MB\n"
        "- Supports multiple GPX formats (cgeo, pocket_query)\n"
        "- Returns an import summary and challenge-related statistics"
    ),
    responses={
        200: {"description": "GPX import successful"},
        400: {"description": "Invalid GPX/ZIP file"},
        401: {"description": "Unauthenticated"},
        413: {"description": "Payload too large"},
    },
)
async def upload_gpx(
    request: Request,
    user_id: CurrentUserId,
    file: Annotated[
        UploadFile, File(..., description="GPX file to import (or ZIP containing a GPX).")
    ],
    import_mode: Literal["all", "found"] = Query(
        "all",
        description="Import mode: ‘all’ (all caches) or ‘found’ (my finds)",
    ),
    source_type: Literal["auto", "cgeo", "pocket_query"] = Query(
        "auto",
        description="GPX source type: ‘auto’ (auto-detect), ‘cgeo’, ‘pocket_query’",
    ),
):
    """Imports a GPX/ZIP file and triggers challenge creation.

    Description:
        Reads a GPX file (or a ZIP containing a GPX), imports the caches into the database,
        then triggers processing to auto-create challenges from the newly imported caches.

    Args:
        file (UploadFile): GPX or ZIP file to process.
        import_mode (str): Import mode - ‘all’ to import all caches, ‘found’ to mark as found.
        source_type (str): GPX file format - ‘auto’ for auto-detection, ‘cgeo’, or ‘pocket_query’.

    Returns:
        dict: Object containing the import summary (`summary`) and challenge-related statistics (`challenges_stats`).
    """

    result = {}
    # streaming read with size limit
    read_bytes = 0
    chunks: list[bytes] = []
    while True:
        chunk = await file.read(settings.one_mb)
        if not chunk:
            break
        read_bytes += len(chunk)
        if read_bytes > settings.max_upload_bytes:
            # Important: close the file and return 413
            await file.close()
            raise HTTPException(
                status_code=413,
                detail=f"Fichier trop volumineux (>{settings.max_upload_mb} Mo).",
            )
        chunks.append(chunk)

    await file.close()
    payload = b"".join(chunks)

    try:
        result["summary"] = await import_gpx_payload(
            payload=payload,
            filename=file.filename or "upload.gpx",
            import_mode=import_mode,
            user_id=ObjectId(str(user_id)),
            request=request,
            source_type=source_type,
            force_update_attributes=False,  # Always False in the standard version
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid GPX/ZIP: {e}") from e

    try:
        # Simple variant (optimized global scan: only processes new challenge caches)
        challenges_stats = await create_new_challenges_from_caches()
        # Optimized variant if you have the list of imported cache _ids:
        # challenge_stats = create_new_challenges_from_caches(cache_ids=upserted_cache_ids)
    except Exception as e:
        challenges_stats = {"error": str(e)}
    result["challenges_stats"] = challenges_stats

    try:
        result["sync_stats"] = await sync_user_challenges(ObjectId(str(user_id)))
    except Exception as e:
        result["sync_stats"] = {"error": str(e)}

    if import_mode == "found":
        try:
            coll_uc = await get_collection("user_challenges")
            uid = ObjectId(str(user_id))
            accepted_docs = await coll_uc.find(
                {"user_id": uid, "status": "accepted"},
                {"_id": 1},
            ).to_list(length=None)

            log.info(
                "[progress] GPX found import — evaluating %d accepted UC(s)", len(accepted_docs)
            )

            eval_results = await asyncio.gather(
                *(evaluate_progress(uid, doc["_id"]) for doc in accepted_docs),
                return_exceptions=True,
            )

            evaluated = 0
            for doc, res in zip(accepted_docs, eval_results):
                uc_id_str = str(doc["_id"])
                if isinstance(res, BaseException):
                    log.warning("[progress] UC %s — evaluation failed: %s", uc_id_str, res)
                else:
                    pct = res.get("percent", "?")
                    done = res.get("tasks_done", "?")
                    total = res.get("tasks_total", "?")
                    log.info(
                        "[progress] UC %s — %s%% (%s/%s tasks done)", uc_id_str, pct, done, total
                    )
                    evaluated += 1

            result["progress_stats"] = {
                "evaluated": evaluated,
                "total": len(accepted_docs),
            }
        except Exception as e:
            log.exception("[progress] Unexpected error during post-import evaluation")
            result["progress_stats"] = {"error": str(e)}

    return result


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
    q: dict[str, Any] = {}

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
    if payload.difficulty:
        rng = {}
        if payload.difficulty.min is not None:
            rng["$gte"] = payload.difficulty.min
        if payload.difficulty.max is not None:
            rng["$lte"] = payload.difficulty.max
        if rng:
            q["difficulty"] = rng
    if payload.terrain:
        rng = {}
        if payload.terrain.min is not None:
            rng["$gte"] = payload.terrain.min
        if payload.terrain.max is not None:
            rng["$lte"] = payload.terrain.max
        if rng:
            q["terrain"] = rng
    if payload.placed_after or payload.placed_before:
        rng_dt = {}
        if payload.placed_after:
            rng_dt["$gte"] = payload.placed_after
        if payload.placed_before:
            rng_dt["$lte"] = payload.placed_before
        q["placed_at"] = rng_dt
    if payload.attr_pos:
        q.setdefault("$and", []).append(
            {
                "attributes": {
                    "$elemMatch": {
                        "attribute_doc_id": {"$in": payload.attr_pos},
                        "is_positive": True,
                    }
                }
            }
        )
    if payload.attr_neg:
        q.setdefault("$and", []).append(
            {
                "attributes": {
                    "$elemMatch": {
                        "attribute_doc_id": {"$in": payload.attr_neg},
                        "is_positive": False,
                    }
                }
            }
        )
    if payload.bbox:
        bb = payload.bbox
        q["lat"] = {"$gte": bb.min_lat, "$lte": bb.max_lat}
        q["lon"] = {"$gte": bb.min_lon, "$lte": bb.max_lon}

    # sort
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

    if compact:
        pipeline = [
            {"$match": q},
            {"$sort": dict(sort)},
            {"$skip": skip},
            {"$limit": page_size},
            *_compact_lookups_and_project(),
        ]
        docs = [_doc(d) async for d in coll.aggregate(pipeline)]
    else:
        docs = [_doc(d) async for d in coll.find(q).sort(sort).skip(skip).limit(page_size)]

    total = await coll.count_documents(q)
    nb_pages = math.ceil(total / page_size)

    return {
        "items": docs,
        "total": total,
        "page": page,
        "nb_pages": nb_pages,
        "page_size": page_size,
    }


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
        "lat": {"$gte": min_lat, "$lte": max_lat},
        "lon": {"$gte": min_lon, "$lte": max_lon},
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


# DONE: [BACKLOG] Route /caches/{gc} (GET) verified
@router.get(
    "/{gc}",
    summary="Get a cache by GC code",
    description="Returns a single cache by its GC code.",
)
async def get_by_gc(
    gc: str = Path(..., description="Unique GC code of the cache."),
):
    """Read a cache (GC code).

    Description:
        Retrieves the cache identified by its GC code. Returns 404 if not found.

    Args:
        gc (str): GC code of the cache.

    Returns:
        dict: Serialized cache document.
    """

    coll = await get_collection("caches")
    cur = await coll.aggregate(
        [
            {"$match": {"GC": gc}},
            {
                "$lookup": {
                    "from": "cache_types",
                    "localField": "type_id",
                    "foreignField": "_id",
                    "as": "_type",
                }
            },
            {
                "$lookup": {
                    "from": "cache_sizes",
                    "localField": "size_id",
                    "foreignField": "_id",
                    "as": "_size",
                }
            },
            {
                "$addFields": {
                    "type": {
                        "label": {"$ifNull": [{"$arrayElemAt": ["$_type.name", 0]}, None]},
                        "code": {"$ifNull": [{"$arrayElemAt": ["$_type.code", 0]}, None]},
                    },
                    "size": {
                        "label": {"$ifNull": [{"$arrayElemAt": ["$_size.name", 0]}, None]},
                        "code": {"$ifNull": [{"$arrayElemAt": ["$_size.code", 0]}, None]},
                    },
                }
            },
            {"$limit": 1},
        ]
    ).to_list(length=None)
    doc = next(iter(cur), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Cache not found")
    return _doc(doc)


# DONE: [BACKLOG] Route /caches/by-id/{id} (GET) verified
@router.get(
    "/by-id/{id}",
    summary="Get a cache by MongoDB identifier",
    description="Returns a single cache by its ObjectId (string format).",
)
async def get_by_id(
    id: str = Path(..., description="MongoDB identifier (ObjectId) of the cache, as a string."),
):
    """Read a cache (ObjectId).

    Description:
        Retrieves the cache by its MongoDB identifier. Returns 404 if not found
        and 400 if the ObjectId is invalid.

    Args:
        id (str): MongoDB identifier (ObjectId as a string).

    Returns:
        dict: Serialized cache document.
    """
    coll = await get_collection("caches")
    oid = _oid(id)
    cur = await coll.aggregate(
        [
            {"$match": {"_id": oid}},
            {
                "$lookup": {
                    "from": "cache_types",
                    "localField": "type_id",
                    "foreignField": "_id",
                    "as": "_type",
                }
            },
            {
                "$lookup": {
                    "from": "cache_sizes",
                    "localField": "size_id",
                    "foreignField": "_id",
                    "as": "_size",
                }
            },
            {
                "$addFields": {
                    "type": {
                        "label": {"$ifNull": [{"$arrayElemAt": ["$_type.name", 0]}, None]},
                        "code": {"$ifNull": [{"$arrayElemAt": ["$_type.code", 0]}, None]},
                    },
                    "size": {
                        "label": {"$ifNull": [{"$arrayElemAt": ["$_size.name", 0]}, None]},
                        "code": {"$ifNull": [{"$arrayElemAt": ["$_size.code", 0]}, None]},
                    },
                }
            },
            {"$limit": 1},
        ]
    ).to_list(length=None)
    doc = next(iter(cur), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Cache not found")
    return _doc(doc)
