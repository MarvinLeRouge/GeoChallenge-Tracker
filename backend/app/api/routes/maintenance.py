# app/api/routes/maintenance.py

from __future__ import annotations

import json
import secrets
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal, cast
from zipfile import ZIP_DEFLATED, ZipFile

from bson import ObjectId, json_util
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi import (
    Path as ApiPath,
)
from fastapi.responses import FileResponse

from app.api.deps import CurrentUserId, require_admin
from app.api.dto.user_stats import UserStatsOut
from app.core.backup_config import BACKUP_ROOT_DIR, CLEANUP_BACKUP_DIR, FULL_BACKUP_DIR
from app.core.email import send_test_email
from app.core.middleware import read_upload_file_with_limit
from app.core.settings import get_settings
from app.core.utils import utcnow
from app.db.mongodb import get_collection, get_db
from app.services.found_caches_sync import extract_gc_codes, sync_found_caches
from app.services.gpx_import.referential_mapper import ReferentialMapper
from app.services.gpx_importer_service import import_gpx_payload
from app.services.targets_service import evaluate_all_for_user
from app.services.user_stats import get_user_stats

# Confirmation key validity duration (in minutes)
CONFIRMATION_KEY_TTL = 10

# Directory for persisting pending cleanup analyses awaiting confirmation
PENDING_CLEANUP_DIR = BACKUP_ROOT_DIR / "pending_cleanups"

# Directory for persisting pending destructive-restore requests awaiting confirmation
PENDING_RESTORE_DIR = BACKUP_ROOT_DIR / "pending_restores"


def _pending_key_path(directory: Path, key: str) -> Path:
    """Returns the path to the JSON file associated with a confirmation key."""
    return directory / f"{key}.json"


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


def save_restore_pending(key: str, filename: str, expires_at: datetime) -> None:
    """Persists a pending destructive-restore request into a JSON file."""
    PENDING_RESTORE_DIR.mkdir(parents=True, exist_ok=True)
    with open(_pending_key_path(PENDING_RESTORE_DIR, key), "w", encoding="utf-8") as f:
        json.dump({"filename": filename, "expires_at": expires_at.isoformat()}, f)


def load_restore_pending(key: str) -> dict | None:
    """Loads a pending restore request from the JSON file. Returns None if not found."""
    p = _pending_key_path(PENDING_RESTORE_DIR, key)
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def delete_restore_pending(key: str) -> None:
    """Deletes the JSON file of a pending restore request."""
    _pending_key_path(PENDING_RESTORE_DIR, key).unlink(missing_ok=True)


# Order matters for deletion: most central to most dependent (to prevent creating new orphans during cleanup)
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


# ============================================================================
# UTILITIES
# ============================================================================


def serialize_mongo_doc(doc):
    """Converts a Mongo document (containing ObjectId) to a JSON-serializable dict."""
    return json.loads(json_util.dumps(doc))


def clean_expired_keys(directory: Path = PENDING_CLEANUP_DIR) -> None:
    """Deletes confirmation files whose expiration date has passed."""
    if not directory.exists():
        return
    now = utcnow()
    for p in directory.glob("*.json"):
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            if datetime.fromisoformat(data["expires_at"]) < now:
                p.unlink(missing_ok=True)
        except Exception:
            p.unlink(missing_ok=True)


router = APIRouter(
    prefix="/maintenance", tags=["Maintenance"], dependencies=[Depends(require_admin)]
)


# DONE: [BACKLOG] Route /maintenance (GET) verified
@router.get("")
async def maintenance_get_1() -> dict:
    result = {
        "status": "ok",
        "route": "/maintenance",
        "method": "GET",
        "function": "maintenance_get_1",
    }

    return result


# DONE: [BACKLOG] Route /maintenance (POST) verified
@router.post("")
async def maintenance_post_1() -> dict:
    result = {
        "status": "ok",
        "route": "/maintenance",
        "method": "POST",
        "function": "maintenance_post_1",
    }

    return result


# ============================================================================
# ROUTES
# ============================================================================

# ============================================================================
# ORPHAN ANALYSIS
# ============================================================================


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


