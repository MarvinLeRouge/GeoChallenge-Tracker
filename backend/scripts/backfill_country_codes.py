#!/usr/bin/env python
# backend/scripts/backfill_country_codes.py
# One-shot script: backfills `code` (ISO 3166-1 alpha-2) and `name_fr` on the
# `countries` collection, from data/seeds/countries.json (249 ISO territories).
# Safety: copies the `countries` collection to a timestamped backup collection
# before writing anything.
# Idempotent: existing countries are matched by normalized English name (same
# normalization as app/services/gpx_import/referential_mapper.py) and updated
# in place; unmatched ISO entries are inserted as new documents.
#
# Usage (from backend/):
#   python scripts/backfill_country_codes.py [--dry-run]

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow imports from app/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.utils import now  # noqa: E402
from app.db.mongodb import get_collection, get_db  # noqa: E402
from app.services.gpx_import.referential_mapper import ReferentialMapper  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
SEED_FILE = BACKEND_DIR / "data" / "seeds" / "countries.json"

# Known naming variants between the Geocaching.com country name stored in
# `countries.name` and the ISO 3166-1 English short name used in the seed
# data. Used only to resolve matching; `name` itself is left untouched.
NAME_ALIASES = {
    "United Kingdom": "United Kingdom of Great Britain and Northern Ireland",
    "United States": "United States of America",
    "Tanzania": "Tanzania, United Republic of",
    "Vatican City State": "Holy See",
}


def load_seed(seed_file: Path) -> list[dict]:
    """Loads the ISO country seed data.

    Args:
        seed_file (Path): Path to data/seeds/countries.json.

    Returns:
        list[dict]: Entries shaped {code, name, name_fr}.
    """
    with seed_file.open(encoding="utf-8") as f:
        return json.load(f)


async def backup_countries_collection() -> str:
    """Copies the current `countries` collection into a timestamped backup collection.

    Returns:
        str: Name of the backup collection created.
    """
    db = get_db()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_name = f"countries_backup_{timestamp}"
    docs = await db.countries.find({}).to_list(length=None)
    if docs:
        await db[backup_name].insert_many(docs)
    print(f"[BACKUP] {len(docs)} document(s) copied to '{backup_name}'")
    return backup_name


def _build_name_alias_lookup(existing_docs: list[dict]) -> dict[str, dict]:
    """Build a normalized-name -> doc lookup, including declared aliases.

    Args:
        existing_docs: Existing `countries` documents (projected `_id`, `name`, `created_at`).

    Returns:
        dict: `{normalized_name: doc}`, including alias name entries.
    """
    existing_by_norm_name = {
        ReferentialMapper.normalize_name(doc["name"]): doc for doc in existing_docs
    }
    for db_name, iso_name in NAME_ALIASES.items():
        existing = existing_by_norm_name.get(ReferentialMapper.normalize_name(db_name))
        if existing:
            existing_by_norm_name[ReferentialMapper.normalize_name(iso_name)] = existing
    return existing_by_norm_name


async def _update_existing_country(col, existing: dict, entry: dict, dry_run: bool) -> None:
    """Update an existing country doc with the seed's code/name_fr, unless dry-running.

    Args:
        col: `countries` collection.
        existing: The matched existing document.
        entry: Seed entry (`code`, `name_fr`).
        dry_run: If True, skip the write.
    """
    if dry_run:
        return
    update_fields = {
        "code": entry["code"],
        "name_fr": entry["name_fr"],
        "updated_at": now(),
    }
    if existing.get("created_at") is None:
        update_fields["created_at"] = now()
    await col.update_one({"_id": existing["_id"]}, {"$set": update_fields})


async def _insert_new_country(col, entry: dict, dry_run: bool) -> None:
    """Insert a new country doc from the seed entry, unless dry-running.

    Args:
        col: `countries` collection.
        entry: Seed entry (`name`, `name_fr`, `code`).
        dry_run: If True, skip the write.
    """
    if dry_run:
        return
    creation_time = now()
    await col.insert_one(
        {
            "name": entry["name"],
            "name_fr": entry["name_fr"],
            "code": entry["code"],
            "created_at": creation_time,
            "updated_at": creation_time,
        }
    )


async def main(dry_run: bool) -> None:
    """Backfills ISO code and French name on the `countries` collection.

    Args:
        dry_run (bool): If True, prints planned changes without writing.
    """
    seed = load_seed(SEED_FILE)
    print(f"[SEED] {len(seed)} ISO country entries loaded from {SEED_FILE}")

    if not dry_run:
        await backup_countries_collection()
    else:
        print("[DRY-RUN] Skipping backup (no write will be performed)")

    col = await get_collection("countries")
    existing_docs = await col.find({}, {"_id": 1, "name": 1, "created_at": 1}).to_list(length=None)
    existing_by_norm_name = _build_name_alias_lookup(existing_docs)

    matched = 0
    inserted = 0
    for entry in seed:
        norm_name = ReferentialMapper.normalize_name(entry["name"])
        existing = existing_by_norm_name.get(norm_name)

        if existing:
            await _update_existing_country(col, existing, entry, dry_run)
            matched += 1
        else:
            await _insert_new_country(col, entry, dry_run)
            inserted += 1

    action = "Would update" if dry_run else "Updated"
    insert_action = "Would insert" if dry_run else "Inserted"
    print(f"[{'DRY-RUN' if dry_run else 'DONE'}] {action} {matched} existing countries")
    print(f"[{'DRY-RUN' if dry_run else 'DONE'}] {insert_action} {inserted} new countries")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes without writing anything (no backup, no writes).",
    )
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
