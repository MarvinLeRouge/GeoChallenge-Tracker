# backend/app/api/routes/caches_geocoding.py
# Admin routes to backfill missing country/state via reverse geocoding (Nominatim).

from __future__ import annotations

import logging
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pymongo import UpdateOne

from app.api.deps import require_admin
from app.core.security import get_current_user
from app.db.mongodb import get_collection, get_db
from app.domain.models.user import User
from app.services.gpx_import.referential_mapper import ReferentialMapper
from app.services.providers import geocoding_nominatim

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/caches_geocoding",
    tags=["Caches geocoding"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/backfill",
    summary="Backfill missing country/state via reverse geocoding (admin)",
    description=(
        "Fills in `country_id` and `state_id` for caches that are missing both fields but have valid coordinates.\n\n"
        "- Uses Nominatim (OSM) — 1 request per point, sequential, respects 1 req/sec ToS\n"
        "- Creates country/state referential entries if they do not yet exist\n"
        "- `page_size` should remain small (≤ 50) to avoid long request chains per batch\n"
        "- `dry_run` mode simulates the work without writing to the database\n"
        "- Reserved for administrators"
    ),
)
async def backfill_geocoding(
    admin: Annotated[User, Depends(require_admin)],
    limit: int = Query(200, ge=1, le=5000, description="Maximum number of caches to process."),
    page_size: int = Query(
        50, ge=1, le=200, description="Batch size (one Nominatim request per cache)."
    ),
    dry_run: bool = Query(False, description="If true, does not persist updates (simulation)."),
) -> dict[str, Any]:
    """Reverse-geocoding backfill (admin).

    Description:
        Selects caches with null country_id and null state_id but valid lat/lon,
        reverse-geocodes each point via Nominatim, resolves or creates country/state
        referential entries, and applies bulk updates.

    Args:
        limit (int): Maximum number of caches to process.
        page_size (int): Batch size.
        dry_run (bool): If true, executes without writing to the database.

    Returns:
        dict: Processing statistics (scanned, updated, failed, batches, requests_used,
              duration_s, had_non_200, dry_run).
    """
    coll = await get_collection("caches")
    db = get_db()
    mapper = ReferentialMapper(db)
    await mapper.load_all_referentials()

    filt: dict[str, Any] = {
        "country_id": None,
        "state_id": None,
        "lat": {"$ne": None},
        "lon": {"$ne": None},
    }

    scanned = updated = failed = requests_used = 0
    batches = 0
    global_http_stats: dict[int, int] = {}
    job_start = time.monotonic()

    log.info(
        "Nominatim backfill started — limit=%d page_size=%d dry_run=%s",
        limit,
        page_size,
        dry_run,
    )

    while scanned < limit:
        cursor = coll.find(filt, {"_id": 1, "lat": 1, "lon": 1}).limit(
            min(page_size, limit - scanned)
        )
        docs_buffer: list[dict[str, Any]] = await cursor.to_list(length=page_size)

        if not docs_buffer:
            break

        batches += 1
        batch_start = time.monotonic()

        if dry_run:
            scanned += len(docs_buffer)
            requests_used += len(docs_buffer)
            log.info(
                "Nominatim backfill batch %d (dry_run) — %d points skipped",
                batches,
                len(docs_buffer),
            )
            continue

        pts = [(float(d["lat"]), float(d["lon"])) for d in docs_buffer]
        geo_results, batch_http_stats = await geocoding_nominatim.fetch_batch(pts)
        requests_used += len(pts)
        scanned += len(docs_buffer)

        # Merge batch HTTP stats into global counters
        for code, count in batch_http_stats.items():
            global_http_stats[code] = global_http_stats.get(code, 0) + count

        batch_duration = round(time.monotonic() - batch_start, 2)
        log.info(
            "Nominatim backfill batch %d — %d points, %.2fs, http_stats=%s",
            batches,
            len(pts),
            batch_duration,
            batch_http_stats,
        )

        bulk_ops: list[UpdateOne] = []
        for doc, geo in zip(docs_buffer, geo_results):
            if geo is None:
                failed += 1
                continue

            country_name, state_name = geo
            country_id, state_id = await mapper.ensure_country_and_state(country_name, state_name)

            if country_id is None:
                failed += 1
                continue

            update_fields: dict[str, Any] = {"country_id": country_id}
            if state_id is not None:
                update_fields["state_id"] = state_id

            bulk_ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": update_fields}))

        if bulk_ops:
            await coll.bulk_write(bulk_ops, ordered=False)
            updated += len(bulk_ops)

    duration_s = round(time.monotonic() - job_start, 2)
    had_non_200 = any(code != 200 for code in global_http_stats)

    log.info(
        "Nominatim backfill done — scanned=%d updated=%d failed=%d batches=%d "
        "requests=%d duration=%.2fs had_non_200=%s http_stats=%s",
        scanned,
        updated,
        failed,
        batches,
        requests_used,
        duration_s,
        had_non_200,
        global_http_stats,
    )

    return {
        "scanned": scanned,
        "updated": updated,
        "failed": failed,
        "batches": batches,
        "requests_used": requests_used,
        "duration_s": duration_s,
        "had_non_200": had_non_200,
        "dry_run": dry_run,
    }
