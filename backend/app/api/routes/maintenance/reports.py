# app/api/routes/maintenance/reports.py
# Admin diagnostic/report routes: expired-verification cleanup, geo anomalies,
# system snapshot, and referential-duplicates detection.

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Query, Request

from app.api.deps import require_admin
from app.core.utils import utcnow
from app.db.mongodb import get_collection, get_db
from app.services.gpx_import.referential_mapper import ReferentialMapper

from ._router import router


@router.delete(
    "/expired-verifications",
    summary="Clean up expired verification codes",
    description=(
        "Removes the `verification_code` and `verification_expires_at` fields "
        "from unverified accounts whose code has expired.\n\n"
        "**RESTRICTED TO ADMINISTRATORS**\n\n"
        "Does not delete accounts — only removes stale verification fields."
    ),
    responses={
        200: {"description": "Cleanup completed"},
        401: {"description": "Not authenticated"},
        403: {"description": "Access denied (admin required)"},
    },
)
async def cleanup_expired_verifications(
    _: Annotated[Any, Depends(require_admin)],
) -> dict[str, Any]:
    """Cleans up expired verification codes from unverified accounts.

    Description:
        Finds all unverified users whose `verification_expires_at` is before
        the current time, and removes the `verification_code` and
        `verification_expires_at` fields (without deleting the account).

    Args:
        _: Admin authorization dependency (not used directly).

    Returns:
        dict: Number of updated documents.
    """
    coll_users = await get_collection("users")
    result = await coll_users.update_many(
        {
            "is_verified": False,
            "verification_expires_at": {"$lt": utcnow()},
        },
        {
            "$unset": {"verification_code": "", "verification_expires_at": ""},
        },
    )
    return {"cleaned": result.modified_count}


@router.get(
    "/caches-geo-anomalies",
    summary="Count caches with missing country_id or state_id",
    description="Reports how many caches have null country_id and/or null state_id.",
    dependencies=[Depends(require_admin)],
)
async def caches_geo_anomalies(_: Annotated[bool, Depends(require_admin)]) -> dict:
    """Count caches with incomplete geographic data.

    Returns:
        dict: Counts for null country_id, null state_id, and both null.
    """
    coll = await get_collection("caches")

    total = await coll.count_documents({})
    null_country = await coll.count_documents({"country_id": None})
    null_state = await coll.count_documents({"state_id": None})
    null_both = await coll.count_documents({"country_id": None, "state_id": None})
    null_country_only = await coll.count_documents({"country_id": None, "state_id": {"$ne": None}})
    null_state_only = await coll.count_documents({"country_id": {"$ne": None}, "state_id": None})

    # Sample non-AL affected caches to understand the pattern
    sample = []
    async for doc in coll.find(
        {"country_id": None, "GC": {"$not": {"$regex": "^AL"}}},
        {"GC": 1, "title": 1, "lat": 1, "lon": 1, "location_more": 1},
    ).limit(20):
        sample.append(
            {
                "GC": doc.get("GC"),
                "title": doc.get("title"),
                "lat": doc.get("lat"),
                "lon": doc.get("lon"),
                "location_more": doc.get("location_more"),
            }
        )

    # Check how many affected caches have coordinates
    with_coords = await coll.count_documents({"country_id": None, "lat": {"$ne": None}})

    # Verify the AL-prefix hypothesis
    null_and_al = await coll.count_documents({"country_id": None, "GC": {"$regex": "^AL"}})
    null_and_not_al = await coll.count_documents(
        {"country_id": None, "GC": {"$not": {"$regex": "^AL"}}}
    )

    return {
        "total_caches": total,
        "null_country_id": null_country,
        "null_state_id": null_state,
        "null_both": null_both,
        "null_country_only": null_country_only,
        "null_state_only": null_state_only,
        "null_both_with_coords": with_coords,
        "al_prefix_hypothesis": {
            "null_and_gc_starts_with_AL": null_and_al,
            "null_and_gc_does_not_start_with_AL": null_and_not_al,
            "hypothesis_confirmed": null_and_not_al == 0,
        },
        "sample": sample,
    }


