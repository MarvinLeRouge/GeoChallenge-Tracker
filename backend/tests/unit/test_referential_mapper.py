"""Tests for app/services/gpx_import/referential_mapper.py."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId

from app.services.gpx_import.referential_mapper import ReferentialMapper

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db():
    class MockDB:
        def __init__(self):
            self.countries = MagicMock()
            self.states = MagicMock()
            self.cache_types = MagicMock()
            self.cache_sizes = MagicMock()
            self.cache_attributes = MagicMock()

    return MockDB()


def _async_cursor(*docs):
    """Return a mock cursor that asynchronously yields docs."""

    async def aiter():
        for doc in docs:
            yield doc

    cursor = MagicMock()
    cursor.__aiter__ = MagicMock(return_value=aiter())
    return cursor


def _make_mapper(db=None) -> ReferentialMapper:
    return ReferentialMapper(db or _make_db())


# ---------------------------------------------------------------------------
# normalize_name
# ---------------------------------------------------------------------------


class TestNormalizeName:
    def test_empty_returns_empty(self):
        assert ReferentialMapper.normalize_name("") == ""

    def test_none_returns_empty(self):
        assert ReferentialMapper.normalize_name(None) == ""

    def test_lowercases(self):
        assert ReferentialMapper.normalize_name("France") == "france"

    def test_strips_diacritics(self):
        assert ReferentialMapper.normalize_name("Île-de-France") == "iledefrance"

    def test_removes_special_chars(self):
        assert ReferentialMapper.normalize_name("New-York!") == "newyork"

    def test_ascii_digits_kept(self):
        assert ReferentialMapper.normalize_name("Region1") == "region1"


# ---------------------------------------------------------------------------
# _load_countries / _load_states / _load_types / _load_sizes / _load_attributes
# ---------------------------------------------------------------------------


class TestLoadReferentials:
    @pytest.mark.asyncio
    async def test_load_countries_populates_cache(self):
        db = _make_db()
        oid = ObjectId()
        db.countries.find = MagicMock(return_value=_async_cursor({"_id": oid, "name": "France"}))
        mapper = _make_mapper(db)
        await mapper._load_countries()
        assert mapper._countries_cache["france"] == oid

    @pytest.mark.asyncio
    async def test_load_states_populates_cache(self):
        db = _make_db()
        country_id = ObjectId()
        state_id = ObjectId()
        db.states.find = MagicMock(
            return_value=_async_cursor(
                {"_id": state_id, "name": "Normandy", "country_id": country_id}
            )
        )
        mapper = _make_mapper(db)
        await mapper._load_states()
        assert mapper._states_cache[country_id]["normandy"] == state_id

    @pytest.mark.asyncio
    async def test_load_types_populates_cache(self):
        db = _make_db()
        oid = ObjectId()
        db.cache_types.find = MagicMock(
            return_value=_async_cursor({"_id": oid, "name": "Traditional"})
        )
        mapper = _make_mapper(db)
        await mapper._load_types()
        assert mapper._types_cache["traditional"] == oid

    @pytest.mark.asyncio
    async def test_load_sizes_populates_cache(self):
        db = _make_db()
        oid = ObjectId()
        db.cache_sizes.find = MagicMock(return_value=_async_cursor({"_id": oid, "name": "Regular"}))
        mapper = _make_mapper(db)
        await mapper._load_sizes()
        assert mapper._sizes_cache["regular"] == oid

    @pytest.mark.asyncio
    async def test_load_attributes_populates_cache(self):
        db = _make_db()
        oid = ObjectId()
        db.cache_attributes.find = MagicMock(
            return_value=_async_cursor({"_id": oid, "cache_attribute_id": 8})
        )
        mapper = _make_mapper(db)
        await mapper._load_attributes()
        assert mapper._attributes_cache[8] == oid

    @pytest.mark.asyncio
    async def test_load_attributes_skips_missing_id(self):
        db = _make_db()
        oid = ObjectId()
        db.cache_attributes.find = MagicMock(
            return_value=_async_cursor({"_id": oid})  # no cache_attribute_id key
        )
        mapper = _make_mapper(db)
        await mapper._load_attributes()
        assert mapper._attributes_cache == {}

    @pytest.mark.asyncio
    async def test_load_all_referentials_calls_all(self):
        db = _make_db()
        for coll in [db.countries, db.states, db.cache_types, db.cache_sizes, db.cache_attributes]:
            coll.find = MagicMock(return_value=_async_cursor())
        mapper = _make_mapper(db)
        await mapper.load_all_referentials()
        # All 5 caches should be cleared/populated (empty)
        assert mapper._countries_cache == {}
        assert mapper._types_cache == {}


# ---------------------------------------------------------------------------
# ensure_country_and_state
# ---------------------------------------------------------------------------


class TestEnsureCountryAndState:
    @pytest.mark.asyncio
    async def test_returns_none_none_when_no_country(self):
        mapper = _make_mapper()
        result = await mapper.ensure_country_and_state(None, None)
        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_returns_cached_country(self):
        mapper = _make_mapper()
        oid = ObjectId()
        mapper._countries_cache["france"] = oid
        country_id, state_id = await mapper.ensure_country_and_state("France", None)
        assert country_id == oid
        assert state_id is None

    @pytest.mark.asyncio
    async def test_creates_country_when_not_cached(self):
        db = _make_db()
        new_id = ObjectId()
        db.countries.insert_one = AsyncMock(return_value=MagicMock(inserted_id=new_id))
        mapper = _make_mapper(db)

        country_id, _ = await mapper.ensure_country_and_state("Germany", None)
        assert country_id == new_id
        assert mapper._countries_cache["germany"] == new_id

    @pytest.mark.asyncio
    async def test_returns_cached_state(self):
        mapper = _make_mapper()
        country_id = ObjectId()
        state_id = ObjectId()
        mapper._countries_cache["france"] = country_id
        mapper._states_cache[country_id] = {"normandy": state_id}

        _, result_state_id = await mapper.ensure_country_and_state("France", "Normandy")
        assert result_state_id == state_id

    @pytest.mark.asyncio
    async def test_creates_state_when_not_cached(self):
        db = _make_db()
        country_id = ObjectId()
        state_id = ObjectId()
        db.states.insert_one = AsyncMock(return_value=MagicMock(inserted_id=state_id))
        mapper = _make_mapper(db)
        mapper._countries_cache["france"] = country_id

        _, result_state_id = await mapper.ensure_country_and_state("France", "Bretagne")
        assert result_state_id == state_id
        assert mapper._states_cache[country_id]["bretagne"] == state_id

    @pytest.mark.asyncio
    async def test_create_state_initialises_country_entry_in_cache(self):
        """_create_state initialises _states_cache[country_id] if absent."""
        db = _make_db()
        country_id = ObjectId()
        state_id = ObjectId()
        db.states.insert_one = AsyncMock(return_value=MagicMock(inserted_id=state_id))
        mapper = _make_mapper(db)
        mapper._countries_cache["spain"] = country_id
        # Ensure there is no entry yet
        assert country_id not in mapper._states_cache

        await mapper.ensure_country_and_state("Spain", "Catalonia")
        assert country_id in mapper._states_cache


# ---------------------------------------------------------------------------
# get_type_by_name / get_size_by_name / get_attribute_by_gc_id
# ---------------------------------------------------------------------------


class TestGetters:
    def test_get_type_none_returns_none(self):
        mapper = _make_mapper()
        assert mapper.get_type_by_name(None) is None

    def test_get_type_unknown_returns_none(self):
        mapper = _make_mapper()
        assert mapper.get_type_by_name("Mystery") is None

    def test_get_type_returns_cached_id(self):
        mapper = _make_mapper()
        oid = ObjectId()
        mapper._types_cache["traditional"] = oid
        assert mapper.get_type_by_name("Traditional") == oid

    def test_get_size_none_returns_none(self):
        mapper = _make_mapper()
        assert mapper.get_size_by_name(None) is None

    def test_get_size_returns_cached_id(self):
        mapper = _make_mapper()
        oid = ObjectId()
        mapper._sizes_cache["regular"] = oid
        assert mapper.get_size_by_name("Regular") == oid

    def test_get_attribute_none_returns_none(self):
        mapper = _make_mapper()
        assert mapper.get_attribute_by_gc_id(None) is None

    def test_get_attribute_returns_cached_id(self):
        mapper = _make_mapper()
        oid = ObjectId()
        mapper._attributes_cache[8] = oid
        assert mapper.get_attribute_by_gc_id(8) == oid

    def test_get_attribute_unknown_returns_none(self):
        mapper = _make_mapper()
        assert mapper.get_attribute_by_gc_id(999) is None


# ---------------------------------------------------------------------------
# map_cache_referentials
# ---------------------------------------------------------------------------


class TestMapCacheReferentials:
    @pytest.mark.asyncio
    async def test_maps_country_and_state(self):
        mapper = _make_mapper()
        country_id = ObjectId()
        state_id = ObjectId()
        mapper._countries_cache["france"] = country_id
        mapper._states_cache[country_id] = {"normandy": state_id}

        result = await mapper.map_cache_referentials({"country": "France", "state": "Normandy"})
        assert result["country_id"] == country_id
        assert result["state_id"] == state_id

    @pytest.mark.asyncio
    async def test_maps_type_and_size(self):
        mapper = _make_mapper()
        type_id = ObjectId()
        size_id = ObjectId()
        mapper._types_cache["traditional"] = type_id
        mapper._sizes_cache["regular"] = size_id

        result = await mapper.map_cache_referentials(
            {"type": "Traditional", "size": "Regular", "country": None}
        )
        assert result["type_id"] == type_id
        assert result["size_id"] == size_id

    @pytest.mark.asyncio
    async def test_maps_attributes(self):
        mapper = _make_mapper()
        attr_id = ObjectId()
        mapper._attributes_cache[8] = attr_id

        result = await mapper.map_cache_referentials(
            {
                "country": None,
                "attributes": [{"id": 8, "is_positive": True}, {"id": 999}],
            }
        )
        assert len(result["attributes"]) == 1
        assert result["attributes"][0]["attribute_doc_id"] == attr_id

    @pytest.mark.asyncio
    async def test_skips_attr_without_id_key(self):
        mapper = _make_mapper()
        result = await mapper.map_cache_referentials(
            {"country": None, "attributes": [{"is_positive": True}]}
        )
        assert result["attributes"] == []

    @pytest.mark.asyncio
    async def test_no_country_no_ids_added(self):
        mapper = _make_mapper()
        result = await mapper.map_cache_referentials({"country": None})
        assert "country_id" not in result
        assert "state_id" not in result
