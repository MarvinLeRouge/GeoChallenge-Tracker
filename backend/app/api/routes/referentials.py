# backend/app/api/routes/referentials.py

from fastapi import APIRouter

from app.db.mongodb import get_collection

router = APIRouter(tags=["Referentials"])


# DONE: [BACKLOG] Route /cache_types (GET) vérifiée
@router.get("/cache_types", summary="Get all cache types")
async def get_cache_types():
    """Get all available cache types."""

    cache_types_coll = await get_collection("cache_types")
    cache_types = await cache_types_coll.find({}).to_list(length=None)

    # Convert ObjectId to string for JSON serialization
    for cache_type in cache_types:
        cache_type["_id"] = str(cache_type["_id"])

    return cache_types


# DONE: [BACKLOG] Route /cache_sizes (GET) vérifiée
@router.get("/cache_sizes", summary="Get all cache sizes")
async def get_cache_sizes():
    """Get all available cache sizes."""

    cache_sizes_coll = await get_collection("cache_sizes")
    cache_sizes = await cache_sizes_coll.find({}).to_list(length=None)

    # Convert ObjectId to string for JSON serialization
    for cache_size in cache_sizes:
        cache_size["_id"] = str(cache_size["_id"])

    return cache_sizes


# DONE: [ZONES-EXPLORER] Route /countries (GET) - referential list for the World view
@router.get("/countries", summary="Get all countries with a known ISO code")
async def get_countries():
    """Get all countries that have a resolved ISO 3166-1 alpha-2 code.

    Description:
        Countries without a resolved `code` are excluded since they cannot be
        matched to `administrative_zones.country_code` or to `/zones` results.
        Used by the zones explorer's World view, independently of the
        authenticated user's found-cache counts (unlike `GET /zones?level=0`).
    """
    countries_coll = await get_collection("countries")
    docs = await countries_coll.find(
        {"code": {"$ne": None}}, {"_id": 0, "code": 1, "name": 1, "name_fr": 1}
    ).to_list(length=None)
    items = [
        {"code": d["code"], "name": d.get("name_fr") or d["name"]}
        for d in docs
        if d.get("code") is not None
    ]
    items.sort(key=lambda c: c["name"])
    return items
