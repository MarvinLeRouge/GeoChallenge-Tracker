# backend/app/api/routes/caches.py

from __future__ import annotations

import datetime as dt
from typing import Optional, List, Literal, Dict, Any

from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends, Query, Body
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from bson import ObjectId
from pymongo import DESCENDING, ASCENDING
from pymongo.collation import Collation

from app.core.security import get_current_user
from app.db.mongodb import get_collection
from app.core.bson_utils import PyObjectId
from app.services.gpx_importer import import_gpx_payload
from app.services.challenge_autocreate import create_new_challenges_from_caches

router = APIRouter(prefix="/caches", tags=["caches"])


# ------------------------- helpers -------------------------

def _doc(d: Dict[str, Any]) -> Dict[str, Any]:
    return jsonable_encoder(d, custom_encoder={ObjectId: str})

def _oid(v: str | ObjectId | None) -> ObjectId | None:
    if v is None:
        return None
    if isinstance(v, ObjectId):
        return v
    try:
        return ObjectId(v)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid ObjectId: {v}")


# ------------------------- schemas -------------------------

class Range(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None

class BBox(BaseModel):
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

class CacheFilterIn(BaseModel):
    q: Optional[str] = None
    type_id: Optional[PyObjectId] = None
    size_id: Optional[PyObjectId] = None
    country_id: Optional[PyObjectId] = None
    state_id: Optional[PyObjectId] = None
    difficulty: Optional[Range] = None
    terrain: Optional[Range] = None
    placed_after: Optional[dt.datetime] = None
    placed_before: Optional[dt.datetime] = None
    attr_pos: Optional[List[PyObjectId]] = None
    attr_neg: Optional[List[PyObjectId]] = None
    bbox: Optional[BBox] = None
    sort: Optional[str] = Field(default="-placed_at", description="e.g. -placed_at, -favorites, difficulty, terrain")
    page: int = 1
    page_size: int = 50


# ------------------------- routes -------------------------

@router.post("/upload-gpx")
async def upload_gpx(
    file: UploadFile = File(...),
    found: bool = Query(False, description="If true, also create found_caches with found_date"),
    current_user: dict = Depends(get_current_user),
):
    result = {}
    payload = await file.read()
    await file.close()
    try:
        summary = import_gpx_payload(
            payload=payload,
            filename=file.filename or "upload.gpx",
            user=current_user,
            found=found,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid GPX/ZIP: {e}")

    try:
        # Variante simple (scan global optimisé: ne traite que les nouvelles caches challenge)
        challenges_stats = create_new_challenges_from_caches()
        # Variante optimisée si tu as la liste des _id caches importées :
        # challenge_stats = create_new_challenges_from_caches(cache_ids=upserted_cache_ids)
    except Exception as e:
        challenges_stats = {"error": str(e)}
    result["challenges_stats"] = challenges_stats

    return result

@router.get("/{gc}")
def get_by_gc(gc: str):
    coll = get_collection("caches")
    doc = coll.find_one({"GC": gc})
    if not doc:
        raise HTTPException(status_code=404, detail="Cache not found")
    return _doc(doc)


@router.get("/by-id/{id}")
def get_by_id(id: str):
    coll = get_collection("caches")
    doc = coll.find_one({"_id": _oid(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Cache not found")
    return _doc(doc)


@router.post("/by-filter")
def by_filter(payload: CacheFilterIn = Body(...)):
    coll = get_collection("caches")
    q: Dict[str, Any] = {}

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
        q.setdefault("$and", []).append({"attributes": {"$elemMatch": {"attribute_doc_id": {"$in": payload.attr_pos}, "is_positive": True}}})
    if payload.attr_neg:
        q.setdefault("$and", []).append({"attributes": {"$elemMatch": {"attribute_doc_id": {"$in": payload.attr_neg}, "is_positive": False}}})
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

    cur = coll.find(q).sort(sort).skip(skip).limit(page_size)
    docs = [_doc(d) for d in cur]
    total = coll.count_documents(q)
    return {"items": docs, "total": total, "page": page, "page_size": page_size}


@router.get("/within-bbox")
def within_bbox(
    min_lat: float = Query(...),
    min_lon: float = Query(...),
    max_lat: float = Query(...),
    max_lon: float = Query(...),
    type_id: Optional[str] = None,
    size_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
    sort: Literal["-placed_at", "-favorites", "difficulty", "terrain"] = "-placed_at",
):
    coll = get_collection("caches")
    q: Dict[str, Any] = {
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

    cur = coll.find(q).sort(order).skip(skip).limit(page_size)
    docs = [_doc(d) for d in cur]
    total = coll.count_documents(q)
    return {"items": docs, "total": total, "page": page, "page_size": page_size}


@router.get("/within-radius")
def within_radius(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(10.0, ge=0.1, le=100.0),
    type_id: Optional[str] = None,
    size_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
):
    """
    Requires caches.loc (GeoJSON Point [lon, lat]) and an index: { loc: "2dsphere" }.
    """
    coll = get_collection("caches")
    geo = {"type": "Point", "coordinates": [lon, lat]}
    q: Dict[str, Any] = {}
    if type_id:
        q["type_id"] = _oid(type_id)
    if size_id:
        q["size_id"] = _oid(size_id)

    pipeline = [
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
        {"$skip": max(0, (page - 1) * min(page_size, 200))},
        {"$limit": min(page_size, 200)},
    ]
    try:
        cur = coll.aggregate(pipeline)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"2dsphere index required on caches.loc: {e}")
    docs = [_doc(d) for d in cur]
    # count with same query (rough, not exact geo count but OK for paging UI)
    total = coll.count_documents({"loc": {"$nearSphere": {"$geometry": geo, "$maxDistance": radius_km * 1000.0}}, **q})
    return {"items": docs, "total": total, "page": page, "page_size": min(page_size, 200)}
