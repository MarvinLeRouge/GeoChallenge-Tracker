# backend/app/api/routes/caches_elevation.py
# Admin routes to enrich caches with elevation data (external provider call).

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_admin
from app.core.security import get_current_user
from app.db.mongodb import get_collection
from app.domain.models.user import User
from app.services.elevation_retrieval import fetch as fetch_elevations

router = APIRouter(
    prefix="/caches_elevation",
    tags=["Caches elevation"],
    dependencies=[Depends(get_current_user)],
)


# TODO: [BACKLOG] Route /caches_elevation/caches/elevation/backfill (POST) to verify
@router.post(
    "/caches/elevation/backfill",
    summary="Backfill missing elevation data (admin)",
    description=(
        "Fills in the elevation for caches that have no value, in batches, respecting provider quotas.\n\n"
        "- Paginated scan of the collection\n"
        "- `dry_run` mode to simulate without writing to the database\n"
        "- Reserved for administrators"
    ),
)
async def backfill_elevation(
    admin: Annotated[User, Depends(require_admin)],
    limit: int = Query(1000, ge=1, le=20000, description="Maximum number of caches to process."),
    page_size: int = Query(500, ge=10, le=1000, description="Batch size for reads/writes."),
    dry_run: bool = Query(False, description="If true, does not persist updates (simulation)."),
):
    """Elevation backfill (admin).

    Description:
        Selects caches without elevation (but with valid lat/lon), retrieves elevation via an external provider,
        and applies batch updates. Can run in simulation mode.

    Args:
        limit (int): Maximum number of caches to process.
        page_size (int): Batch size.
        dry_run (bool): If true, executes without writing to the database.

    Returns:
        dict: Processing statistics (scanned, updated, failed, batches, requests_used, dry_run).
    """

    coll = await get_collection("caches")

    # Build cursor for missing elevation but with valid lat/lon
    filt = {
        "$and": [
            {"$or": [{"elevation": {"$exists": False}}, {"elevation": None}]},
            {"lat": {"$ne": None}},
            {"lon": {"$ne": None}},
        ]
    }

    scanned = updated = failed = requests_used = 0
    batches = 0
    docs_buffer: list[dict] = []

    while scanned < limit:
        cursor = coll.find(filt, {"_id": 1, "lat": 1, "lon": 1}).limit(
            min(page_size, limit - scanned)
        )
        docs_buffer = await cursor.to_list(length=page_size)

        if not docs_buffer:
            break
        batches += 1
        scanned += len(docs_buffer)

        if dry_run:
            # simulate work but do not write
            requests_used += 1
            continue

        pts = [(float(d["lat"]), float(d["lon"])) for d in docs_buffer]
        elevs = await fetch_elevations(pts)

        # Apply updates in bulk
        ops = []
        for d, ev in zip(docs_buffer, elevs):
            if ev is None:
                failed += 1
                continue
            ops.append(
                {
                    "filter": {"_id": d["_id"]},
                    "update": {"$set": {"elevation": int(ev)}},
                }
            )

        if ops:
            # manual bulk since we can't import UpdateOne here safely in routes
            bulk_ops = []
            from pymongo import UpdateOne

            for op in ops:
                bulk_ops.append(UpdateOne(op["filter"], op["update"]))
            await coll.bulk_write(bulk_ops, ordered=False)
            updated += len(bulk_ops)

        # simple estimate of requests used: provider increments in its own quota; we expose batches as proxy
        requests_used += 1

    return {
        "scanned": scanned,
        "updated": updated,
        "failed": failed,
        "batches": batches,
        "requests_used": requests_used,
        "dry_run": dry_run,
    }
