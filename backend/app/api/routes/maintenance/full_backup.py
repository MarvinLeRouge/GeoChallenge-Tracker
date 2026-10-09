# app/api/routes/maintenance/full_backup.py
# Full database backup and restore routes (POST /maintenance/db_full_backup,
# POST /maintenance/db_full_restore/{filename}).

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from bson import ObjectId
from fastapi import HTTPException, Query

from app.core.backup_config import FULL_BACKUP_DIR
from app.core.utils import utcnow
from app.db.mongodb import get_db

from ._router import router
from ._shared import (
    CONFIRMATION_KEY_TTL,
    PENDING_RESTORE_DIR,
    _pending_key_path,
    clean_expired_keys,
    serialize_mongo_doc,
    write_json_zip,
)


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


async def _restore_all_backup_collections(
    db: Any, backup_data: dict[str, Any], dry_run: bool, drop_existing: bool
) -> tuple[dict[str, int], list[str]]:
    """Restore every collection in a backup payload, collecting counts and drops.

    Args:
        db (Any): Database handle.
        backup_data (dict): Parsed backup payload (`{"collections": {...}}`).
        dry_run (bool): Simulate only, don't write.
        drop_existing (bool): Drop each collection's existing data first.

    Returns:
        tuple[dict[str, int], list[str]]: (restored counts per collection, dropped collection names).
    """
    restored: dict[str, int] = {}
    dropped: list[str] = []

    for collection_name, docs in backup_data.get("collections", {}).items():
        restored_count, was_dropped = await _restore_backup_collection(
            db, collection_name, docs, dry_run, drop_existing
        )
        if was_dropped:
            dropped.append(collection_name)
        if restored_count is not None:
            restored[collection_name] = restored_count

    return restored, dropped


def _build_restore_response(
    restored: dict[str, int], dropped: list[str], dry_run: bool, backup_data: dict[str, Any]
) -> dict[str, Any]:
    """Assemble the JSON response for a full backup restore.

    Args:
        restored (dict): Restored counts per collection.
        dropped (list): Dropped collection names.
        dry_run (bool): Whether the restore was a simulation.
        backup_data (dict): Parsed backup payload (for its timestamp).

    Returns:
        dict: Response payload.
    """
    response: dict[str, Any] = {
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
    db = get_db()

    restored, dropped = await _restore_all_backup_collections(
        db, backup_data, dry_run, drop_existing
    )

    return _build_restore_response(restored, dropped, dry_run, backup_data)
