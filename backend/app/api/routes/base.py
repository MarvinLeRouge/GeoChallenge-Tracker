# backend/app/api/routes/base.py

from fastapi import APIRouter

router = APIRouter()


# DONE: [BACKLOG] Route /cache_types (GET) vérifiée
@router.get("/cache_types", summary="Get all cache types")
async def get_cache_types():
    """Get all available cache types."""
    from app.db.mongodb import get_collection

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
    from app.db.mongodb import get_collection

    cache_sizes_coll = await get_collection("cache_sizes")
    cache_sizes = await cache_sizes_coll.find({}).to_list(length=None)

    # Convert ObjectId to string for JSON serialization
    for cache_size in cache_sizes:
        cache_size["_id"] = str(cache_size["_id"])

    return cache_sizes
