#!/usr/bin/env python
# backend/scripts/rename_fr_geojson_files.py
# One-shot script: renames the `geojson_file` field on France's `administrative_zones`
# documents from the old `regions.geojson`/`departements.geojson` names to the
# generic `adm1.geojson`/`adm2.geojson` convention.
# Safety: copies the `administrative_zones` collection to a timestamped backup
# collection before writing anything.
# Idempotent: only matches documents still holding an old `geojson_file` value.
#
# Prerequisite: the physical files under backend/data/admin/FR/ must already be
# renamed (regions.geojson -> adm1.geojson, departements.geojson -> adm2.geojson)
# on this environment before running this script, otherwise /geo/FR/adm{1,2}.geojson
# will 404 until the rename is done.
#
# Usage (from backend/):
#   python scripts/rename_fr_geojson_files.py [--dry-run]

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.utils import now  # noqa: E402
from app.db.mongodb import get_client, get_collection, get_db  # noqa: E402

RENAMES = {
    "FR/regions.geojson": "FR/adm1.geojson",
    "FR/departements.geojson": "FR/adm2.geojson",
}


async def backup_administrative_zones_collection() -> str:
    """Copies the current `administrative_zones` collection into a timestamped backup.

    Returns:
        str: Name of the backup collection created.
    """
    db = get_db()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_name = f"administrative_zones_backup_{timestamp}"
    docs = await db.administrative_zones.find({}).to_list(length=None)
    if docs:
        await db[backup_name].insert_many(docs)
    print(f"[BACKUP] {len(docs)} document(s) copied to '{backup_name}'")
    return backup_name


async def main(dry_run: bool) -> None:
    """Renames `geojson_file` values for France's administrative zones.

    Args:
        dry_run (bool): If True, prints planned changes without writing.
    """
    if not dry_run:
        await backup_administrative_zones_collection()
    else:
        print("[DRY-RUN] Skipping backup (no write will be performed)")

    col = await get_collection("administrative_zones")
    updated = 0
    for old_value, new_value in RENAMES.items():
        matching = await col.count_documents({"geojson_file": old_value})
        if matching == 0:
            print(f"[SKIP] No document with geojson_file='{old_value}'")
            continue

        action = "Would update" if dry_run else "Updated"
        if not dry_run:
            await col.update_many(
                {"geojson_file": old_value},
                {"$set": {"geojson_file": new_value, "updated_at": now()}},
            )
        print(
            f"[{'DRY-RUN' if dry_run else 'DONE'}] {action} {matching} doc(s): '{old_value}' -> '{new_value}'"
        )
        updated += matching

    print(
        f"\n[{'DRY-RUN' if dry_run else 'DONE'}] Total: {updated} document(s) {'would be ' if dry_run else ''}renamed"
    )

    if not dry_run:
        client = get_client()
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes without writing anything (no backup, no writes).",
    )
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
