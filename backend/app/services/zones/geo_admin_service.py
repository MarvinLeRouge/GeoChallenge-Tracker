# backend/app/services/zones/geo_admin_service.py
# Admin-only service for managing GeoJSON coverage of administrative zones.
# Powers the /admin/geo endpoints (missing-countries detection, file upload/ingestion).

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.settings import get_settings
from app.db.mongodb import get_collection

log = logging.getLogger(__name__)

REQUIRED_FEATURE_PROPERTIES = ("code", "nom", "feature_code")


def _geo_data_dir() -> Path:
    """Resolves the root directory storing GeoJSON files, relative to the process CWD.

    Returns:
        Path: Same directory `app.main`'s `/geo` StaticFiles mount serves from.
    """
    return Path(get_settings().geo_data_dir)


async def get_missing_countries() -> list[dict]:
    """Returns countries with found caches but no GeoJSON directory on disk yet.

    Description:
        Aggregates `found_caches` (all users - deliberately not scoped to one user,
        so that a cache found by many users weighs more than one found by a single
        user) grouped by `cache.zones.country`, then excludes any country code that
        already has a `{geo_data_dir}/{code}/` directory.

    Returns:
        list[dict]: `{"code": str, "found_count": int}`, sorted by `found_count` desc.
    """
    data_dir = _geo_data_dir()
    found_col = await get_collection("found_caches")
    pipeline = [
        {
            "$lookup": {
                "from": "caches",
                "localField": "cache_id",
                "foreignField": "_id",
                "as": "cache",
            }
        },
        {"$unwind": "$cache"},
        {"$match": {"cache.zones.country": {"$ne": None}}},
        {"$group": {"_id": "$cache.zones.country", "found_count": {"$sum": 1}}},
    ]
    raw = await found_col.aggregate(pipeline).to_list(length=None)  # type: ignore[arg-type]

    missing = [
        {"code": doc["_id"], "found_count": doc["found_count"]}
        for doc in raw
        if not (data_dir / doc["_id"]).is_dir()
    ]
    missing.sort(key=lambda m: m["found_count"], reverse=True)
    return missing


def _validate_feature_collection(payload: dict, level: int) -> list[dict]:
    """Validates the normalized GeoJSON contract and returns its features.

    Args:
        payload (dict): Parsed JSON content.
        level (int): Administrative level being uploaded (0, 1 or 2).

    Returns:
        list[dict]: The FeatureCollection's `features` list.

    Raises:
        ValueError: If the payload does not follow the normalized contract
            (see ~/projets/geo_json/CONTRACT.md).
    """
    if payload.get("type") != "FeatureCollection":
        raise ValueError("Payload is not a GeoJSON FeatureCollection.")

    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("FeatureCollection has no 'features' array.")

    for i, feature in enumerate(features):
        props = feature.get("properties", {})
        for field in REQUIRED_FEATURE_PROPERTIES:
            if not props.get(field):
                raise ValueError(f"Feature {i} is missing required property '{field}'.")
        if level == 2 and not props.get("parent_code"):
            raise ValueError(f"Feature {i} is missing required property 'parent_code' (level 2).")
        if "bbox" not in feature:
            raise ValueError(f"Feature {i} is missing the GeoJSON 'bbox' member.")

    return features


async def upload_zone_level(country_code: str, level: int, content: bytes) -> dict:
    """Validates, stores, and (for level 1/2) ingests a normalized GeoJSON file.

    Description:
        Writes the raw file to `{geo_data_dir}/{country_code}/adm{level}.geojson`.
        For level 1/2, also upserts one `administrative_zones` document per feature,
        trusting the file's own precomputed `parent_code`/`bbox` (unlike
        `scripts/seed_zones.py`, which recomputes them via Shapely for the older,
        non-normalized source files). Level 0 is stored for forward-compatibility
        only - no collection is seeded from it (see Global Constraints).

    Args:
        country_code (str): ISO 3166-1 alpha-2 code, e.g. "FR".
        level (int): Administrative level - 0, 1 or 2.
        content (bytes): Raw uploaded file content.

    Returns:
        dict: `{country_code, level, features_count, inserted, updated}`.

    Raises:
        ValueError: If the content is not valid JSON or violates the normalized contract.
    """
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("Uploaded file is not valid JSON.") from exc

    features = _validate_feature_collection(payload, level)

    dest_rel = f"{country_code}/adm{level}.geojson"
    dest_path = _geo_data_dir() / dest_rel
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(content)

    inserted = updated = 0
    if level in (1, 2):
        collection = await get_collection("administrative_zones")
        for feature in features:
            props = feature["properties"]
            feature_code = str(props["code"])
            zone_doc = {
                "code": f"{country_code}-{feature_code}",
                "country_code": country_code,
                "level": level,
                "name": props["nom"],
                "parent_code": props.get("parent_code"),
                "geojson_file": dest_rel,
                "feature_code": feature_code,
                "bbox": feature["bbox"],
            }
            result = await collection.update_one(
                {"code": zone_doc["code"], "level": level},
                {"$set": zone_doc},
                upsert=True,
            )
            if result.upserted_id:
                inserted += 1
            else:
                updated += 1

    return {
        "country_code": country_code,
        "level": level,
        "features_count": len(features),
        "inserted": inserted,
        "updated": updated,
    }
