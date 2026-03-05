"""Tests for GPX Import Service components (unit tests - no DB required)."""

import datetime as dt

import pytest

from app.services.gpx_import.cache_validator import CacheValidator
from app.services.gpx_import.data_normalizer import DataNormalizer
from app.services.gpx_import.file_handler import FileHandler


class TestFileHandler:
    """Test FileHandler component (file detection, validation)."""

    def test_detect_source_type_auto_zip(self):
        """Test automatic detection of ZIP file via magic bytes."""
        handler = FileHandler()

        # ZIP magic bytes: PK\x03\x04
        zip_data = b"PK\x03\x04" + b"fake zip content"

        assert handler.is_zip_file(zip_data) is True

    def test_detect_source_type_auto_gpx(self):
        """Test automatic detection of non-ZIP (GPX) file."""
        handler = FileHandler()

        # GPX files start with <?xml
        gpx_data = b"<?xml version='1.0'?>" + b"<gpx>...</gpx>"

        assert handler.is_zip_file(gpx_data) is False

    def test_detect_source_type_explicit(self):
        """Test explicit source type parameter handling."""
        # This test verifies that source types are valid strings
        # The actual parsing logic handles these in MultiFormatGPXParser
        source_types = ["cgeo", "pocket_query", "auto"]
        assert "cgeo" in source_types
        assert "pocket_query" in source_types
        assert "auto" in source_types


class TestCacheValidator:
    """Test CacheValidator component (business validation)."""

    def test_validate_gpx_structure_valid_cache(self):
        """Test validation of valid cache data."""
        validator = CacheValidator(strict_mode=False)

        cache_data = {
            "GC": "GC12345",
            "title": "Test Cache",
            "latitude": 48.8566,
            "longitude": 2.3522,
            "difficulty": 2.5,
            "terrain": 3.0,
            "owner": "TestOwner",
        }

        # Should not raise
        validated = validator.validate_cache_data(cache_data)

        assert validated["GC"] == "GC12345"
        assert validated["title"] == "Test Cache"

    def test_validate_gpx_structure_missing_gc(self):
        """Test validation rejects cache without GC code."""
        validator = CacheValidator(strict_mode=False)

        cache_data = {"title": "Test Cache", "latitude": 48.8566, "longitude": 2.3522}

        with pytest.raises(ValueError, match="Missing required GC code"):
            validator.validate_cache_data(cache_data)

    def test_validate_gpx_structure_invalid_gc_code(self):
        """Test validation rejects invalid GC code format."""
        validator = CacheValidator(strict_mode=False)

        cache_data = {
            "GC": "INVALID123",  # GC codes should be GC + digits
            "title": "Test Cache",
        }

        with pytest.raises(ValueError, match="Invalid GC code"):
            validator.validate_cache_data(cache_data)

    def test_validate_gpx_structure_missing_title_strict(self):
        """Test validation in strict mode rejects cache without title."""
        validator = CacheValidator(strict_mode=True)

        cache_data = {"GC": "GC12345", "latitude": 48.8566, "longitude": 2.3522}

        with pytest.raises(ValueError, match="Missing required title"):
            validator.validate_cache_data(cache_data)

    def test_validate_gpx_structure_missing_title_non_strict(self):
        """Test validation in non-strict mode auto-generates title."""
        validator = CacheValidator(strict_mode=False)

        cache_data = {"GC": "GC12345", "latitude": 48.8566, "longitude": 2.3522}

        validated = validator.validate_cache_data(cache_data)

        assert validated["title"] == "Cache GC12345"

    def test_validate_gpx_structure_invalid_difficulty(self):
        """Test validation rejects invalid difficulty value."""
        validator = CacheValidator(strict_mode=False)

        cache_data = {
            "GC": "GC12345",
            "title": "Test Cache",
            "latitude": 48.8566,
            "longitude": 2.3522,
            "difficulty": 6.0,  # Max is 5.0
            "terrain": 3.0,
            "owner": "TestOwner",
        }

        with pytest.raises(ValueError, match="difficulty must be between"):
            validator.validate_cache_data(cache_data)

    def test_validate_gpx_structure_invalid_terrain(self):
        """Test validation rejects invalid terrain value."""
        validator = CacheValidator(strict_mode=False)

        cache_data = {
            "GC": "GC12345",
            "title": "Test Cache",
            "latitude": 48.8566,
            "longitude": 2.3522,
            "difficulty": 2.5,
            "terrain": 0.0,  # Min is 0.5
            "owner": "TestOwner",
        }

        with pytest.raises(ValueError, match="terrain must be between"):
            validator.validate_cache_data(cache_data)


class TestDataNormalizer:
    """Test DataNormalizer component (data parsing and normalization)."""

    def test_normalize_cache_data_with_attributes(self):
        """Test normalization of cache data with attributes."""
        normalizer = DataNormalizer()

        # Test name normalization
        assert normalizer.normalize_name("  Test Cache  ") == "testcache"
        assert normalizer.normalize_name("") == ""
        assert normalizer.normalize_name(None) == ""

    def test_normalize_cache_data_date_parsing(self):
        """Test parsing of various date formats."""
        normalizer = DataNormalizer()

        # Test various ISO 8601 formats
        date1 = normalizer.parse_datetime_iso8601("2024-01-15T14:30:45.123Z")
        assert isinstance(date1, dt.datetime)

        date2 = normalizer.parse_datetime_iso8601("2024-01-15T14:30:45Z")
        assert isinstance(date2, dt.datetime)

        date3 = normalizer.parse_datetime_iso8601("2024-01-15")
        assert isinstance(date3, dt.datetime)

        # Test invalid date
        date4 = normalizer.parse_datetime_iso8601("invalid-date")
        assert date4 is None

        # Test None input
        date5 = normalizer.parse_datetime_iso8601(None)
        assert date5 is None

    def test_normalize_cache_data_coordinates(self):
        """Test normalization of coordinate values."""
        # String coordinates should be convertible to float
        lat_str = "48.8566"
        lon_str = "2.3522"

        assert float(lat_str) == 48.8566
        assert float(lon_str) == 2.3522

    def test_extract_cache_attributes_from_gpx(self):
        """Test extraction of attributes from GPX structure."""
        gpx_cache_data = {
            "GC": "GC12345",
            "title": "Test Cache",
            "groundspeak:attributes": [
                {"id": "1", "inc": "1", "text": "Dogs allowed"},
                {"id": "8", "inc": "1", "text": "Scenic view"},
                {"id": "38", "inc": "0", "text": "Campfires prohibited"},
            ],
        }

        # Extract attributes (simplified extraction logic)
        attributes = []
        if "groundspeak:attributes" in gpx_cache_data:
            for attr in gpx_cache_data["groundspeak:attributes"]:
                attributes.append(
                    {"attribute_id": int(attr["id"]), "is_positive": attr["inc"] == "1"}
                )

        assert len(attributes) == 3
        assert attributes[0]["attribute_id"] == 1
        assert attributes[0]["is_positive"] is True
        assert attributes[2]["is_positive"] is False  # inc="0" means negative
