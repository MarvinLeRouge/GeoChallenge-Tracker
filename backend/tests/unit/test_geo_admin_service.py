# backend/tests/unit/test_geo_admin_service.py
"""Tests for app.services.zones.geo_admin_service."""

from __future__ import annotations

import json as jsonlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

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


def _mock_upsert_collection() -> MagicMock:
    coll = MagicMock()
    coll.update_one = AsyncMock(return_value=MagicMock(upserted_id=ObjectId()))
    return coll


def _feature(code: str, nom: str, bbox: list[float], parent_code: str | None = None) -> dict:
    props = {"code": code, "nom": nom, "feature_code": code}
    if parent_code is not None:
        props["parent_code"] = parent_code
    return {
        "type": "Feature",
        "properties": props,
        "bbox": bbox,
        "geometry": {"type": "Point", "coordinates": [0, 0]},
    }


class TestUploadZoneLevel:
    @pytest.mark.asyncio
    async def test_rejects_invalid_json(self, tmp_path: Path):
        with patch.object(svc, "_geo_data_dir", return_value=tmp_path):
            with pytest.raises(ValueError, match="not valid JSON"):
                await svc.upload_zone_level("FR", 1, b"not json")

    @pytest.mark.asyncio
    async def test_rejects_non_feature_collection(self, tmp_path: Path):
        content = jsonlib.dumps({"type": "Feature"}).encode()
        with patch.object(svc, "_geo_data_dir", return_value=tmp_path):
            with pytest.raises(ValueError, match="FeatureCollection"):
                await svc.upload_zone_level("FR", 1, content)

    @pytest.mark.asyncio
    async def test_rejects_missing_features_array(self, tmp_path: Path):
        content = jsonlib.dumps({"type": "FeatureCollection"}).encode()
        with patch.object(svc, "_geo_data_dir", return_value=tmp_path):
            with pytest.raises(ValueError, match="no 'features' array"):
                await svc.upload_zone_level("FR", 1, content)

    @pytest.mark.asyncio
    async def test_rejects_feature_missing_bbox(self, tmp_path: Path):
        feature = _feature("84", "Auvergne-Rhône-Alpes", [0, 0, 1, 1])
        del feature["bbox"]
        fc = {"type": "FeatureCollection", "features": [feature]}
        content = jsonlib.dumps(fc).encode()
        with patch.object(svc, "_geo_data_dir", return_value=tmp_path):
            with pytest.raises(ValueError, match="'bbox' member"):
                await svc.upload_zone_level("FR", 1, content)

    @pytest.mark.asyncio
    async def test_rejects_feature_missing_required_property(self, tmp_path: Path):
        fc = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {}, "geometry": None}],
        }
        content = jsonlib.dumps(fc).encode()
        with patch.object(svc, "_geo_data_dir", return_value=tmp_path):
            with pytest.raises(ValueError, match="'code'"):
                await svc.upload_zone_level("FR", 1, content)

    @pytest.mark.asyncio
    async def test_rejects_level_2_feature_missing_parent_code(self, tmp_path: Path):
        fc = {
            "type": "FeatureCollection",
            "features": [_feature("38", "Isère", [0, 0, 1, 1])],
        }
        content = jsonlib.dumps(fc).encode()
        with patch.object(svc, "_geo_data_dir", return_value=tmp_path):
            with pytest.raises(ValueError, match="parent_code"):
                await svc.upload_zone_level("FR", 2, content)

    @pytest.mark.asyncio
    async def test_writes_file_and_upserts_level_1(self, tmp_path: Path):
        fc = {
            "type": "FeatureCollection",
            "features": [_feature("84", "Auvergne-Rhône-Alpes", [4.0, 44.0, 7.0, 46.5])],
        }
        content = jsonlib.dumps(fc).encode()
        col = _mock_upsert_collection()
        with (
            patch.object(svc, "_geo_data_dir", return_value=tmp_path),
            patch.object(svc, "get_collection", AsyncMock(return_value=col)),
        ):
            result = await svc.upload_zone_level("FR", 1, content)

        written = tmp_path / "FR" / "adm1.geojson"
        assert written.exists()
        assert jsonlib.loads(written.read_text()) == fc
        assert result == {
            "country_code": "FR",
            "level": 1,
            "features_count": 1,
            "inserted": 1,
            "updated": 0,
        }
        col.update_one.assert_awaited_once_with(
            {"code": "FR-84", "level": 1},
            {
                "$set": {
                    "code": "FR-84",
                    "country_code": "FR",
                    "level": 1,
                    "name": "Auvergne-Rhône-Alpes",
                    "parent_code": None,
                    "geojson_file": "FR/adm1.geojson",
                    "feature_code": "84",
                    "bbox": [4.0, 44.0, 7.0, 46.5],
                }
            },
            upsert=True,
        )

    @pytest.mark.asyncio
    async def test_writes_file_and_updates_existing_zone(self, tmp_path: Path):
        fc = {
            "type": "FeatureCollection",
            "features": [_feature("84", "Auvergne-Rhône-Alpes", [4.0, 44.0, 7.0, 46.5])],
        }
        content = jsonlib.dumps(fc).encode()
        col = MagicMock()
        col.update_one = AsyncMock(return_value=MagicMock(upserted_id=None))
        with (
            patch.object(svc, "_geo_data_dir", return_value=tmp_path),
            patch.object(svc, "get_collection", AsyncMock(return_value=col)),
        ):
            result = await svc.upload_zone_level("FR", 1, content)

        assert result == {
            "country_code": "FR",
            "level": 1,
            "features_count": 1,
            "inserted": 0,
            "updated": 1,
        }

    @pytest.mark.asyncio
    async def test_level_0_writes_file_without_db_upsert(self, tmp_path: Path):
        fc = {"type": "FeatureCollection", "features": [_feature("FR", "France", [-5, 41, 10, 51])]}
        content = jsonlib.dumps(fc).encode()
        with (
            patch.object(svc, "_geo_data_dir", return_value=tmp_path),
            patch.object(svc, "get_collection", AsyncMock()) as mock_get_collection,
        ):
            result = await svc.upload_zone_level("FR", 0, content)

        assert (tmp_path / "FR" / "adm0.geojson").exists()
        assert result == {
            "country_code": "FR",
            "level": 0,
            "features_count": 1,
            "inserted": 0,
            "updated": 0,
        }
        mock_get_collection.assert_not_awaited()
