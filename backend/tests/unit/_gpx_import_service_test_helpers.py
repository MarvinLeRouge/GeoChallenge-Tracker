"""Shared test helpers for the test_gpx_import_service_main_* split test files."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


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
