# backend/app/api/routes/base.py
# Routes de base (health check, version de l’API, etc.).

from fastapi import APIRouter

router = APIRouter()


# TODO: [BACKLOG] Route /cache_types (GET) à vérifier
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


# TODO: [BACKLOG] Route /cache_sizes (GET) à vérifier
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


# TODO: [BACKLOG] Route /ping (GET) à vérifier
@router.get(
    "/ping",
    tags=["Health"],
    summary="Vérification de santé de l’API",
    description="Retourne un message 'pong' permettant de tester que l’API répond.",
)
async def ping():
    """Health-check API.

    Description:
        Route basique permettant de vérifier la disponibilité de l’API.

    Returns:
        dict: Statut et message de réponse.
    """
    return {"status": "ok", "message": "pong"}
