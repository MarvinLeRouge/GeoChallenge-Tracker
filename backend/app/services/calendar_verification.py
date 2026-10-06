"""Service for calendar verification functionality."""

from collections.abc import Mapping, Sequence
from typing import Any, cast

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.dto.calendar_verification import CalendarFilters, CalendarResult


class CalendarVerificationService:
    """Service to verify user's calendar completion based on found caches."""

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
            {"$project": {"found_date": 1, "cache_info.type_id": 1, "cache_info.size_id": 1}}
        )
        return pipeline

    @staticmethod
    def _extract_day_combinations(
        found_caches: list[dict[str, Any]],
    ) -> tuple[set[str], dict[str, int]]:
        """Extract unique (MM-DD) days, and their find counts, from found caches.

        Args:
            found_caches: Aggregated found-cache docs.

        Returns:
            tuple: `(completed_days_set, found_dates_count)`.
        """
        completed_days_set: set[str] = set()
        found_dates_count: dict[str, int] = {}

        for found_cache in found_caches:
            found_date = found_cache["found_date"]
            day_month = found_date.strftime("%m-%d")
            completed_days_set.add(day_month)

            if day_month in found_dates_count:
                found_dates_count[day_month] += 1
            else:
                found_dates_count[day_month] = 1

        return completed_days_set, found_dates_count

    @staticmethod
    def _group_missing_days_by_month(missing_days: list[str]) -> dict[str, list[str]]:
        """Group missing (MM-DD) days by month.

        Args:
            missing_days: Sorted list of missing "MM-DD" days.

        Returns:
            dict: `{month: [day, ...]}`.
        """
        missing_days_by_month: dict[str, list[str]] = {}
        for day in missing_days:
            month = day[:2]  # Extract month part (MM from MM-DD)
            if month not in missing_days_by_month:
                missing_days_by_month[month] = []
            missing_days_by_month[month].append(day)
        return missing_days_by_month

    @staticmethod
    def _compute_calendar_tours(completed_365: int, completed_days: list[dict[str, Any]]) -> int:
        """Compute the calendar-tours count.

        Description:
            Only meaningful once all 365 days are completed at least once.

        Args:
            completed_365: Number of distinct completed days (365-day scenario).
            completed_days: `[{"day", "count"}, ...]`.

        Returns:
            int: Calendar tours (0 if not all 365 days are completed yet).
        """
        if completed_365 != 365:
            return 0
        return int(min(item["count"] for item in completed_days))

    async def verify_user_calendar(self, user_id: str, filters: CalendarFilters) -> CalendarResult:
        """
        Verify if user has completed calendar challenges.

        Args:
            user_id: The user ID to check
            filters: Optional filters for cache type and size

        Returns:
            CalendarResult with completion status for both 365 and 366 days
        """
        cache_type_id, type_not_found = await self._resolve_cache_type_id(filters.cache_type_name)
        if type_not_found:
            return self._empty_calendar_result(filters)

        cache_size_id, size_not_found = await self._resolve_cache_size_id(filters.cache_size_name)
        if size_not_found:
            return self._empty_calendar_result(filters)

        pipeline = self._build_found_caches_pipeline(user_id, cache_type_id, cache_size_id)
        found_caches = await self.db.found_caches.aggregate(
            cast(Sequence[Mapping[str, Any]], pipeline)
        ).to_list(length=None)

        completed_days_set, found_dates_count = self._extract_day_combinations(found_caches)

        # Generate all possible days
        all_days_365 = self._generate_all_days(include_leap_day=False)
        all_days_366 = self._generate_all_days(include_leap_day=True)

        # Calculate completion for 365 days
        completed_365 = len(completed_days_set.intersection(set(all_days_365)))
        completion_rate_365 = completed_365 / 365

        # Calculate completion for 366 days
        completed_366 = len(completed_days_set.intersection(set(all_days_366)))
        completion_rate_366 = completed_366 / 366

        # Find missing days (missing in both 365 and 366 day scenarios)
        missing_days = sorted(set(all_days_366) - completed_days_set)

        missing_days_by_month = self._group_missing_days_by_month(missing_days)

        # Format completed days with counts
        completed_days = [
            {"day": day, "count": found_dates_count[day]} for day in sorted(completed_days_set)
        ]

        calendar_tours = self._compute_calendar_tours(completed_365, completed_days)

        # Use the filter names directly (already resolved above)
        cache_type_name = filters.cache_type_name if cache_type_id else None
        cache_size_name = filters.cache_size_name if cache_size_id else None

        return CalendarResult(
            completed_days_365=completed_365,
            completion_rate_365=completion_rate_365,
            completed_days_366=completed_366,
            completion_rate_366=completion_rate_366,
            missing_days=missing_days,
            missing_days_by_month=missing_days_by_month,
            completed_days=completed_days,
            cache_type_filter=cache_type_name,
            cache_size_filter=cache_size_name,
            calendar_tours=calendar_tours,
        )

    def _generate_all_days(self, include_leap_day: bool = True) -> list[str]:
        """
        Generate list of all days in MM-DD format.

        Args:
            include_leap_day: Whether to include February 29th

        Returns:
            List of day strings in MM-DD format
        """
        days = []

        # Days per month (non-leap year)
        days_per_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

        # Add leap day if requested
        if include_leap_day:
            days_per_month[1] = 29

        for month in range(1, 13):
            for day in range(1, days_per_month[month - 1] + 1):
                days.append(f"{month:02d}-{day:02d}")

        return days

    def _empty_calendar_result(self, filters: CalendarFilters) -> CalendarResult:
        """
        Return empty calendar result when filters don't match any cache types/sizes.

        Args:
            filters: The applied filters

        Returns:
            CalendarResult with zero completions
        """
        all_days_366 = self._generate_all_days(include_leap_day=True)

        # Group all days as missing by month
        missing_days_by_month: dict[str, list[str]] = {}
        for day in all_days_366:
            month = day[:2]  # Extract month part (MM from MM-DD)
            if month not in missing_days_by_month:
                missing_days_by_month[month] = []
            missing_days_by_month[month].append(day)

        return CalendarResult(
            completed_days_365=0,
            completion_rate_365=0.0,
            completed_days_366=0,
            completion_rate_366=0.0,
            missing_days=all_days_366,
            missing_days_by_month=missing_days_by_month,
            completed_days=[],
            cache_type_filter=filters.cache_type_name,
            cache_size_filter=filters.cache_size_name,
        )
