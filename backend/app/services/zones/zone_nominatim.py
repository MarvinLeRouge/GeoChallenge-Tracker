# backend/app/services/zones/zone_nominatim.py
# Nominatim-based zone resolution fallback.
# Used when Shapely exact point-in-polygon fails (simplified boundary approximations).
# Calls Nominatim /reverse with addressdetails=1 to get ISO3166-2-lvl6 (département code),
# then derives the region via parent_code from the administrative_zones collection.

from __future__ import annotations

import asyncio
import logging

import httpx

from app.db.mongodb import get_collection

log = logging.getLogger(__name__)

ENDPOINT = "https://nominatim.openstreetmap.org/reverse"
RATE_DELAY_S = 1.1  # Nominatim ToS: max 1 req/sec
TIMEOUT_S = 10.0
USER_AGENT = "GeoChallenge-Tracker/1.0 (zone-resolution; OSM Nominatim)"


def _extract_dept_code(data: dict) -> str | None:
    """Extracts the ISO3166-2 département code from a Nominatim response.

    Description:
        Reads `address.ISO3166-2-lvl6` (e.g. "FR-83") which Nominatim returns
        for French locations. This code directly matches our zone `code` field.

    Args:
        data (dict): Parsed JSON response from Nominatim /reverse.

    Returns:
        str | None: Zone code (e.g. "FR-83"), or None if not present.
    """
    address = data.get("address") or {}
    code = address.get("ISO3166-2-lvl6") or ""
    return code.strip() or None


async def _fetch_one(
    lat: float,
    lon: float,
    client: httpx.AsyncClient,
) -> str | None:
    """Reverse-geocodes a single point and returns the département zone code.

    Args:
        lat (float): Latitude.
        lon (float): Longitude.
        client (httpx.AsyncClient): Shared HTTP client.

    Returns:
        str | None: Zone code (e.g. "FR-83"), or None on failure.
    """
    try:
        resp = await client.get(
            ENDPOINT,
            params={"lat": lat, "lon": lon, "format": "json", "addressdetails": 1},
            headers={"User-Agent": USER_AGENT},
        )
        if resp.status_code == 200:
            return _extract_dept_code(resp.json())
        log.warning("Nominatim HTTP %s for (%.5f, %.5f)", resp.status_code, lat, lon)
        return None
    except Exception as exc:
        log.warning("Nominatim error for (%.5f, %.5f): %s", lat, lon, exc)
        return None


async def _resolve_parent(dept_code: str) -> str | None:
    """Looks up the region code (parent_code) for a given département code.

    Args:
        dept_code (str): Département zone code, e.g. "FR-83".

    Returns:
        str | None: Region zone code (e.g. "FR-93"), or None if not found.
    """
    collection = await get_collection("administrative_zones")
    doc = await collection.find_one({"code": dept_code}, {"parent_code": 1})
    return doc["parent_code"] if doc else None


async def resolve_zones_batch(
    points: list[tuple[float, float]],
    country_code: str,
) -> list[dict[str, str | None]]:
    """Resolves zone codes for a batch of unmatched points via Nominatim.

    Description:
        Issues one Nominatim /reverse request per point (respecting the 1 req/sec
        ToS limit). For each result, derives the région via `parent_code` from the
        `administrative_zones` collection. Returns None values for points where
        Nominatim returns no usable code.

    Args:
        points (list[tuple[float, float]]): List of (lat, lon) pairs.
        country_code (str): ISO country code (e.g. "FR") — used to fill `zones.country`.

    Returns:
        list[dict[str, str | None]]: Zone dicts aligned with `points`, e.g.
            [{"country": "FR", "level1": "FR-93", "level2": "FR-83"}, ...]
            Values may be None if resolution failed for a point.
    """
    if not points:
        return []

    log.info("Nominatim fallback: resolving %d point(s) at 1 req/sec…", len(points))
    results: list[dict[str, str | None]] = []

    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        for i, (lat, lon) in enumerate(points):
            dept_code = await _fetch_one(lat, lon, client)
            region_code: str | None = None

            if dept_code:
                region_code = await _resolve_parent(dept_code)
            else:
                log.debug("Nominatim returned no code for (%.5f, %.5f)", lat, lon)

            results.append(
                {
                    "country": country_code,
                    "level1": region_code,
                    "level2": dept_code,
                }
            )

            if i < len(points) - 1:
                await asyncio.sleep(RATE_DELAY_S)

    matched = sum(1 for r in results if r["level2"] is not None)
    log.info("Nominatim fallback: %d/%d points resolved.", matched, len(points))
    return results
