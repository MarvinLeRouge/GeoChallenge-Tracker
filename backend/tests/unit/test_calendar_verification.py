"""Tests for calendar verification functionality."""

from datetime import datetime

import pytest
from bson import ObjectId

from app.api.dto.calendar_verification import CalendarFilters
from app.services.calendar_verification import CalendarVerificationService


class TestCalendarVerificationService:
    """Test calendar verification service."""

    @pytest.fixture
    def mock_db(self):
        """Mock database for testing."""

        class MockAsyncCursor:
            """Mock async cursor for aggregate().to_list()."""

            def __init__(self, data):
                self.data = data

            async def to_list(self, length=None):
                return self.data

        class MockCollection:
            def __init__(self, data):
                self.data = data

            async def find_one(self, query):
                # Handle cache_types and cache_sizes lookups
                if "cache_types" in str(self.__class__.__name__):
                    return {"_id": ObjectId(), "name": "Traditional Cache", "code": "TRAD"}
                elif "cache_sizes" in str(self.__class__.__name__):
                    return {"_id": ObjectId(), "name": "Regular", "code": "REG", "aliases": []}
                return None

            def aggregate(self, pipeline):
                """Return mock aggregate results."""
                # Return empty results by default (no found caches)
                return MockAsyncCursor([])

        class MockDB:
            def __init__(self):
                self.found_caches = MockCollection([])
                self.cache_types = MockCollection([])
                self.cache_sizes = MockCollection([])

        return MockDB()

    def test_generate_all_days_365(self, mock_db):
        """Test generation of 365 days."""
        service = CalendarVerificationService(mock_db)
        days = service._generate_all_days(include_leap_day=False)

        assert len(days) == 365
        assert "01-01" in days  # January 1st
        assert "12-31" in days  # December 31st
        assert "02-29" not in days  # No leap day

    def test_generate_all_days_366(self, mock_db):
        """Test generation of 366 days including leap day."""
        service = CalendarVerificationService(mock_db)
        days = service._generate_all_days(include_leap_day=True)

        assert len(days) == 366
        assert "01-01" in days  # January 1st
        assert "12-31" in days  # December 31st
        assert "02-29" in days  # Leap day included

    @pytest.mark.asyncio
    async def test_verify_user_calendar_empty(self, mock_db):
        """Test calendar verification with no found caches."""
        service = CalendarVerificationService(mock_db)
        filters = CalendarFilters()

        result = await service.verify_user_calendar(str(ObjectId()), filters)

        assert result.completed_days_365 == 0
        assert result.completion_rate_365 == 0.0
        assert result.completed_days_366 == 0
        assert result.completion_rate_366 == 0.0
        assert len(result.missing_days) == 366
        assert len(result.completed_days) == 0

    @pytest.mark.asyncio
    async def test_verify_user_calendar_partial(self, mock_db):
        """Test calendar verification with some found caches."""

        # Mock found caches data
        mock_found_caches = [
            {"found_date": datetime(2024, 1, 1), "cache_info": {}},  # Jan 1st
            {"found_date": datetime(2024, 2, 29), "cache_info": {}},  # Feb 29th (leap day)
            {"found_date": datetime(2024, 1, 1), "cache_info": {}},  # Jan 1st again (duplicate)
        ]

        # Create a proper mock cursor
        class MockAsyncCursor:
            async def to_list(self, length=None):
                return mock_found_caches

        class MockCollection:
            async def find_one(self, query):
                return None  # No cache type/size filters

            def aggregate(self, pipeline):
                return MockAsyncCursor()

        class MockDB:
            def __init__(self):
                self.found_caches = MockCollection()
                self.cache_types = MockCollection()
                self.cache_sizes = MockCollection()

        service = CalendarVerificationService(MockDB())
        filters = CalendarFilters()

        result = await service.verify_user_calendar(str(ObjectId()), filters)

        # Should have 2 unique days: 01-01 and 02-29
        assert result.completed_days_365 == 1  # Only 01-01 (no leap day in 365)
        assert result.completion_rate_365 == 1 / 365
        assert result.completed_days_366 == 2  # Both 01-01 and 02-29
        assert result.completion_rate_366 == 2 / 366

        # Check completed days format
        assert len(result.completed_days) == 2
        assert {"day": "01-01", "count": 2} in result.completed_days
        assert {"day": "02-29", "count": 1} in result.completed_days

        # Missing days should not include completed ones
        assert "01-01" not in result.missing_days
        assert "02-29" not in result.missing_days

    @pytest.mark.asyncio
    async def test_verify_user_calendar_with_filters(self, mock_db):
        """Test calendar verification with cache type and size filters."""
        # Test that filters are properly handled and returned in response
        # Note: The actual filtering happens in MongoDB aggregation pipeline,
        # which is tested through integration tests.

        service = CalendarVerificationService(mock_db)
        filters = CalendarFilters(cache_type_name="Traditional Cache", cache_size_name="Regular")

        result = await service.verify_user_calendar(str(ObjectId()), filters)

        # Verify filters are acknowledged in the response
        assert result.cache_type_filter == "Traditional Cache"
        assert result.cache_size_filter == "Regular"
        # With empty DB, all days should be missing
        assert result.completed_days_365 == 0
        assert result.completed_days_366 == 0
