"""Tests for GpxImportService: _enrich_with_elevation, _enrich_with_geocoding."""

from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId

from tests.unit._gpx_import_service_test_helpers import (
    _make_service,
)


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
