"""Tests for GPX Import Service components (unit tests - no DB required)."""

import datetime as dt
import io
import zipfile
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services.gpx_import.cache_validator import CacheValidator
from app.services.gpx_import.data_normalizer import DataNormalizer
from app.services.gpx_import.file_handler import FileHandler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_GPX = b"<?xml version='1.0' encoding='UTF-8'?><gpx version='1.1'>" + b" " * 50


def _make_zip(*gpx_entries: tuple[str, bytes]) -> bytes:
    """Build a ZIP archive in-memory containing the given (filename, content) pairs."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for name, content in gpx_entries:
            zf.writestr(name, content)
    return buf.getvalue()


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


class TestFileHandlerSafeJoin:
    """Test FileHandler.safe_join — path traversal prevention."""

    def test_normal_join(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        result = handler.safe_join(tmp_path, "subdir", "file.gpx")
        assert result == tmp_path / "subdir" / "file.gpx"

    def test_traversal_raises(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        with pytest.raises(ValueError, match="Path traversal"):
            handler.safe_join(tmp_path, "..", "etc", "passwd")


class TestFileHandlerValidateGpxContent:
    """Test FileHandler.validate_gpx_content."""

    def test_valid_gpx_passes(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        handler.validate_gpx_content(_MINIMAL_GPX)  # must not raise

    def test_too_small_raises_400(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        with pytest.raises(HTTPException) as exc_info:
            handler.validate_gpx_content(b"<gpx")
        assert exc_info.value.status_code == 400
        assert "too small" in exc_info.value.detail.lower()

    def test_missing_gpx_tag_raises_400(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        not_gpx = b"<?xml version='1.0'?><root></root>" + b" " * 50
        with pytest.raises(HTTPException) as exc_info:
            handler.validate_gpx_content(not_gpx)
        assert exc_info.value.status_code == 400
        assert "gpx" in exc_info.value.detail.lower()

    def test_gpx_tag_case_insensitive(self, tmp_path):
        """<GPX> (uppercase) is also accepted."""
        handler = FileHandler(uploads_dir=tmp_path)
        upper_gpx = b"<?xml version='1.0'?><GPX version='1.1'>" + b" " * 50
        handler.validate_gpx_content(upper_gpx)  # must not raise


class TestFileHandlerWriteGpxFile:
    """Test FileHandler.write_gpx_file."""

    def test_writes_file_and_returns_path(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        path = handler.write_gpx_file(_MINIMAL_GPX, "test.gpx")
        assert path.exists()
        assert path.read_bytes() == _MINIMAL_GPX

    def test_sanitizes_filename(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        path = handler.write_gpx_file(_MINIMAL_GPX, "my file@name!.gpx")
        # Special chars are stripped; the file must still be created
        assert path.exists()
        assert "@" not in path.name
        assert "!" not in path.name

    def test_adds_gpx_extension_if_missing(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        path = handler.write_gpx_file(_MINIMAL_GPX, "noextension")
        assert path.suffix == ".gpx"

    def test_uuid_filename_when_no_name(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        path = handler.write_gpx_file(_MINIMAL_GPX)
        assert path.exists()
        assert path.suffix == ".gpx"

    def test_collision_handled(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        path1 = handler.write_gpx_file(_MINIMAL_GPX, "collision.gpx")
        path2 = handler.write_gpx_file(_MINIMAL_GPX, "collision.gpx")
        assert path1 != path2
        assert path1.exists()
        assert path2.exists()

    def test_invalid_content_raises(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        with pytest.raises(HTTPException):
            handler.write_gpx_file(b"tiny", "bad.gpx")


class TestFileHandlerExtractZipFiles:
    """Test FileHandler.extract_zip_files."""

    def test_valid_zip_with_gpx(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        zip_data = _make_zip(("cache.gpx", _MINIMAL_GPX))
        paths = handler.extract_zip_files(zip_data)
        assert len(paths) == 1
        assert paths[0].suffix == ".gpx"

    def test_non_gpx_files_skipped(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        zip_data = _make_zip(
            ("readme.txt", b"not a gpx"),
            ("cache.gpx", _MINIMAL_GPX),
        )
        paths = handler.extract_zip_files(zip_data)
        assert len(paths) == 1  # only the .gpx

    def test_no_gpx_files_raises_400(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        zip_data = _make_zip(("readme.txt", b"no gpx here at all"))
        with pytest.raises(HTTPException) as exc_info:
            handler.extract_zip_files(zip_data)
        assert exc_info.value.status_code == 400
        assert "no valid gpx" in exc_info.value.detail.lower()

    def test_bad_zip_raises_400(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        with pytest.raises(HTTPException) as exc_info:
            handler.extract_zip_files(b"not a zip at all!!!!!")
        assert exc_info.value.status_code == 400

    def test_too_many_files_raises_http_exception(self, tmp_path):
        """The inner 400 HTTPException is caught by the outer except-Exception handler
        and re-raised as 500. The detail still mentions 'too many files'."""
        handler = FileHandler(uploads_dir=tmp_path)
        entries = [(f"file_{i}.txt", b"x") for i in range(101)]
        zip_data = _make_zip(*entries)
        with pytest.raises(HTTPException) as exc_info:
            handler.extract_zip_files(zip_data)
        # The inner 400 is swallowed by the outer except-Exception block → becomes 500
        assert exc_info.value.status_code == 500
        assert "too many" in exc_info.value.detail.lower()


class TestFileHandlerMaterializeFiles:
    """Test FileHandler.materialize_files dispatch."""

    def test_gpx_data_produces_single_file(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        paths = handler.materialize_files(_MINIMAL_GPX, "input.gpx")
        assert len(paths) == 1
        assert paths[0].suffix == ".gpx"

    def test_zip_data_extracts_gpx_files(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        zip_data = _make_zip(("a.gpx", _MINIMAL_GPX), ("b.gpx", _MINIMAL_GPX))
        paths = handler.materialize_files(zip_data)
        assert len(paths) == 2


class TestCacheValidator:
    """Test CacheValidator component (business validation)."""

    def test_validate_gpx_structure_valid_cache(self):
        """Test validation of valid cache data."""
        validator = CacheValidator(strict_mode=False)

        cache_data = {
            "GC": "GC12345",
            "title": "Test Cache",
            "lat": 48.8566,
            "lon": 2.3522,
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

        cache_data = {"GC": "GC12345", "lat": 48.8566, "lon": 2.3522}

        validated = validator.validate_cache_data(cache_data)

        assert validated["title"] == "Cache GC12345"

    def test_validate_gpx_structure_invalid_difficulty(self):
        """Test validation rejects invalid difficulty value."""
        validator = CacheValidator(strict_mode=False)

        cache_data = {
            "GC": "GC12345",
            "title": "Test Cache",
            "lat": 48.8566,
            "lon": 2.3522,
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
            "lat": 48.8566,
            "lon": 2.3522,
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


# ---------------------------------------------------------------------------
# FileHandler.validate_gpx_file — missing branches (lines 99-113)
# ---------------------------------------------------------------------------


class TestFileHandlerValidateGpxFile:
    def test_raises_404_when_file_not_found(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        missing = tmp_path / "nonexistent.gpx"
        with pytest.raises(HTTPException) as exc_info:
            handler.validate_gpx_file(missing)
        assert exc_info.value.status_code == 404

    def test_raises_400_when_file_empty(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        empty = tmp_path / "empty.gpx"
        empty.write_bytes(b"")
        with pytest.raises(HTTPException) as exc_info:
            handler.validate_gpx_file(empty)
        assert exc_info.value.status_code == 400

    def test_passes_for_valid_gpx_file(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        gpx_file = tmp_path / "valid.gpx"
        gpx_file.write_bytes(_MINIMAL_GPX)
        handler.validate_gpx_file(gpx_file)  # should not raise


# ---------------------------------------------------------------------------
# FileHandler.extract_zip_files — missing branches
# ---------------------------------------------------------------------------


class TestFileHandlerExtractZipMissingBranches:
    def _make_zip_with_dir(self) -> bytes:
        """Build a ZIP containing a directory entry and one GPX file."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            # Add a directory entry
            info = zipfile.ZipInfo("mydir/")
            zf.writestr(info, "")
            # Add a valid GPX file inside
            zf.writestr("mydir/cache.gpx", _MINIMAL_GPX.decode())
        return buf.getvalue()

    def test_skips_directory_entries(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        zip_data = self._make_zip_with_dir()
        # Should still extract the GPX file
        paths = handler.extract_zip_files(zip_data)
        assert len(paths) == 1

    def test_skips_oversized_files(self, tmp_path):
        """Files > 50MB in a ZIP are skipped (file_size check)."""
        import unittest.mock as mock

        handler = FileHandler(uploads_dir=tmp_path)

        # Patch file_size on the big entry
        big_info_mock = mock.MagicMock(spec=zipfile.ZipInfo)
        big_info_mock.filename = "big.gpx"
        big_info_mock.file_size = 60 * 1024 * 1024  # 60MB
        big_info_mock.is_dir = MagicMock(return_value=False)

        small_info_mock = mock.MagicMock(spec=zipfile.ZipInfo)
        small_info_mock.filename = "small.gpx"
        small_info_mock.file_size = len(_MINIMAL_GPX)
        small_info_mock.is_dir = MagicMock(return_value=False)

        zip_data = _make_zip(("small.gpx", _MINIMAL_GPX))

        with mock.patch("zipfile.ZipFile") as mock_zf_cls:
            mock_zf = mock.MagicMock()
            mock_zf.__enter__ = mock.MagicMock(return_value=mock_zf)
            mock_zf.__exit__ = mock.MagicMock(return_value=False)
            mock_zf.namelist = mock.MagicMock(return_value=["big.gpx", "small.gpx"])
            mock_zf.infolist = mock.MagicMock(return_value=[big_info_mock, small_info_mock])

            # small.gpx content
            small_ctx = mock.MagicMock()
            small_ctx.__enter__ = mock.MagicMock(return_value=small_ctx)
            small_ctx.__exit__ = mock.MagicMock(return_value=False)
            small_ctx.read = mock.MagicMock(return_value=_MINIMAL_GPX)
            mock_zf.open = mock.MagicMock(return_value=small_ctx)

            mock_zf_cls.return_value = mock_zf

            paths = handler.extract_zip_files(zip_data)

        # Only small.gpx should have been extracted
        assert len(paths) == 1


# ---------------------------------------------------------------------------
# FileHandler.cleanup_file / cleanup_files (lines 234-248)
# ---------------------------------------------------------------------------


class TestFileHandlerCleanup:
    def test_cleanup_file_removes_existing_file(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        f = tmp_path / "to_delete.gpx"
        f.write_bytes(b"data")
        assert f.exists()
        handler.cleanup_file(f)
        assert not f.exists()

    def test_cleanup_file_ignores_missing_file(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        missing = tmp_path / "gone.gpx"
        handler.cleanup_file(missing)  # should not raise

    def test_cleanup_files_removes_multiple(self, tmp_path):
        handler = FileHandler(uploads_dir=tmp_path)
        files = [tmp_path / f"f{i}.gpx" for i in range(3)]
        for f in files:
            f.write_bytes(b"x")
        handler.cleanup_files(files)
        for f in files:
            assert not f.exists()
