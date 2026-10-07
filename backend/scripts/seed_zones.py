#!/usr/bin/env python
# backend/scripts/seed_zones.py
# Parses downloaded GeoJSON FeatureCollections and upserts administrative zones
# into the `administrative_zones` MongoDB collection.
# Idempotent: existing zones (matched by `code`) are updated in place.
#
# Usage (from backend/):
#   python scripts/seed_zones.py

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import yaml
from shapely.geometry import shape

# Allow imports from app/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.settings import get_settings  # noqa: E402
from app.db.mongodb import get_client, get_collection  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
CONFIG_FILE = BACKEND_DIR / "config" / "geo_sources.yml"


def load_sources(config_file: Path) -> list[dict]:
    """Loads GeoJSON source definitions from the YAML config.

    Args:
        config_file (Path): Path to geo_sources.yml.

    Returns:
        list[dict]: Source definitions ordered by level (level 1 first).
    """
    with config_file.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)
    sources = config.get("sources", [])
    return sorted(sources, key=lambda s: s["level"])


def build_zone_code(country: str, feature_code: str) -> str:
    """Builds the canonical zone code from country and feature code.

    Args:
        country (str): ISO country code, e.g. "FR".
        feature_code (str): Feature code from GeoJSON properties, e.g. "38".

    Returns:
        str: Zone code, e.g. "FR-38".
    """
    return f"{country}-{feature_code}"


def find_parent_code(centroid, parent_shapes: list, parent_zones: list[dict]) -> str | None:
    """Finds the parent zone code by testing centroid containment.

    Description:
        Tests whether the centroid of a child zone is contained in each parent
        polygon. Falls back to the nearest parent if no exact match is found
        (handles boundary approximation issues).

    Args:
        centroid: Shapely Point representing the child zone centroid.
        parent_shapes (list): Shapely geometries of all parent zones.
        parent_zones (list[dict]): Parent zone documents (must include 'code').

    Returns:
        str | None: Code of the matched parent zone, or None if no parent found.
    """
    # Pass 1: exact containment
    for geom, zone in zip(parent_shapes, parent_zones):
        if geom.contains(centroid):
            return zone["code"]

    # Pass 2: nearest parent (handles coastal/border approximations)
    if parent_shapes:
        min_dist = float("inf")
        nearest_code = None
        for geom, zone in zip(parent_shapes, parent_zones):
            dist = geom.distance(centroid)
            if dist < min_dist:
                min_dist = dist
                nearest_code = zone["code"]
        return nearest_code

    return None


async def seed_level(
    source: dict,
    data_dir: Path,
    parent_shapes: list,
    parent_zones: list[dict],
) -> list[dict]:
    """Seeds one administrative level from its FeatureCollection.

    Description:
        Loads the GeoJSON file, iterates features, builds zone documents
        with bbox and parent_code, and upserts them into `administrative_zones`.

    Args:
        source (dict): Source definition from geo_sources.yml.
        data_dir (Path): Root directory for GeoJSON files.
        parent_shapes (list): Shapely geometries of parent zones (empty for level 1).
        parent_zones (list[dict]): Parent zone documents (empty for level 1).

    Returns:
        list[dict]: Seeded zone documents (used as parent_zones for the next level).
    """
    dest_rel = source["dest"]
    country = source["country"]
    level = source["level"]
    geojson_path = data_dir / dest_rel

    if not geojson_path.exists():
        print(f"[ERROR] GeoJSON file not found: {geojson_path}", file=sys.stderr)
        print("  → Run: python scripts/download_geo_data.py", file=sys.stderr)
        sys.exit(1)

    with geojson_path.open(encoding="utf-8") as f:
        feature_collection = json.load(f)

    features = feature_collection.get("features", [])
    collection = await get_collection("administrative_zones")

    seeded_zones: list[dict] = []
    inserted = updated = 0

    for feature in features:
        props = feature.get("properties", {})
        feature_code = str(props.get("code", ""))
        name = props.get("nom", "")

        if not feature_code:
            print(f"[WARN] Feature without 'code' property in {dest_rel}, skipping.")
            continue

        geom = shape(feature["geometry"])
        bounds = geom.bounds  # (lon_min, lat_min, lon_max, lat_max)
        bbox = list(bounds)

        zone_code = build_zone_code(country, feature_code)

        parent_code: str | None = None
        if parent_shapes:
            centroid = geom.centroid
            parent_code = find_parent_code(centroid, parent_shapes, parent_zones)

        zone_doc = {
            "code": zone_code,
            "country_code": country,
            "level": level,
            "name": name,
            "parent_code": parent_code,
            "geojson_file": dest_rel,
            "feature_code": feature_code,
            "bbox": bbox,
        }

        result = await collection.update_one(
            {"code": zone_code, "level": level},
            {"$set": zone_doc},
            upsert=True,
        )
        if result.upserted_id:
            inserted += 1
        else:
            updated += 1

        seeded_zones.append(zone_doc)

    print(f"[OK]   level {level} ({country}) — {inserted} inserted, {updated} updated")
    return seeded_zones


