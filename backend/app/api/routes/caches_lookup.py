# backend/app/api/routes/caches_lookup.py
# Retrieval routes by GC code or MongoDB ObjectId.

from __future__ import annotations

from fastapi import HTTPException, Path

from app.db.mongodb import get_collection

from .caches import router
from .caches_search import _doc, _oid


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