# DONE: [BACKLOG] Route /maintenance/db_cleanup/backups (GET) verified
@router.get("/db_cleanup/backups")
async def cleanup_list_backups():
    """Lists all available backup files."""
    backups = []

    for backup_file in sorted(CLEANUP_BACKUP_DIR.glob("*_cleanup.zip"), reverse=True):
        try:
            with ZipFile(backup_file, "r") as zf:
                # the internal JSON is named f"{base_name}.json"
                # if the name is unknown, take the first .json entry
                json_name = next((n for n in zf.namelist() if n.endswith(".json")), None)
                if json_name:
                    data = json.loads(zf.read(json_name).decode("utf-8"))
                    backups.append(
                        {
                            "filename": backup_file.name,
                            "timestamp": data.get("timestamp", "unknown"),
                            "total_deleted": data.get("total_deleted", 0),
                            "collections": list(data.get("deleted_by_collection", {}).keys()),
                            "size_kb": round(backup_file.stat().st_size / 1024, 2),
                        }
                    )
        except Exception as e:
            # On read error, report it but do not crash
            backups.append({"filename": backup_file.name, "error": str(e)})

    return {"backups": backups, "total_backups": len(backups)}


# DONE: [BACKLOG] Route /maintenance/backups/{filepath:path} (GET) verified
@router.get("/backups/{filepath:path}")
async def get_backup_file(filepath: str):
    """Downloads a backup file (db_cleanup, full_backup, etc.)."""
    requested_path = (BACKUP_ROOT_DIR / filepath).resolve()

    # Security: prevent any path traversal outside the root directory
    if not str(requested_path).startswith(str(BACKUP_ROOT_DIR)):
        raise HTTPException(status_code=400, detail="Invalid file path")

    if not requested_path.exists() or not requested_path.is_file():
        raise HTTPException(status_code=404, detail="Backup file not found")

    # Detect file type
    ext = requested_path.suffix.lower()
    media_type = {
        ".zip": "application/zip",
        ".json": "application/json",
        ".gz": "application/gzip",
    }.get(ext, "application/octet-stream")

    # Return the file with correct headers
    return FileResponse(
        path=str(requested_path),
        media_type=media_type,
        filename=requested_path.name,
    )


# DONE: [BACKLOG] Route /maintenance/db_full_backup (POST) verified
@router.post("/db_full_backup")
async def full_backup_create():
    """
    Creates a full backup of the entire database.
    Saves all collections to a timestamped JSON file.

    Warning: may be large on big databases.
    """
    db = get_db()
    backup_data = {"timestamp": utcnow().isoformat(), "database": db.name, "collections": {}}

    total_documents = 0

    # Retrieve the list of all collections
    collection_names = await db.list_collection_names()

    # For each collection
    for collection_name in collection_names:
        # Skip MongoDB system collections
        if collection_name.startswith("system."):
            continue

        # Retrieve all documents from the collection
        cursor = db[collection_name].find()
        docs = await cursor.to_list(length=None)

        if docs:
            # Serialize documents (handles ObjectId)
            backup_data["collections"][collection_name] = [serialize_mongo_doc(doc) for doc in docs]
            total_documents += len(docs)

    backup_data["total_collections"] = len(backup_data["collections"])
    backup_data["total_documents"] = total_documents

    # Create the backup file
    timestamp_str = utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = FULL_BACKUP_DIR
    base_name = f"{timestamp_str}_full_backup"
    backup_file = write_json_zip(
        backup_data=backup_data, output_dir=output_dir, base_name=base_name
    )

    file_size_mb = round(backup_file.stat().st_size / (1024 * 1024), 2)

    return {
        "message": "Full backup created successfully",
        "backup_file": str(backup_file),
        "total_collections": backup_data["total_collections"],
        "total_documents": total_documents,
        "size_mb": file_size_mb,
        "timestamp": backup_data["timestamp"],
    }


