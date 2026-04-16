"""Unit tests for zone_nominatim — Nominatim reverse geocoding fallback.

All HTTP calls and DB access are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.zones.zone_nominatim import (
    _extract_dept_code,
    resolve_zones_batch,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _nominatim_response(iso_code: str | None) -> dict:
    """Build a minimal Nominatim /reverse JSON payload."""
    address: dict = {}
    if iso_code:
        address["ISO3166-2-lvl6"] = iso_code
    return {"address": address}


def _mock_http_response(status: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    return resp


# ── Tests: _extract_dept_code ─────────────────────────────────────────────


class TestExtractDeptCode:
    """Tests for the pure _extract_dept_code function."""

    def test_returns_code_when_present(self):
        data = _nominatim_response("FR-83")
        assert _extract_dept_code(data) == "FR-83"

    def test_returns_none_when_key_missing(self):
        data = {"address": {"city": "Toulon"}}
        assert _extract_dept_code(data) is None

    def test_returns_none_when_address_missing(self):
        assert _extract_dept_code({}) is None

    def test_returns_none_when_address_is_none(self):
        assert _extract_dept_code({"address": None}) is None

    def test_returns_none_when_code_is_empty_string(self):
        data = {"address": {"ISO3166-2-lvl6": ""}}
        assert _extract_dept_code(data) is None

    def test_strips_whitespace(self):
        data = {"address": {"ISO3166-2-lvl6": "  FR-06  "}}
        assert _extract_dept_code(data) == "FR-06"


# ── Tests: resolve_zones_batch ────────────────────────────────────────────


def _patch_nominatim(responses: list[MagicMock]):
    """Patches httpx.AsyncClient.get to return responses in order."""
    get_mock = AsyncMock(side_effect=responses)

    class _FakeClient:
        async def __aenter__(self):
            self.get = get_mock
            return self

        async def __aexit__(self, *args):
            pass

    return patch(
        "app.services.zones.zone_nominatim.httpx.AsyncClient", return_value=_FakeClient()
    ), get_mock


def _patch_db(parent_code: str | None = "FR-93"):
    """Patches get_collection so find_one returns a zone doc with parent_code."""
    col = AsyncMock()
    col.find_one = AsyncMock(return_value={"parent_code": parent_code} if parent_code else None)
    return patch(
        "app.services.zones.zone_nominatim.get_collection",
        AsyncMock(return_value=col),
    )


class TestResolveZonesBatch:
    """Tests for resolve_zones_batch."""

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self):
        result = await resolve_zones_batch([], "FR")
        assert result == []

    @pytest.mark.asyncio
    async def test_single_point_resolved(self):
        resp = _mock_http_response(200, _nominatim_response("FR-83"))
        http_patch, _ = _patch_nominatim([resp])

        with http_patch, _patch_db("FR-93"):
            with patch("app.services.zones.zone_nominatim.asyncio.sleep", new_callable=AsyncMock):
                result = await resolve_zones_batch([(43.1, 5.9)], "FR")

        assert len(result) == 1
        assert result[0]["level2"] == "FR-83"
        assert result[0]["level1"] == "FR-93"
        assert result[0]["country"] == "FR"

    @pytest.mark.asyncio
    async def test_nominatim_no_code_gives_none(self):
        resp = _mock_http_response(200, _nominatim_response(None))
        http_patch, _ = _patch_nominatim([resp])

        with http_patch, _patch_db():
            with patch("app.services.zones.zone_nominatim.asyncio.sleep", new_callable=AsyncMock):
                result = await resolve_zones_batch([(43.1, 5.9)], "FR")

        assert result[0]["level2"] is None
        assert result[0]["level1"] is None

    @pytest.mark.asyncio
    async def test_nominatim_http_error_gives_none(self):
        resp = _mock_http_response(429, {})
        http_patch, _ = _patch_nominatim([resp])

        with http_patch, _patch_db():
            with patch("app.services.zones.zone_nominatim.asyncio.sleep", new_callable=AsyncMock):
                result = await resolve_zones_batch([(43.1, 5.9)], "FR")

        assert result[0]["level2"] is None

    @pytest.mark.asyncio
    async def test_parent_not_found_in_db(self):
        resp = _mock_http_response(200, _nominatim_response("FR-83"))
        http_patch, _ = _patch_nominatim([resp])

        with http_patch, _patch_db(parent_code=None):
            with patch("app.services.zones.zone_nominatim.asyncio.sleep", new_callable=AsyncMock):
                result = await resolve_zones_batch([(43.1, 5.9)], "FR")

        assert result[0]["level2"] == "FR-83"
        assert result[0]["level1"] is None

    @pytest.mark.asyncio
    async def test_multiple_points_sleep_between_calls(self):
        responses = [
            _mock_http_response(200, _nominatim_response("FR-83")),
            _mock_http_response(200, _nominatim_response("FR-06")),
        ]
        http_patch, _ = _patch_nominatim(responses)
        sleep_mock = AsyncMock()

        with http_patch, _patch_db("FR-93"):
            with patch("app.services.zones.zone_nominatim.asyncio.sleep", sleep_mock):
                result = await resolve_zones_batch([(43.1, 5.9), (43.7, 7.2)], "FR")

        # sleep should be called once (between the two points, not after the last)
        assert sleep_mock.call_count == 1
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_network_exception_gives_none(self):
        async def _raise(*args, **kwargs):
            raise httpx.ConnectError("timeout")

        class _FakeClient:
            async def __aenter__(self):
                self.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))
                return self

            async def __aexit__(self, *args):
                pass

        with patch(
            "app.services.zones.zone_nominatim.httpx.AsyncClient", return_value=_FakeClient()
        ):
            with patch("app.services.zones.zone_nominatim.asyncio.sleep", new_callable=AsyncMock):
                result = await resolve_zones_batch([(43.1, 5.9)], "FR")

        assert result[0]["level2"] is None
