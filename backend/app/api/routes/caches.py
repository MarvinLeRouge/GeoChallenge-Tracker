# backend/app/api/routes/caches.py
# Routes liées aux géocaches :
# - Upload GPX et import
# - Recherche par filtres, bbox ou rayon
# - Récupération par identifiant ou code GC

from __future__ import annotations

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

from app.api.dto.cache_query import CacheFilterIn
from app.core.security import CurrentUserId, get_current_user
from app.core.settings import get_settings
from app.db.mongodb import get_collection
from app.services.challenge_autocreate import create_new_challenges_from_caches
from app.services.gpx_importer_service import import_gpx_payload

settings = get_settings()

router = APIRouter(prefix="/caches", tags=["caches"], dependencies=[Depends(get_current_user)])

# ------------------------- helpers -------------------------


def _doc(d: dict[str, Any]) -> dict[str, Any]:
    """Encode un document MongoDB (ObjectId -> str)."""
    return jsonable_encoder(d, custom_encoder={ObjectId: str})


def _oid(v: str | ObjectId | None) -> ObjectId | None:
    """Convertit une valeur en ObjectId MongoDB ou lève HTTP 400 si invalide."""
    if v is None:
        return None
    if isinstance(v, ObjectId):
        return v
    try:
        return ObjectId(v)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid ObjectId: {v}") from e


# ------------------------- compact helpers -------------------------

# Collections et champs d'étiquette (ajuste "name" si ton schéma diffère)
TYPE_COLLECTION = "cache_types"
SIZE_COLLECTION = "cache_sizes"


TYPE_LABEL_FIELD = "name"
TYPE_CODE_FIELD = "code"
SIZE_LABEL_FIELD = "name"
SIZE_CODE_FIELD = "code"

# Liste des champs à retourner en mode "compact"
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
    """Stades $lookup/$project pour enrichir type/size (label+code) et projeter les champs compacts."""
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
        # on prend les 1ers éléments et on fabrique des objets {label, code}
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
        # on retire les tableaux temporaires
        {"$project": {**COMPACT_FIELDS, "type": 1, "size": 1}},
    ]


# ------------------------- routes -------------------------


# DONE: [BACKLOG] Route /caches/upload-gpx (POST) à vérifier
@router.post(
    "/upload-gpx",
    summary="Importe des caches depuis un fichier GPX/ZIP",
    description=(
        "Charge un fichier GPX (ou ZIP contenant un GPX) et importe les géocaches associées.\n\n"
        "- Optionnellement, marque les caches comme trouvées (création de `found_caches`)\n"
        "- Tente ensuite une création automatique de challenges à partir des caches importées\n"
        f"- **Limite de taille** : {settings.max_upload_mb} Mo\n"
        "- Supporte plusieurs formats de GPX (cgeo, pocket_query)\n"
        "- Retourne un résumé d’import et des statistiques liées aux challenges"
    ),
    responses={
        413: {"description": "Payload too large"},
        400: {"description": "Fichier invalide"},
    },
)
async def upload_gpx(
    request: Request,
    user_id: CurrentUserId,
    file: Annotated[
        UploadFile, File(..., description="Fichier GPX à importer (ou ZIP contenant un GPX).")
    ],
    import_mode: Literal["all", "found"] = Query(
        "all",
        description="Mode d'import: 'all' (toutes les caches) ou 'found' (mes trouvailles)",
    ),
    source_type: Literal["auto", "cgeo", "pocket_query"] = Query(
        "auto",
        description="Type de source GPX: 'auto' (détection automatique), 'cgeo', 'pocket_query'",
    ),
):
    """Importe un fichier GPX/ZIP et déclenche la création de challenges.

    Description:
        Cette route lit un fichier GPX (ou un ZIP qui contient un GPX), importe les caches dans la base,
        puis lance un traitement pour auto-créer des challenges basés sur les caches nouvellement importées.

    Args:
        file (UploadFile): Fichier GPX ou ZIP à traiter.
        import_mode (str): Mode d'import - 'all' pour importer toutes les caches, 'found' pour marquer comme trouvées.
        source_type (str): Format du fichier GPX - 'auto' pour détection automatique, 'cgeo' ou 'pocket_query'.

    Returns:
        dict: Objet contenant le récapitulatif d'import (`summary`) et des statistiques liées aux challenges (`challenges_stats`).
    """

    result = {}
    # lecture streaming avec limite de taille
    read_bytes = 0
    chunks: list[bytes] = []
    while True:
        chunk = await file.read(settings.one_mb)
        if not chunk:
            break
        read_bytes += len(chunk)
        if read_bytes > settings.max_upload_bytes:
            # Important: fermer le fichier et renvoyer 413
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
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid GPX/ZIP: {e}") from e

    try:
        # Variante simple (scan global optimisé: ne traite que les nouvelles caches challenge)
        challenges_stats = await create_new_challenges_from_caches()
        # Variante optimisée si tu as la liste des _id caches importées :
        # challenge_stats = create_new_challenges_from_caches(cache_ids=upserted_cache_ids)
    except Exception as e:
        challenges_stats = {"error": str(e)}
    result["challenges_stats"] = challenges_stats

    return result


