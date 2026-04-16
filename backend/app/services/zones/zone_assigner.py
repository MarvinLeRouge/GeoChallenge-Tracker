# backend/app/services/zones/zone_assigner.py
# High-level zone assignment: enriches a list of cache dicts with `zones` field.
# Called from the GPX import pipeline (step 5b) and can be reused anywhere
# cache dicts need zone enrichment before persistence.
#
# Three-pass algorithm:
#   Pass 1 — Shapely exact point-in-polygon (fast, local, most accurate)
#   Pass 2 — Nominatim reverse geocoding for unmatched points (1 req/sec, accurate)
#   Pass 3 — Nearest polygon fallback for points Nominatim couldn't resolve (last resort)

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.core.settings import get_settings
from app.db.mongodb import get_collection
from app.services.zones.zone_nominatim import resolve_zones_batch
from app.services.zones.zone_utils import SpatialIndex, build_spatial_index, resolve_zones_for_point

log = logging.getLogger(__name__)

# In-memory cache of spatial indexes keyed by (country_code, level)
_index_cache: dict[tuple[str, int], SpatialIndex] = {}


async def _get_index(country_code: str, level: int) -> SpatialIndex | None:
    """Returns (and caches) the spatial index for a given country and level.

    Description:
        Loads zone documents from the DB and builds the STRtree index on first
        call. Subsequent calls return the cached index. Returns None if no zones
        are found (e.g. country not yet seeded).

    Args:
        country_code (str): ISO country code, e.g. "FR".
        level (int): Administrative level (1 or 2).

    Returns:
        SpatialIndex | None: Populated index, or None if unavailable.
    """
    key = (country_code, level)
    if key in _index_cache:
        return _index_cache[key]

    settings = get_settings()
    data_dir = Path(settings.geo_data_dir)

    collection = await get_collection("administrative_zones")
    zone_docs = await collection.find({"country_code": country_code, "level": level}).to_list(
        length=None
    )

    if not zone_docs:
        log.debug("No level-%d zones found for %s — zone assignment skipped.", level, country_code)
        return None

    geojson_file = zone_docs[0]["geojson_file"]
    geojson_path = data_dir / geojson_file

    if not geojson_path.exists():
        log.warning(
            "GeoJSON file not found: %s — zone assignment skipped for %s level %d.",
            geojson_path,
            country_code,
            level,
        )
        return None

    index = build_spatial_index(geojson_path, zone_docs)
    _index_cache[key] = index
    log.info("Spatial index built: %s level %d (%d zones)", country_code, level, len(index.shapes))
    return index


async def assign_zones_to_caches(caches_data: list[dict[str, Any]]) -> None:
    """Enriches a list of cache dicts with their administrative zones (3-pass).

    Description:
        Pass 1 — Shapely exact containment for all caches with coordinates.
        Pass 2 — Nominatim reverse geocoding (batched, 1 req/sec) for caches
                 where Shapely found no containing polygon (simplified boundaries).
        Pass 3 — Nearest polygon fallback for caches Nominatim couldn't resolve.

        Caches without coordinates are silently skipped.
        If zone indexes are unavailable (not seeded), returns silently.
        Currently supports FR only; other countries are silently skipped.

    Args:
        caches_data (list[dict]): Cache dicts enriched in place with a `zones` field.
    """
    country_groups: dict[str, list[int]] = {}
    for i, cache in enumerate(caches_data):
        if cache.get("lat") is None or cache.get("lon") is None:
            continue
        country_code = "FR"  # extend when multi-country support is added
        country_groups.setdefault(country_code, []).append(i)

    for country_code, indices in country_groups.items():
        idx1 = await _get_index(country_code, 1)
        idx2 = await _get_index(country_code, 2)

        if idx1 is None or idx2 is None:
            log.debug("Indexes unavailable for %s — skipping zone assignment.", country_code)
            continue

        # --- Pass 1: Shapely exact containment ---
        unmatched_indices: list[int] = []
        for i in indices:
            cache = caches_data[i]
            try:
                zones = resolve_zones_for_point(
                    cache["lat"], cache["lon"], country_code, idx1, idx2, exact_only=True
                )
                if zones["level1"] is None or zones["level2"] is None:
                    unmatched_indices.append(i)
                else:
                    cache["zones"] = zones
            except Exception as exc:
                log.warning(
                    "Shapely error for cache %s (%.5f, %.5f): %s",
                    cache.get("GC", "?"),
                    cache["lat"],
                    cache["lon"],
                    exc,
                )
                unmatched_indices.append(i)

        if not unmatched_indices:
            continue

        log.info(
            "%d/%d caches unmatched by Shapely for %s — sending to Nominatim.",
            len(unmatched_indices),
            len(indices),
            country_code,
        )

        # --- Pass 2: Nominatim reverse geocoding ---
        points = [(caches_data[i]["lat"], caches_data[i]["lon"]) for i in unmatched_indices]
        nominatim_results = await resolve_zones_batch(points, country_code)

        still_unmatched: list[int] = []
        for i, zones in zip(unmatched_indices, nominatim_results):
            if zones["level2"] is not None:
                caches_data[i]["zones"] = zones
            else:
                still_unmatched.append(i)

        if not still_unmatched:
            continue

        log.info(
            "%d cache(s) still unresolved after Nominatim — applying nearest-polygon fallback.",
            len(still_unmatched),
        )

        # --- Pass 3: Nearest polygon fallback ---
        for i in still_unmatched:
            cache = caches_data[i]
            try:
                zones = resolve_zones_for_point(
                    cache["lat"], cache["lon"], country_code, idx1, idx2, exact_only=False
                )
                cache["zones"] = zones
            except Exception as exc:
                log.warning(
                    "Nearest-polygon fallback failed for cache %s (%.5f, %.5f): %s",
                    cache.get("GC", "?"),
                    cache["lat"],
                    cache["lon"],
                    exc,
                )
