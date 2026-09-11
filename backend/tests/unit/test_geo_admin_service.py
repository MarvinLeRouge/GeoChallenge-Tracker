# backend/tests/unit/test_geo_admin_service.py
"""Tests for app.services.zones.geo_admin_service."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.zones import geo_admin_service as svc


def _mock_aggregate_collection(docs: list[dict]) -> MagicMock:
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=docs)
    coll = MagicMock()
    coll.aggregate.return_value = cursor
    return coll


class TestGetMissingCountries:
    @pytest.mark.asyncio
    async def test_excludes_countries_with_existing_directory(self, tmp_path: Path):
        (tmp_path / "FR").mkdir()
        docs = [
            {"_id": "FR", "found_count": 100},
            {"_id": "DE", "found_count": 5},
        ]
        with (
            patch.object(
                svc, "get_collection", AsyncMock(return_value=_mock_aggregate_collection(docs))
            ),
            patch.object(svc, "_geo_data_dir", return_value=tmp_path),
        ):
            result = await svc.get_missing_countries()

        assert result == [{"code": "DE", "found_count": 5}]

    @pytest.mark.asyncio
    async def test_sorted_by_found_count_desc(self, tmp_path: Path):
        docs = [
            {"_id": "DE", "found_count": 5},
            {"_id": "ES", "found_count": 42},
        ]
        with (
            patch.object(
                svc, "get_collection", AsyncMock(return_value=_mock_aggregate_collection(docs))
            ),
            patch.object(svc, "_geo_data_dir", return_value=tmp_path),
        ):
            result = await svc.get_missing_countries()

        assert [r["code"] for r in result] == ["ES", "DE"]

    @pytest.mark.asyncio
    async def test_empty_when_no_found_caches(self, tmp_path: Path):
        with (
            patch.object(
                svc, "get_collection", AsyncMock(return_value=_mock_aggregate_collection([]))
            ),
            patch.object(svc, "_geo_data_dir", return_value=tmp_path),
        ):
            result = await svc.get_missing_countries()

        assert result == []
