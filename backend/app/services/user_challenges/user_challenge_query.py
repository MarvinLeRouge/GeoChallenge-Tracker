# backend/app/services/user_challenges/user_challenge_query.py
# Optimized query service for UserChallenges.

from __future__ import annotations

from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from .status_calculator import StatusCalculator


class UserChallengeQuery:
    """Query service for UserChallenges.

    Description:
        Responsible for complex queries with joins, pagination,
        and filtering for UserChallenges.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize the query service.

        Args:
            db: MongoDB database instance.
        """
        self.db = db
        self.status_calculator = StatusCalculator()

    async def list_user_challenges(
        self,
        user_id: ObjectId,
        status_filter: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """List UserChallenges with pagination and filtering.

        Args:
            user_id: User identifier.
            status_filter: Effective status filter.
            page: Page number (1-based).
            page_size: Page size.

        Returns:
            dict: Paginated results with metadata.
        """
        # Build the base pipeline
        pipeline = self._build_list_pipeline(user_id, status_filter)

        # Count total
        total_count = await self._count_filtered_user_challenges(user_id, status_filter)

        # Pagination
        skip = (page - 1) * page_size
        pipeline.extend(
            [
                {"$skip": skip},
                {"$limit": page_size},
            ]
        )

        # Execute the query
        coll_ucs = self.db.user_challenges
        cursor = coll_ucs.aggregate(pipeline)
        items = []

        async for doc in cursor:
            # Calculate the effective status
            doc["effective_status"] = self.status_calculator.calculate_effective_status(
                doc.get("status"), doc.get("computed_status")
            )
            # Convert _id to string
            doc["id"] = str(doc.pop("_id"))
            items.append(doc)

        # Calculate pagination
        nb_pages = (total_count + page_size - 1) // page_size

        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "nb_pages": nb_pages,
            "nb_items": total_count,
        }

    async def get_user_challenge_detail(
        self, user_id: ObjectId, uc_id: ObjectId
    ) -> dict[str, Any] | None:
        """Retrieve the full detail of a UserChallenge.

        Args:
            user_id: User identifier.
            uc_id: UserChallenge identifier.

        Returns:
            dict | None: Enriched detail or None if not found.
        """
        pipeline: list[dict[str, Any]] = [
            # Match the specific UC
            {"$match": {"_id": uc_id, "user_id": user_id}},
            # Join with challenge
            {
                "$lookup": {
                    "from": "challenges",
                    "localField": "challenge_id",
                    "foreignField": "_id",
                    "as": "challenge",
                }
            },
            {"$unwind": "$challenge"},
            # Join with cache
            {
                "$lookup": {
                    "from": "caches",
                    "localField": "challenge.cache_id",
                    "foreignField": "_id",
                    "as": "cache",
                }
            },
            {"$unwind": {"path": "$cache", "preserveNullAndEmptyArrays": True}},
            # Full projection
            {
                "$project": {
                    "_id": 1,
                    "status": 1,
                    "computed_status": 1,
                    "manual_override": 1,
                    "override_reason": 1,
                    "overridden_at": 1,
                    "notes": 1,
                    "progress": 1,
                    "created_at": 1,
                    "updated_at": 1,
                    "challenge": {
                        "id": "$challenge._id",
                        "name": "$challenge.name",
                        "description": "$challenge.description",
                    },
                    "cache": {
                        "$cond": {
                            "if": {"$eq": ["$cache", None]},
                            "then": None,
                            "else": {
                                "id": "$cache._id",
                                "GC": "$cache.GC",
                                "difficulty": "$cache.difficulty",
                                "terrain": "$cache.terrain",
                            },
                        }
                    },
                }
            },
        ]

        coll_ucs = self.db.user_challenges
        cursor = coll_ucs.aggregate(pipeline)

        try:
            doc = await cursor.next()
            # Calculate the effective status
            doc["effective_status"] = self.status_calculator.calculate_effective_status(
                doc.get("status"), doc.get("computed_status")
            )
            # Convert _id to string
            doc["id"] = str(doc.pop("_id"))
            return doc
        except StopAsyncIteration:
            return None

    def _build_list_pipeline(
        self, user_id: ObjectId, status_filter: str | None
    ) -> list[dict[str, Any]]:
        """Build the base pipeline for the list query.

        Args:
            user_id: User identifier.
            status_filter: Status filter.

        Returns:
            list: MongoDB pipeline.
        """
        pipeline: list[dict[str, Any]] = [
            {"$match": {"user_id": user_id}},
        ]

        # Add the status filter if specified
        if status_filter:
            status_stages = self.status_calculator.build_status_filter_pipeline(status_filter)
            pipeline.extend(status_stages)

        # Joins with challenge and cache
        pipeline.extend(
            [
                # Join with challenge
                {
                    "$lookup": {
                        "from": "challenges",
                        "localField": "challenge_id",
                        "foreignField": "_id",
                        "as": "challenge",
                    }
                },
                {"$unwind": "$challenge"},
                # Join with cache
                {
                    "$lookup": {
                        "from": "caches",
                        "localField": "challenge.cache_id",
                        "foreignField": "_id",
                        "as": "cache",
                    }
                },
                {"$unwind": {"path": "$cache", "preserveNullAndEmptyArrays": True}},
                # List projection
                {
                    "$project": {
                        "_id": 1,
                        "status": 1,
                        "computed_status": 1,
                        "progress": 1,
                        "updated_at": 1,
                        "challenge": {
                            "id": "$challenge._id",
                            "name": "$challenge.name",
                        },
                        "cache": {
                            "$cond": {
                                "if": {"$eq": ["$cache", None]},
                                "then": None,
                                "else": {
                                    "id": "$cache._id",
                                    "GC": "$cache.GC",
                                    "difficulty": "$cache.difficulty",
                                    "terrain": "$cache.terrain",
                                },
                            }
                        },
                    }
                },
                # Default sort by updated_at descending
                {"$sort": {"updated_at": -1}},
            ]
        )

        return pipeline

    async def _count_filtered_user_challenges(
        self, user_id: ObjectId, status_filter: str | None
    ) -> int:
        """Count UserChallenges with filtering.

        Args:
            user_id: User identifier.
            status_filter: Status filter.

        Returns:
            int: Number of results.
        """
        pipeline: list[dict[str, Any]] = [
            {"$match": {"user_id": user_id}},
        ]

        # Add the status filter if specified
        if status_filter:
            status_stages = self.status_calculator.build_status_filter_pipeline(status_filter)
            pipeline.extend(status_stages)

        # Count
        pipeline.append({"$count": "total"})

        coll_ucs = self.db.user_challenges
        cursor = coll_ucs.aggregate(pipeline)

        try:
            result = await cursor.next()
            return result["total"]
        except StopAsyncIteration:
            return 0