def _load_geojson_features(path: Path) -> list[dict]:
    """Load a GeoJSON file's feature list.

    Args:
        path: Path to the GeoJSON file.

    Returns:
        list[dict]: The `features` array.
    """
    with path.open(encoding="utf-8") as f:
        fc = json.load(f)
    return fc["features"]


async def _rebuild_parent_shapes_from_db(
    source: dict, sources: list[dict], data_dir: Path, level: int
) -> tuple[list, list[dict]]:
    """Rebuild parent shapes/zones from the DB and their source GeoJSON.

    Description:
        Used when level > 1 and no cached parent shapes are available yet.

    Args:
        source: Current source entry being seeded.
        sources: All source entries (to find the parent level's GeoJSON).
        data_dir: Base directory for GeoJSON files.
        level: Current level (> 1).

    Returns:
        tuple: `(parent_shapes, parent_zones)`, both empty if the parent source
            or matching docs aren't found.
    """
    parent_col = await get_collection("administrative_zones")
    parent_docs = await parent_col.find(
        {"country_code": source["country"], "level": level - 1}
    ).to_list(length=None)

    # Reload parent geometries from GeoJSON
    parent_source = next(
        (s for s in sources if s["country"] == source["country"] and s["level"] == level - 1),
        None,
    )
    if not parent_source:
        return [], []

    parent_geojson = data_dir / parent_source["dest"]
    features = _load_geojson_features(parent_geojson)
    code_to_shape = {str(feat["properties"]["code"]): shape(feat["geometry"]) for feat in features}
    parent_shapes = [
        code_to_shape[z["feature_code"]] for z in parent_docs if z["feature_code"] in code_to_shape
    ]
    parent_zones = [z for z in parent_docs if z["feature_code"] in code_to_shape]
    return parent_shapes, parent_zones


async def _resolve_parent_shapes(
    source: dict,
    sources: list[dict],
    data_dir: Path,
    level: int,
    parent_shapes: list,
    parent_zones: list[dict],
) -> tuple[list, list[dict]]:
    """Resolve the parent shapes/zones to use for seeding one source.

    Description:
        Reuses already-built parent shapes/zones from the previous iteration when
        available; otherwise rebuilds them from the DB (level > 1 only); level 1
        has no parent, so the inputs are returned unchanged.

    Args:
        source: Current source entry.
        sources: All source entries.
        data_dir: Base directory for GeoJSON files.
        level: Current level.
        parent_shapes: Parent shapes carried over from the previous level.
        parent_zones: Parent zones carried over from the previous level.

    Returns:
        tuple: `(parent_shapes, parent_zones)` to use for this source.
    """
    if level > 1 and parent_shapes:
        # Parent shapes already built from previous level
        return parent_shapes, parent_zones
    if level > 1:
        # Build parent shapes on the fly from the DB
        return await _rebuild_parent_shapes_from_db(source, sources, data_dir, level)
    return parent_shapes, parent_zones


async def main() -> None:
    """Seeds all administrative zones from GeoJSON sources."""
    settings = get_settings()
    data_dir = BACKEND_DIR / settings.geo_data_dir

    if not CONFIG_FILE.exists():
        print(f"[ERROR] Config file not found: {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)

    sources = load_sources(CONFIG_FILE)
    print(f"Found {len(sources)} source(s) to seed.\n")

    parent_shapes: list = []
    parent_zones: list[dict] = []

    for source in sources:
        level = source["level"]
        dest_rel = source["dest"]
        print(f"[SEED] level {level} ← {dest_rel}")

        parent_shapes, parent_zones = await _resolve_parent_shapes(
            source, sources, data_dir, level, parent_shapes, parent_zones
        )

        seeded = await seed_level(source, data_dir, parent_shapes, parent_zones)

        # Use this level's shapes as parents for the next level
        geojson_path_level = data_dir / source["dest"]
        features = _load_geojson_features(geojson_path_level)
        parent_shapes = [shape(feat["geometry"]) for feat in features]
        parent_zones = seeded

    print("\nDone.")

    # Close MongoDB connection
    client = get_client()
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