def _load_backup_payload(backup_file: Path) -> dict[str, Any]:
    """Load the JSON payload from a full-backup zip archive.

    Args:
        backup_file (Path): Path to the backup `.zip` file.

    Returns:
        dict: Parsed backup payload (`collections`, `timestamp`, ...).
    """
    with ZipFile(backup_file, "r") as zf:
        json_name = next((n for n in zf.namelist() if n.endswith(".json")), None)
        if not json_name:
            raise HTTPException(status_code=400, detail="No JSON found in backup archive")
        return json.loads(zf.read(json_name).decode("utf-8"))


def _resolve_destructive_confirmation(filename: str, key: str | None) -> dict[str, Any] | None:
    """Resolve a destructive restore's two-step confirmation dance.

    Description:
        On first call (no `key`), generates and persists a confirmation key, returning
        the response to send back to re-confirm. Once a valid, matching, non-expired
        key is supplied, consumes it and returns None (restore may proceed).

    Args:
        filename (str): Backup filename being restored.
        key (str | None): Confirmation key from a prior call, if any.

    Returns:
        dict | None: Confirmation response to return immediately, or None to proceed.
    """
    clean_expired_keys(PENDING_RESTORE_DIR)

    if key is None:
        confirmation_key = secrets.token_urlsafe(16)
        expires_at = utcnow() + timedelta(minutes=CONFIRMATION_KEY_TTL)
        save_restore_pending(confirmation_key, filename, expires_at)
        return {
            "confirmation_key": confirmation_key,
            "expires_at": expires_at.isoformat(),
            "message": (
                "This would drop all existing data before restoring. Re-submit this "
                "request with the confirmation key (?key=...) to proceed."
            ),
        }

    pending = load_restore_pending(key)
    if pending is None:
        raise HTTPException(status_code=404, detail="Invalid or expired confirmation key")
    if utcnow() > datetime.fromisoformat(pending["expires_at"]):
        delete_restore_pending(key)
        raise HTTPException(
            status_code=410, detail="Confirmation key expired. Please request a new one."
        )
    if pending["filename"] != filename:
        raise HTTPException(
            status_code=400, detail="Confirmation key does not match this backup file."
        )
    delete_restore_pending(key)
    return None


async def _restore_backup_collection(
    db: Any, collection_name: str, docs: list[dict[str, Any]], dry_run: bool, drop_existing: bool
) -> tuple[int | None, bool]:
    """Restore (or simulate restoring) one collection's documents from a backup.

    Description:
        Reconverts `{"$oid": ...}` placeholders back to `ObjectId`, optionally drops the
        existing collection first, then inserts the documents (or just counts them when
        `dry_run` is True).

    Args:
        db (Any): Database handle.
        collection_name (str): Target collection.
        docs (list[dict]): Documents to restore.
        dry_run (bool): Simulate only, don't write.
        drop_existing (bool): Drop the collection's existing data first.

    Returns:
        tuple[int | None, bool]: `(restored_count, was_dropped)`. `restored_count` is
            None when nothing was actually inserted (non-dry-run with no documents).
    """
    for doc in docs:
        if "_id" in doc and isinstance(doc["_id"], dict) and "$oid" in doc["_id"]:
            doc["_id"] = ObjectId(doc["_id"]["$oid"])

    if dry_run:
        return len(docs), False

    dropped = False
    if drop_existing:
        await db[collection_name].delete_many({})
        dropped = True

    if docs:
        result = await db[collection_name].insert_many(docs)
        return len(result.inserted_ids), dropped
    return None, dropped


