# backend/app/services/base_verification_service.py
# Shared behavior for calendar/matrix verification services, factored out of
# CalendarVerificationService and MatrixVerificationService to remove duplication.

from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase


class BaseVerificationService:
    """Shared behavior for challenge verification services.

    Description:
        Hosts the cache-type/cache-size filter resolution and the found-caches
        aggregation pipeline builder common to every verification service
        (calendar, matrix). Subclasses provide their own `$project` fields to
        `_build_found_caches_pipeline`, since that's the only part of the
        pipeline that differs between them.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def _resolve_cache_type_id(
        self, cache_type_name: str | None
    ) -> tuple[ObjectId | None, bool]:
        """Resolve a cache type name/code/ObjectId string to its ObjectId.

        Args:
            cache_type_name: Cache type ObjectId string, name, or code (optional).

        Returns:
            tuple[ObjectId | None, bool]: `(resolved_id, not_found)`. `not_found` is
                True when a filter was requested but couldn't be resolved to an
                existing type.
        """
        if not cache_type_name:
            return None, False

        try:
            potential_id = ObjectId(cache_type_name)
            cache_type = await self.db.cache_types.find_one({"_id": potential_id})
            if cache_type:
                return potential_id, False
            return None, True
        except InvalidId:
            cache_type = await self.db.cache_types.find_one(
                {
                    "$or": [
                        {"name": {"$regex": f"^{cache_type_name}$", "$options": "i"}},
                        {"code": {"$regex": f"^{cache_type_name}$", "$options": "i"}},
                    ]
                }
            )
            if cache_type:
                return cache_type["_id"], False
            return None, True

    async def _resolve_cache_size_id(
        self, cache_size_name: str | None
    ) -> tuple[ObjectId | None, bool]:
        """Resolve a cache size name/code/alias/ObjectId string to its ObjectId.

        Args:
            cache_size_name: Cache size ObjectId string, name, code, or alias (optional).

        Returns:
            tuple[ObjectId | None, bool]: `(resolved_id, not_found)`. `not_found` is
                True when a filter was requested but couldn't be resolved to an
                existing size.
        """
        if not cache_size_name:
            return None, False

        try:
            potential_id = ObjectId(cache_size_name)
            cache_size = await self.db.cache_sizes.find_one({"_id": potential_id})
            if cache_size:
                return potential_id, False
            return None, True
        except InvalidId:
            cache_size = await self.db.cache_sizes.find_one(
                {
                    "$or": [
                        {"name": {"$regex": f"^{cache_size_name}$", "$options": "i"}},
                        {"code": {"$regex": f"^{cache_size_name}$", "$options": "i"}},
                        {
                            "aliases": {
                                "$regex": f"^{cache_size_name}$",
                                "$options": "i",
                            }
                        },
                    ]
                }
            )
            if cache_size:
                return cache_size["_id"], False
            return None, True

    @staticmethod
    def _build_found_caches_pipeline(
        user_id: str,
        cache_type_id: ObjectId | None,
        cache_size_id: ObjectId | None,
        project_fields: dict[str, int],
    ) -> list[dict[str, Any]]:
        """Build the aggregation pipeline fetching a user's found caches, with filters.

        Args:
            user_id: The user ID to check.
            cache_type_id: Resolved cache type filter (optional).
            cache_size_id: Resolved cache size filter (optional).
            project_fields: Fields to keep in the final `$project` stage
                (the only part of the pipeline specific to each verification
                service).

        Returns:
            list[dict]: Aggregation pipeline on `found_caches`.
        """
        query = {"user_id": ObjectId(user_id)}

        cache_filter: dict[str, Any] = {}
        if cache_type_id:
            cache_filter["type_id"] = cache_type_id
        if cache_size_id:
            cache_filter["size_id"] = cache_size_id

        pipeline: list[dict[str, Any]] = [
            {"$match": query},
            {
                "$lookup": {
                    "from": "caches",
                    "localField": "cache_id",
                    "foreignField": "_id",
                    "as": "cache_info",
                }
            },
            {"$unwind": "$cache_info"},
        ]

        if cache_filter:
            pipeline.append({"$match": {f"cache_info.{k}": v for k, v in cache_filter.items()}})

        pipeline.append({"$project": project_fields})
        return pipeline
