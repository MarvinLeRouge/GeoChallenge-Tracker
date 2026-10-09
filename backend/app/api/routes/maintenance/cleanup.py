# app/api/routes/maintenance/cleanup.py
# Orphan-reference detection and cleanup routes (GET/DELETE /maintenance/db_cleanup,
# GET /maintenance/db_cleanup/backups).

from __future__ import annotations

import json
import secrets
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any, cast

from bson import ObjectId
from fastapi import HTTPException

from app.core.backup_config import CLEANUP_BACKUP_DIR
from app.core.utils import utcnow
from app.db.mongodb import get_collection

from ._router import router
from ._shared import (
    CONFIRMATION_KEY_TTL,
    PENDING_CLEANUP_DIR,
    _pending_key_path,
    clean_expired_keys,
    serialize_mongo_doc,
    write_json_zip,
)


def save_cleanup_pending(key: str, orphans: dict, expires_at: datetime) -> None:
    """Persists an orphan analysis pending confirmation into a JSON file."""
    PENDING_CLEANUP_DIR.mkdir(parents=True, exist_ok=True)
    with open(_pending_key_path(PENDING_CLEANUP_DIR, key), "w", encoding="utf-8") as f:
        json.dump({"orphans": orphans, "expires_at": expires_at.isoformat()}, f)


def load_cleanup_pending(key: str) -> dict | None:
    """Loads a pending analysis from the JSON file. Returns None if not found."""
    p = _pending_key_path(PENDING_CLEANUP_DIR, key)
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def delete_cleanup_pending(key: str) -> None:
    """Deletes the JSON file of a pending analysis."""
    _pending_key_path(PENDING_CLEANUP_DIR, key).unlink(missing_ok=True)


COLLECTION_DEPENDENCY_ORDER = [
    "countries",  # Level 0: no dependencies
    "cache_types",  # Level 0: no dependencies
    "cache_sizes",  # Level 0: no dependencies
    "cache_attributes",  # Level 0: no dependencies
    "users",  # Level 0: no dependencies
    "states",  # Level 1: depends on countries
    "caches",  # Level 1: depends on cache_types, cache_sizes, countries, states, cache_attributes (nested)
    "challenges",  # Level 2: depends on caches
    "user_challenges",  # Level 3: depends on users, challenges
    "found_caches",  # Level 3: depends on users, caches
    "user_challenge_tasks",  # Level 4: depends on user_challenges
    "progress",  # Level 4: depends on user_challenges
    "targets",  # Level 5: depends on users, user_challenges, caches, user_challenge_tasks
]


REFERENCES_MAP = {
    "caches": {
        "country_id": "countries",
        "state_id": "states",
        "type_id": "cache_types",  # Added: CacheType reference
        "size_id": "cache_sizes",  # Added: CacheSize reference
    },
    "challenges": {
        "cache_id": "caches",
    },
    "found_caches": {
        "cache_id": "caches",
        "user_id": "users",
    },
    "progress": {
        "user_challenge_id": "user_challenges",
    },
    "states": {
        "country_id": "countries",
    },
    "targets": {
        "user_id": "users",
        "user_challenge_id": "user_challenges",
        "cache_id": "caches",
        "primary_task_id": "user_challenge_tasks",
    },
    "user_challenge_tasks": {
        "user_challenge_id": "user_challenges",
    },
    "user_challenges": {
        "challenge_id": "challenges",
        "user_id": "users",
    },
}


