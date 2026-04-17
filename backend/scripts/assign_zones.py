#!/usr/bin/env python
# backend/scripts/assign_zones.py
# One-shot script: assigns administrative zones to all existing caches that have
# lat/lon coordinates but no `zones` field yet.
# Idempotent: skips caches that already have zones assigned.
# Uses Shapely STRtree with nearest-zone fallback (see zone_utils.py).
#
# Usage (from backend/):
#   python scripts/assign_zones.py [--country FR] [--force]
#
# Options:
#   --country CODE  Only process caches for this country (default: FR)
#   --force         Re-assign zones even if already set

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow imports from app/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.settings import get_settings  # noqa: E402
from app.db.mongodb import get_client, get_collection  # noqa: E402
from app.services.zones.zone_utils import build_spatial_index, resolve_zones_for_point  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
BATCH_SIZE = 500


async def load_zone_index(country_code: str, level: int, data_dir: Path):
    """Loads zone documents from DB and builds the spatial index for a given level.

    Args:
        country_code (str): ISO country code, e.g. "FR".
        level (int): Administrative level (1 or 2).
        data_dir (Path): Root directory for GeoJSON files.

    Returns:
        SpatialIndex: Populated spatial index.
    """

    collection = await get_collection("administrative_zones")
    zone_docs = await collection.find({"country_code": country_code, "level": level}).to_list(
        length=None
    )

    if not zone_docs:
        print(f"[ERROR] No level-{level} zones found for {country_code}.", file=sys.stderr)
        print("  → Run: python scripts/seed_zones.py", file=sys.stderr)
        sys.exit(1)

    # Use geojson_file from the first zone document (all zones of the same level
    # reference the same FeatureCollection file)
    geojson_file = zone_docs[0]["geojson_file"]
    geojson_path = data_dir / geojson_file

    if not geojson_path.exists():
        print(f"[ERROR] GeoJSON file not found: {geojson_path}", file=sys.stderr)
        print("  → Run: python scripts/download_geo_data.py", file=sys.stderr)
        sys.exit(1)

    index = build_spatial_index(geojson_path, zone_docs)
    print(f"[IDX]  level {level} ({country_code}): {len(index.shapes)} zones indexed")
    return index


_COUNTRY_NAMES: dict[str, str] = {
    "FR": "France",
}


async def _resolve_country_id(country_code: str):
    """Resolves the MongoDB ObjectId for a country by code.

    Args:
        country_code (str): ISO country code, e.g. "FR".

    Returns:
        ObjectId: The country's _id, or None if not found.
    """
    name = _COUNTRY_NAMES.get(country_code)
    if not name:
        return None
    col = await get_collection("countries")
    doc = await col.find_one({"name": name}, {"_id": 1})
    return doc["_id"] if doc else None


async def main(country_code: str = "FR", force: bool = False) -> None:
    """Assigns zones to all caches missing them (or all caches if --force).

    Args:
        country_code (str): ISO country code to process.
        force (bool): If True, re-assigns even already-zoned caches.
    """
    settings = get_settings()
    data_dir = BACKEND_DIR / settings.geo_data_dir

    print(f"Loading spatial indexes for {country_code}...")
    level1_index = await load_zone_index(country_code, 1, data_dir)
    level2_index = await load_zone_index(country_code, 2, data_dir)

    caches_col = await get_collection("caches")

    # Restrict to caches whose country matches, to avoid assigning French zones
    # to border caches from neighbouring countries (nearest-polygon fallback issue).
    country_id = await _resolve_country_id(country_code)
    if country_id is None:
        print(f"[WARN] Country '{country_code}' not found in DB — processing all caches.")
        country_filter: dict = {}
    else:
        country_filter = {"country_id": country_id}

    # Build query: caches with coordinates and missing zones (or all if --force)
    query: dict = {"lat": {"$ne": None}, "lon": {"$ne": None}, **country_filter}
    if not force:
        query["zones"] = {"$exists": False}

    total = await caches_col.count_documents(query)
    print(f"\nCaches to process: {total} ({'forced re-assign' if force else 'unassigned only'})")

    if total == 0:
        print("Nothing to do.")
        client = get_client()
        client.close()
        return

    processed = assigned = skipped = 0
    batch: list = []

    async for cache in caches_col.find(query, {"_id": 1, "lat": 1, "lon": 1}):
        lat = cache.get("lat")
        lon = cache.get("lon")

        if lat is None or lon is None:
            skipped += 1
            continue

        zones = resolve_zones_for_point(lat, lon, country_code, level1_index, level2_index)
        batch.append({"_id": cache["_id"], "zones": zones})
        assigned += 1

        if len(batch) >= BATCH_SIZE:
            await _flush_batch(caches_col, batch)
            processed += len(batch)
            print(f"  [{processed}/{total}] flushed batch of {len(batch)}")
            batch = []

    # Flush remaining
    if batch:
        await _flush_batch(caches_col, batch)
        processed += len(batch)

    print(f"\nDone. {assigned} caches assigned, {skipped} skipped (no coordinates).")

    get_client().close()


async def _flush_batch(collection, batch: list) -> None:
    """Bulk-updates zone assignments for a batch of caches.

    Args:
        collection: Motor collection.
        batch (list): List of dicts with `_id` and `zones`.
    """
    from pymongo import UpdateOne

    ops = [UpdateOne({"_id": doc["_id"]}, {"$set": {"zones": doc["zones"]}}) for doc in batch]
    await collection.bulk_write(ops, ordered=False)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Assign administrative zones to caches.")
    parser.add_argument("--country", default="FR", help="Country code (default: FR)")
    parser.add_argument("--force", action="store_true", help="Re-assign already-zoned caches")
    args = parser.parse_args()

    asyncio.run(main(country_code=args.country, force=args.force))
