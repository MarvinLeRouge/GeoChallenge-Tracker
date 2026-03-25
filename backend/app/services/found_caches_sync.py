# backend/app/services/found_caches_sync.py
# Synchronise la liste complète des found caches d'un utilisateur depuis un fichier texte.

from __future__ import annotations

import re
from datetime import date
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.utils import utcnow

# Regex GC codes — case-insensitive, word boundary to avoid partial matches
_GC_PATTERN = re.compile(r"\bGC[A-Z0-9]+\b", re.IGNORECASE)


def extract_gc_codes(text: str) -> list[str]:
    """Extract unique GC codes from arbitrary text.

    Args:
        text: Raw file content.

    Returns:
        list[str]: Deduplicated GC codes in uppercase, preserving first-seen order.
    """
    seen: dict[str, None] = {}
    for match in _GC_PATTERN.finditer(text):
        seen[match.group().upper()] = None
    return list(seen)


async def sync_found_caches(
    db: AsyncIOMotorDatabase,
    user_id: ObjectId,
    gc_codes: list[str],
) -> dict[str, Any]:
    """Synchronise the user's found caches from a canonical GC code list.

    Description:
        Computes the diff between the provided list and the current state in
        ``found_caches``, then applies deletions and insertions atomically.
        Caches not present in the ``caches`` collection are reported as unknown
        but do not cause the operation to fail.

    Args:
        db: MongoDB database instance.
        user_id: Target user identifier.
        gc_codes: Deduplicated list of GC codes to treat as the complete found list.

    Returns:
        dict: {
            nb_provided (int): number of GC codes in the input,
            nb_deleted (int): found caches removed,
            nb_added (int): found caches inserted,
            nb_unknown_gc (int): GC codes not found in the caches collection,
            unknown_gc_codes (list[str]): the unknown codes,
        }
    """
    coll_caches = db.caches
    coll_found = db.found_caches

    # --- Resolve GC codes to cache ObjectIds ---
    known_docs = await coll_caches.find({"GC": {"$in": gc_codes}}, {"_id": 1, "GC": 1}).to_list(
        length=None
    )

    known_by_gc: dict[str, ObjectId] = {doc["GC"]: doc["_id"] for doc in known_docs}
    known_ids: set[ObjectId] = set(known_by_gc.values())
    unknown_gc_codes: list[str] = [gc for gc in gc_codes if gc not in known_by_gc]

    # --- Current found caches for this user ---
    existing_docs = await coll_found.find({"user_id": user_id}, {"_id": 1, "cache_id": 1}).to_list(
        length=None
    )

    existing_by_cache_id: dict[ObjectId, ObjectId] = {
        doc["cache_id"]: doc["_id"] for doc in existing_docs
    }
    existing_ids: set[ObjectId] = set(existing_by_cache_id)

    # --- Compute diff ---
    to_delete: set[ObjectId] = existing_ids - known_ids
    to_add: set[ObjectId] = known_ids - existing_ids

    # --- Apply deletions ---
    nb_deleted = 0
    if to_delete:
        del_result = await coll_found.delete_many(
            {"user_id": user_id, "cache_id": {"$in": list(to_delete)}}
        )
        nb_deleted = del_result.deleted_count

    # --- Apply insertions ---
    nb_added = 0
    if to_add:
        now = utcnow()
        today = date.today()
        docs = [
            {
                "user_id": user_id,
                "cache_id": cache_id,
                "found_date": today,
                "notes": None,
                "created_at": now,
                "updated_at": None,
            }
            for cache_id in to_add
        ]
        ins_result = await coll_found.insert_many(docs, ordered=False)
        nb_added = len(ins_result.inserted_ids)

    return {
        "nb_provided": len(gc_codes),
        "nb_deleted": nb_deleted,
        "nb_added": nb_added,
        "nb_unknown_gc": len(unknown_gc_codes),
        "unknown_gc_codes": unknown_gc_codes,
    }