async def find_nested_array_orphans(collection_name: str, field_path: str, ref_collection: str):
    """
    Find orphan references in nested arrays (like caches.attributes.attribute_doc_id -> cache_attributes)

    Args:
        collection_name: Source collection name
        field_path: Dot notation path to the nested field (e.g., "attributes.attribute_doc_id")
        ref_collection: Target collection name for reference check
    """
    # Split the field_path to get the array field and the nested reference field
    parts = field_path.split(".")
    if len(parts) < 2:
        return []

    array_field = ".".join(parts[:-1])  # "attributes"
    nested_field = parts[-1]  # "attribute_doc_id"

    # Get all valid IDs from the reference collection
    ref_collection_obj = await get_collection(ref_collection)
    valid_ids = await ref_collection_obj.distinct("_id")

    # Use aggregation to find documents with nested references that are not in valid_ids
    pipeline = [
        # Unwind the array to work with individual elements
        {"$unwind": f"${array_field}"},
        # Match where the nested field exists and is not in valid_ids
        {
            "$match": {
                f"{array_field}.{nested_field}": {"$exists": True, "$ne": None, "$nin": valid_ids}
            }
        },
        # Project the document _id and the problematic reference
        {
            "$project": {
                "_id": 1,
                "problematic_ref": f"${array_field}.{nested_field}",
                "full_array_item": f"${array_field}",
            }
        },
    ]

    collection_obj = await get_collection(collection_name)
    cursor = collection_obj.aggregate(cast(Sequence[Mapping[str, Any]], pipeline))
    orphan_docs = await cursor.to_list(length=None)

    # Extract unique document IDs that contain orphaned references
    orphan_ids = list(set(str(doc["_id"]) for doc in orphan_docs))
    return orphan_ids


def _build_collection_references_map() -> dict[str, list[tuple[str, str]]]:
    """Build a map of target_collection -> [(source_collection, field), ...] from REFERENCES_MAP.

    Returns:
        dict: Reverse-reference map used to detect orphans.
    """
    collection_references: dict[str, list[tuple[str, str]]] = {}
    all_refs = {
        **{
            f"{coll}.{field}": ref_coll
            for coll, field_refs in REFERENCES_MAP.items()
            for field, ref_coll in field_refs.items()
        },
        "caches.attributes.attribute_doc_id": "cache_attributes",
    }
    for ref_key, target_collection in all_refs.items():
        source_collection, field = ref_key.split(".", 1)
        collection_references.setdefault(target_collection, []).append((source_collection, field))
    return collection_references


async def _find_nested_attribute_orphans(source_collection_obj: Any) -> list[str]:
    """Find cache documents whose nested attribute references an invalid cache_attribute.

    Args:
        source_collection_obj (Any): The `caches` collection handle.

    Returns:
        list[str]: Orphan document ids (as strings).
    """
    pipeline = [
        {"$unwind": "$attributes"},
        {"$match": {"attributes.attribute_doc_id": {"$exists": True, "$ne": None}}},
        {
            "$lookup": {
                "from": "cache_attributes",
                "localField": "attributes.attribute_doc_id",
                "foreignField": "_id",
                "as": "valid_attribute",
            }
        },
        {"$match": {"valid_attribute": {"$size": 0}}},  # No match found
        {"$project": {"_id": 1}},
        {"$group": {"_id": None, "orphan_ids": {"$addToSet": "$_id"}}},
    ]
    results = await source_collection_obj.aggregate(pipeline).to_list(length=None)
    if results and results[0]["orphan_ids"]:
        return [str(obj_id) for obj_id in results[0]["orphan_ids"]]
    return []


async def _find_reference_orphans(
    source_collection_obj: Any, field: str, current_target_ids: set[Any]
) -> list[str]:
    """Find source documents whose `field` references an id outside `current_target_ids`.

    Args:
        source_collection_obj (Any): Source collection handle.
        field (str): Field holding the reference.
        current_target_ids (set): Still-valid target ids.

    Returns:
        list[str]: Orphan document ids (as strings).
    """
    pipeline = [
        {"$match": {field: {"$exists": True, "$ne": None}}},
        {"$match": {field: {"$nin": list(current_target_ids)}}},
        {"$project": {"_id": 1}},
    ]
    cursor = source_collection_obj.aggregate(pipeline)
    orphan_docs = await cursor.to_list(length=None)
    return [str(doc["_id"]) for doc in orphan_docs]


async def _find_orphan_ids_for_field(
    source_collection: str,
    source_collection_obj: Any,
    field: str,
    current_target_ids: set[Any],
) -> list[str]:
    """Find orphan ids for one (source_collection, field) reference, nested or regular.

    Args:
        source_collection (str): Name of the source collection.
        source_collection_obj (Any): Source collection handle.
        field (str): Field holding the reference (may be nested, e.g. `attributes.x`).
        current_target_ids (set): Still-valid target ids (for non-nested references).

    Returns:
        list[str]: Orphan document ids (as strings).
    """
    if "." in field:
        if f"{source_collection}.{field}" == "caches.attributes.attribute_doc_id":
            # Handle nested reference case
            return await _find_nested_attribute_orphans(source_collection_obj)
        return []
    return await _find_reference_orphans(source_collection_obj, field, current_target_ids)


