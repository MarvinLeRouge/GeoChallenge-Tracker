# backend/app/services/providers/geocoding_nominatim.py
# Nominatim (OSM) reverse geocoding provider: one request per point, 1 req/sec rate limit.
"""
Nominatim reverse geocoding provider.

Nominatim ToS:
- Max 1 request/second.
- Requires a descriptive User-Agent header.
- Free for non-commercial and light-commercial use.

Each call returns (country_name, state_name) or None on failure.
State resolution order: state → region → county (first non-empty wins).
"""

from __future__ import annotations

import asyncio
import logging

import httpx

log = logging.getLogger(__name__)

ENDPOINT = "https://nominatim.openstreetmap.org/reverse"
RATE_DELAY_S = 1.1  # slightly above 1 to respect the 1 req/sec ToS limit
TIMEOUT_S = 10.0
USER_AGENT = "GeoChallenge-Tracker/1.0 (reverse-geocoding backfill; OSM Nominatim)"


def _parse_response(data: dict) -> tuple[str, str] | None:
    """Extract (country, state) from a Nominatim reverse-geocoding response.

    Description:
        Reads `address.country` and the first non-empty of
        `address.state`, `address.region`, `address.county`.

    Args:
        data (dict): Parsed JSON response from Nominatim.

    Returns:
        tuple[str, str] | None: (country_name, state_name) or None if country is missing.
    """
    address = data.get("address") or {}
    country = (address.get("country") or "").strip()
    if not country:
        return None
    state = (address.get("state") or address.get("region") or address.get("county") or "").strip()
    return country, state


async def fetch_one(
    lat: float,
    lon: float,
    client: httpx.AsyncClient,
) -> tuple[tuple[str, str] | None, int]:
    """Reverse-geocode a single point.

    Args:
        lat (float): Latitude.
        lon (float): Longitude.
        client (httpx.AsyncClient): Shared HTTP client.

    Returns:
        tuple: ((country_name, state_name) or None, HTTP status code or 0 on exception).
    """
    try:
        resp = await client.get(
            ENDPOINT,
            params={"lat": lat, "lon": lon, "format": "json", "accept-language": "fr"},
            headers={"User-Agent": USER_AGENT},
        )
        if resp.status_code == 200:
            return _parse_response(resp.json()), 200
        log.warning("Nominatim HTTP %s for (%.5f, %.5f)", resp.status_code, lat, lon)
        return None, resp.status_code
    except Exception as exc:
        log.warning("Nominatim error for (%.5f, %.5f): %s", lat, lon, exc)
        return None, 0


async def fetch_batch(
    points: list[tuple[float, float]],
) -> tuple[list[tuple[str, str] | None], dict[int, int]]:
    """Reverse-geocode a list of points sequentially, respecting the 1 req/sec limit.

    Description:
        Issues one HTTP request per point with a `RATE_DELAY_S` pause between
        consecutive calls. Returns results aligned with the input list, plus
        a dict of HTTP status code counts.

    Args:
        points (list[tuple[float, float]]): List of (lat, lon) pairs.

    Returns:
        tuple:
            - list[tuple[str, str] | None]: (country, state) per point, or None on failure.
            - dict[int, int]: HTTP status code counts (0 = exception/timeout).
    """
    if not points:
        return [], {}

    results: list[tuple[str, str] | None] = []
    http_stats: dict[int, int] = {}

    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        for i, (lat, lon) in enumerate(points):
            geo, status = await fetch_one(lat, lon, client)
            results.append(geo)
            http_stats[status] = http_stats.get(status, 0) + 1
            if i < len(points) - 1:
                await asyncio.sleep(RATE_DELAY_S)

    return results, http_stats
