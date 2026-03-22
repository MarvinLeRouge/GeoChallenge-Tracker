# backend/app/services/gpx_import/cache_persister.py
# Optimized persistence service for caches and found caches.

from __future__ import annotations

from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError

from app.core.utils import now


class CachePersister:
    """Optimized persistence service for caches and found caches.

    Description:
        Responsible for bulk persistence of cache and found-cache data
        with error handling and conflict management.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize the persistence service.

        Args:
            db: MongoDB database instance.
        """
        self.db = db

    async def persist_caches(
        self, caches_data: list[dict[str, Any]], force_update_attributes: bool = False
    ) -> dict[str, int]:
        """Persist caches to the database using upsert.

        Args:
            caches_data: List of cache data to persist.
            force_update_attributes: Force attribute update (admin only).

        Returns:
            dict: Persistence statistics {inserted, updated, errors}.
        """
        if not caches_data:
            return {"inserted": 0, "updated": 0, "errors": 0}

        coll_caches = self.db.caches
        operations = []
        current_time = now()

        for cache_data in caches_data:
            # Prepare the upsert operation
            filter_query = {"GC": cache_data["GC"]}

            # Data to insert/update
            update_doc = {
                "$set": {
                    **cache_data,
                    "updated_at": current_time,
                },
                "$setOnInsert": {
                    "created_at": current_time,
                },
            }

            # When force_update_attributes is enabled, replace attributes even if they exist
            if force_update_attributes and "attributes" in cache_data:
                update_doc["$set"]["attributes"] = cache_data["attributes"]

            operations.append(UpdateOne(filter_query, update_doc, upsert=True))

        # Execute operations in bulk
        try:
            result = await coll_caches.bulk_write(operations, ordered=False)
            return {
                "inserted": result.upserted_count,
                "updated": result.modified_count,
                "errors": 0,
            }
        except BulkWriteError as e:
            # Handle partial errors
            inserted = e.details.get("nUpserted", 0)
            updated = e.details.get("nModified", 0)
            errors = len(e.details.get("writeErrors", []))

            return {
                "inserted": inserted,
                "updated": updated,
                "errors": errors,
            }

    async def persist_found_caches(
        self, found_caches_data: list[dict[str, Any]], user_id: ObjectId
    ) -> dict[str, int]:
        """Persist found caches to the database using upsert.

        Args:
            found_caches_data: List of found cache data.
            user_id: ID of the user who found the caches.

        Returns:
            dict: Persistence statistics {inserted, updated, errors}.
        """
        if not found_caches_data:
            return {"inserted": 0, "updated": 0, "errors": 0}

        coll_found = self.db.found_caches
        operations = []
        current_time = now()

        for found_data in found_caches_data:
            # Look up the cache ID by GC code
            cache_id = await self._get_cache_id_by_gc(found_data["GC"])
            if not cache_id:
                continue  # Skip if cache not found

            # Prepare the upsert operation
            filter_query = {
                "user_id": user_id,
                "cache_id": cache_id,
            }

            # Data to insert/update
            update_doc = {
                "$setOnInsert": {
                    "found_date": found_data["found_date"],
                    "created_at": current_time,
                },
                "$set": {
                    "updated_at": current_time,
                },
            }

            # Handle notes (optional)
            if "notes" in found_data:
                if found_data["notes"] is None:
                    update_doc["$unset"] = {"notes": ""}
                else:
                    update_doc["$set"]["notes"] = found_data["notes"]

            operations.append(UpdateOne(filter_query, update_doc, upsert=True))

        # Execute operations in bulk
        try:
            result = await coll_found.bulk_write(operations, ordered=False)
            return {
                "inserted": result.upserted_count,
                "updated": result.modified_count,
                "errors": 0,
            }
        except BulkWriteError as e:
            # Handle partial errors
            inserted = e.details.get("nUpserted", 0)
            updated = e.details.get("nModified", 0)
            errors = len(e.details.get("writeErrors", []))

            return {
                "inserted": inserted,
                "updated": updated,
                "errors": errors,
            }

    async def _get_cache_id_by_gc(self, gc_code: str) -> ObjectId | None:
        """Retrieve the cache ID by GC code.

        Args:
            gc_code: Cache GC code.

        Returns:
            ObjectId | None: Cache ID or None if not found.
        """
        coll_caches = self.db.caches
        cache_doc = await coll_caches.find_one({"GC": gc_code}, {"_id": 1})
        return cache_doc["_id"] if cache_doc else None

    async def get_existing_caches_by_gc(self, gc_codes: list[str]) -> dict[str, ObjectId]:
        """Retrieve IDs of existing caches by GC codes.

        Args:
            gc_codes: List of GC codes to look up.

        Returns:
            dict: Mapping of GC_code -> ObjectId for existing caches.
        """
        if not gc_codes:
            return {}

        coll_caches = self.db.caches
        cursor = coll_caches.find({"GC": {"$in": gc_codes}}, {"_id": 1, "GC": 1})

        result = {}
        async for doc in cursor:
            result[doc["GC"]] = doc["_id"]

        return result

    async def count_existing_found_caches(self, user_id: ObjectId, gc_codes: list[str]) -> int:
        """Count existing found caches for a user.

        Args:
            user_id: User ID.
            gc_codes: List of GC codes to check.

        Returns:
            int: Number of existing found caches.
        """
        if not gc_codes:
            return 0

        # Retrieve cache IDs
        cache_ids_map = await self.get_existing_caches_by_gc(gc_codes)
        cache_ids = list(cache_ids_map.values())

        if not cache_ids:
            return 0

        coll_found = self.db.found_caches
        return await coll_found.count_documents(
            {
                "user_id": user_id,
                "cache_id": {"$in": cache_ids},
            }
        )

    async def get_referential_counts(self) -> dict[str, int]:
        """Retrieve referential counts for statistics.

        Returns:
            dict: Counts per collection.
        """
        results = {}

        collections = ["countries", "states", "cache_types", "cache_sizes"]

        for collection_name in collections:
            collection = getattr(self.db, collection_name)
            count = await collection.count_documents({})
            results[collection_name] = count

        return results

    async def cleanup_temp_data(self, gc_codes: list[str]) -> None:
        """Clean up temporary data if needed.

        Args:
            gc_codes: Processed GC codes (for logging/debug).
        """
        # No specific cleanup at this time.
        # Can be extended to handle temporary collections.
        pass