async def _detect_orphans_for_collection(
    collection_name: str,
    refs: list[tuple[str, str]],
    simulated_orphan_ids: dict[str, set[Any]],
    orphans: dict[str, list[str]],
) -> None:
    """Detect orphans for every (source_collection, field) referencing `collection_name`.

    Description:
        Mutates `simulated_orphan_ids` and `orphans` in place as orphans are found, so
        later collections in the dependency order see the simulated removals.

    Args:
        collection_name (str): Collection currently being processed (the reference target).
        refs (list[tuple]): `(source_collection, field)` pairs referencing it.
        simulated_orphan_ids (dict): Per-collection sets of ids simulated as removed.
        orphans (dict): `{"<collection>.<field>": [orphan_id, ...]}`, accumulated.
    """
    for source_collection, field in refs:
        target_collection_obj = await get_collection(collection_name)
        all_target_ids = set(await target_collection_obj.distinct("_id"))
        current_target_ids = all_target_ids - simulated_orphan_ids[collection_name]

        source_collection_obj = await get_collection(source_collection)
        orphan_ids = await _find_orphan_ids_for_field(
            source_collection, source_collection_obj, field, current_target_ids
        )

        if orphan_ids:
            ref_key = f"{source_collection}.{field}"
            orphans.setdefault(ref_key, []).extend(orphan_ids)
            simulated_orphan_ids[source_collection].update(ObjectId(oid) for oid in orphan_ids)


# DONE: [BACKLOG] Route /maintenance/db_cleanup (GET) verified
@router.get("/db_cleanup")
async def cleanup_analyze():
    """
    Analyzes the database to detect orphaned records.
    Scans from most central to most peripheral to detect direct and indirect orphans.
    Simulates the deletion process to detect all potential orphans.
    Returns a report and a confirmation key for the cleanup.
    """
    clean_expired_keys()

    collection_references = _build_collection_references_map()

    # Copy original collection contents to simulate removals
    # This is a simplified approach: we'll simulate by tracking what would be removed
    # and then calculate orphans based on that simulated state
    simulated_orphan_ids: dict[str, set[Any]] = {
        collection_name: set() for collection_name in COLLECTION_DEPENDENCY_ORDER
    }
    orphans: dict[str, list[str]] = {}

    # Process from most central to most dependent
    for collection_name in COLLECTION_DEPENDENCY_ORDER:
        if collection_name in collection_references:
            await _detect_orphans_for_collection(
                collection_name,
                collection_references[collection_name],
                simulated_orphan_ids,
                orphans,
            )

    # Remove duplicates
    for key in orphans:
        orphans[key] = list(set(orphans[key]))

    total_orphans = sum(len(ids) for ids in orphans.values())

    if not orphans:
        return {
            "message": "No orphans found. Database is clean!",
            "orphans_found": {},
            "total_orphans": 0,
        }

    # Generate a secure confirmation key
    confirmation_key = secrets.token_urlsafe(16)
    expires_at = utcnow() + timedelta(minutes=CONFIRMATION_KEY_TTL)

    # Persist the analysis in a file shared across workers
    save_cleanup_pending(confirmation_key, orphans, expires_at)

    return {
        "orphans_found": orphans,
        "total_orphans": total_orphans,
        "confirmation_key": confirmation_key,
        "expires_at": expires_at.isoformat(),
        "message": f"Found {total_orphans} orphan(s). Use DELETE with this key to clean.",
    }


def _collect_orphan_object_ids(
    collection_name: str, orphans_by_key_path: dict[str, list[str]]
) -> list[ObjectId]:
    """Collect every orphan ObjectId recorded for `collection_name` across all key paths.

    Args:
        collection_name (str): Collection currently being processed.
        orphans_by_key_path (dict): `{"<collection>.<field>": [orphan_id, ...]}` from the analysis.

    Returns:
        list[ObjectId]: Deduplicated ObjectIds to delete from `collection_name`.
    """
    all_orphan_ids: set[str] = set()
    for key_path, orphan_ids in orphans_by_key_path.items():
        current_collection, _field = key_path.split(".", 1)
        if current_collection == collection_name:
            all_orphan_ids.update(orphan_ids)
    return [ObjectId(oid) for oid in all_orphan_ids]


