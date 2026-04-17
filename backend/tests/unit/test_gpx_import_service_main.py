"""Tests for app/services/gpx_import/gpx_import_service.py."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db():
    class MockDB:
        def __init__(self):
            self.caches = AsyncMock()
            self.found_caches = AsyncMock()
            self.countries = AsyncMock()
            self.states = AsyncMock()
            self.cache_types = AsyncMock()
            self.cache_sizes = AsyncMock()
            self.cache_attributes = AsyncMock()

    return MockDB()


def _make_service(db=None):
    from app.services.gpx_import.gpx_import_service import GpxImportService

    db = db or _make_db()
    return GpxImportService(db)


def _patch_components(
    service,
    *,
    gpx_paths=None,
    caches=None,
    found=None,
    ref_before=None,
    ref_after=None,
    persist_caches=None,
    persist_found=None,
):
    """Set up all sub-component mocks on the service."""
    gpx_paths = gpx_paths if gpx_paths is not None else [Path("/tmp/test.gpx")]
    caches = caches if caches is not None else []
    found = found if found is not None else []
    ref_before = ref_before or {"countries": 10, "states": 20, "cache_types": 5, "cache_sizes": 3}
    ref_after = ref_after or {"countries": 10, "states": 20, "cache_types": 5, "cache_sizes": 3}
    persist_caches = persist_caches or {"inserted": 0, "updated": 0, "errors": 0}
    persist_found = persist_found or {"inserted": 0, "updated": 0, "errors": 0}

    service.file_handler.materialize_files = MagicMock(return_value=gpx_paths)
    service.file_handler.cleanup_files = MagicMock()
    service.referential_mapper.load_all_referentials = AsyncMock()
    service.cache_persister.get_referential_counts = AsyncMock(side_effect=[ref_before, ref_after])
    service.cache_persister.persist_caches = AsyncMock(return_value=persist_caches)
    service.cache_persister.persist_found_caches = AsyncMock(return_value=persist_found)
    service._process_gpx_files = AsyncMock(return_value=(caches, found))
    service._enrich_with_geocoding = AsyncMock()
    service._enrich_with_elevation = AsyncMock()
    service._assign_zones = AsyncMock()


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestGpxImportServiceInit:
    def test_creates_components(self):
        service = _make_service()
        assert service.file_handler is not None
        assert service.data_normalizer is not None
        assert service.cache_validator is not None
        assert service.referential_mapper is not None
        assert service.cache_persister is not None
        assert service.gpx_parser is None


# ---------------------------------------------------------------------------
# import_gpx_payload — top-level orchestration
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# _process_gpx_files
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# _process_single_gpx_file
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# _enrich_with_elevation
# ---------------------------------------------------------------------------


class TestEnrichWithElevation:
    @pytest.mark.asyncio
    async def test_skips_when_empty(self):
        service = _make_service()
        await service._enrich_with_elevation([])  # should not raise

    @pytest.mark.asyncio
    async def test_skips_when_no_valid_coords(self):
        service = _make_service()
        caches = [{"GC": "GC12345"}]  # no lat/lon
        with patch(
            "app.services.gpx_import.gpx_import_service.fetch_elevations",
            new_callable=AsyncMock,
        ) as mock_fetch:
            await service._enrich_with_elevation(caches)
            mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_assigns_elevation_to_cache(self):
        service = _make_service()
        caches = [{"GC": "GC12345", "lat": 48.85, "lon": 2.35}]
        with patch(
            "app.services.gpx_import.gpx_import_service.fetch_elevations",
            new_callable=AsyncMock,
            return_value=[200],
        ):
            await service._enrich_with_elevation(caches)

        assert caches[0]["elevation"] == 200

    @pytest.mark.asyncio
    async def test_handles_none_elevation(self):
        service = _make_service()
        caches = [{"GC": "GC12345", "lat": 48.85, "lon": 2.35}]
        with patch(
            "app.services.gpx_import.gpx_import_service.fetch_elevations",
            new_callable=AsyncMock,
            return_value=[None],
        ):
            await service._enrich_with_elevation(caches)

        assert "elevation" not in caches[0]

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self):
        service = _make_service()
        caches = [{"GC": "GC12345", "lat": 48.85, "lon": 2.35}]
        with patch(
            "app.services.gpx_import.gpx_import_service.fetch_elevations",
            new_callable=AsyncMock,
            side_effect=Exception("API down"),
        ):
            await service._enrich_with_elevation(caches)  # should not raise


# ---------------------------------------------------------------------------
# _enrich_with_geocoding
# ---------------------------------------------------------------------------


class TestEnrichWithGeocoding:
    @pytest.mark.asyncio
    async def test_skips_when_all_have_country_id(self):
        service = _make_service()
        country_id = ObjectId()
        caches = [{"GC": "GC12345", "lat": 48.85, "lon": 2.35, "country_id": country_id}]

        with patch(
            "app.services.gpx_import.gpx_import_service.geocoding_nominatim.fetch_batch",
            new_callable=AsyncMock,
        ) as mock_fetch:
            await service._enrich_with_geocoding(caches)
            mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_caches_without_coords(self):
        service = _make_service()
        caches = [{"GC": "GC12345"}]  # no lat/lon, no country_id

        with patch(
            "app.services.gpx_import.gpx_import_service.geocoding_nominatim.fetch_batch",
            new_callable=AsyncMock,
        ) as mock_fetch:
            await service._enrich_with_geocoding(caches)
            mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_assigns_country_and_state(self):
        service = _make_service()
        caches = [{"GC": "GC12345", "lat": 48.85, "lon": 2.35}]
        country_id = ObjectId()
        state_id = ObjectId()

        with patch(
            "app.services.gpx_import.gpx_import_service.geocoding_nominatim.fetch_batch",
            new_callable=AsyncMock,
            return_value=([("France", "Normandy")], {200: 1}),
        ):
            service.referential_mapper.ensure_country_and_state = AsyncMock(
                return_value=(country_id, state_id)
            )
            await service._enrich_with_geocoding(caches)

        assert caches[0]["country_id"] == country_id
        assert caches[0]["state_id"] == state_id

    @pytest.mark.asyncio
    async def test_skips_when_geo_result_is_none(self):
        service = _make_service()
        caches = [{"GC": "GC12345", "lat": 48.85, "lon": 2.35}]

        with patch(
            "app.services.gpx_import.gpx_import_service.geocoding_nominatim.fetch_batch",
            new_callable=AsyncMock,
            return_value=([None], {}),
        ):
            await service._enrich_with_geocoding(caches)

        assert "country_id" not in caches[0]

    @pytest.mark.asyncio
    async def test_skips_when_country_id_none_from_mapper(self):
        service = _make_service()
        caches = [{"GC": "GC12345", "lat": 48.85, "lon": 2.35}]

        with patch(
            "app.services.gpx_import.gpx_import_service.geocoding_nominatim.fetch_batch",
            new_callable=AsyncMock,
            return_value=([("Unknown", None)], {}),
        ):
            service.referential_mapper.ensure_country_and_state = AsyncMock(
                return_value=(None, None)
            )
            await service._enrich_with_geocoding(caches)

        assert "country_id" not in caches[0]

    @pytest.mark.asyncio
    async def test_assigns_country_without_state(self):
        service = _make_service()
        caches = [{"GC": "GC12345", "lat": 48.85, "lon": 2.35}]
        country_id = ObjectId()

        with patch(
            "app.services.gpx_import.gpx_import_service.geocoding_nominatim.fetch_batch",
            new_callable=AsyncMock,
            return_value=([("France", None)], {}),
        ):
            service.referential_mapper.ensure_country_and_state = AsyncMock(
                return_value=(country_id, None)
            )
            await service._enrich_with_geocoding(caches)

        assert caches[0]["country_id"] == country_id
        assert "state_id" not in caches[0]


# ---------------------------------------------------------------------------
# get_import_statistics
# ---------------------------------------------------------------------------


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