# DONE: [BACKLOG] Route /maintenance/db_full_restore/{filename} (POST) verified
@router.post("/db_full_restore/{filename}")
async def full_backup_restore(
    filename: str,
    dry_run: bool = True,
    drop_existing: bool = False,
    key: str | None = Query(
        None,
        description="Confirmation key from a prior drop_existing=True call, required to actually run it.",
    ),
):
    """
    Restores a complete database from a backup.

    Args:
        filename: Name of the full backup file
        dry_run: If True, simulates the restore without inserting (default: True)
        drop_existing: If True, clears collections before restoring (default: False)
        key: Confirmation key obtained from a prior call with drop_existing=True and no key.

    WARNING: drop_existing=True deletes all existing data! Because of that, a destructive
    restore (dry_run=False and drop_existing=True) needs two calls: the first, without
    `key`, only validates the backup file and returns a short-lived confirmation_key
    instead of restoring anything; the actual restore only runs once that same key is
    passed back via `key=...`. Non-destructive calls (dry_run=True, or drop_existing=False)
    are unaffected and run immediately, as before.
    """
    # Security check
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    backup_file = FULL_BACKUP_DIR / filename

    if not backup_file.exists():
        raise HTTPException(status_code=404, detail="Backup file not found")

    destructive = not dry_run and drop_existing

    if destructive:
        confirmation_response = _resolve_destructive_confirmation(filename, key)
        if confirmation_response is not None:
            return confirmation_response

    backup_data = _load_backup_payload(backup_file)

    restored: dict[str, int] = {}
    dropped: list[str] = []
    db = get_db()

    for collection_name, docs in backup_data.get("collections", {}).items():
        restored_count, was_dropped = await _restore_backup_collection(
            db, collection_name, docs, dry_run, drop_existing
        )
        if was_dropped:
            dropped.append(collection_name)
        if restored_count is not None:
            restored[collection_name] = restored_count

    response = {
        "restored": restored,
        "total_restored": sum(restored.values()),
        "dry_run": dry_run,
        "backup_timestamp": backup_data.get("timestamp"),
        "message": "Simulation only - no data inserted"
        if dry_run
        else "Full backup restored successfully",
    }

    if dropped:
        response["dropped_collections"] = dropped

    return response


def _describe_cleanup_backup_file(backup_file: Path) -> dict[str, Any] | None:
    """Build the summary entry for one cleanup-backup zip file.

    Args:
        backup_file (Path): Path to the backup `.zip` file.

    Returns:
        dict | None: Summary entry, or None if the archive has no JSON metadata.
    """
    with ZipFile(backup_file, "r") as zf:
        # the internal JSON is named f"{base_name}.json"
        # if the name is unknown, take the first .json entry
        json_name = next((n for n in zf.namelist() if n.endswith(".json")), None)
        if not json_name:
            return None
        data = json.loads(zf.read(json_name).decode("utf-8"))
    return {
        "filename": backup_file.name,
        "timestamp": data.get("timestamp", "unknown"),
        "total_deleted": data.get("total_deleted", 0),
        "collections": list(data.get("deleted_by_collection", {}).keys()),
        "size_kb": round(backup_file.stat().st_size / 1024, 2),
        "type": "cleanup",
    }


def _list_cleanup_backup_entries() -> list[dict[str, Any]]:
    """List all cleanup-backup zip files, newest first.

    Returns:
        list[dict]: One summary entry per file (or an error entry if it couldn't be read).
    """
    entries: list[dict[str, Any]] = []
    for backup_file in sorted(CLEANUP_BACKUP_DIR.glob("*.zip"), reverse=True):
        try:
            entry = _describe_cleanup_backup_file(backup_file)
            if entry:
                entries.append(entry)
        except Exception as e:
            entries.append({"filename": backup_file.name, "error": str(e)})
    return entries


def _describe_full_backup_file(backup_file: Path) -> dict[str, Any]:
    """Build the summary entry for one full-backup zip file.

    Args:
        backup_file (Path): Path to the backup `.zip` file.

    Returns:
        dict: Summary entry, or an error entry if the archive has no JSON metadata.
    """
    with ZipFile(backup_file, "r") as zf:
        # the internal JSON is named f"{base_name}.json"
        # if the name is unknown, take the first .json entry
        json_name = next((n for n in zf.namelist() if n.endswith(".json")), None)
        if not json_name:
            # If no JSON file is found in the ZIP
            return {
                "filename": backup_file.name,
                "error": "No JSON metadata file found in archive",
            }
        data = json.loads(zf.read(json_name).decode("utf-8"))
    return {
        "filename": backup_file.name,
        "timestamp": data.get("timestamp", "unknown"),
        "total_collections": data.get("total_collections", 0),
        "total_documents": data.get("total_documents", 0),
        "size_mb": round(backup_file.stat().st_size / (1024 * 1024), 2),
        "type": "full",
    }


