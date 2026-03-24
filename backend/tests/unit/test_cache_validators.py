"""Tests for cache_validators (unit tests - no external DB required)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from bson import ObjectId

from app.services.cache_validators import validate_cache_comprehensive

_OID_TYPE = ObjectId()
_OID_SIZE = ObjectId()

_ALL_TYPES = {"traditional": _OID_TYPE}
_ALL_SIZES = {"regular": _OID_SIZE}

_BASE_ITEM = {
    "latitude": 48.8566,
    "longitude": 2.3522,
    "cache_type": "traditional",
    "cache_size": "regular",
    "difficulty": "2.5",
    "terrain": "3.0",
}


@pytest.fixture
def exists_id_true():
    with patch(
        "app.services.referentials_cache.exists_id",
        return_value=True,
    ):
        yield


# ---------------------------------------------------------------------------
# Coordinate validation (no mocking needed — returns early)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_lat_invalid():
    item = {"longitude": 2.3522}
    result = await validate_cache_comprehensive(item, {}, {})
    assert result["is_valid"] is False
    assert result["reason"] == "missing_coordinates"


@pytest.mark.asyncio
async def test_missing_lon_invalid():
    item = {"latitude": 48.8566}
    result = await validate_cache_comprehensive(item, {}, {})
    assert result["is_valid"] is False
    assert result["reason"] == "missing_coordinates"


@pytest.mark.asyncio
async def test_lat_out_of_range():
    item = {"latitude": 91.0, "longitude": 2.3522}
    result = await validate_cache_comprehensive(item, {}, {})
    assert result["is_valid"] is False
    assert "range" in result["reason"]


@pytest.mark.asyncio
async def test_invalid_coordinate_values():
    item = {"latitude": "not_a_number", "longitude": 2.3522}
    result = await validate_cache_comprehensive(item, {}, {})
    assert result["is_valid"] is False
    assert "invalid_coordinate" in result["reason"]


# ---------------------------------------------------------------------------
# Type/size validation (needs mocking)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_type_invalid():
    item = {**_BASE_ITEM, "cache_type": "nonexistent_type"}
    with (
        patch("app.services.referentials_cache.resolve_type_code", return_value=None),
        patch("app.services.referentials_cache.exists_id", return_value=True),
    ):
        result = await validate_cache_comprehensive(item, {}, _ALL_SIZES)
    assert result["is_valid"] is False
    assert "unknown_cache_type" in result["reason"]


@pytest.mark.asyncio
async def test_type_found_but_not_in_db():
    item = {**_BASE_ITEM}
    with patch("app.services.referentials_cache.exists_id", side_effect=[False, True]):
        result = await validate_cache_comprehensive(item, _ALL_TYPES, _ALL_SIZES)
    assert result["is_valid"] is False
    assert "cache_type_not_in_db" in result["reason"]


@pytest.mark.asyncio
async def test_unknown_size_invalid():
    item = {**_BASE_ITEM, "cache_size": "unknown_size"}
    with (
        patch("app.services.referentials_cache.exists_id", return_value=True),
        patch("app.services.referentials_cache.resolve_size_code", return_value=None),
        patch("app.services.referentials_cache.resolve_size_name", return_value=None),
    ):
        result = await validate_cache_comprehensive(item, _ALL_TYPES, {})
    assert result["is_valid"] is False
    assert "unknown_cache_size" in result["reason"]


@pytest.mark.asyncio
async def test_size_found_but_not_in_db(exists_id_true):
    item = {**_BASE_ITEM}
    with patch("app.services.referentials_cache.exists_id", side_effect=[True, False]):
        result = await validate_cache_comprehensive(item, _ALL_TYPES, _ALL_SIZES)
    assert result["is_valid"] is False
    assert "cache_size_not_in_db" in result["reason"]


# ---------------------------------------------------------------------------
# Difficulty / terrain validation (needs type+size mocking)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_difficulty_out_of_range(exists_id_true):
    item = {**_BASE_ITEM, "difficulty": "6.0"}
    result = await validate_cache_comprehensive(item, _ALL_TYPES, _ALL_SIZES)
    assert result["is_valid"] is False
    assert "difficulty_out_of_range" in result["reason"]


@pytest.mark.asyncio
async def test_difficulty_invalid_increment(exists_id_true):
    item = {**_BASE_ITEM, "difficulty": "2.3"}
    result = await validate_cache_comprehensive(item, _ALL_TYPES, _ALL_SIZES)
    assert result["is_valid"] is False
    assert "difficulty_invalid_increment" in result["reason"]


@pytest.mark.asyncio
async def test_terrain_out_of_range(exists_id_true):
    item = {**_BASE_ITEM, "terrain": "0.5"}
    result = await validate_cache_comprehensive(item, _ALL_TYPES, _ALL_SIZES)
    assert result["is_valid"] is False
    assert "terrain_out_of_range" in result["reason"]


@pytest.mark.asyncio
async def test_terrain_invalid_increment(exists_id_true):
    item = {**_BASE_ITEM, "terrain": "2.7"}
    result = await validate_cache_comprehensive(item, _ALL_TYPES, _ALL_SIZES)
    assert result["is_valid"] is False
    assert "terrain_invalid_increment" in result["reason"]


@pytest.mark.asyncio
async def test_valid_item_passes(exists_id_true):
    result = await validate_cache_comprehensive(_BASE_ITEM, _ALL_TYPES, _ALL_SIZES)
    assert result["is_valid"] is True
    assert result["reason"] == "valid"


@pytest.mark.asyncio
async def test_empty_difficulty_and_terrain_ok(exists_id_true):
    item = {**_BASE_ITEM, "difficulty": "", "terrain": ""}
    result = await validate_cache_comprehensive(item, _ALL_TYPES, _ALL_SIZES)
    assert result["is_valid"] is True
