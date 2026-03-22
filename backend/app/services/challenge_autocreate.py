# backend/app/services/challenge_autocreate.py
# Generates Challenge documents for caches carrying the "challenge" attribute (id=71). Idempotent, via upsert.

"""
Automatic Challenge creation from caches that carry the "challenge" attribute.
Criterion: presence of the geocaching.com attribute `cache_attribute_id = 71` set to positive.

Optimizations:
- Caches already present in `challenges` are excluded upfront.
- When scanning the full collection, a `$lookup` pipeline (indexed on `challenges.cache_id`)
  is used to avoid loading a large set into memory.
- When limiting to a subset (e.g. imported IDs), a `$in` + local exclusion is applied.

Idempotent: a challenge is unique per `cache_id` (unique index required on `challenges(cache_id)`).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from bson import ObjectId
from pymongo import UpdateOne

from app.core.utils import utcnow
from app.db.mongodb import get_collection

# Business constant: "Challenge cache" attribute (geocaching.com)
CHALLENGE_ATTRIBUTE_ID = 71


async def _get_attribute_doc_id(attribute_id: int = CHALLENGE_ATTRIBUTE_ID) -> ObjectId:
    """Resolve the referential `_id` for the "challenge" attribute.

    Description:
        Searches the `cache_attributes` collection for a document where `cache_attribute_id == attribute_id`
        (default 71) and returns its `_id`. Used to match challenge caches.

    Args:
        attribute_id (int): Global numeric attribute identifier (default 71).

    Returns:
        ObjectId: Attribute referential document identifier.

    Raises:
        RuntimeError: If no matching attribute is found (referentials not seeded).
    """
    coll_attrs = await get_collection("cache_attributes")
    doc = await coll_attrs.find_one({"cache_attribute_id": attribute_id}, {"_id": 1})
    if not doc:
        raise RuntimeError(
            f"cache_attributes: no document with cache_attribute_id={attribute_id}. "
            "Ensure the attribute referential is seeded."
        )
    return doc["_id"]


async def _iter_new_challenge_caches_all(attribute_doc_id: ObjectId):
    """List all challenge caches not yet present in `challenges`.

    Description:
        Runs an aggregation pipeline on `caches`:
        - filters on `attributes.elemMatch(attribute_doc_id, is_positive=True)`
        - `$lookup` into `challenges` to exclude already-linked caches
        - lightweight projection (`title`, `description_html`)

    Args:
        attribute_doc_id (ObjectId): Reference to the "challenge" attribute (referential).

    Returns:
        Iterable[dict]: Aggregation cursor over candidate caches.
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
    """List a subset of challenge caches from provided _ids.

    Description:
        Applies `_id ∈ cache_ids` then locally excludes `cache_id`s already present in `challenges`.
        Also filters by positive "challenge" attribute.

    Args:
        attribute_doc_id (ObjectId): Reference to the "challenge" attribute (referential).
        cache_ids (Iterable[ObjectId]): Subset of cache identifiers to consider.

    Returns:
        Iterable[dict]: Search cursor over candidate caches (lightweight projection).
    """
    coll_caches = await get_collection("caches")
    coll_challenges = await get_collection("challenges")

    cache_ids = list(cache_ids)
    if not cache_ids:
        return iter(())

    # Already known (restricted to this subset)
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
    """Create (upsert) challenges from "challenge" caches.

    Description:
        Source of candidate caches:
        - if `cache_ids` is provided, uses the optimized subset approach;
        - otherwise, scans the collection via `$lookup` to exclude existing entries.
        Performs `UpdateOne(..., upsert=True)` on `challenges` using a unique `cache_id`.

    Args:
        cache_ids (Iterable[ObjectId] | None): Optional — restrict to the provided caches.

    Returns:
        dict: Statistics `{‘matched’: int, ‘created’: int, ‘skipped_existing’: int}`.
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
    """Wrapper: explicitly determine new `_id`s before creation.

    Description:
        Computes the candidate set (`caches` + "challenge" attribute) then subtracts
        the `cache_id`s already present in `challenges`. If the set is empty, **does not**
        perform an unnecessary global scan. Delegates to `create_challenges_from_caches`.

    Args:
        cache_ids (Iterable[ObjectId] | None): Optional — input subset.

    Returns:
        dict: Statistics `{‘matched’: int, ‘created’: int, ‘skipped_existing’: int}` (zeros if nothing to create).
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
