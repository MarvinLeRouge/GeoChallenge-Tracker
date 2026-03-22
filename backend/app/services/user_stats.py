# backend/app/services/user_stats.py
# Service for computing summary statistics for a user.

from collections.abc import Mapping, Sequence
from typing import Any, Optional, cast

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from app.api.dto.user_stats import CacheTypeStats, UserStatsOut
from app.db.mongodb import get_collection


async def get_user_stats(user_id: ObjectId, target_username: Optional[str] = None) -> UserStatsOut:
    """Compute summary statistics for a user.

    Description:
        Retrieves statistics for the current user or another user
        (if target_username is provided and the current user is an admin).
        Reuses existing collections to compute the metrics.

    Args:
        user_id (ObjectId): Current user's identifier.
        target_username (str | None): Target username (requires admin rights).

    Returns:
        UserStatsOut: Computed statistics.

    Raises:
        PermissionError: If target_username is provided without admin rights.
        ValueError: If target_username is not found.
    """
    users_coll = await get_collection("users")

    # Determine the target user
    if target_username:
        # Verify that the current user is an admin
        current_user = await users_coll.find_one({"_id": user_id}, {"role": 1})
        if not current_user or current_user.get("role") != "admin":
            raise PermissionError("Admin rights required to view other users' stats")

        # Retrieve the target user
        target_user = await users_coll.find_one({"username": target_username})
        if not target_user:
            raise ValueError(f"User '{target_username}' not found")

        target_user_id = target_user["_id"]
        username = target_user["username"]
        created_at = target_user["created_at"]
    else:
        # Current user
        current_user = await users_coll.find_one({"_id": user_id})
        if not current_user:
            raise ValueError("Current user not found")

        target_user_id = user_id
        username = current_user["username"]
        created_at = current_user["created_at"]

    # Compute total number of found caches
    found_caches_coll = await get_collection("found_caches")
    total_caches_found = await found_caches_coll.count_documents({"user_id": target_user_id})

    # Dates of first and last found cache
    first_cache = await found_caches_coll.find_one(
        {"user_id": target_user_id}, sort=[("found_date", ASCENDING)]
    )
    first_cache_found_at = first_cache["found_date"] if first_cache else None

    last_cache = await found_caches_coll.find_one(
        {"user_id": target_user_id}, sort=[("found_date", DESCENDING)]
    )
    last_cache_found_at = last_cache["found_date"] if last_cache else None

    # Challenge statistics
    user_challenges_coll = await get_collection("user_challenges")

    # Total number of challenges
    total_challenges = await user_challenges_coll.count_documents({"user_id": target_user_id})

    # Active challenges (status: accepted)
    active_challenges = await user_challenges_coll.count_documents(
        {"user_id": target_user_id, "status": "accepted"}
    )

    # Completed challenges (status: completed OR computed_status: completed)
    completed_challenges = await user_challenges_coll.count_documents(
        {
            "user_id": target_user_id,
            "$or": [{"status": "completed"}, {"computed_status": "completed"}],
        }
    )

    # Last activity: max of last found cache and last created challenge
    last_challenge = await user_challenges_coll.find_one(
        {"user_id": target_user_id}, sort=[("created_at", DESCENDING)]
    )
    last_challenge_created = last_challenge["created_at"] if last_challenge else None

    # Per-type cache statistics
    cache_types_stats = None
    try:
        # Use a MongoDB aggregation to count found caches by type.
        # found_caches.cache_id references the caches collection.
        pipeline = [
            {"$match": {"user_id": target_user_id}},
            {
                "$lookup": {
                    "from": "caches",
                    "localField": "cache_id",
                    "foreignField": "_id",
                    "as": "cache",
                }
            },
            {"$unwind": "$cache"},
            {
                "$group": {
                    "_id": "$cache.type_id",  # group by cache type_id
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"count": -1}},
        ]

        found_caches_agg = found_caches_coll.aggregate(cast(Sequence[Mapping[str, Any]], pipeline))
        type_counts = await found_caches_agg.to_list(length=None)

        if type_counts and type_counts[0]["_id"] is not None:  # verify data exists
            # Retrieve cache type details
            cache_types_coll = await get_collection("cache_types")
            type_ids = [item["_id"] for item in type_counts if item["_id"] is not None]

            if type_ids:  # verify there are IDs to look up
                cache_types = await cache_types_coll.find().to_list(length=None)
                type_map = {ct["_id"]: ct for ct in cache_types}

                # Build CacheTypeStats objects
                all_caches_type_ids = {cache_type["_id"] for cache_type in cache_types}
                found_caches_type_ids = set()
                cache_types_stats = []
                for tc in type_counts:
                    if tc["_id"] is not None and tc["_id"] in type_map:
                        found_caches_type_ids.add(tc["_id"])
                        type_info = type_map[tc["_id"]]
                        cache_types_stats.append(
                            CacheTypeStats(
                                type_id=tc["_id"],
                                type_label=type_info.get("name", "Unknown"),
                                type_code=type_info.get("code", "UNKNOWN"),
                                count=tc["count"],
                            )
                        )
                not_found_type_ids = all_caches_type_ids - found_caches_type_ids
                not_found_types = [type_map[type_id] for type_id in not_found_type_ids]
                not_found_types = sorted(not_found_types, key=lambda x: x["name"])
                for not_found_type in not_found_types:
                    cache_types_stats.append(
                        CacheTypeStats(
                            type_id=not_found_type["_id"],
                            type_label=not_found_type.get("name", "Unknown"),
                            type_code=not_found_type.get("code", "UNKNOWN"),
                            count=0,
                        )
                    )

    except Exception as e:
        # On error, continue without per-type statistics
        print(f"Error calculating cache type stats: {e}")

    # Compute last_activity_at
    last_activity_candidates = [
        dt for dt in [last_cache_found_at, last_challenge_created] if dt is not None
    ]
    last_activity_at = max(last_activity_candidates) if last_activity_candidates else None

    return UserStatsOut(
        user_id=target_user_id,
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


async def get_user_by_username(username: str) -> Optional[dict]:
    """Retrieve a user by username.

    Args:
        username (str): Username.

    Returns:
        dict | None: User document or None if not found.
    """
    users_coll = await get_collection("users")
    return await users_coll.find_one({"username": username})