# TODO: [BACKLOG] Route /caches/by-filter (POST) à vérifier
@router.post(
    "/by-filter",
    summary="Recherche de caches par filtres",
    description=(
        "Retourne une liste paginée de géocaches selon des filtres combinables :\n"
        "- Texte (`$text`), type, taille, pays/état\n"
        "- Difficulté/terrain (plages min/max)\n"
        "- Période de placement (après/avant)\n"
        "- Attributs positifs/négatifs\n"
        "- BBox optionnelle et tri (-placed_at, -favorites, difficulty, terrain)"
    ),
)
async def by_filter(
    payload: Annotated[
        CacheFilterIn,
        Body(
            ...,
            description=(
                "Objet de filtrage et de pagination :\n"
                "- `q`: recherche plein texte\n"
                "- `type_id`, `size_id`, `country_id`, `state_id`\n"
                "- `difficulty`, `terrain`: objets `Range {min,max}`\n"
                "- `placed_after`, `placed_before`: bornes temporelles\n"
                "- `attr_pos`, `attr_neg`: listes d’attributs (ObjectId)\n"
                "- `bbox`: `{min_lat,min_lon,max_lat,max_lon}`\n"
                "- `sort`, `page`, `page_size`"
            ),
        ),
    ],
    compact: bool = Query(
        True,
        description="Retourne une version abrégée (_id, GC, title, type_id, type, size_id, size, difficulty, terrain).",
    ),
):
    """Recherche multi-critères de géocaches.

    Description:
        Filtre les caches selon plusieurs critères combinables, applique le tri et retourne des résultats paginés.

    Args:
        payload (CacheFilterIn): Paramètres de filtrage, tri et pagination.

    Returns:
        dict: Résultats paginés `{items, total, page, page_size}`.
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


# TODO: [BACKLOG] Route /caches/within-bbox (GET) à vérifier
@router.get(
    "/within-bbox",
    summary="Caches dans une bounding box",
    description=(
        "Liste paginée des caches comprises dans une BBox.\n"
        "- Filtre optionnel par `type_id` et `size_id`\n"
        "- Tri: `-placed_at`, `-favorites`, `difficulty`, `terrain`\n"
        "- Pagination avec `page` et `page_size` (max 200)"
    ),
)
async def within_bbox(
    min_lat: float = Query(..., description="Latitude minimale de la BBox."),
    min_lon: float = Query(..., description="Longitude minimale de la BBox."),
    max_lat: float = Query(..., description="Latitude maximale de la BBox."),
    max_lon: float = Query(..., description="Longitude maximale de la BBox."),
    type_id: str | None = Query(
        None, description="Filtre optionnel: identifiant de type (ObjectId)."
    ),
    size_id: str | None = Query(
        None, description="Filtre optionnel: identifiant de taille (ObjectId)."
    ),
    page: int = Query(1, ge=1, description="Numéro de page (≥1)."),
    page_size: int = Query(100, ge=1, le=200, description="Taille de page (1–200)."),
    sort: Literal["-placed_at", "-favorites", "difficulty", "terrain"] = Query(
        "-placed_at",
        description="Clé de tri: '-placed_at' (défaut), '-favorites', 'difficulty', 'terrain'.",
    ),
    compact: bool = Query(
        True,
        description="Retourne une version abrégée (_id, GC, title, type_id, type, size_id, size, difficulty, terrain).",
    ),
):
    """Liste les caches d’une BBox.

    Description:
        Applique un filtre spatial rectangulaire (BBox) avec options de tri et de pagination.
        Peut restreindre par type et/ou taille de cache.

    Args:
        min_lat (float): Latitude minimale.
        min_lon (float): Longitude minimale.
        max_lat (float): Latitude maximale.
        max_lon (float): Longitude maximale.
        type_id (str | None): Identifiant de type de cache (ObjectId).
        size_id (str | None): Identifiant de taille de cache (ObjectId).
        page (int): Numéro de page.
        page_size (int): Taille de page.
        sort (Literal): Clé de tri.

    Returns:
        dict: Résultats paginés `{items, total, page, page_size}`.
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


