# backend/app/services/providers/elevation_opentopo.py
# OpenTopoData/Mapzen provider: elevation retrieval, request chunking (URL/count),
# daily quota enforcement via the `api_quotas` collection, and client-side rate limiting.

from __future__ import annotations

import asyncio
import os

import httpx

from app.core.settings import get_settings
from app.core.utils import utcnow
from app.db.mongodb import get_collection

settings = get_settings()

# Config
ENDPOINT = settings.elevation_provider_endpoint
MAX_POINTS_PER_REQ = settings.elevation_provider_max_points_per_req
RATE_DELAY_S = settings.elevation_provider_rate_delay_s
URL_MAXLEN = 1800
ENABLED = settings.elevation_enabled

# Quota
PROVIDER_KEY = "opentopodata_mapzen"


def _quota_key_for_today() -> str:
    """Daily quota key for the provider.

    Description:
        Builds a unique key for the current UTC day (via `utcnow()`),
        in the form `"opentopodata_mapzen:YYYY-MM-DD"`. Used as the document
        identifier in the `api_quotas` collection.

    Args:
        None

    Returns:
        str: Today's quota key (e.g. "opentopodata_mapzen:2025-08-27").
    """
    today = utcnow().date().isoformat()
    return f"{PROVIDER_KEY}:{today}"


async def _read_quota() -> int:
    """Read today's request counter.

    Description:
        Reads the `api_quotas[_id=_quota_key_for_today()]` document and returns
        the `count` field if present; otherwise 0. This counter represents the
        **number of HTTP requests** already made to the provider today.

    Args:
        None

    Returns:
        int: Current request counter (>= 0).
    """
    coll_quotas = await get_collection("api_quotas")
    doc = await coll_quotas.find_one({"_id": _quota_key_for_today()})
    return int(doc["count"]) if doc and "count" in doc else 0


async def _inc_quota(n: int) -> None:
    """Increment today's quota counter.

    Description:
        Applies `update_one(..., {"$inc": {"count": int(n)}, "$setOnInsert": {"created_at": utcnow()}}, upsert=True)`
        on `api_quotas` for the daily key. Called after **each** HTTP request.

    Args:
        n (int): Number of requests to add (converted to int).

    Returns:
        None
    """
    coll_quotas = await get_collection("api_quotas")
    await coll_quotas.update_one(
        {"_id": _quota_key_for_today()},
        {"$inc": {"count": int(n)}, "$setOnInsert": {"created_at": utcnow()}},
        upsert=True,
    )


def _build_param(points: list[tuple[float, float]]) -> str:
    """Build the `locations` API parameter.

    Description:
        Serializes the list of `(lat, lon)` points into the format expected by the API:
        `"lat,lon|lat,lon|..."`.

    Args:
        points (list[tuple[float, float]]): Coordinates (latitude, longitude).

    Returns:
        str: `locations` string ready to append to the URL.
    """
    return "|".join(f"{lat},{lon}" for (lat, lon) in points)


def _split_params_by_url_and_count(all_param: str) -> list[str]:
    """Split `locations` into URL-compatible and per-request quota chunks.

    Description:
        Splits the large `locations` string into **chunks** respecting:
        - Maximum URL length (~`URL_MAXLEN`), accounting for the `?locations=` prefix.
        - The `MAX_POINTS_PER_REQ` limit (number of points per call).

        Heuristic:
        - Cuts at the last pipe `|` to avoid splitting a lat/lon pair.
        - If a chunk exceeds the point limit, truncates to the **allowed count** and
          reinjects the overflow at the start of the remainder.

    Args:
        all_param (str): Global `locations` string built by `_build_param`.

    Returns:
        list[str]: List of `locations` fragments to call sequentially.
    """
    prefix_len = len(f"{ENDPOINT}?locations=")
    max_param_len = max(1, URL_MAXLEN - prefix_len)

    chunks: list[str] = []
    remaining = all_param
    while remaining:
        # take max slice by URL size
        take = remaining[:max_param_len]
        if len(take) == len(remaining):
            chunk = take
            remaining = ""
        else:
            # cut back to last '|' so we don't split a coordinate
            cut = take.rfind("|")
            if cut == -1:
                # no '|' found -> single coordinate longer than max? take it anyway
                chunk = take
                remaining = remaining[len(take) :]
            else:
                chunk = take[:cut]
                remaining = remaining[cut + 1 :]  # drop the '|'

        # enforce MAX_POINTS_PER_REQ
        # number of points = number of pipes + 1 (unless chunk empty)
        if chunk:
            pipes = chunk.count("|")
            if pipes >= MAX_POINTS_PER_REQ:
                # keep only first MAX_POINTS_PER_REQ points (=> MAX_POINTS_PER_REQ-1 pipes)
                # find the index of the (MAX_POINTS_PER_REQ-1)-th '|' (0-based)
                keep_pipes = MAX_POINTS_PER_REQ - 1
                idx = -1
                count = 0
                for i, ch in enumerate(chunk):
                    if ch == "|":
                        count += 1
                        if count == keep_pipes:
                            idx = i
                            break
                if idx != -1:
                    extra = chunk[idx + 1 :]
                    chunk = chunk[:idx]
                    # prepend overflow back to remaining (with a '|' if needed)
                    remaining = (extra + ("|" + remaining if remaining else "")).lstrip("|")

        chunks.append(chunk)
    return [c for c in chunks if c]


