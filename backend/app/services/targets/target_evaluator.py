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

        # Base filter — exclude only explicitly disabled/archived caches
        base_match: dict[str, Any] = {
            "status": {"$not": {"$in": ["disabled", "archived"]}},
        }

        # Exclude caches owned by the user
        if username:
            base_match["owner"] = {"$ne": username}

        pipeline.append({"$match": base_match})

        # Apply task filters before the $lookup to allow index usage on caches
        task_expression = task_doc.get("expression")
        agg_spec = None
        match_filters: dict[str, Any] = {}
        if task_expression:
            try:
                _sig, match_filters, supported, _notes, agg_spec = compile_and_only(task_expression)
                if supported and match_filters:
                    pipeline.append({"$match": match_filters})
                if not supported:
                    agg_spec = None
            except Exception:
                match_filters = {}
                agg_spec = None

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

        # For dt_matrix tasks: enforce D/T bounds then exclude covered cells
        if agg_spec and agg_spec.get("kind") == "dt_matrix":
            max_d = float(agg_spec.get("max_difficulty", 5.0))
            max_t = float(agg_spec.get("max_terrain", 5.0))
            pipeline.append(
                {
                    "$match": {
                        "difficulty": {"$gte": 1.0, "$lte": max_d},
                        "terrain": {"$gte": 1.0, "$lte": max_t},
                    }
                }
            )
            covered = await self._get_covered_dt_cells(user_id, match_filters or {}, agg_spec)
            if covered:
                pipeline.append(
                    {"$match": {"$nor": [{"difficulty": d, "terrain": t} for d, t in covered]}}
                )

        # Resolve cache type code via lookup
        pipeline.extend(
            [
                {
                    "$lookup": {
                        "from": "cache_types",
                        "localField": "type_id",
                        "foreignField": "_id",
                        "as": "_ct",
                    }
                },
                {
                    "$addFields": {
                        "type_code": {
                            "$toLower": {"$ifNull": [{"$arrayElemAt": ["$_ct.code", 0]}, "unknown"]}
                        }
                    }
                },
            ]
        )

        # Project the required fields
        projection = {
            "_id": 1,
            "GC": 1,
            "title": 1,
            "loc": 1,
            "owner": 1,
            "difficulty": 1,
            "terrain": 1,
            "type_code": 1,
        }

        # Add distance_m if a geographic context is provided
        if geo_ctx and "radius_km" in geo_ctx:
            projection["distance_m"] = 1

        pipeline.append({"$project": projection})
        pipeline.append({"$limit": limit_per_task})

        return pipeline

    async def _get_covered_dt_cells(
        self,
        user_id: ObjectId,
        match_filters: dict[str, Any],
        agg_spec: dict[str, Any],
    ) -> set[tuple[float, float]]:
        """Return (difficulty, terrain) pairs already covered by the user for a dt_matrix task.

        Args:
            user_id: User identifier.
            match_filters: Cache-level match conditions (same format as compile_and_only output).
            agg_spec: Aggregate spec with ``max_difficulty`` and ``max_terrain``.

        Returns:
            set: Covered (difficulty, terrain) pairs within the matrix bounds.
        """
        fc = self.db.found_caches
        pipeline: list[dict[str, Any]] = [
            {"$match": {"user_id": user_id}},
            {
                "$lookup": {
                    "from": "caches",
                    "localField": "cache_id",
                    "foreignField": "_id",
                    "as": "cache",
                }
            },
            {"$unwind": "$cache"},
        ]

        # Apply match_filters on cache.* fields (same pattern as progress service)
        conds: list[dict[str, Any]] = []
        for field, cond in match_filters.items():
            if isinstance(cond, list):
                for c in cond:
                    conds.append({f"cache.{field}": c})
            else:
                conds.append({f"cache.{field}": cond})
        if conds:
            pipeline.append({"$match": {"$and": conds}})

        pipeline.append({"$group": {"_id": {"d": "$cache.difficulty", "t": "$cache.terrain"}}})

        rows = await fc.aggregate(pipeline, allowDiskUse=False).to_list(length=None)

        max_d = float(agg_spec.get("max_difficulty", 5.0))
        max_t = float(agg_spec.get("max_terrain", 5.0))
        d_values = {round(1.0 + i * 0.5, 1) for i in range(round((max_d - 1.0) / 0.5) + 1)}
        t_values = {round(1.0 + i * 0.5, 1) for i in range(round((max_t - 1.0) / 0.5) + 1)}

        covered: set[tuple[float, float]] = set()
        for r in rows:
            d = r["_id"].get("d")
            t = r["_id"].get("t")
            if d is not None and t is not None:
                dr = round(float(d), 1)
                tr = round(float(t), 1)
                if dr in d_values and tr in t_values:
                    covered.add((dr, tr))

        return covered

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
            # Skip OR/NOT tasks (complex expressions) — expression uses "kind", not "type"
            if task_doc.get("expression", {}).get("kind") != "and":
                continue

            # Skip fully completed tasks — no point in finding more candidates
            task_progress = progress_map.get(task_doc["_id"], {})
            if task_progress.get("percent", 0) >= 100:
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
                task_progress = progress_map.get(task_doc["_id"], {})
                ratio = task_progress.get("percent", 0.0) / 100.0

                # Add task info
                unique_by_cache[cache_id]["matched_tasks"].append(
                    {
                        "_id": task_doc["_id"],
                        "ratio": ratio,
                    }
                )

            if total_seen >= hard_limit_total:
                break

        return unique_by_cache