@router.get(
    "/snapshot",
    summary="System snapshot for a user",
    description="Returns global counts (caches, challenges) and user-specific stats (found caches, user_challenges by status).",
    dependencies=[Depends(require_admin)],
)
async def snapshot(
    _: Annotated[bool, Depends(require_admin)],
    user_id: str = Query(..., description="User ObjectId as string"),
) -> dict:
    """Snapshot of system state for before/after comparison.

    Args:
        user_id: User ObjectId string.

    Returns:
        dict: Global and user-scoped counts.
    """
    from bson import ObjectId

    uid = ObjectId(user_id)

    coll_caches = await get_collection("caches")
    coll_challenges = await get_collection("challenges")
    coll_found = await get_collection("found_caches")
    coll_ucs = await get_collection("user_challenges")

    total_caches = await coll_caches.count_documents({})
    total_challenges = await coll_challenges.count_documents({})
    total_found = await coll_found.count_documents({"user_id": uid})
    total_ucs = await coll_ucs.count_documents({"user_id": uid})

    # user_challenges grouped by computed_status
    pipeline: list[dict[str, Any]] = [
        {"$match": {"user_id": uid}},
        {"$group": {"_id": "$computed_status", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    uc_by_status: dict[str, int] = {}
    async for doc in coll_ucs.aggregate(pipeline):
        key = doc["_id"] if doc["_id"] is not None else "null"
        uc_by_status[key] = doc["count"]

    return {
        "global": {
            "caches": total_caches,
            "challenges": total_challenges,
        },
        "user": {
            "found_caches": total_found,
            "user_challenges": total_ucs,
            "user_challenges_by_computed_status": uc_by_status,
        },
    }


@router.get(
    "/referentials-duplicates",
    dependencies=[Depends(require_admin)],
    summary="Detect duplicate countries and states (admin)",
    description=(
        "Loads all countries and states, computes their normalized form "
        "(NFKD + lowercase + alphanumeric), and returns groups where multiple "
        "documents share the same normalized key. Useful to audit the referential "
        "after a backfill or import."
    ),
)
async def referentials_duplicates(_: Request) -> dict[str, Any]:
    """Detect duplicate country/state entries (admin).

    Returns:
        dict: Lists of duplicate groups for countries and states.
    """
    db = get_db()

    # --- Countries ---
    country_groups: dict[str, list[dict[str, Any]]] = {}
    async for doc in db.countries.find({}, {"_id": 1, "name": 1}):
        key = ReferentialMapper.normalize_name(doc.get("name"))
        entry = {"id": str(doc["_id"]), "name": doc.get("name")}
        country_groups.setdefault(key, []).append(entry)

    duplicate_countries = [
        {"normalized": key, "entries": entries}
        for key, entries in country_groups.items()
        if len(entries) > 1
    ]

    # --- States ---
    state_groups: dict[str, list[dict[str, Any]]] = {}
    async for doc in db.states.find({}, {"_id": 1, "name": 1, "country_id": 1}):
        # Key includes country_id to only flag duplicates within the same country
        key = f"{doc.get('country_id')}::{ReferentialMapper.normalize_name(doc.get('name'))}"
        entry = {
            "id": str(doc["_id"]),
            "name": doc.get("name"),
            "country_id": str(doc.get("country_id")),
        }
        state_groups.setdefault(key, []).append(entry)

    duplicate_states = [
        {"normalized": key, "entries": entries}
        for key, entries in state_groups.items()
        if len(entries) > 1
    ]

    return {
        "duplicate_countries": duplicate_countries,
        "nb_duplicate_country_groups": len(duplicate_countries),
        "duplicate_states": duplicate_states,
        "nb_duplicate_state_groups": len(duplicate_states),
    }
