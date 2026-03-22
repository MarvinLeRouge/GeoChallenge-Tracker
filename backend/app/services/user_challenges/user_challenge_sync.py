# backend/app/services/user_challenges/user_challenge_sync.py
# Synchronization service for missing UserChallenges.

from __future__ import annotations

from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import UpdateOne

from app.core.utils import utcnow

from .status_calculator import StatusCalculator


class UserChallengeSync:
    """Synchronization service for UserChallenges.

    Description:
        Responsible for creating missing UserChallenges
        and auto-completing them based on found caches.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize the synchronization service.

        Args:
            db: MongoDB database instance.
        """
        self.db = db
        self.status_calculator = StatusCalculator()

    async def sync_user_challenges(self, user_id: ObjectId) -> dict[str, int]:
        """Create missing UserChallenges for a user.

        Args:
            user_id: User identifier.

        Returns:
            dict: Synchronization statistics.
        """
        # Step 1: Create missing UCs
        creation_stats = await self._create_missing_user_challenges(user_id)

        # Step 2: Auto-complete those whose cache has been found
        completion_stats = await self._auto_complete_found_challenges(user_id)

        # Count the final total
        total_count = await self._count_user_challenges(user_id)

        return {
            "created": creation_stats["created"],
            "existing": creation_stats["existing"],
            "auto_completed": completion_stats["updated"],
            "total_user_challenges": total_count,
        }

    async def _create_missing_user_challenges(self, user_id: ObjectId) -> dict[str, int]:
        """Create missing UserChallenges with status=pending.

        Args:
            user_id: User identifier.

        Returns:
            dict: Creation statistics.
        """
        coll_challenges = self.db.challenges
        coll_ucs = self.db.user_challenges

        # Retrieve all challenge IDs
        challenge_ids = await coll_challenges.distinct("_id")
        if not challenge_ids:
            return {"created": 0, "existing": 0}

        # Identify missing challenges
        existing_challenge_ids = set(await coll_ucs.distinct("challenge_id", {"user_id": user_id}))
        missing_challenge_ids = [cid for cid in challenge_ids if cid not in existing_challenge_ids]

        if not missing_challenge_ids:
            return {"created": 0, "existing": len(existing_challenge_ids)}

        # Prepare insert operations
        operations = []
        now = utcnow()

        for challenge_id in missing_challenge_ids:
            operations.append(
                UpdateOne(
                    {"user_id": user_id, "challenge_id": challenge_id},
                    {
                        "$setOnInsert": {
                            "user_id": user_id,
                            "challenge_id": challenge_id,
                            "status": "pending",
                            "created_at": now,
                        },
                        "$set": {"updated_at": now},
                    },
                    upsert=True,
                )
            )

        # Execute operations
        if operations:
            result = await coll_ucs.bulk_write(operations, ordered=False)
            created_count = result.upserted_count
        else:
            created_count = 0

        return {
            "created": created_count,
            "existing": len(existing_challenge_ids),
        }

    async def _auto_complete_found_challenges(self, user_id: ObjectId) -> dict[str, int]:
        """Auto-complete UCs whose cache has been found.

        Args:
            user_id: User identifier.

        Returns:
            dict: Auto-completion statistics.
        """
        # Pipeline to identify UCs to auto-complete
        pipeline: list[dict[str, Any]] = [
            # Match the user's UCs
            {"$match": {"user_id": user_id}},
            # Join with challenges
            {
                "$lookup": {
                    "from": "challenges",
                    "localField": "challenge_id",
                    "foreignField": "_id",
                    "as": "challenge",
                }
            },
            {"$unwind": "$challenge"},
            # Join with found_caches
            {
                "$lookup": {
                    "from": "found_caches",
                    "let": {"cache_id": "$challenge.cache_id", "user_id": "$user_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$cache_id", "$$cache_id"]},
                                        {"$eq": ["$user_id", "$$user_id"]},
                                    ]
                                }
                            }
                        }
                    ],
                    "as": "found",
                }
            },
            # Filter those whose cache is found but not yet completed
            {
                "$match": {
                    "$and": [
                        {"found": {"$ne": []}},  # Cache found
                        {"status": {"$ne": "completed"}},  # Not manually completed
                        {"computed_status": {"$ne": "completed"}},  # Not automatically completed
                    ]
                }
            },
            # Project only the ID
            {"$project": {"_id": 1}},
        ]

        coll_ucs = self.db.user_challenges
        cursor = coll_ucs.aggregate(pipeline)
        ucs_to_complete = [doc["_id"] async for doc in cursor]

        if not ucs_to_complete:
            return {"updated": 0}

        # Update the identified UCs
        now = utcnow()
        progress_snapshot = self.status_calculator.create_progress_snapshot(100.0)

        result = await coll_ucs.update_many(
            {"_id": {"$in": ucs_to_complete}},
            {
                "$set": {
                    "computed_status": "completed",
                    "progress": progress_snapshot,
                    "updated_at": now,
                }
            },
        )

        return {"updated": result.modified_count}

    async def _count_user_challenges(self, user_id: ObjectId) -> int:
        """Count the total number of UserChallenges for a user.

        Args:
            user_id: User identifier.

        Returns:
            int: Total number of UserChallenges.
        """
        coll_ucs = self.db.user_challenges
        return await coll_ucs.count_documents({"user_id": user_id})

    async def reset_user_challenge_status(self, user_id: ObjectId, uc_id: ObjectId) -> bool:
        """Reset a UserChallenge to its default state.

        Args:
            user_id: User identifier.
            uc_id: UserChallenge identifier.

        Returns:
            bool: True if the reset succeeded.
        """
        coll_ucs = self.db.user_challenges
        now = utcnow()

        result = await coll_ucs.update_one(
            {"_id": uc_id, "user_id": user_id},
            {
                "$set": {
                    "status": "pending",
                    "updated_at": now,
                },
                "$unset": {
                    "computed_status": "",
                    "progress": "",
                    "manual_override": "",
                    "override_reason": "",
                    "overridden_at": "",
                    "notes": "",
                },
            },
        )

        return result.modified_count > 0
