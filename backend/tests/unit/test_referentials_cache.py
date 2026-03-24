"""Tests for referentials_cache (unit — no DB, sync + async)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

import app.services.referentials_cache as rc
from app.services.referentials_cache import (
    _map_collection,
    _map_collection_states,
    _resolve_code_to_id,
    exists_attribute_id,
    exists_id,
    populate_mapping,
    refresh_referentials_cache,
    resolve_attribute_code,
    resolve_country_name,
    resolve_size_alias,
    resolve_size_code,
    resolve_size_name,
    resolve_state_name,
    resolve_type_code,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_mapping():
    """Reset the in-memory mapping before and after every test."""
    rc.collections_mapping.clear()
    yield
    rc.collections_mapping.clear()


def _mock_collection(docs: list[dict]) -> MagicMock:
    """Return a Motor collection mock whose .find().to_list() returns *docs*."""
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=docs)
    coll = MagicMock()
    coll.find.return_value = cursor
    return coll


# ---------------------------------------------------------------------------
# exists_id
# ---------------------------------------------------------------------------


class TestExistsId:
    def test_found(self):
        oid = ObjectId()
        rc.collections_mapping["cache_types"] = {"ids": {oid}}
        assert exists_id("cache_types", oid) is True

    def test_not_found(self):
        rc.collections_mapping["cache_types"] = {"ids": set()}
        assert exists_id("cache_types", ObjectId()) is False

    def test_unknown_collection(self):
        assert exists_id("nonexistent", ObjectId()) is False

    def test_invalid_oid_string(self):
        rc.collections_mapping["cache_types"] = {"ids": set()}
        assert exists_id("cache_types", "not-an-oid") is False

    def test_oid_as_string_valid(self):
        oid = ObjectId()
        rc.collections_mapping["cache_types"] = {"ids": {oid}}
        assert exists_id("cache_types", str(oid)) is True


# ---------------------------------------------------------------------------
# exists_attribute_id
# ---------------------------------------------------------------------------


class TestExistsAttributeId:
    def test_found(self):
        rc.collections_mapping["cache_attributes"] = {"numeric_ids": {42}}
        assert exists_attribute_id(42) is True

    def test_not_found(self):
        rc.collections_mapping["cache_attributes"] = {"numeric_ids": {1, 2}}
        assert exists_attribute_id(99) is False

    def test_collection_absent(self):
        assert exists_attribute_id(1) is False

    def test_invalid_value_returns_false(self):
        rc.collections_mapping["cache_attributes"] = {"numeric_ids": {1}}
        assert exists_attribute_id("not-a-number") is False


# ---------------------------------------------------------------------------
# _resolve_code_to_id
# ---------------------------------------------------------------------------


class TestResolveCodeToId:
    def test_resolve_by_code(self):
        oid = ObjectId()
        rc.collections_mapping["cache_types"] = {"code": {"tr": oid}}
        result = _resolve_code_to_id("cache_types", "code", "TR")
        assert result == oid

    def test_resolve_by_code_case_insensitive(self):
        oid = ObjectId()
        rc.collections_mapping["cache_types"] = {"code": {"tr": oid}}
        assert _resolve_code_to_id("cache_types", "code", "tr") == oid

    def test_resolve_by_aliases(self):
        oid = ObjectId()
        rc.collections_mapping["cache_sizes"] = {"aliases": {"nano": oid}}
        result = _resolve_code_to_id("cache_sizes", "aliases", "nano")
        assert result == oid

    def test_not_found(self):
        rc.collections_mapping["cache_types"] = {"code": {}}
        assert _resolve_code_to_id("cache_types", "code", "unknown") is None

    def test_missing_collection(self):
        assert _resolve_code_to_id("nonexistent", "code", "x") is None


# ---------------------------------------------------------------------------
# resolve_attribute_code
# ---------------------------------------------------------------------------


class TestResolveAttributeCode:
    def test_found_by_code(self):
        oid = ObjectId()
        rc.collections_mapping["cache_attributes"] = {
            "code": {"dogs_allowed": oid},
            "name": {},
            "doc_by_id": {oid: {"cache_attribute_id": 7}},
        }
        result = resolve_attribute_code("dogs_allowed")
        assert result == (oid, 7)

    def test_found_by_name_fallback(self):
        oid = ObjectId()
        rc.collections_mapping["cache_attributes"] = {
            "code": {},
            "name": {"dogs allowed": oid},
            "doc_by_id": {oid: {"cache_attribute_id": 7}},
        }
        result = resolve_attribute_code("Dogs Allowed")
        assert result == (oid, 7)

    def test_not_found(self):
        rc.collections_mapping["cache_attributes"] = {
            "code": {},
            "name": {},
            "doc_by_id": {},
        }
        assert resolve_attribute_code("nonexistent") is None

    def test_no_numeric_id_in_doc(self):
        oid = ObjectId()
        rc.collections_mapping["cache_attributes"] = {
            "code": {"x": oid},
            "name": {},
            "doc_by_id": {oid: {}},
        }
        result = resolve_attribute_code("x")
        assert result == (oid, None)


# ---------------------------------------------------------------------------
# resolve_type_code / resolve_size_code / resolve_size_name / resolve_size_alias / resolve_country_name
# ---------------------------------------------------------------------------


class TestResolveHelpers:
    def test_resolve_type_code_found(self):
        oid = ObjectId()
        rc.collections_mapping["cache_types"] = {"code": {"tr": oid}}
        assert resolve_type_code("TR") == oid

    def test_resolve_type_code_not_found(self):
        rc.collections_mapping["cache_types"] = {"code": {}}
        assert resolve_type_code("unknown") is None

    def test_resolve_size_code_found(self):
        oid = ObjectId()
        rc.collections_mapping["cache_sizes"] = {"code": {"s": oid}}
        assert resolve_size_code("S") == oid

    def test_resolve_size_name_by_name(self):
        oid = ObjectId()
        rc.collections_mapping["cache_sizes"] = {"name": {"micro": oid}, "aliases": {}}
        assert resolve_size_name("Micro") == oid

    def test_resolve_size_name_falls_back_to_alias(self):
        oid = ObjectId()
        rc.collections_mapping["cache_sizes"] = {"name": {}, "aliases": {"nano": oid}}
        assert resolve_size_name("nano") == oid

    def test_resolve_size_name_not_found(self):
        rc.collections_mapping["cache_sizes"] = {"name": {}, "aliases": {}}
        assert resolve_size_name("unknown") is None

    def test_resolve_size_alias(self):
        oid = ObjectId()
        rc.collections_mapping["cache_sizes"] = {"aliases": {"nano": oid}}
        assert resolve_size_alias("nano") == oid

    def test_resolve_country_name(self):
        oid = ObjectId()
        rc.collections_mapping["countries"] = {"name": {"france": oid}}
        assert resolve_country_name("France") == oid


# ---------------------------------------------------------------------------
# resolve_state_name
# ---------------------------------------------------------------------------


class TestResolveStateName:
    def _setup(self, country_id: ObjectId, state_id: ObjectId, state_name: str):
        rc.collections_mapping["states"] = {
            "ids": {state_id},
            "by_country": {str(country_id): {state_name.lower(): state_id}},
        }

    def test_with_country_found(self):
        cid, sid = ObjectId(), ObjectId()
        self._setup(cid, sid, "Bretagne")
        result, err = resolve_state_name("Bretagne", country_id=cid)
        assert result == sid
        assert err is None

    def test_with_country_not_found(self):
        cid = ObjectId()
        rc.collections_mapping["states"] = {"ids": set(), "by_country": {}}
        result, err = resolve_state_name("Unknown", country_id=cid)
        assert result is None
        assert "not found" in err

    def test_without_country_single_hit(self):
        cid, sid = ObjectId(), ObjectId()
        self._setup(cid, sid, "Bretagne")
        result, err = resolve_state_name("Bretagne")
        assert result == sid
        assert err is None

    def test_without_country_no_hit(self):
        rc.collections_mapping["states"] = {"ids": set(), "by_country": {}}
        result, err = resolve_state_name("unknown")
        assert result is None
        assert "not found" in err

    def test_without_country_ambiguous(self):
        cid1, cid2 = ObjectId(), ObjectId()
        sid1, sid2 = ObjectId(), ObjectId()
        rc.collections_mapping["states"] = {
            "ids": {sid1, sid2},
            "by_country": {
                str(cid1): {"bretagne": sid1},
                str(cid2): {"bretagne": sid2},
            },
        }
        result, err = resolve_state_name("Bretagne")
        assert result is None
        assert "ambiguous" in err


# ---------------------------------------------------------------------------
# _map_collection (async — mocked get_collection)
# ---------------------------------------------------------------------------


class TestMapCollection:
    @pytest.mark.asyncio
    async def test_minimal_no_fields(self):
        oid = ObjectId()
        docs = [{"_id": oid}]
        with patch(
            "app.services.referentials_cache.get_collection",
            AsyncMock(return_value=_mock_collection(docs)),
        ):
            await _map_collection("cache_types")

        mapping = rc.collections_mapping["cache_types"]
        assert oid in mapping["ids"]

    @pytest.mark.asyncio
    async def test_with_code_and_name_fields(self):
        oid = ObjectId()
        docs = [{"_id": oid, "code": "TR", "name": "Traditional"}]
        with patch(
            "app.services.referentials_cache.get_collection",
            AsyncMock(return_value=_mock_collection(docs)),
        ):
            await _map_collection("cache_types", code_field="code", name_field="name")

        mapping = rc.collections_mapping["cache_types"]
        assert mapping["code"]["tr"] == oid
        assert mapping["name"]["traditional"] == oid

    @pytest.mark.asyncio
    async def test_with_numeric_id_field(self):
        oid = ObjectId()
        docs = [{"_id": oid, "cache_attribute_id": 7}]
        with patch(
            "app.services.referentials_cache.get_collection",
            AsyncMock(return_value=_mock_collection(docs)),
        ):
            await _map_collection("cache_attributes", extra_numeric_id_field="cache_attribute_id")

        assert 7 in rc.collections_mapping["cache_attributes"]["numeric_ids"]

    @pytest.mark.asyncio
    async def test_with_aliases_field(self):
        oid = ObjectId()
        docs = [{"_id": oid, "aliases": ["nano", "extra-small"]}]
        with patch(
            "app.services.referentials_cache.get_collection",
            AsyncMock(return_value=_mock_collection(docs)),
        ):
            await _map_collection("cache_sizes", aliases_field="aliases")

        mapping = rc.collections_mapping["cache_sizes"]
        assert mapping["aliases"]["nano"] == oid
        assert mapping["aliases"]["extra-small"] == oid

    @pytest.mark.asyncio
    async def test_invalid_numeric_id_silently_skipped(self):
        oid = ObjectId()
        docs = [{"_id": oid, "cache_attribute_id": "not_a_number"}]
        with patch(
            "app.services.referentials_cache.get_collection",
            AsyncMock(return_value=_mock_collection(docs)),
        ):
            await _map_collection("cache_attributes", extra_numeric_id_field="cache_attribute_id")

        assert rc.collections_mapping["cache_attributes"]["numeric_ids"] == set()


# ---------------------------------------------------------------------------
# _map_collection_states (async)
# ---------------------------------------------------------------------------


class TestMapCollectionStates:
    @pytest.mark.asyncio
    async def test_populates_by_country(self):
        cid = ObjectId()
        sid = ObjectId()
        docs = [{"_id": sid, "country_id": cid, "name": "Bretagne"}]
        with patch(
            "app.services.referentials_cache.get_collection",
            AsyncMock(return_value=_mock_collection(docs)),
        ):
            await _map_collection_states()

        mapping = rc.collections_mapping["states"]
        assert sid in mapping["ids"]
        assert mapping["by_country"][str(cid)]["bretagne"] == sid

    @pytest.mark.asyncio
    async def test_skips_doc_missing_fields(self):
        sid = ObjectId()
        docs = [{"_id": sid}]  # no country_id, no name
        with patch(
            "app.services.referentials_cache.get_collection",
            AsyncMock(return_value=_mock_collection(docs)),
        ):
            await _map_collection_states()

        mapping = rc.collections_mapping["states"]
        assert sid in mapping["ids"]
        assert mapping["by_country"] == {}


# ---------------------------------------------------------------------------
# populate_mapping / refresh_referentials_cache (async)
# ---------------------------------------------------------------------------


class TestPopulateMapping:
    @pytest.mark.asyncio
    async def test_sets_mapping_ready(self):
        with patch(
            "app.services.referentials_cache.get_collection",
            AsyncMock(return_value=_mock_collection([])),
        ):
            await populate_mapping()

        assert rc._mapping_ready is True
        assert isinstance(rc.collections_mapping, dict)

    @pytest.mark.asyncio
    async def test_refresh_calls_populate(self):
        with patch(
            "app.services.referentials_cache.populate_mapping",
            new_callable=AsyncMock,
        ) as mock_populate:
            await refresh_referentials_cache()

        mock_populate.assert_called_once()
