# backend/app/services/user_stats.py
# Service for computing summary statistics for a user.

from collections.abc import Mapping, Sequence
from typing import Any, cast

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from app.api.dto.user_stats import CacheTypeStats, UserStatsOut
from app.core.bson_utils import PyObjectId
from app.db.mongodb import get_collection


async def _resolve_target_user(
    users_coll: Any, user_id: ObjectId, target_user_id: ObjectId | None
) -> tuple[ObjectId, dict[str, Any]]:
    """Resolve the effective user to compute stats for, raising if not found.

    Args:
        users_coll: `users` collection.
        user_id: Current user's identifier.
        target_user_id: Target user identifier (admin route), if any.

    Returns:
        tuple[ObjectId, dict]: `(effective_id, user_doc)`.

    Raises:
        ValueError: If the target user is not found.
    """
    effective_id = target_user_id if target_user_id is not None else user_id
    user_doc = await users_coll.find_one({"_id": effective_id})
    if not user_doc:
        raise ValueError(f"User '{effective_id}' not found")
    return effective_id, user_doc


async def _get_found_cache_date_bounds(found_caches_coll: Any, effective_id: ObjectId) -> tuple:
    """Get the first and last found-cache dates for a user.

    Args:
        found_caches_coll: `found_caches` collection.
        effective_id: User identifier.

    Returns:
        tuple: `(first_cache_found_at, last_cache_found_at)`.
    """
    first_cache = await found_caches_coll.find_one(
        {"user_id": effective_id}, sort=[("found_date", ASCENDING)]
    )
    last_cache = await found_caches_coll.find_one(
        {"user_id": effective_id}, sort=[("found_date", DESCENDING)]
    )
    return (
        first_cache["found_date"] if first_cache else None,
        last_cache["found_date"] if last_cache else None,
    )


async def _get_challenge_stats(user_challenges_coll: Any, effective_id: ObjectId) -> tuple:
    """Compute challenge counts and the last challenge's creation date.

    Args:
        user_challenges_coll: `user_challenges` collection.
        effective_id: User identifier.

    Returns:
        tuple: `(total_challenges, active_challenges, completed_challenges,
            last_challenge_created)`.
    """
    total_challenges = await user_challenges_coll.count_documents({"user_id": effective_id})
    active_challenges = await user_challenges_coll.count_documents(
        {"user_id": effective_id, "status": "accepted"}
    )
    completed_challenges = await user_challenges_coll.count_documents(
        {
            "user_id": effective_id,
            "$or": [{"status": "completed"}, {"computed_status": "completed"}],
        }
    )

    last_challenge = await user_challenges_coll.find_one(
        {"user_id": effective_id}, sort=[("created_at", DESCENDING)]
    )
    last_challenge_created = last_challenge["created_at"] if last_challenge else None

    return total_challenges, active_challenges, completed_challenges, last_challenge_created


