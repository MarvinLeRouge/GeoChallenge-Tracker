# backend/app/api/routes/base.py
# Routes de base (health check, version de l’API, etc.).

from fastapi import APIRouter

router = APIRouter()


@router.get("/cache_types", summary="Get all cache types")
async def get_cache_types():
    """Get all available cache types."""
    from app.db.mongodb import get_collection
    cache_types_coll = await get_collection("cache_types")
    cache_types = await cache_types_coll.find({}).to_list(length=None)
    return cache_types


@router.get("/cache_sizes", summary="Get all cache sizes") 
async def get_cache_sizes():
    """Get all available cache sizes."""
    from app.db.mongodb import get_collection
    cache_sizes_coll = await get_collection("cache_sizes")
    cache_sizes = await cache_sizes_coll.find({}).to_list(length=None)
    return cache_sizes


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
