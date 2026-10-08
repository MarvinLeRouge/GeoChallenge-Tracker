"""Tests for GpxImportService: _process_gpx_files, _process_single_gpx_file, _assign_zones."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.unit._gpx_import_service_test_helpers import (
    _make_service,
)


class TestProcessGpxFiles:
    @pytest.mark.asyncio
    async def test_empty_paths_returns_empty(self):
        service = _make_service()
        caches, found = await service._process_gpx_files([], "both")
        assert caches == []
        assert found == []

    @pytest.mark.asyncio
    async def test_aggregates_results_from_multiple_files(self):
        service = _make_service()
        path1 = Path("/tmp/a.gpx")
        path2 = Path("/tmp/b.gpx")

        async def mock_process(path, mode, force=False):
            if path == path1:
                return ([{"GC": "GC00001"}], [])
            return ([{"GC": "GC00002"}], [{"GC": "GC00002"}])

        service._process_single_gpx_file = mock_process

        caches, found = await service._process_gpx_files([path1, path2], "both")
        assert len(caches) == 2
        assert len(found) == 1

    @pytest.mark.asyncio
    async def test_skips_file_on_exception(self):
        service = _make_service()

        async def mock_process(path, mode, force=False):
            raise RuntimeError("parse error")

        service._process_single_gpx_file = mock_process
        caches, found = await service._process_gpx_files([Path("/tmp/bad.gpx")], "both")
        assert caches == []
        assert found == []


class TestProcessSingleGpxFile:
    @pytest.mark.asyncio
    async def test_skips_item_without_gc_code(self):
        service = _make_service()
        gpx_path = Path("/tmp/test.gpx")

        mock_parser = MagicMock()
        mock_parser.parse = MagicMock(return_value=[{"title": "No GC"}])
        service.file_handler.validate_gpx_file = MagicMock()
        service.data_normalizer.extract_cache_metadata = MagicMock(return_value={})
        service.data_normalizer.extract_found_metadata = MagicMock(return_value=None)
        service.data_normalizer.is_valid_for_import_mode = MagicMock(return_value=True)

        with patch(
            "app.services.gpx_import.gpx_import_service.MultiFormatGPXParser",
            return_value=mock_parser,
        ):
            caches, found = await service._process_single_gpx_file(gpx_path, "both")

        assert caches == []

    @pytest.mark.asyncio
    async def test_skips_item_not_valid_for_mode(self):
        service = _make_service()
        gpx_path = Path("/tmp/test.gpx")

        mock_parser = MagicMock()
        mock_parser.parse = MagicMock(return_value=[{"GC": "GC12345"}])
        service.file_handler.validate_gpx_file = MagicMock()
        service.data_normalizer.extract_cache_metadata = MagicMock(return_value={"GC": "GC12345"})
        service.data_normalizer.extract_found_metadata = MagicMock(return_value=None)
        service.data_normalizer.is_valid_for_import_mode = MagicMock(return_value=False)

        with patch(
            "app.services.gpx_import.gpx_import_service.MultiFormatGPXParser",
            return_value=mock_parser,
        ):
            caches, found = await service._process_single_gpx_file(gpx_path, "found")

        assert caches == []

    @pytest.mark.asyncio
    async def test_processes_valid_item(self):
        service = _make_service()
        gpx_path = Path("/tmp/test.gpx")

        cache_meta = {"GC": "GC12345", "lat": 48.85, "lon": 2.35}
        validated_cache = {**cache_meta, "status": "active"}

        mock_parser = MagicMock()
        mock_parser.parse = MagicMock(return_value=[{"GC": "GC12345"}])
        service.file_handler.validate_gpx_file = MagicMock()
        service.data_normalizer.extract_cache_metadata = MagicMock(return_value=cache_meta)
        service.data_normalizer.extract_found_metadata = MagicMock(return_value=None)
        service.data_normalizer.is_valid_for_import_mode = MagicMock(return_value=True)
        service.referential_mapper.map_cache_referentials = AsyncMock(return_value=cache_meta)
        service.cache_validator.validate_cache_data = MagicMock(return_value=validated_cache)
        service.cache_validator.validate_found_data = MagicMock()
        service.cache_validator.validate_import_consistency = MagicMock()

        with patch(
            "app.services.gpx_import.gpx_import_service.MultiFormatGPXParser",
            return_value=mock_parser,
        ):
            caches, found = await service._process_single_gpx_file(gpx_path, "both")

        assert len(caches) == 1
        assert found == []

    @pytest.mark.asyncio
    async def test_processes_found_metadata(self):
        service = _make_service()
        gpx_path = Path("/tmp/test.gpx")

        cache_meta = {"GC": "GC12345", "lat": 48.85, "lon": 2.35}
        found_meta = {"found_date": "2024-01-01"}
        validated_cache = {**cache_meta, "status": "active"}
        validated_found = {"found_date": "2024-01-01"}

        mock_parser = MagicMock()
        mock_parser.parse = MagicMock(return_value=[{"GC": "GC12345"}])
        service.file_handler.validate_gpx_file = MagicMock()
        service.data_normalizer.extract_cache_metadata = MagicMock(return_value=cache_meta)
        service.data_normalizer.extract_found_metadata = MagicMock(return_value=found_meta)
        service.data_normalizer.is_valid_for_import_mode = MagicMock(return_value=True)
        service.referential_mapper.map_cache_referentials = AsyncMock(return_value=cache_meta)
        service.cache_validator.validate_cache_data = MagicMock(return_value=validated_cache)
        service.cache_validator.validate_found_data = MagicMock(return_value=validated_found)
        service.cache_validator.validate_import_consistency = MagicMock()

        with patch(
            "app.services.gpx_import.gpx_import_service.MultiFormatGPXParser",
            return_value=mock_parser,
        ):
            caches, found = await service._process_single_gpx_file(gpx_path, "both")

        assert len(caches) == 1
        assert len(found) == 1

    @pytest.mark.asyncio
    async def test_skips_item_on_validation_error(self):
        service = _make_service()
        gpx_path = Path("/tmp/test.gpx")

        mock_parser = MagicMock()
        mock_parser.parse = MagicMock(return_value=[{"GC": "GC12345"}])
        service.file_handler.validate_gpx_file = MagicMock()
        service.data_normalizer.extract_cache_metadata = MagicMock(return_value={"GC": "GC12345"})
        service.data_normalizer.extract_found_metadata = MagicMock(return_value=None)
        service.data_normalizer.is_valid_for_import_mode = MagicMock(return_value=True)
        service.referential_mapper.map_cache_referentials = AsyncMock(
            return_value={"GC": "GC12345"}
        )
        service.cache_validator.validate_cache_data = MagicMock(
            side_effect=ValueError("validation failed")
        )

        with patch(
            "app.services.gpx_import.gpx_import_service.MultiFormatGPXParser",
            return_value=mock_parser,
        ):
            caches, found = await service._process_single_gpx_file(gpx_path, "both")

        assert caches == []


class TestAssignZones:
    @pytest.mark.asyncio
    async def test_delegates_to_assign_zones_to_caches(self):
        service = _make_service()
        caches = [{"GC": "GC00001", "lat": 48.85, "lon": 2.35}]

        with patch(
            "app.services.gpx_import.gpx_import_service.assign_zones_to_caches",
            new=AsyncMock(),
        ) as mock_assign:
            await service._assign_zones(caches)

        mock_assign.assert_called_once_with(caches)
