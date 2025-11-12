# backend/app/services/challenge_autocreate.py
# Génère des documents Challenge pour les caches portant l’attribut "challenge" (id=71). Idempotent, via upsert.

"""
Création automatique des Challenges à partir des caches qui portent l'attribut "challenge".
Critère: présence de l'attribut geocaching.com `cache_attribute_id = 71` en positif.

Optimisations:
- On exclut d'emblée les caches déjà présentes dans `challenges`.
- Quand on balaye toute la base, on utilise un pipeline `$lookup` (indexé sur `challenges.cache_id`)
  pour éviter de charger un gros set en mémoire.
- Quand on limite à un sous-ensemble (ex: IDs importés), on fait un `$in` + exclusion locale.

Idempotent: un challenge est unique par `cache_id` (index unique requis sur `challenges(cache_id)`).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from bson import ObjectId
from pymongo import UpdateOne

from app.core.utils import utcnow
from app.db.mongodb import get_collection

# Constante métier: attribut "Challenge cache" (geocaching.com)
CHALLENGE_ATTRIBUTE_ID = 71


async def _get_attribute_doc_id(attribute_id: int = CHALLENGE_ATTRIBUTE_ID) -> ObjectId:
    """Résoudre l’_id référentiel de l’attribut « challenge ».

    Description:
        Cherche dans la collection `cache_attributes` le document dont `cache_attribute_id == attribute_id`
        (par défaut 71), et retourne son `_id`. Utilisé pour matcher les caches challenge.

    Args:
        attribute_id (int): Identifiant numérique global de l’attribut (par défaut 71).

    Returns:
        ObjectId: Identifiant du document référentiel d’attribut.

    Raises:
        RuntimeError: Si aucun attribut correspondant n’est trouvé (référentiels non seedés).
    """
    coll_attrs = await get_collection("cache_attributes")
    doc = await coll_attrs.find_one({"cache_attribute_id": attribute_id}, {"_id": 1})
    if not doc:
        raise RuntimeError(
            f"cache_attributes: aucun document avec cache_attribute_id={attribute_id}. "
            "Vérifie que le référentiel des attributs est seedé."
        )
    return doc["_id"]


async def _iter_new_challenge_caches_all(attribute_doc_id: ObjectId):
    """Lister globalement les caches challenge non encore présentes dans `challenges`.

    Description:
        Exécute un pipeline d’agrégation sur `caches` :
        - filtre `attributes.elemMatch(attribute_doc_id, is_positive=True)`
        - `$lookup` vers `challenges` pour exclure celles déjà liées
        - projection légère (`title`, `description_html`)

    Args:
        attribute_doc_id (ObjectId): Référence de l’attribut « challenge » (référentiel).

    Returns:
        Iterable[dict]: Curseur d’agrégation sur les caches candidates.
    """
    coll_caches = await get_collection("caches")
    pipeline: list[dict[str, Any]] = [
        {
            "$match": {
                "attributes": {
                    "$elemMatch": {
                        "attribute_doc_id": attribute_doc_id,
                        "is_positive": True,
                    }
                }
            }
        },
        {
            "$lookup": {
                "from": "challenges",
                "localField": "_id",
                "foreignField": "cache_id",
                "as": "existing",
            }
        },
        {"$match": {"$expr": {"$eq": [{"$size": "$existing"}, 0]}}},
        {"$project": {"title": 1, "description_html": 1}},
    ]
    return coll_caches.aggregate(pipeline, allowDiskUse=True)


async def _iter_new_challenge_caches_subset(
    attribute_doc_id: ObjectId, cache_ids: Iterable[ObjectId]
):
    """Lister un sous-ensemble de caches challenge à partir d’_id fournis.

    Description:
        Applique `_id ∈ cache_ids` puis exclut localement les `cache_id` déjà présents dans `challenges`.
        Filtre également par attribut « challenge » positif.

    Args:
        attribute_doc_id (ObjectId): Référence de l’attribut « challenge » (référentiel).
        cache_ids (Iterable[ObjectId]): Sous-ensemble d’identifiants de caches à considérer.

    Returns:
        Iterable[dict]: Curseur de recherche sur les caches candidates (projection légère).
    """
    coll_caches = await get_collection("caches")
    coll_challenges = await get_collection("challenges")

    cache_ids = list(cache_ids)
    if not cache_ids:
        return iter(())

    # Déjà connus (uniquement dans ce sous-ensemble)
    known_ids = set(await coll_challenges.distinct("cache_id", {"cache_id": {"$in": cache_ids}}))

    base_filter: dict[str, Any] = {
        "_id": {"$in": [cid for cid in cache_ids if cid not in known_ids]},
        "attributes": {
            "$elemMatch": {
                "attribute_doc_id": attribute_doc_id,
                "is_positive": True,
            }
        },
    }
    projection = {"title": 1, "description_html": 1}
    return coll_caches.find(base_filter, projection)


async def create_challenges_from_caches(
    *, cache_ids: Iterable[ObjectId] | None = None
) -> dict[str, Any]:
    """Créer (upsert) les challenges à partir des caches « challenge ».

    Description:
        Source des caches candidates :
        - si `cache_ids` est fourni, utilise le sous-ensemble (optimisé) ;
        - sinon, scanne la collection via `$lookup` pour exclure l’existant.
        Effectue des `UpdateOne(..., upsert=True)` sur `challenges` avec `cache_id` unique.

    Args:
        cache_ids (Iterable[ObjectId] | None): Optionnel — restreindre aux caches fournies.

    Returns:
        dict: Statistiques `{'matched': int, 'created': int, 'skipped_existing': int}`.
    """
    attr_doc_id = await _get_attribute_doc_id(CHALLENGE_ATTRIBUTE_ID)

    if cache_ids is None:
        cursor = await _iter_new_challenge_caches_all(attr_doc_id)
    else:
        cursor = await _iter_new_challenge_caches_subset(attr_doc_id, cache_ids)

    coll_challenges = await get_collection("challenges")

    ops: list[UpdateOne] = []
    matched = 0
    async for cache in cursor:
        matched += 1
        cache_id = cache["_id"]
        title = cache.get("title") or "Challenge"
        description = cache.get("description_html") or ""

        ops.append(
            UpdateOne(
                {"cache_id": cache_id},
                {
                    "$setOnInsert": {
                        "cache_id": cache_id,
                        "name": title,
                        "description": description,
                        "created_at": utcnow(),
                    },
                    "$set": {
                        "updated_at": utcnow(),
                    },
                },
                upsert=True,
            )
        )

    created = 0
    if ops:
        res = await coll_challenges.bulk_write(ops, ordered=False)
        created = len(res.upserted_ids or {})

    skipped_existing = matched - created
    return {
        "matched": matched,
        "created": created,
        "skipped_existing": skipped_existing,
    }


async def create_new_challenges_from_caches(
    *, cache_ids: Iterable[ObjectId] | None = None
) -> dict[str, Any]:
    """Wrapper : déterminer explicitement les nouveaux `_id` avant création.

    Description:
        Calcule l’ensemble des candidates (`caches` + attribut « challenge ») puis soustrait
        les `cache_id` déjà présents dans `challenges`. Si l’ensemble est vide, **n’effectue pas**
        de scan global inutile. Délègue ensuite à `create_challenges_from_caches`.

    Args:
        cache_ids (Iterable[ObjectId] | None): Optionnel — sous-ensemble d’entrée.

    Returns:
        dict: Statistiques `{'matched': int, 'created': int, 'skipped_existing': int}` (zéro si rien à créer).
    """
    attr_doc_id = await _get_attribute_doc_id(CHALLENGE_ATTRIBUTE_ID)
    coll_caches = await get_collection("caches")
    coll_challenges = await get_collection("challenges")

    if cache_ids is not None:
        subset = list(cache_ids)
        if not subset:
            return {"matched": 0, "created": 0, "skipped_existing": 0}
        known = set(await coll_challenges.distinct("cache_id", {"cache_id": {"$in": subset}}))
        new_ids = [cid for cid in subset if cid not in known]
        if not new_ids:
            return {"matched": 0, "created": 0, "skipped_existing": 0}
        return await create_challenges_from_caches(cache_ids=new_ids)

    candidate_ids = await coll_caches.distinct(
        "_id",
        {"attributes": {"$elemMatch": {"attribute_doc_id": attr_doc_id, "is_positive": True}}},
    )
    if not candidate_ids:
        return {"matched": 0, "created": 0, "skipped_existing": 0}

    known = set(await coll_challenges.distinct("cache_id", {"cache_id": {"$in": candidate_ids}}))
    new_ids = [cid for cid in candidate_ids if cid not in known]
    if not new_ids:
        return {"matched": 0, "created": 0, "skipped_existing": 0}
    return await create_challenges_from_caches(cache_ids=new_ids)
