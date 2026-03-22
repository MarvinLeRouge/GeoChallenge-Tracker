# backend/app/services/targets/target_evaluator.py
# Cache target evaluation logic for a UserChallenge.

from __future__ import annotations

from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services.query_builder import compile_and_only

from .geo_utils import build_geo_pipeline_stage
from .target_scorer import TargetScorer


class TargetEvaluator:
    """Cache target evaluation service for a UserChallenge.

    Description:
        Responsible for identifying and scoring candidate caches
        based on challenge tasks and the user profile.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize the evaluator.

        Args:
            db: MongoDB database instance.
        """
        self.db = db
        self.scorer = TargetScorer()

    async def get_username(self, user_id: ObjectId) -> str | None:
        """Retrieve the username.

        Args:
            user_id: User identifier.

        Returns:
            str | None: Username or None.
        """
        coll_users = self.db.users
        user_doc = await coll_users.find_one({"_id": user_id}, {"username": 1})
        return user_doc.get("username") if user_doc else None

    async def get_latest_progress_task_map(self, uc_id: ObjectId) -> dict[ObjectId, dict[str, Any]]:
        """Retrieve the progress map by task.

        Args:
            uc_id: UserChallenge identifier.

        Returns:
            dict: Mapping of task_id -> progress_data.
        """
        coll_progress = self.db.progress
        progress_doc = await coll_progress.find_one(
            {"user_challenge_id": uc_id}, sort=[("checked_at", -1)]
        )

        if not progress_doc:
            return {}

        task_map = {}
        for task_progress in progress_doc.get("tasks", []):
            task_id = task_progress.get("task_id")
            if task_id:
                task_map[task_id] = task_progress

        return task_map

    async def get_user_challenge_tasks(self, uc_id: ObjectId) -> list[dict[str, Any]]:
        """Retrieve the tasks of a UserChallenge.

        Args:
            uc_id: UserChallenge identifier.

        Returns:
            list: List of task documents.
        """
        coll_tasks = self.db.user_challenge_tasks
        tasks_cursor = coll_tasks.find({"user_challenge_id": uc_id}, sort=[("order", 1)])
        return await tasks_cursor.to_list(length=None)

    async def build_cache_pipeline_for_task(
        self,
        task_doc: dict[str, Any],
        username: str | None,
        user_id: ObjectId,
        geo_ctx: dict[str, Any] | None,
        limit_per_task: int,
    ) -> list[dict[str, Any]]:
        """Build the MongoDB pipeline for a task.

        Args:
            task_doc: Task document.
            username: Username (to exclude the user's own caches).
            user_id: User ID (to exclude the user's found caches).
            geo_ctx: Optional geographic context.
            limit_per_task: Result limit per task.

        Returns:
            list: MongoDB aggregation pipeline.
        """
        pipeline = []

        # Add $geoNear first if a geographic context is provided
        if geo_ctx and "radius_km" in geo_ctx:
            geo_stage = build_geo_pipeline_stage(
                geo_ctx["lat"], geo_ctx["lon"], geo_ctx["radius_km"]
            )
            pipeline.append(geo_stage)

        # Base filter
        base_match: dict[str, Any] = {
            "status": {"$in": ["active"]},  # Active caches only
        }

        # Exclude caches owned by the user
        if username:
            base_match["owner"] = {"$ne": username}

        pipeline.append({"$match": base_match})

        # Anti-join with the user's found_caches
        pipeline.extend(
            [
                {
                    "$lookup": {
                        "from": "found_caches",
                        "let": {"cache_id": "$_id"},
                        "pipeline": [
                            {
                                "$match": {
                                    "$expr": {
                                        "$and": [
                                            {"$eq": ["$cache_id", "$$cache_id"]},
                                            {"$eq": ["$user_id", user_id]},
                                        ]
                                    }
                                }
                            }
                        ],
                        "as": "found_by_user",
                    }
                },
                {"$match": {"found_by_user": {"$size": 0}}},
            ]
        )

        # Apply task filters
        task_expression = task_doc.get("expression")
        if task_expression:
            try:
                match_filters = compile_and_only(task_expression)
                if match_filters:
                    pipeline.append({"$match": match_filters})
            except Exception:
                # On compilation error, skip the filter
                pass

        # Project the required fields
        projection = {
            "_id": 1,
            "GC": 1,
            "title": 1,
            "loc": 1,
            "owner": 1,
            "difficulty": 1,
            "terrain": 1,
        }

        # Add distance_m if a geographic context is provided
        if geo_ctx and "radius_km" in geo_ctx:
            projection["distance_m"] = 1

        pipeline.append({"$project": projection})
        pipeline.append({"$limit": limit_per_task})

        return pipeline

    async def evaluate_cache_candidates(
        self,
        tasks: list[dict[str, Any]],
        progress_map: dict[ObjectId, dict[str, Any]],
        username: str | None,
        user_id: ObjectId,
        geo_ctx: dict[str, Any] | None,
        limit_per_task: int,
        hard_limit_total: int,
    ) -> dict[ObjectId, dict[str, Any]]:
        """Evaluate candidate caches for all tasks.

        Args:
            tasks: List of UserChallenge tasks.
            progress_map: Progress map by task.
            username: Username.
            user_id: User ID.
            geo_ctx: Geographic context.
            limit_per_task: Per-task limit.
            hard_limit_total: Global limit.

        Returns:
            dict: Unique caches with their matched tasks.
        """
        coll_caches = self.db.caches
        unique_by_cache = {}
        total_seen = 0

        for task_doc in tasks:
            # Skip OR/NOT tasks (complex expressions)
            if task_doc.get("expression", {}).get("type") != "and":
                continue

            # Build and execute the pipeline
            pipeline = await self.build_cache_pipeline_for_task(
                task_doc, username, user_id, geo_ctx, limit_per_task
            )

            aggregate_cursor = coll_caches.aggregate(pipeline, allowDiskUse=False)
            rows = await aggregate_cursor.to_list(length=None)

            # Process each candidate cache
            for cache_row in rows:
                cache_id = cache_row["_id"]

                # Add to the unique collection
                if cache_id not in unique_by_cache:
                    unique_by_cache[cache_id] = {
                        "cache": cache_row,
                        "matched_tasks": [],
                    }
                    total_seen += 1
                    if total_seen >= hard_limit_total:
                        break

                # Calculate task metrics
                min_count = self.scorer.get_task_constraints_min_count(task_doc)
                current_count = progress_map.get(task_doc["_id"], {}).get("current_count", 0)
                remaining = max(0, min_count - current_count)
                ratio = current_count / max(min_count, 1) if min_count > 0 else 0.0

                # Add task info
                unique_by_cache[cache_id]["matched_tasks"].append(
                    {
                        "_id": task_doc["_id"],
                        "min_count": min_count,
                        "current_count": current_count,
                        "remaining": remaining,
                        "ratio": ratio,
                    }
                )

            if total_seen >= hard_limit_total:
                break

        return unique_by_cache