async def fetch(points: list[tuple[float, float]]) -> list[int | None]:
    """Retrieve elevations for a list of points (aligned with the input).

    Description:
        - If the provider is disabled (`settings.elevation_enabled=False`) **or** the
          `points` list is empty, returns a list of `None` of the same length.
        - Respects a **daily quota** in number of HTTP calls, tracked in the `api_quotas`
          collection and the `ELEVATION_DAILY_LIMIT` environment variable (default 1000).
          If the quota is reached, returns `None` for the remaining points.
        - Builds a `locations` string, then **splits** it via `_split_params_by_url_and_count`
          respecting `URL_MAXLEN` and `MAX_POINTS_PER_REQ`.
        - For each chunk:
            * performs a `GET` on `ENDPOINT?locations=...` (timeout configurable via
              `ELEVATION_TIMEOUT_S`, default "5.0")
            * parses the JSON response and extracts `results[*].elevation`
            * maps each elevation (rounded to int) back to the **correct original index**
            * on HTTP/JSON error, leaves the corresponding values as `None`
            * increments the quota and respects a **rate delay** (`RATE_DELAY_S`) between
              calls (except after the last one)
        - Never raises an exception; any network/parse error results in localized `None` values.

    Args:
        points (list[tuple[float, float]]): List of `(lat, lon)` for which to retrieve elevation.

    Returns:
        list[int | None]: Elevations in meters (or `None` on failure), **aligned** with `points`.
    """
    if not ENABLED or not points:
        return [None] * len(points)

    # Respect daily quota (1000 calls/day), counting *requests*, not points
    daily_count = await _read_quota()
    DAILY_LIMIT = int(os.getenv("ELEVATION_DAILY_LIMIT", "1000"))
    if daily_count >= DAILY_LIMIT:
        return [None] * len(points)

    # We keep a parallel index list to map back results to original points
    # Build one big param string then split smartly
    param_all = _build_param(points)
    param_chunks = _split_params_by_url_and_count(param_all)

    results: list[int | None] = [None] * len(points)
    # We need to also split the original points list in the same way to keep indices aligned.
    # We'll reconstruct chunk-wise indices by counting commas/pipes.
    idx_start = 0
    async with httpx.AsyncClient(timeout=float(os.getenv("ELEVATION_TIMEOUT_S", "5.0"))) as client:
        for i, param in enumerate(param_chunks):
            # Determine how many points are in this chunk
            n_pts = 1 if param and "|" not in param else (param.count("|") + 1 if param else 0)

            # Quota guard: stop if next request would exceed
            if daily_count >= DAILY_LIMIT:
                break

            url = f"{ENDPOINT}?locations={param}"
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json() or {}
                    arr = data.get("results") or []
                    for j, rec in enumerate(arr[:n_pts]):
                        elev = rec.get("elevation", None)
                        if isinstance(elev, (int, float)):
                            results[idx_start + j] = int(round(elev))
                        else:
                            results[idx_start + j] = None
                else:
                    # leave None for this slice
                    pass
            except Exception:
                # leave None for this slice
                pass

            # update quota & delay
            daily_count += 1
            await _inc_quota(1)
            idx_start += n_pts

            # Rate-limit (skip after the last chunk)
            if i < len(param_chunks) - 1:
                await asyncio.sleep(RATE_DELAY_S)

    return results
