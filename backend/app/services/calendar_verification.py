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

    async def verify_user_calendar(self, user_id: str, filters: CalendarFilters) -> CalendarResult:
        """
        Verify if user has completed calendar challenges.

        Args:
            user_id: The user ID to check
            filters: Optional filters for cache type and size

        Returns:
            CalendarResult with completion status for both 365 and 366 days
        """
        # Build query for found caches
        query = {"user_id": ObjectId(user_id)}

        # Resolve cache type and size names to IDs if provided
        cache_type_id = None
        cache_size_id = None

        if filters.cache_type_name:
            # Check if it's a valid ObjectId first
            try:
                potential_id = ObjectId(filters.cache_type_name)
                # Verify the ObjectId exists in cache_types
                cache_type = await self.db.cache_types.find_one({"_id": potential_id})
                if cache_type:
                    cache_type_id = potential_id
                else:
                    # ObjectId not found - return empty result
                    return self._empty_calendar_result(filters)
            except InvalidId:
                # Not a valid ObjectId, search by name OR code (case insensitive)
                cache_type = await self.db.cache_types.find_one(
                    {
                        "$or": [
                            {"name": {"$regex": f"^{filters.cache_type_name}$", "$options": "i"}},
                            {"code": {"$regex": f"^{filters.cache_type_name}$", "$options": "i"}},
                        ]
                    }
                )
                if cache_type:
                    cache_type_id = cache_type["_id"]
                else:
                    # Cache type name/code not found - return empty result
                    return self._empty_calendar_result(filters)

        if filters.cache_size_name:
            # Check if it's a valid ObjectId first
            try:
                potential_id = ObjectId(filters.cache_size_name)
                # Verify the ObjectId exists in cache_sizes
                cache_size = await self.db.cache_sizes.find_one({"_id": potential_id})
                if cache_size:
                    cache_size_id = potential_id
                else:
                    # ObjectId not found - return empty result
                    return self._empty_calendar_result(filters)
            except InvalidId:
                # Not a valid ObjectId, search by name OR code OR aliases (case insensitive)
                cache_size = await self.db.cache_sizes.find_one(
                    {
                        "$or": [
                            {"name": {"$regex": f"^{filters.cache_size_name}$", "$options": "i"}},
                            {"code": {"$regex": f"^{filters.cache_size_name}$", "$options": "i"}},
                            {
                                "aliases": {
                                    "$regex": f"^{filters.cache_size_name}$",
                                    "$options": "i",
                                }
                            },
                        ]
                    }
                )
                if cache_size:
                    cache_size_id = cache_size["_id"]
                else:
                    # Cache size name/code/alias not found - return empty result
                    return self._empty_calendar_result(filters)

        # Add cache filters if resolved
        cache_filter = {}
        if cache_type_id:
            cache_filter["type_id"] = cache_type_id
        if cache_size_id:
            cache_filter["size_id"] = cache_size_id

        # Get found caches with optional filtering
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

        # Add cache type/size filters to pipeline if needed
        if cache_filter:
            pipeline.append({"$match": {f"cache_info.{k}": v for k, v in cache_filter.items()}})

        # Project only needed fields
        pipeline.append(
            {"$project": {"found_date": 1, "cache_info.type_id": 1, "cache_info.size_id": 1}}
        )

        found_caches = await self.db.found_caches.aggregate(
            cast(Sequence[Mapping[str, Any]], pipeline)
        ).to_list(length=None)

        # Extract unique days from found dates
        completed_days_set = set()
        found_dates_count: dict[str, int] = {}

        for found_cache in found_caches:
            found_date = found_cache["found_date"]
            day_month = found_date.strftime("%m-%d")
            completed_days_set.add(day_month)

            if day_month in found_dates_count:
                found_dates_count[day_month] += 1
            else:
                found_dates_count[day_month] = 1

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
        missing_days = sorted(list(set(all_days_366) - completed_days_set))

        # Group missing days by month
        missing_days_by_month: dict[str, list[str]] = {}
        for day in missing_days:
            month = day[:2]  # Extract month part (MM from MM-DD)
            if month not in missing_days_by_month:
                missing_days_by_month[month] = []
            missing_days_by_month[month].append(day)

        # Format completed days with counts
        completed_days = [
            {"day": day, "count": found_dates_count[day]} for day in sorted(completed_days_set)
        ]

        # Calendar tours
        calendar_tours = 0
        if completed_365 == 365:
            calendar_tours = int(min(item["count"] for item in completed_days))

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
