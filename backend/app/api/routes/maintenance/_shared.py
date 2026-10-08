# app/api/routes/maintenance/_shared.py
# Shared utilities for the maintenance route package: confirmation-key
# persistence, document serialization, and backup zip writing.

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from bson import json_util

from app.core.backup_config import BACKUP_ROOT_DIR
from app.core.utils import utcnow

CONFIRMATION_KEY_TTL = 10

PENDING_CLEANUP_DIR = BACKUP_ROOT_DIR / "pending_cleanups"

PENDING_RESTORE_DIR = BACKUP_ROOT_DIR / "pending_restores"


def _pending_key_path(directory: Path, key: str) -> Path:
    """Returns the path to the JSON file associated with a confirmation key."""
    return directory / f"{key}.json"


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
