"""Service for matrix D/T verification functionality."""

from collections.abc import Mapping, Sequence
from typing import Any, cast

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.dto.calendar_verification import MatrixFilters, MatrixResult
from app.shared.constants import MATRIX_DT_TOTAL_COMBINATIONS


class MatrixVerificationService:
    """Service to verify user's matrix D/T completion based on found caches."""

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
        user_id: str, cache_type_id: ObjectId | None, cache_size_id: ObjectId | None
    ) -> list[dict[str, Any]]:
        """Build the aggregation pipeline fetching a user's found caches, with filters.

        Args:
            user_id: The user ID to check.
            cache_type_id: Resolved cache type filter (optional).
            cache_size_id: Resolved cache size filter (optional).

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

        pipeline.append(
            {
                "$project": {
                    "cache_info.difficulty": 1,
                    "cache_info.terrain": 1,
                    "cache_info.type_id": 1,
                    "cache_info.size_id": 1,
                }
            }
        )
        return pipeline

    @staticmethod
    def _extract_dt_combinations(
        found_caches: list[dict[str, Any]],
    ) -> tuple[set[tuple[float, float]], dict[tuple[float, float], int]]:
        """Extract unique D/T combinations (and their find counts) from found caches.

        Args:
            found_caches: Aggregated found-cache docs (with `cache_info`).

        Returns:
            tuple: `(completed_combinations_set, dt_combinations_count)`.
        """
        completed_combinations_set: set[tuple[float, float]] = set()
        dt_combinations_count: dict[tuple[float, float], int] = {}

        for found_cache in found_caches:
            cache_info = found_cache["cache_info"]
            difficulty = float(cache_info["difficulty"])
            terrain = float(cache_info["terrain"])

            # Round to nearest 0.5 to ensure consistency
            difficulty = round(difficulty * 2) / 2
            terrain = round(terrain * 2) / 2

            dt_combo = (difficulty, terrain)
            completed_combinations_set.add(dt_combo)

            if dt_combo in dt_combinations_count:
                dt_combinations_count[dt_combo] += 1
            else:
                dt_combinations_count[dt_combo] = 1

        return completed_combinations_set, dt_combinations_count

    @staticmethod
    def _group_missing_by_difficulty(
        missing_combinations: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        """Group missing D/T combinations by difficulty.

        Args:
            missing_combinations: `[{"difficulty": ..., "terrain": ...}, ...]`.

        Returns:
            dict: `{difficulty_str: [{"terrain": ...}, ...]}`.
        """
        missing_combinations_by_difficulty: dict[str, list[dict[str, Any]]] = {}
        for combo in missing_combinations:
            difficulty_str = str(combo["difficulty"])
            if difficulty_str not in missing_combinations_by_difficulty:
                missing_combinations_by_difficulty[difficulty_str] = []
            missing_combinations_by_difficulty[difficulty_str].append({"terrain": combo["terrain"]})
        return missing_combinations_by_difficulty

    @staticmethod
    def _compute_matrix_tours(
        completed_count: int, completed_combinations: list[dict[str, Any]]
    ) -> tuple[int, int, float]:
        """Compute the matrix-tours count and next-round progress.

        Description:
            Only meaningful once all combinations are completed at least once
            (`completed_count == MATRIX_DT_TOTAL_COMBINATIONS`).

        Args:
            completed_count: Number of distinct completed D/T combinations.
            completed_combinations: `[{"difficulty", "terrain", "count"}, ...]`.

        Returns:
            tuple[int, int, float]: `(matrix_tours, next_round_completed_count,
                next_round_completion_rate)`.
        """
        if completed_count != MATRIX_DT_TOTAL_COMBINATIONS:
            return 0, completed_count, completed_count / MATRIX_DT_TOTAL_COMBINATIONS

        matrix_tours = int(min(item["count"] for item in completed_combinations))
        next_round_completed_count = len(
            [item for item in completed_combinations if item["count"] > matrix_tours]
        )
        next_round_completion_rate = next_round_completed_count / MATRIX_DT_TOTAL_COMBINATIONS
        return matrix_tours, next_round_completed_count, next_round_completion_rate

    async def verify_user_matrix(self, user_id: str, filters: MatrixFilters) -> MatrixResult:
        """
        Verify if user has completed matrix D/T challenge.

        Args:
            user_id: The user ID to check
            filters: Optional filters for cache type and size

        Returns:
            MatrixResult with completion status for 9x9 D/T matrix
        """
        cache_type_id, type_not_found = await self._resolve_cache_type_id(filters.cache_type_name)
        if type_not_found:
            return self._empty_matrix_result(filters)

        cache_size_id, size_not_found = await self._resolve_cache_size_id(filters.cache_size_name)
        if size_not_found:
            return self._empty_matrix_result(filters)

        pipeline = self._build_found_caches_pipeline(user_id, cache_type_id, cache_size_id)
        found_caches = await self.db.found_caches.aggregate(
            cast(Sequence[Mapping[str, Any]], pipeline)
        ).to_list(length=None)

        completed_combinations_set, dt_combinations_count = self._extract_dt_combinations(
            found_caches
        )

        # Generate all possible D/T combinations (9x9 matrix)
        all_combinations = self._generate_all_dt_combinations()
        all_combinations_set = set(all_combinations)

        # Calculate completion
        completed_count = len(completed_combinations_set.intersection(all_combinations_set))
        completion_rate = completed_count / MATRIX_DT_TOTAL_COMBINATIONS

        # Find missing combinations
        missing_combinations_set = all_combinations_set - completed_combinations_set
        missing_combinations = [
            {"difficulty": combo[0], "terrain": combo[1]}
            for combo in sorted(missing_combinations_set)
        ]
        missing_combinations_by_difficulty = self._group_missing_by_difficulty(missing_combinations)

        # Format completed combinations with counts
        completed_combinations = [
            {"difficulty": combo[0], "terrain": combo[1], "count": dt_combinations_count[combo]}
            for combo in sorted(completed_combinations_set)
        ]

        matrix_tours, next_round_completed_count, next_round_completion_rate = (
            self._compute_matrix_tours(completed_count, completed_combinations)
        )

        # Use the filter names directly (already resolved above)
        cache_type_name = filters.cache_type_name if cache_type_id else None
        cache_size_name = filters.cache_size_name if cache_size_id else None

        return MatrixResult(
            completed_combinations_count=completed_count,
            completion_rate=completion_rate,
            missing_combinations=missing_combinations,
            missing_combinations_by_difficulty=missing_combinations_by_difficulty,
            completed_combinations_details=completed_combinations,
            cache_type_filter=cache_type_name,
            cache_size_filter=cache_size_name,
            matrix_tours=matrix_tours,
            next_round_completed_count=next_round_completed_count,
            next_round_completion_rate=next_round_completion_rate,
        )

    def _generate_all_dt_combinations(self) -> list[tuple[float, float]]:
        """
        Generate list of all D/T combinations for 9x9 matrix.

        Returns:
            List of (difficulty, terrain) tuples from 1.0 to 5.0 by 0.5
        """
        combinations = []

        for difficulty in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]:
            for terrain in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]:
                combinations.append((difficulty, terrain))

        return combinations

    def _empty_matrix_result(self, filters: MatrixFilters) -> MatrixResult:
        """
        Return empty matrix result when filters don't match any cache types/sizes.

        Args:
            filters: The applied filters

        Returns:
            MatrixResult with zero completions
        """
        all_combinations = self._generate_all_dt_combinations()
        missing_combinations: list[dict[str, float]] = [
            {"difficulty": combo[0], "terrain": combo[1]} for combo in all_combinations
        ]

        # Group all combinations as missing by difficulty
        missing_combinations_by_difficulty: dict[str, list[dict[str, float]]] = {}
        for combo in missing_combinations:
            difficulty_str = str(combo["difficulty"])
            if difficulty_str not in missing_combinations_by_difficulty:
                missing_combinations_by_difficulty[difficulty_str] = []
            missing_combinations_by_difficulty[difficulty_str].append({"terrain": combo["terrain"]})

        return MatrixResult(
            completed_combinations_count=0,
            completion_rate=0.0,
            missing_combinations=missing_combinations,
            missing_combinations_by_difficulty=missing_combinations_by_difficulty,
            completed_combinations_details=[],
            cache_type_filter=filters.cache_type_name,
            cache_size_filter=filters.cache_size_name,
            next_round_completed_count=0,
            next_round_completion_rate=0,
        )
