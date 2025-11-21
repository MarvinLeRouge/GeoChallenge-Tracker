"""Tests for matrix D/T verification functionality."""

import pytest
from bson import ObjectId

from app.models.calendar_verification import MatrixFilters
from app.services.matrix_verification import MatrixVerificationService


class TestMatrixVerificationService:
    """Test matrix D/T verification service."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database for testing."""
        class MockCollection:
            def __init__(self, data):
                self.data = data
            
            def aggregate(self, pipeline):
                return self
                
            async def to_list(self, length):
                return self.data
            
            async def find_one(self, query):
                if "cache_types" in str(query) or ("name" in query and query.get("name") == "Traditional Cache"):
                    return {"_id": ObjectId(), "name": "Traditional Cache"}
                elif "cache_sizes" in str(query) or ("name" in query and query.get("name") == "Regular"):
                    return {"_id": ObjectId(), "name": "Regular"}
                return None
        
        class MockDB:
            def __init__(self):
                self.found_caches = MockCollection([])
                self.cache_types = MockCollection([])
                self.cache_sizes = MockCollection([])
        
        return MockDB()
    
    def test_generate_all_dt_combinations(self, mock_db):
        """Test generation of all 81 D/T combinations."""
        service = MatrixVerificationService(mock_db)
        combinations = service._generate_all_dt_combinations()
        
        assert len(combinations) == 81  # 9x9 matrix
        assert (1.0, 1.0) in combinations  # Min D/T
        assert (5.0, 5.0) in combinations  # Max D/T
        assert (2.5, 3.5) in combinations  # Mid values
        assert (1.0, 5.0) in combinations  # Mixed values
    
    @pytest.mark.asyncio
    async def test_verify_user_matrix_empty(self, mock_db):
        """Test matrix verification with no found caches."""
        service = MatrixVerificationService(mock_db)
        filters = MatrixFilters()
        
        result = await service.verify_user_matrix("user123", filters)
        
        assert result.completed_combinations == 0
        assert result.completion_rate == 0.0
        assert len(result.missing_combinations) == 81
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
        mock_db.found_caches.data = mock_found_caches
        
        service = MatrixVerificationService(mock_db)
        filters = MatrixFilters()
        
        result = await service.verify_user_matrix("user123", filters)
        
        # Should have 3 unique combinations: (1.0,1.0), (1.0,1.5), (2.5,3.0)
        assert result.completed_combinations == 3
        assert result.completion_rate == 3/81
        assert len(result.missing_combinations) == 78
        
        # Check completed combinations details
        assert len(result.completed_combinations_details) == 3
        
        # Check for the duplicate count
        d1_t1_details = next(
            (combo for combo in result.completed_combinations_details 
             if combo["difficulty"] == 1.0 and combo["terrain"] == 1.0), 
            None
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
        # Mock found caches data
        mock_found_caches = [
            {"cache_info": {"difficulty": 1.0, "terrain": 1.0, "cache_type_id": ObjectId(), "cache_size_id": ObjectId()}},
        ]
        mock_db.found_caches.data = mock_found_caches
        
        service = MatrixVerificationService(mock_db)
        filters = MatrixFilters(
            cache_type_name="Traditional Cache",
            cache_size_name="Regular"
        )
        
        result = await service.verify_user_matrix("user123", filters)
        
        assert result.cache_type_filter == "Traditional Cache"
        assert result.cache_size_filter == "Regular"
        assert result.completed_combinations == 1
        assert result.completion_rate == 1/81
    
    @pytest.mark.asyncio
    async def test_verify_user_matrix_rounding(self, mock_db):
        """Test that D/T values are properly rounded to nearest 0.5."""
        # Mock found caches with slightly off values
        mock_found_caches = [
            {"cache_info": {"difficulty": 1.01, "terrain": 1.49}},  # Should round to 1.0, 1.5
            {"cache_info": {"difficulty": 2.24, "terrain": 2.26}},  # Should round to 2.0, 2.5
        ]
        mock_db.found_caches.data = mock_found_caches
        
        service = MatrixVerificationService(mock_db)
        filters = MatrixFilters()
        
        result = await service.verify_user_matrix("user123", filters)
        
        assert result.completed_combinations == 2
        
        # Check that rounded values are used
        details = result.completed_combinations_details
        assert any(d["difficulty"] == 1.0 and d["terrain"] == 1.5 for d in details)
        assert any(d["difficulty"] == 2.0 and d["terrain"] == 2.5 for d in details)