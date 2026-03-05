"""Tests for matrix D/T verification functionality."""

import pytest
from bson import ObjectId

from app.api.dto.calendar_verification import MatrixFilters
from app.services.matrix_verification import MatrixVerificationService
from app.shared.constants import MATRIX_DT_TOTAL_COMBINATIONS


class TestMatrixVerificationService:
    """Test matrix D/T verification service."""

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
                return MockAsyncCursor([])

        class MockDB:
            def __init__(self):
                self.found_caches = MockCollection([])
                self.cache_types = MockCollection([])
                self.cache_sizes = MockCollection([])

        return MockDB()

    def test_generate_all_dt_combinations(self, mock_db):
        """Test generation of all D/T combinations (9x9 matrix = 81 combinations)."""
        service = MatrixVerificationService(mock_db)
        combinations = service._generate_all_dt_combinations()

        assert (
            len(combinations) == MATRIX_DT_TOTAL_COMBINATIONS
        )  # 9x9 matrix (9 difficulty levels × 9 terrain levels)
        assert (1.0, 1.0) in combinations  # Min D/T
        assert (5.0, 5.0) in combinations  # Max D/T
        assert (2.5, 3.5) in combinations  # Mid values
        assert (1.0, 5.0) in combinations  # Mixed values

    @pytest.mark.asyncio
    async def test_verify_user_matrix_empty(self, mock_db):
        """Test matrix verification with no found caches."""
        service = MatrixVerificationService(mock_db)
        filters = MatrixFilters()

        result = await service.verify_user_matrix(str(ObjectId()), filters)

        assert result.completed_combinations_count == 0
        assert result.completion_rate == 0.0
        assert (
            len(result.missing_combinations) == MATRIX_DT_TOTAL_COMBINATIONS
        )  # All combinations missing when no caches found
        assert len(result.completed_combinations_details) == 0

        # Check that all difficulties are represented in missing combinations
        assert "1.0" in result.missing_combinations_by_difficulty
        assert "5.0" in result.missing_combinations_by_difficulty
        assert len(result.missing_combinations_by_difficulty["1.0"]) == 9  # 9 terrains for D=1.0

    @pytest.mark.asyncio
    async def test_verify_user_matrix_partial(self, mock_db):
        """Test matrix verification with some found caches."""
        # Mock found caches data
        mock_found_caches = [
            {"cache_info": {"difficulty": 1.0, "terrain": 1.0}},  # D1/T1
            {"cache_info": {"difficulty": 1.0, "terrain": 1.5}},  # D1/T1.5
            {"cache_info": {"difficulty": 1.0, "terrain": 1.0}},  # D1/T1 duplicate
            {"cache_info": {"difficulty": 2.5, "terrain": 3.0}},  # D2.5/T3
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

        service = MatrixVerificationService(MockDB())
        filters = MatrixFilters()

        result = await service.verify_user_matrix(str(ObjectId()), filters)

        # Should have 3 unique combinations: (1.0,1.0), (1.0,1.5), (2.5,3.0)
        assert result.completed_combinations_count == 3
        assert (
            result.completion_rate == 3 / MATRIX_DT_TOTAL_COMBINATIONS
        )  # 3 out of total combinations completed
        assert len(result.missing_combinations) == 78

        # Check completed combinations details
        assert len(result.completed_combinations_details) == 3

        # Check for the duplicate count
        d1_t1_details = next(
            (
                combo
                for combo in result.completed_combinations_details
                if combo["difficulty"] == 1.0 and combo["terrain"] == 1.0
            ),
            None,
        )
        assert d1_t1_details is not None
        assert d1_t1_details["count"] == 2  # Duplicate count

        # Check missing combinations by difficulty
        assert "1.0" in result.missing_combinations_by_difficulty
        # Should have 7 missing terrains for D=1.0 (9 total - 2 found)
        assert len(result.missing_combinations_by_difficulty["1.0"]) == 7

    @pytest.mark.asyncio
    async def test_verify_user_matrix_with_filters(self, mock_db):
        """Test matrix verification with cache type and size filters."""
        # Test that filters are properly handled and returned in response
        # Note: The actual filtering happens in MongoDB aggregation pipeline,
        # which is tested through integration tests.

        service = MatrixVerificationService(mock_db)
        filters = MatrixFilters(cache_type_name="Traditional Cache", cache_size_name="Regular")

        result = await service.verify_user_matrix(str(ObjectId()), filters)

        # Verify filters are acknowledged in the response
        assert result.cache_type_filter == "Traditional Cache"
        assert result.cache_size_filter == "Regular"
        # With empty DB, all combinations should be missing
        assert result.completed_combinations_count == 0
        assert result.completion_rate == 0.0

    @pytest.mark.asyncio
    async def test_verify_user_matrix_rounding(self, mock_db):
        """Test that D/T values are properly rounded to nearest 0.5."""
        # Mock found caches with slightly off values
        mock_found_caches = [
            {"cache_info": {"difficulty": 1.01, "terrain": 1.49}},  # Should round to 1.0, 1.5
            {"cache_info": {"difficulty": 2.24, "terrain": 2.26}},  # Should round to 2.0, 2.5
        ]

        # Create a proper mock cursor
        class MockAsyncCursor:
            async def to_list(self, length=None):
                return mock_found_caches

        class MockCollection:
            async def find_one(self, query):
                return None

            def aggregate(self, pipeline):
                return MockAsyncCursor()

        class MockDB:
            def __init__(self):
                self.found_caches = MockCollection()
                self.cache_types = MockCollection()
                self.cache_sizes = MockCollection()

        service = MatrixVerificationService(MockDB())
        filters = MatrixFilters()

        result = await service.verify_user_matrix(str(ObjectId()), filters)

        assert result.completed_combinations_count == 2

        # Check that rounded values are used
        details = result.completed_combinations_details
        assert any(d["difficulty"] == 1.0 and d["terrain"] == 1.5 for d in details)
        assert any(d["difficulty"] == 2.0 and d["terrain"] == 2.5 for d in details)
