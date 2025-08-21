from __future__ import annotations
from typing import Optional, List

import asyncio
from fastapi import APIRouter, Depends, Query, HTTPException, status

from app.core.security import get_current_user
from app.db.mongodb import get_collection
from app.services.elevation_retrieval import fetch as fetch_elevations

router = APIRouter(tags=["caches", "admin-elevation"])

def _is_admin(user) -> bool:
    # accept 'admin' role string or boolean flag
    role = getattr(user, "role", None) or getattr(user, "roles", None)
    if isinstance(role, str):
        return role.lower() == "admin"
    if isinstance(role, (list, tuple, set)):
        return any((str(r).lower() == "admin") for r in role)
    # fallback: allow if user has attribute is_admin True
    return bool(getattr(user, "is_admin", False))

@router.post("/caches/elevation/backfill")
async def backfill_elevation(
    limit: int = Query(1000, ge=1, le=20000),
    page_size: int = Query(500, ge=10, le=1000),
    dry_run: bool = Query(False),
    user = Depends(get_current_user),
):
    """Admin-only: fill elevation for caches missing it, respecting provider quotas & 1 req/s."""
    if not _is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    coll = get_collection("caches")

    # Build cursor for missing elevation but with valid lat/lon
    filt = {"$and": [
        {"$or": [{"elevation": {"$exists": False}}, {"elevation": None}]},
        {"lat": {"$ne": None}}, {"lon": {"$ne": None}},
    ]}

    scanned = updated = failed = requests_used = 0
    batches = 0
    docs_buffer: List[dict] = []

    cursor = coll.find(filt, {"_id": 1, "lat": 1, "lon": 1}).limit(limit)
    while True:
        docs_buffer = list(cursor[:page_size])  # using slicing to page-lightly
        if not docs_buffer:
            break
        batches += 1
        scanned += len(docs_buffer)

        if dry_run:
            # simulate work but do not write
            continue

        pts = [(float(d["lat"]), float(d["lon"])) for d in docs_buffer]
        elevs = await fetch_elevations(pts)

        # Apply updates in bulk
        ops = []
        for d, ev in zip(docs_buffer, elevs):
            if ev is None:
                failed += 1
                continue
            ops.append({"filter": {"_id": d["_id"]},
                        "update": {"$set": {"elevation": int(ev)}}})

        if ops:
            # manual bulk since we can't import UpdateOne here safely in routes
            bulk_ops = []
            from pymongo import UpdateOne
            for op in ops:
                bulk_ops.append(UpdateOne(op["filter"], op["update"]))
            coll.bulk_write(bulk_ops, ordered=False)

        # simple estimate of requests used: provider increments in its own quota; we expose batches as proxy
        requests_used += 1

        # move the cursor forward
        cursor = coll.find(filt, {"_id": 1, "lat": 1, "lon": 1}).skip(scanned).limit(limit - scanned)
        if scanned >= limit:
            break

    return {
        "scanned": scanned,
        "updated": updated + (len([1 for d, ev in zip(docs_buffer, elevs) if ev is not None]) if not dry_run and docs_buffer else 0),
        "failed": failed,
        "batches": batches,
        "requests_used": requests_used,
        "dry_run": dry_run,
    }
