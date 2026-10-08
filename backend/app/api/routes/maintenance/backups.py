# app/api/routes/maintenance/backups.py
# Backup listing and download routes (GET /maintenance/db_cleanup/backups,
# GET /maintenance/backups/{filepath}, GET /maintenance/db_backups).

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from fastapi import HTTPException
from fastapi.responses import FileResponse

from app.core.backup_config import BACKUP_ROOT_DIR, CLEANUP_BACKUP_DIR, FULL_BACKUP_DIR

from . import router


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