def _list_full_backup_entries() -> list[dict[str, Any]]:
    """List all full-backup zip files, newest first.

    Returns:
        list[dict]: One summary entry per file (or an error entry if it couldn't be read).
    """
    entries: list[dict[str, Any]] = []
    for backup_file in sorted(FULL_BACKUP_DIR.glob("*.zip"), reverse=True):
        try:
            entries.append(_describe_full_backup_file(backup_file))
        except Exception as e:
            entries.append({"filename": backup_file.name, "error": str(e)})
    return entries


# DONE: [BACKLOG] Route /maintenance/db_backups (GET) verified
@router.get("/db_backups")
async def list_all_backups():
    """Lists all backup files (cleanup + full)."""
    backups = {
        "cleanup_backups": _list_cleanup_backup_entries(),
        "full_backups": _list_full_backup_entries(),
    }

    return {
        "backups": backups,
        "total_cleanup_backups": len(backups["cleanup_backups"]),
        "total_full_backups": len(backups["full_backups"]),
    }


def write_json_zip(backup_data: dict, output_dir: str | Path, base_name: str) -> Path:
    """
    Writes a ZIP file containing a single JSON file directly from a Python object.

    Args:
        backup_data: Data to save (dict, list, etc.)
        output_dir: Destination directory.
        base_name: Base filename (without extension).

    Returns:
        Path: Full path to the created ZIP file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    zip_path = output_dir / f"{base_name}.zip"
    json_name_in_zip = f"{base_name}.json"

    # Convert data to JSON (in memory)
    payload = json.dumps(backup_data, ensure_ascii=False, indent=2)

    # Write the ZIP directly
    with ZipFile(zip_path, mode="w", compression=ZIP_DEFLATED) as zf:
        zf.writestr(json_name_in_zip, payload)

    return zip_path


# TODO: [BACKLOG] Route /maintenance/import-gpx (POST) to verify
@router.post(
    "/upload-gpx",
    summary="Import GPX with forced attribute update",
    description=(
        "Imports a GPX/ZIP file and forces attribute updates for all caches.\n\n"
        "**RESTRICTED TO ADMINISTRATORS**\n\n"
        "Works like the standard import but updates attributes even if they already exist.\n"
        "Supports the same formats as the standard import (cgeo, pocket_query, etc.).\n"
        "Returns an import summary and challenge-related statistics."
    ),
    responses={
        200: {"description": "GPX import successful with forced attribute update"},
        400: {"description": "Invalid GPX/ZIP file"},
        401: {"description": "Not authenticated"},
        403: {"description": "Access denied (admin required)"},
    },
)
async def upload_gpx(
    request: Request,
    user_id: CurrentUserId,
    file: Annotated[
        UploadFile, File(..., description="GPX file to import (or ZIP containing a GPX).")
    ],
    import_mode: Literal["all", "found"] = Query(
        "all",
        description="Import mode: 'all' (all caches) or 'found' (my finds)",
    ),
    source_type: Literal["auto", "cgeo", "pocket_query"] = Query(
        "auto",
        description="GPX source type: 'auto' (automatic detection), 'cgeo', 'pocket_query'",
    ),
) -> dict[str, Any]:
    """Import GPX with forced attribute update.

    Description:
        Imports a GPX/ZIP file and forces attribute updates for all caches.
        This feature is reserved for administrators.

    Args:
        file: GPX or ZIP file to process.
        import_mode: Import mode ('all' for all caches, 'found' for finds only).
        source_type: GPX source type ('auto', 'cgeo', 'pocket_query').

    Returns:
        dict: Import summary and challenge-related statistics.

    Raises:
        HTTPException 400: If the file is invalid.
        HTTPException 403: If the user is not an admin.
    """
    result: dict[str, Any] = {"summary": None, "challenge_stats": None}

    settings = get_settings()
    payload = await read_upload_file_with_limit(file, settings.max_upload_bytes)

    try:
        result["summary"] = await import_gpx_payload(
            payload=payload,
            filename=file.filename or "upload.gpx",
            import_mode=import_mode,
            user_id=None,  # For forced import, a specific user could be provided or left as None
            request=request,
            source_type=source_type,
            force_update_attributes=True,  # Always true for this route
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid GPX/ZIP file: {e}") from e

    return result


@router.delete(
    "/expired-verifications",
    summary="Clean up expired verification codes",
    description=(
        "Removes the `verification_code` and `verification_expires_at` fields "
        "from unverified accounts whose code has expired.\n\n"
        "**RESTRICTED TO ADMINISTRATORS**\n\n"
        "Does not delete accounts — only removes stale verification fields."
    ),
    responses={
        200: {"description": "Cleanup completed"},
        401: {"description": "Not authenticated"},
        403: {"description": "Access denied (admin required)"},
    },
)
async def cleanup_expired_verifications(
    _: Annotated[Any, Depends(require_admin)],
) -> dict[str, Any]:
    """Cleans up expired verification codes from unverified accounts.

    Description:
        Finds all unverified users whose `verification_expires_at` is before
        the current time, and removes the `verification_code` and
        `verification_expires_at` fields (without deleting the account).

    Args:
        _: Admin authorization dependency (not used directly).

    Returns:
        dict: Number of updated documents.
    """
    coll_users = await get_collection("users")
    result = await coll_users.update_many(
        {
            "is_verified": False,
            "verification_expires_at": {"$lt": utcnow()},
        },
        {
            "$unset": {"verification_code": "", "verification_expires_at": ""},
        },
    )
    return {"cleaned": result.modified_count}


@router.get(
    "/caches-geo-anomalies",
    summary="Count caches with missing country_id or state_id",
    description="Reports how many caches have null country_id and/or null state_id.",
    dependencies=[Depends(require_admin)],
)
async def caches_geo_anomalies(_: Annotated[bool, Depends(require_admin)]) -> dict:
    """Count caches with incomplete geographic data.

    Returns:
        dict: Counts for null country_id, null state_id, and both null.
    """
    coll = await get_collection("caches")

    total = await coll.count_documents({})
    null_country = await coll.count_documents({"country_id": None})
    null_state = await coll.count_documents({"state_id": None})
    null_both = await coll.count_documents({"country_id": None, "state_id": None})
    null_country_only = await coll.count_documents({"country_id": None, "state_id": {"$ne": None}})
    null_state_only = await coll.count_documents({"country_id": {"$ne": None}, "state_id": None})

    # Sample non-AL affected caches to understand the pattern
    sample = []
    async for doc in coll.find(
        {"country_id": None, "GC": {"$not": {"$regex": "^AL"}}},
        {"GC": 1, "title": 1, "lat": 1, "lon": 1, "location_more": 1},
    ).limit(20):
        sample.append(
            {
                "GC": doc.get("GC"),
                "title": doc.get("title"),
                "lat": doc.get("lat"),
                "lon": doc.get("lon"),
                "location_more": doc.get("location_more"),
            }
        )

    # Check how many affected caches have coordinates
    with_coords = await coll.count_documents({"country_id": None, "lat": {"$ne": None}})

    # Verify the AL-prefix hypothesis
    null_and_al = await coll.count_documents({"country_id": None, "GC": {"$regex": "^AL"}})
    null_and_not_al = await coll.count_documents(
        {"country_id": None, "GC": {"$not": {"$regex": "^AL"}}}
    )

    return {
        "total_caches": total,
        "null_country_id": null_country,
        "null_state_id": null_state,
        "null_both": null_both,
        "null_country_only": null_country_only,
        "null_state_only": null_state_only,
        "null_both_with_coords": with_coords,
        "al_prefix_hypothesis": {
            "null_and_gc_starts_with_AL": null_and_al,
            "null_and_gc_does_not_start_with_AL": null_and_not_al,
            "hypothesis_confirmed": null_and_not_al == 0,
        },
        "sample": sample,
    }


@router.get(
    "/snapshot",
    summary="System snapshot for a user",
    description="Returns global counts (caches, challenges) and user-specific stats (found caches, user_challenges by status).",
    dependencies=[Depends(require_admin)],
)
async def snapshot(
    _: Annotated[bool, Depends(require_admin)],
    user_id: str = Query(..., description="User ObjectId as string"),
) -> dict:
    """Snapshot of system state for before/after comparison.

    Args:
        user_id: User ObjectId string.

    Returns:
        dict: Global and user-scoped counts.
    """
    from bson import ObjectId

    uid = ObjectId(user_id)

    coll_caches = await get_collection("caches")
    coll_challenges = await get_collection("challenges")
    coll_found = await get_collection("found_caches")
    coll_ucs = await get_collection("user_challenges")

    total_caches = await coll_caches.count_documents({})
    total_challenges = await coll_challenges.count_documents({})
    total_found = await coll_found.count_documents({"user_id": uid})
    total_ucs = await coll_ucs.count_documents({"user_id": uid})

    # user_challenges grouped by computed_status
    pipeline: list[dict[str, Any]] = [
        {"$match": {"user_id": uid}},
        {"$group": {"_id": "$computed_status", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    uc_by_status: dict[str, int] = {}
    async for doc in coll_ucs.aggregate(pipeline):
        key = doc["_id"] if doc["_id"] is not None else "null"
        uc_by_status[key] = doc["count"]

    return {
        "global": {
            "caches": total_caches,
            "challenges": total_challenges,
        },
        "user": {
            "found_caches": total_found,
            "user_challenges": total_ucs,
            "user_challenges_by_computed_status": uc_by_status,
        },
    }


@router.get(
    "/referentials-duplicates",
    dependencies=[Depends(require_admin)],
    summary="Detect duplicate countries and states (admin)",
    description=(
        "Loads all countries and states, computes their normalized form "
        "(NFKD + lowercase + alphanumeric), and returns groups where multiple "
        "documents share the same normalized key. Useful to audit the referential "
        "after a backfill or import."
    ),
)
async def referentials_duplicates(_: Request) -> dict[str, Any]:
    """Detect duplicate country/state entries (admin).

    Returns:
        dict: Lists of duplicate groups for countries and states.
    """
    db = get_db()

    # --- Countries ---
    country_groups: dict[str, list[dict[str, Any]]] = {}
    async for doc in db.countries.find({}, {"_id": 1, "name": 1}):
        key = ReferentialMapper.normalize_name(doc.get("name"))
        entry = {"id": str(doc["_id"]), "name": doc.get("name")}
        country_groups.setdefault(key, []).append(entry)

    duplicate_countries = [
        {"normalized": key, "entries": entries}
        for key, entries in country_groups.items()
        if len(entries) > 1
    ]

    # --- States ---
    state_groups: dict[str, list[dict[str, Any]]] = {}
    async for doc in db.states.find({}, {"_id": 1, "name": 1, "country_id": 1}):
        # Key includes country_id to only flag duplicates within the same country
        key = f"{doc.get('country_id')}::{ReferentialMapper.normalize_name(doc.get('name'))}"
        entry = {
            "id": str(doc["_id"]),
            "name": doc.get("name"),
            "country_id": str(doc.get("country_id")),
        }
        state_groups.setdefault(key, []).append(entry)

    duplicate_states = [
        {"normalized": key, "entries": entries}
        for key, entries in state_groups.items()
        if len(entries) > 1
    ]

    return {
        "duplicate_countries": duplicate_countries,
        "nb_duplicate_country_groups": len(duplicate_countries),
        "duplicate_states": duplicate_states,
        "nb_duplicate_state_groups": len(duplicate_states),
    }


# ---------------------------
# Targets
# ---------------------------


@router.post(
    "/users/{user_id}/targets/evaluate-all",
    status_code=status.HTTP_200_OK,
    summary="Force re-evaluate targets for a given user (admin)",
    description=(
        "Wipes and recomputes targets for **all** accepted UserChallenges of the given user.\n\n"
        "Use this when a user reports stale or missing targets."
    ),
)
async def maintenance_evaluate_all_targets(
    user_id: str = ApiPath(..., description="User identifier."),
):
    """Force re-evaluate targets for a given user.

    Args:
        user_id (str): Target user identifier.

    Returns:
        dict: {ok, evaluated, total_inserted, total_updated, last_targets_evaluated_at}.
    """
    try:
        uid = ObjectId(user_id)
    except Exception as err:
        raise HTTPException(status_code=422, detail="Invalid user_id.") from err

    return await evaluate_all_for_user(user_id=uid, force=True)


@router.post(
    "/users/{user_id}/found-caches/sync",
    status_code=status.HTTP_200_OK,
    summary="Sync found caches from a text file (admin)",
    description=(
        "Uploads a plain-text file and extracts every GC code it contains.\n\n"
        "The extracted list is treated as the **complete and authoritative** found-cache list "
        "for the given user:\n"
        "- Found caches **not in the list** are deleted.\n"
        "- GC codes **not yet in found caches** are inserted.\n"
        "- GC codes not matched to any known cache are reported as `unknown_gc_codes`."
    ),
)
async def maintenance_sync_found_caches(
    user_id: Annotated[str, ApiPath(..., description="Target user identifier.")],
    file: Annotated[UploadFile, File(..., description="Plain-text file containing GC codes.")],
):
    """Sync found caches for a given user from a canonical text file.

    Args:
        user_id (str): Target user identifier.
        file (UploadFile): Text file whose content will be scanned for GC codes.

    Returns:
        dict: {nb_provided, nb_deleted, nb_added, nb_unknown_gc, unknown_gc_codes}.
    """
    try:
        uid = ObjectId(user_id)
    except Exception as err:
        raise HTTPException(status_code=422, detail="Invalid user_id.") from err

    settings = get_settings()
    content = await read_upload_file_with_limit(file, settings.max_upload_bytes)

    try:
        text = content.decode("utf-8", errors="replace")
    except Exception as err:
        raise HTTPException(status_code=400, detail="Unable to decode file content.") from err

    gc_codes = extract_gc_codes(text)
    db = get_db()
    return await sync_found_caches(db=db, user_id=uid, gc_codes=gc_codes)


@router.get(
    "/users/{user_id}/stats",
    response_model=UserStatsOut,
    summary="Get statistics for a given user (admin)",
    description="Returns summary statistics for the specified user.",
)
async def maintenance_get_user_stats(
    user_id: str = ApiPath(..., description="Target user identifier."),
) -> UserStatsOut:
    """Get statistics for a given user.

    Args:
        user_id (str): Target user identifier.

    Returns:
        UserStatsOut: Computed statistics.
    """
    try:
        uid = ObjectId(user_id)
    except Exception as err:
        raise HTTPException(status_code=422, detail="Invalid user_id.") from err

    try:
        return await get_user_stats(user_id=uid, target_user_id=uid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post(
    "/test-email",
    summary="Send a test email",
    description=(
        "Sends a test email to the specified address.\n\n"
        "The email includes the current date/time and basic database statistics "
        "(users, caches, challenges) to avoid spam filters."
    ),
)
async def test_email(
    to_email: Annotated[
        str | None, Query(description="Recipient email address. Defaults to ADMIN_TEST_EMAIL.")
    ] = None,
):
    """Sends a test email with basic app statistics.

    Args:
        to_email (str): Recipient email address.

    Returns:
        dict: Confirmation message and stats included in the email.
    """
    settings = get_settings()
    recipient = to_email or settings.admin_test_email

    coll_users = await get_collection("users")
    coll_caches = await get_collection("caches")
    coll_challenges = await get_collection("challenges")

    user_count = await coll_users.count_documents({})
    cache_count = await coll_caches.count_documents({})
    challenge_count = await coll_challenges.count_documents({})

    await send_test_email(
        to_email=recipient,
        user_count=user_count,
        cache_count=cache_count,
        challenge_count=challenge_count,
    )

    return {
        "message": f"Test email sent to {recipient}",
        "stats": {
            "users": user_count,
            "caches": cache_count,
            "challenges": challenge_count,
        },
    }
