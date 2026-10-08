"""Tests for GpxImportService: __init__, import_gpx_payload, get_import_statistics."""

from unittest.mock import AsyncMock

import pytest
from bson import ObjectId

from tests.unit._gpx_import_service_test_helpers import (
    _make_db,
    _make_service,
    _patch_components,
)


class TestGpxImportServiceInit:
    def test_creates_components(self):
        service = _make_service()
        assert service.file_handler is not None
        assert service.data_normalizer is not None
        assert service.cache_validator is not None
        assert service.referential_mapper is not None
        assert service.cache_persister is not None
        assert service.gpx_parser is None


class TestImportGpxPayload:
    @pytest.mark.asyncio
    async def test_raises_on_invalid_mode(self):
        service = _make_service()
        with pytest.raises(ValueError, match="import mode"):
            await service.import_gpx_payload(b"data", import_mode="invalid")

    @pytest.mark.asyncio
    async def test_empty_result_with_no_caches(self):
        service = _make_service()
        _patch_components(service)

        result = await service.import_gpx_payload(b"data", filename="test.gpx")

        assert result["nb_inserted_caches"] == 0
        assert result["nb_inserted_found_caches"] == 0
        assert result["nb_gpx_files"] == 1

    @pytest.mark.asyncio
    async def test_persists_caches_in_both_mode(self):
        service = _make_service()
        caches = [{"GC": "GC12345", "lat": 48.85, "lon": 2.35}]
        _patch_components(
            service,
            caches=caches,
            persist_caches={"inserted": 1, "updated": 0, "errors": 0},
        )

        result = await service.import_gpx_payload(b"data", import_mode="both")

        assert result["nb_inserted_caches"] == 1
        service.cache_persister.persist_caches.assert_called_once()

    @pytest.mark.asyncio
    async def test_persists_found_caches_in_both_mode(self):
        service = _make_service()
        user_id = ObjectId()
        caches = [{"GC": "GC12345", "lat": 48.85, "lon": 2.35}]
        found = [{"GC": "GC12345", "found_date": "2024-01-01"}]
        _patch_components(
            service,
            caches=caches,
            found=found,
            persist_found={"inserted": 1, "updated": 0, "errors": 0},
        )

        result = await service.import_gpx_payload(b"data", user_id=user_id, import_mode="both")

        assert result["nb_inserted_found_caches"] == 1

    @pytest.mark.asyncio
    async def test_skips_found_when_no_user_id(self):
        service = _make_service()
        caches = [{"GC": "GC12345", "lat": 48.85, "lon": 2.35}]
        found = [{"GC": "GC12345", "found_date": "2024-01-01"}]
        _patch_components(service, caches=caches, found=found)

        await service.import_gpx_payload(b"data", import_mode="both", user_id=None)

        service.cache_persister.persist_found_caches.assert_not_called()

    @pytest.mark.asyncio
    async def test_calls_geocoding_enrichment_when_caches_present(self):
        service = _make_service()
        caches = [{"GC": "GC12345", "lat": 48.85, "lon": 2.35}]
        _patch_components(service, caches=caches)

        await service.import_gpx_payload(b"data")

        service._enrich_with_geocoding.assert_called_once()

    @pytest.mark.asyncio
    async def test_calls_elevation_enrichment_when_enabled(self):
        service = _make_service()
        caches = [{"GC": "GC12345", "lat": 48.85, "lon": 2.35}]
        _patch_components(service, caches=caches)

        await service.import_gpx_payload(b"data", fetch_elevation=True)

        service._enrich_with_elevation.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_called_in_finally(self):
        service = _make_service()
        _patch_components(service)

        await service.import_gpx_payload(b"data")

        service.file_handler.cleanup_files.assert_called_once()

    @pytest.mark.asyncio
    async def test_new_referential_counts_computed(self):
        service = _make_service()
        _patch_components(
            service,
            ref_before={"countries": 10, "states": 20, "cache_types": 5, "cache_sizes": 3},
            ref_after={"countries": 12, "states": 23, "cache_types": 5, "cache_sizes": 3},
        )

        result = await service.import_gpx_payload(b"data")

        assert result["nb_new_countries"] == 2
        assert result["nb_new_states"] == 3

    @pytest.mark.asyncio
    async def test_total_items_reflects_caches_count(self):
        service = _make_service()
        caches = [{"GC": f"GC{i:05d}"} for i in range(5)]
        _patch_components(service, caches=caches)

        result = await service.import_gpx_payload(b"data")

        assert result["nb_total_items"] == 5


class TestGetImportStatistics:
    @pytest.mark.asyncio
    async def test_returns_total_caches(self):
        db = _make_db()
        db.caches.count_documents = AsyncMock(return_value=42)

        service = _make_service(db)
        service.cache_persister.get_referential_counts = AsyncMock(
            return_value={"countries": 5, "states": 10, "cache_types": 3, "cache_sizes": 2}
        )

        result = await service.get_import_statistics()

        assert result["total_caches"] == 42
        assert "countries" in result

    @pytest.mark.asyncio
    async def test_includes_user_found_caches_when_user_id_given(self):
        db = _make_db()
        db.caches.count_documents = AsyncMock(return_value=10)
        db.found_caches.count_documents = AsyncMock(return_value=7)

        service = _make_service(db)
        service.cache_persister.get_referential_counts = AsyncMock(return_value={})

        result = await service.get_import_statistics(user_id=ObjectId())

        assert result["user_found_caches"] == 7