# TODO: [BACKLOG] Route /caches/within-radius (GET) à vérifier
@router.get(
    "/within-radius",
    summary="Caches autour d’un point (rayon)",
    description=(
        "Recherche par distance (geoNear) autour d’un point (lat, lon).\n"
        "- Requiert un index 2dsphere sur `caches.loc`\n"
        "- Filtre optionnel par `type_id` et `size_id`\n"
        "- Pagination via `page`/`page_size` (max 200)"
    ),
)
async def within_radius(
    lat: float = Query(..., description="Latitude du centre."),
    lon: float = Query(..., description="Longitude du centre."),
    radius_km: float = Query(
        10.0,
        ge=0.1,
        le=100.0,
        description="Rayon de recherche en kilomètres (0.1–100).",
    ),
    type_id: str | None = Query(
        None, description="Filtre optionnel: identifiant de type (ObjectId)."
    ),
    size_id: str | None = Query(
        None, description="Filtre optionnel: identifiant de taille (ObjectId)."
    ),
    page: int = Query(1, ge=1, description="Numéro de page (≥1)."),
    page_size: int = Query(100, ge=1, le=200, description="Taille de page (1–200)."),
    compact: bool = Query(
        True,
        description="Retourne une version abrégée (_id, GC, title, type_id, type, size_id, size, difficulty, terrain).",
    ),
):
    """Recherche par rayon autour d’un point.

    Description:
        Effectue une agrégation `$geoNear` centrée sur (lat, lon) avec une distance maximale,
        puis applique tri par distance ascendant, pagination, et compte estimatif.

    Args:
        lat (float): Latitude du centre.
        lon (float): Longitude du centre.
        radius_km (float): Rayon de recherche en kilomètres.
        type_id (str | None): Identifiant de type de cache (ObjectId).
        size_id (str | None): Identifiant de taille de cache (ObjectId).
        page (int): Numéro de page.
        page_size (int): Taille de page.

    Returns:
        dict: Résultats paginés `{items, total, page, nb_pages, page_size}`.

    Raises:
        HTTPException: 400 si l’index `2dsphere` requis sur `caches.loc` est manquant.
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
    radius_radians = radius_km / 6378.1  # rayon de la Terre en km
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


# TODO: [BACKLOG] Route /caches/{gc} (GET) à vérifier
@router.get(
    "/{gc}",
    summary="Récupère une cache par code GC",
    description="Retourne une cache unique à partir de son code GC.",
)
async def get_by_gc(
    gc: str = Path(..., description="Code GC unique de la cache."),
):
    """Lecture d’une cache (code GC).

    Description:
        Récupère la cache identifiée par son code GC. Renvoie 404 si introuvable.

    Args:
        gc (str): Code GC de la cache.

    Returns:
        dict: Document cache sérialisé.
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


# TODO: [BACKLOG] Route /caches/by-id/{id} (GET) à vérifier
@router.get(
    "/by-id/{id}",
    summary="Récupère une cache par identifiant MongoDB",
    description="Retourne une cache unique à partir de son ObjectId (format chaîne).",
)
async def get_by_id(
    id: str = Path(
        ..., description="Identifiant MongoDB (ObjectId) de la cache, au format chaîne."
    ),
):
    """Lecture d’une cache (ObjectId).

    Description:
        Récupère la cache par son identifiant MongoDB. Renvoie 404 si introuvable
        et 400 si l’ObjectId est invalide.

    Args:
        id (str): Identifiant MongoDB (ObjectId sous forme de chaîne).

    Returns:
        dict: Document cache sérialisé.
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
