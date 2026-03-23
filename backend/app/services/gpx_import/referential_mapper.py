# backend/app/services/gpx_import/referential_mapper.py
# Referential mapper (countries, states, types, sizes, attributes).

from __future__ import annotations

import asyncio
import re
import unicodedata
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.utils import now


class ReferentialMapper:
    """Referential mapping service for GPX import.

    Description:
        Handles resolution and creation of referentials
        (countries, states, cache types, sizes, attributes).
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize the mapper.

        Args:
            db: MongoDB database instance.
        """
        self.db = db
        self._countries_cache: dict[str, ObjectId] = {}
        self._states_cache: dict[ObjectId, dict[str, ObjectId]] = {}
        self._types_cache: dict[str, ObjectId] = {}
        self._sizes_cache: dict[str, ObjectId] = {}
        self._attributes_cache: dict[int, ObjectId] = {}

    async def load_all_referentials(self) -> None:
        """Load all referentials into cache."""
        await asyncio.gather(
            self._load_countries(),
            self._load_states(),
            self._load_types(),
            self._load_sizes(),
            self._load_attributes(),
        )

    async def _load_countries(self) -> None:
        """Load all countries into cache."""
        coll_countries = self.db.countries
        cursor = coll_countries.find({}, {"_id": 1, "name": 1})

        self._countries_cache.clear()
        async for doc in cursor:
            name = self.normalize_name(doc["name"])
            self._countries_cache[name] = doc["_id"]

    async def _load_states(self) -> None:
        """Load all states into cache, keyed by country."""
        coll_states = self.db.states
        cursor = coll_states.find({}, {"_id": 1, "name": 1, "country_id": 1})

        self._states_cache.clear()
        async for doc in cursor:
            country_id = doc["country_id"]
            name = self.normalize_name(doc["name"])

            if country_id not in self._states_cache:
                self._states_cache[country_id] = {}

            self._states_cache[country_id][name] = doc["_id"]

    async def _load_types(self) -> None:
        """Load all cache types into cache."""
        coll_types = self.db.cache_types
        cursor = coll_types.find({}, {"_id": 1, "name": 1})

        self._types_cache.clear()
        async for doc in cursor:
            name = self.normalize_name(doc["name"])
            self._types_cache[name] = doc["_id"]

    async def _load_sizes(self) -> None:
        """Load all cache sizes into cache."""
        coll_sizes = self.db.cache_sizes
        cursor = coll_sizes.find({}, {"_id": 1, "name": 1})

        self._sizes_cache.clear()
        async for doc in cursor:
            name = self.normalize_name(doc["name"])
            self._sizes_cache[name] = doc["_id"]

    async def _load_attributes(self) -> None:
        """Load all cache attributes into cache."""
        coll_attributes = self.db.cache_attributes
        cursor = coll_attributes.find({}, {"_id": 1, "cache_attribute_id": 1})

        self._attributes_cache.clear()
        async for doc in cursor:
            cache_attribute_id = doc.get("cache_attribute_id")
            if cache_attribute_id is not None:
                self._attributes_cache[int(cache_attribute_id)] = doc["_id"]

    @staticmethod
    def normalize_name(name: str | None) -> str:
        """Normalize a name for mapping.

        Description:
            Applies NFKD Unicode decomposition to strip diacritics (é→e, î→i, ü→u…),
            then lowercases and removes all non-alphanumeric characters.
            This ensures that accented and non-accented variants of the same name
            resolve to the same key and do not create duplicate referential entries.

        Args:
            name: Name to normalize.

        Returns:
            str: Normalized name (lowercase, ASCII alphanumeric only).
        """
        if not name:
            return ""

        # Decompose accented characters (NFKD), then drop combining marks
        decomposed = unicodedata.normalize("NFKD", name)
        ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
        return re.sub(r"[^a-z0-9]", "", ascii_only.lower())

    async def ensure_country_and_state(
        self, country_name: str | None, state_name: str | None
    ) -> tuple[ObjectId | None, ObjectId | None]:
        """Ensure the country and state exist, creating them if necessary.

        Args:
            country_name: Country name.
            state_name: State/region name.

        Returns:
            tuple: (country_id, state_id) or (None, None) if data is missing.
        """
        if not country_name:
            return None, None

        # Normalize and look up the country
        country_norm = self.normalize_name(country_name)
        country_id = self._countries_cache.get(country_norm)

        # Create the country if it does not exist
        if not country_id:
            country_id = await self._create_country(country_name, country_norm)

        # Handle state if provided
        state_id = None
        if state_name and country_id:
            state_norm = self.normalize_name(state_name)

            # Look up the state in cache
            country_states = self._states_cache.get(country_id, {})
            state_id = country_states.get(state_norm)

            # Create the state if it does not exist
            if not state_id:
                state_id = await self._create_state(state_name, state_norm, country_id)

        return country_id, state_id

    async def _create_country(self, original_name: str, normalized_name: str) -> ObjectId:
        """Create a new country."""
        coll_countries = self.db.countries

        doc = {
            "name": original_name,
            "created_at": now(),
            "updated_at": now(),
        }

        result = await coll_countries.insert_one(doc)
        country_id = result.inserted_id

        # Update the cache
        self._countries_cache[normalized_name] = country_id

        return country_id

    async def _create_state(
        self, original_name: str, normalized_name: str, country_id: ObjectId
    ) -> ObjectId:
        """Create a new state/region."""
        coll_states = self.db.states

        doc = {
            "name": original_name,
            "country_id": country_id,
            "created_at": now(),
            "updated_at": now(),
        }

        result = await coll_states.insert_one(doc)
        state_id = result.inserted_id

        # Update the cache
        if country_id not in self._states_cache:
            self._states_cache[country_id] = {}
        self._states_cache[country_id][normalized_name] = state_id

        return state_id

    def get_type_by_name(self, type_name: str | None) -> ObjectId | None:
        """Retrieve the cache type ID by name.

        Args:
            type_name: Cache type name.

        Returns:
            ObjectId | None: Type ID or None if not found.
        """
        if not type_name:
            return None

        normalized = self.normalize_name(type_name)
        return self._types_cache.get(normalized)

    def get_size_by_name(self, size_name: str | None) -> ObjectId | None:
        """Retrieve the cache size ID by name.

        Args:
            size_name: Cache size name.

        Returns:
            ObjectId | None: Size ID or None if not found.
        """
        if not size_name:
            return None

        normalized = self.normalize_name(size_name)
        return self._sizes_cache.get(normalized)

    def get_attribute_by_gc_id(self, gc_id: int | None) -> ObjectId | None:
        """Retrieve the attribute ID by its Geocaching ID.

        Args:
            gc_id: Geocaching attribute ID.

        Returns:
            ObjectId | None: Attribute ID or None if not found.
        """
        if gc_id is None:
            return None

        return self._attributes_cache.get(gc_id)

    async def map_cache_referentials(self, cache_data: dict[str, Any]) -> dict[str, Any]:
        """Map all referentials for a cache.

        Args:
            cache_data: Cache data to map.

        Returns:
            dict: Cache data enriched with referential IDs.
        """
        mapped_data = cache_data.copy()

        # Map country and state
        country_id, state_id = await self.ensure_country_and_state(
            cache_data.get("country"), cache_data.get("state")
        )

        if country_id:
            mapped_data["country_id"] = country_id
        if state_id:
            mapped_data["state_id"] = state_id

        # Map cache type
        type_id = self.get_type_by_name(cache_data.get("type"))
        if type_id:
            mapped_data["type_id"] = type_id

        # Map cache size
        size_id = self.get_size_by_name(cache_data.get("size"))
        if size_id:
            mapped_data["size_id"] = size_id

        # Map attributes (if present)
        if "attributes" in cache_data and isinstance(cache_data["attributes"], list):
            mapped_attributes = []
            for attr in cache_data["attributes"]:
                if isinstance(attr, dict) and "id" in attr:
                    attr_id = self.get_attribute_by_gc_id(attr["id"])
                    if attr_id:
                        mapped_attr = {
                            "attribute_doc_id": attr_id,
                            "is_positive": attr.get("is_positive", True),
                        }
                        mapped_attributes.append(mapped_attr)

            mapped_data["attributes"] = mapped_attributes

        return mapped_data