async def _fetch_cache_type_counts(
    found_caches_coll: Any, effective_id: ObjectId
) -> list[dict[str, Any]]:
    """Fetch found-cache counts grouped by cache type.

    Args:
        found_caches_coll: `found_caches` collection.
        effective_id: User identifier.

    Returns:
        list[dict]: `[{"_id": type_id, "count": int}, ...]`, sorted by count desc.
    """
    pipeline: list[Mapping[str, Any]] = [
        {"$match": {"user_id": effective_id}},
        {
            "$lookup": {
                "from": "caches",
                "localField": "cache_id",
                "foreignField": "_id",
                "as": "cache",
            }
        },
        {"$unwind": "$cache"},
        {"$group": {"_id": "$cache.type_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    return await found_caches_coll.aggregate(cast(Sequence[Mapping[str, Any]], pipeline)).to_list(
        length=None
    )


def _build_cache_type_stats(
    type_counts: list[dict[str, Any]], cache_types: list[dict[str, Any]]
) -> list[CacheTypeStats]:
    """Build the per-type cache stats list, including zero-count types.

    Args:
        type_counts: `[{"_id": type_id, "count": int}, ...]`.
        cache_types: All `cache_types` documents.

    Returns:
        list[CacheTypeStats]: Found types first (as counted), then zero-count types.
    """
    type_map = {ct["_id"]: ct for ct in cache_types}
    all_type_ids = {ct["_id"] for ct in cache_types}
    found_type_ids: set[ObjectId] = set()
    cache_types_stats: list[CacheTypeStats] = []

    for tc in type_counts:
        if tc["_id"] is not None and tc["_id"] in type_map:
            found_type_ids.add(tc["_id"])
            info = type_map[tc["_id"]]
            cache_types_stats.append(
                CacheTypeStats(
                    type_id=tc["_id"],
                    type_label=info.get("name", "Unknown"),
                    type_code=info.get("code", "UNKNOWN"),
                    count=tc["count"],
                )
            )

    for type_id in sorted(all_type_ids - found_type_ids, key=lambda oid: str(oid)):
        info = type_map[type_id]
        cache_types_stats.append(
            CacheTypeStats(
                type_id=type_id,
                type_label=info.get("name", "Unknown"),
                type_code=info.get("code", "UNKNOWN"),
                count=0,
            )
        )

    return cache_types_stats


async def _compute_cache_type_stats(
    found_caches_coll: Any, effective_id: ObjectId
) -> list[CacheTypeStats] | None:
    """Compute per-cache-type stats for a user, swallowing errors (returns None).

    Args:
        found_caches_coll: `found_caches` collection.
        effective_id: User identifier.

    Returns:
        list[CacheTypeStats] | None: Stats, or None if none found / on error.
    """
    try:
        type_counts = await _fetch_cache_type_counts(found_caches_coll, effective_id)

        if not (type_counts and type_counts[0]["_id"] is not None):
            return None

        type_ids = [item["_id"] for item in type_counts if item["_id"] is not None]
        if not type_ids:
            return None

        cache_types_coll = await get_collection("cache_types")
        cache_types = await cache_types_coll.find().to_list(length=None)
        return _build_cache_type_stats(type_counts, cache_types)

    except Exception as e:
        print(f"Error calculating cache type stats: {e}")
        return None


async def get_user_stats(
    user_id: ObjectId,
    target_user_id: ObjectId | None = None,
) -> UserStatsOut:
    """Compute summary statistics for a user.

    Description:
        Retrieves statistics for the given user. Pass ``target_user_id`` to
        compute stats for a different user (admin use — access control is
        handled at the route layer).

    Args:
        user_id (ObjectId): Current user's identifier (used when no target is specified).
        target_user_id (ObjectId | None): Target user identifier (admin route).

    Returns:
        UserStatsOut: Computed statistics.

    Raises:
        ValueError: If the target user is not found.
    """
    users_coll = await get_collection("users")
    effective_id, user_doc = await _resolve_target_user(users_coll, user_id, target_user_id)

    username: str = user_doc["username"]
    created_at = user_doc["created_at"]

    # Total found caches
    found_caches_coll = await get_collection("found_caches")
    total_caches_found = await found_caches_coll.count_documents({"user_id": effective_id})

    # First / last found cache dates
    first_cache_found_at, last_cache_found_at = await _get_found_cache_date_bounds(
        found_caches_coll, effective_id
    )

    # Challenge statistics
    user_challenges_coll = await get_collection("user_challenges")
    (
        total_challenges,
        active_challenges,
        completed_challenges,
        last_challenge_created,
    ) = await _get_challenge_stats(user_challenges_coll, effective_id)

    # Per-type cache statistics
    cache_types_stats = await _compute_cache_type_stats(found_caches_coll, effective_id)

    last_activity_candidates = [
        dt for dt in [last_cache_found_at, last_challenge_created] if dt is not None
    ]
    last_activity_at = max(last_activity_candidates) if last_activity_candidates else None

    return UserStatsOut(
        user_id=PyObjectId(effective_id),
        username=username,
        total_caches_found=total_caches_found,
        total_challenges=total_challenges,
        active_challenges=active_challenges,
        completed_challenges=completed_challenges,
        first_cache_found_at=first_cache_found_at,
        last_cache_found_at=last_cache_found_at,
        created_at=created_at,
        last_activity_at=last_activity_at,
        cache_types_stats=cache_types_stats,
    )