async def _backup_and_delete_documents(
    collection_name: str, object_ids: list[ObjectId], backup_data: dict[str, Any]
) -> int:
    """Back up then delete the given documents from `collection_name`.

    Description:
        Retrieves the full documents before deletion, appends them (serialized) to
        `backup_data["data"][collection_name]`, then deletes them.

    Args:
        collection_name (str): Collection to delete from.
        object_ids (list[ObjectId]): Document ids to back up and delete.
        backup_data (dict): Backup payload, mutated in place.

    Returns:
        int: Number of documents actually deleted.
    """
    collection_obj = await get_collection(collection_name)
    docs_to_delete = await collection_obj.find({"_id": {"$in": object_ids}}).to_list(None)

    backup_data["data"].setdefault(collection_name, []).extend(
        [serialize_mongo_doc(doc) for doc in docs_to_delete]
    )

    collection_obj = await get_collection(collection_name)
    result = await collection_obj.delete_many({"_id": {"$in": object_ids}})
    return result.deleted_count


def _validate_cleanup_key(key: str) -> dict[str, Any]:
    """Validate a cleanup confirmation key, raising if invalid or expired.

    Args:
        key (str): Confirmation key obtained via GET /db_cleanup.

    Returns:
        dict: The cached analysis data for this key.
    """
    cached_data = load_cleanup_pending(key)
    if cached_data is None:
        raise HTTPException(status_code=404, detail="Invalid or expired confirmation key")

    if utcnow() > datetime.fromisoformat(cached_data["expires_at"]):
        delete_cleanup_pending(key)
        raise HTTPException(
            status_code=410, detail="Confirmation key expired. Please request a new analysis."
        )
    return cached_data


# DONE: [BACKLOG] Route /maintenance/db_cleanup (DELETE) verified
@router.delete("/db_cleanup")
async def cleanup_execute(key: str):
    """
    Executes cleanup of orphaned records after confirmation.
    Saves deleted data to a timestamped JSON file.
    Process collections in dependency order (most central first) to prevent creating new orphans.

    Args:
        key: Confirmation key obtained via GET /db_cleanup
    """
    clean_expired_keys()

    cached_data = _validate_cleanup_key(key)

    # Prepare backup data
    backup_data: dict[str, Any] = {
        "timestamp": utcnow().isoformat(),
        "deleted_by_collection": {},
        "data": {},
    }
    deleted_count: dict[str, int] = {}

    # Process collections in dependency order (most central first)
    # This ensures that when we remove items from central collections,
    # we process potential orphans in dependent collections appropriately
    for collection_name in COLLECTION_DEPENDENCY_ORDER:
        object_ids = _collect_orphan_object_ids(collection_name, cached_data["orphans"])
        if not object_ids:
            continue

        deleted = await _backup_and_delete_documents(collection_name, object_ids, backup_data)
        deleted_count[collection_name] = deleted_count.get(collection_name, 0) + deleted
        backup_data["deleted_by_collection"][collection_name] = deleted_count[collection_name]

    backup_data["total_deleted"] = sum(deleted_count.values())

    # Save the JSON file with timestamp
    timestamp_str = utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = CLEANUP_BACKUP_DIR
    base_name = f"{timestamp_str}_cleanup"
    backup_file = write_json_zip(
        backup_data=backup_data, output_dir=output_dir, base_name=base_name
    )

    file_size_mb = round(backup_file.stat().st_size / (1024 * 1024), 2)

    # Delete the confirmation file
    delete_cleanup_pending(key)

    return {
        "message": f"Successfully deleted {backup_data['total_deleted']} orphan(s)",
        "backup_file": str(backup_file),
        "backup_file_size": f"{file_size_mb} MB",
        "deleted": deleted_count,
        "total_deleted": backup_data["total_deleted"],
        "timestamp": backup_data["timestamp"],
    }
