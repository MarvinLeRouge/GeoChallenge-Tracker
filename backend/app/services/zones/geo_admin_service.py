# backend/app/services/zones/geo_admin_service.py
# Admin-only service for managing GeoJSON coverage of administrative zones.
# Powers the /admin/geo endpoints (missing-countries detection, file upload/ingestion).

from __future__ import annotations

import logging
from pathlib import Path

from app.core.settings import get_settings
from app.db.mongodb import get_collection

log = logging.getLogger(__name__)


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
