# backend/app/services/gpx_import/referential_mapper.py
# Mapper des référentiels (pays, états, types, tailles, attributs).

from __future__ import annotations

import asyncio
import re
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.utils import now


class ReferentialMapper:
    """Service de mapping des référentiels pour l'import GPX.

    Description:
        Gère la résolution et la création des référentiels
        (pays, états, types de caches, tailles, attributs).
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialiser le mapper.

        Args:
            db: Instance de base de données MongoDB.
        """
        self.db = db
        self._countries_cache: dict[str, ObjectId] = {}
        self._states_cache: dict[ObjectId, dict[str, ObjectId]] = {}
        self._types_cache: dict[str, ObjectId] = {}
        self._sizes_cache: dict[str, ObjectId] = {}
        self._attributes_cache: dict[int, ObjectId] = {}

    async def load_all_referentials(self) -> None:
        """Charger tous les référentiels en cache."""
        await asyncio.gather(
            self._load_countries(),
            self._load_states(),
            self._load_types(),
            self._load_sizes(),
            self._load_attributes(),
        )

    async def _load_countries(self) -> None:
        """Charger tous les pays en cache."""
        coll_countries = self.db.countries
        cursor = coll_countries.find({}, {"_id": 1, "name": 1})

        self._countries_cache.clear()
        async for doc in cursor:
            name = self.normalize_name(doc["name"])
            self._countries_cache[name] = doc["_id"]

    async def _load_states(self) -> None:
        """Charger tous les états en cache par pays."""
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
        """Charger tous les types de caches en cache."""
        coll_types = self.db.cache_types
        cursor = coll_types.find({}, {"_id": 1, "name": 1})

        self._types_cache.clear()
        async for doc in cursor:
            name = self.normalize_name(doc["name"])
            self._types_cache[name] = doc["_id"]

    async def _load_sizes(self) -> None:
        """Charger toutes les tailles de caches en cache."""
        coll_sizes = self.db.cache_sizes
        cursor = coll_sizes.find({}, {"_id": 1, "name": 1})

        self._sizes_cache.clear()
        async for doc in cursor:
            name = self.normalize_name(doc["name"])
            self._sizes_cache[name] = doc["_id"]

    async def _load_attributes(self) -> None:
        """Charger tous les attributs de caches en cache."""
        coll_attributes = self.db.cache_attributes
        cursor = coll_attributes.find({}, {"_id": 1, "gc_id": 1})

        self._attributes_cache.clear()
        async for doc in cursor:
            gc_id = doc.get("gc_id")
            if gc_id is not None:
                self._attributes_cache[int(gc_id)] = doc["_id"]

    @staticmethod
    def normalize_name(name: str | None) -> str:
        """Normaliser un nom pour le mapping.

        Args:
            name: Nom à normaliser.

        Returns:
            str: Nom normalisé (minuscules, caractères alphanumériques).
        """
        if not name:
            return ""

        # Normalisation: minuscules, alphanumérique uniquement
        normalized = re.sub(r"[^a-z0-9]", "", name.lower())
        return normalized

    async def ensure_country_and_state(
        self, country_name: str | None, state_name: str | None
    ) -> tuple[ObjectId | None, ObjectId | None]:
        """Assurer l'existence du pays et de l'état, les créer si nécessaire.

        Args:
            country_name: Nom du pays.
            state_name: Nom de l'état/région.

        Returns:
            tuple: (country_id, state_id) ou (None, None) si données manquantes.
        """
        if not country_name:
            return None, None

        # Normaliser et chercher le pays
        country_norm = self.normalize_name(country_name)
        country_id = self._countries_cache.get(country_norm)

        # Créer le pays s'il n'existe pas
        if not country_id:
            country_id = await self._create_country(country_name, country_norm)

        # Gérer l'état si fourni
        state_id = None
        if state_name and country_id:
            state_norm = self.normalize_name(state_name)

            # Chercher l'état dans le cache
            country_states = self._states_cache.get(country_id, {})
            state_id = country_states.get(state_norm)

            # Créer l'état s'il n'existe pas
            if not state_id:
                state_id = await self._create_state(state_name, state_norm, country_id)

        return country_id, state_id

    async def _create_country(self, original_name: str, normalized_name: str) -> ObjectId:
        """Créer un nouveau pays."""
        coll_countries = self.db.countries

        doc = {
            "name": original_name,
            "created_at": now(),
            "updated_at": now(),
        }

        result = await coll_countries.insert_one(doc)
        country_id = result.inserted_id

        # Mettre à jour le cache
        self._countries_cache[normalized_name] = country_id

        return country_id

    async def _create_state(
        self, original_name: str, normalized_name: str, country_id: ObjectId
    ) -> ObjectId:
        """Créer un nouveau état/région."""
        coll_states = self.db.states

        doc = {
            "name": original_name,
            "country_id": country_id,
            "created_at": now(),
            "updated_at": now(),
        }

        result = await coll_states.insert_one(doc)
        state_id = result.inserted_id

        # Mettre à jour le cache
        if country_id not in self._states_cache:
            self._states_cache[country_id] = {}
        self._states_cache[country_id][normalized_name] = state_id

        return state_id

    def get_type_by_name(self, type_name: str | None) -> ObjectId | None:
        """Récupérer l'ID du type de cache par nom.

        Args:
            type_name: Nom du type de cache.

        Returns:
            ObjectId | None: ID du type ou None si non trouvé.
        """
        if not type_name:
            return None

        normalized = self.normalize_name(type_name)
        return self._types_cache.get(normalized)

    def get_size_by_name(self, size_name: str | None) -> ObjectId | None:
        """Récupérer l'ID de la taille de cache par nom.

        Args:
            size_name: Nom de la taille de cache.

        Returns:
            ObjectId | None: ID de la taille ou None si non trouvé.
        """
        if not size_name:
            return None

        normalized = self.normalize_name(size_name)
        return self._sizes_cache.get(normalized)

    def get_attribute_by_gc_id(self, gc_id: int | None) -> ObjectId | None:
        """Récupérer l'ID de l'attribut par son ID Geocaching.

        Args:
            gc_id: ID Geocaching de l'attribut.

        Returns:
            ObjectId | None: ID de l'attribut ou None si non trouvé.
        """
        if gc_id is None:
            return None

        return self._attributes_cache.get(gc_id)

    async def map_cache_referentials(self, cache_data: dict[str, Any]) -> dict[str, Any]:
        """Mapper tous les référentiels d'une cache.

        Args:
            cache_data: Données de cache à mapper.

        Returns:
            dict: Données de cache avec IDs des référentiels.
        """
        mapped_data = cache_data.copy()

        # Mapper pays et état
        country_id, state_id = await self.ensure_country_and_state(
            cache_data.get("country"), cache_data.get("state")
        )

        if country_id:
            mapped_data["country_id"] = country_id
        if state_id:
            mapped_data["state_id"] = state_id

        # Mapper type de cache
        type_id = self.get_type_by_name(cache_data.get("type"))
        if type_id:
            mapped_data["type_id"] = type_id

        # Mapper taille de cache
        size_id = self.get_size_by_name(cache_data.get("size"))
        if size_id:
            mapped_data["size_id"] = size_id

        # Mapper attributs (si présents)
        if "attributes" in cache_data and isinstance(cache_data["attributes"], list):
            mapped_attributes = []
            for attr in cache_data["attributes"]:
                if isinstance(attr, dict) and "gc_id" in attr:
                    attr_id = self.get_attribute_by_gc_id(attr["gc_id"])
                    if attr_id:
                        mapped_attr = {
                            "attribute_doc_id": attr_id,
                            "is_positive": attr.get("is_positive", True),
                        }
                        mapped_attributes.append(mapped_attr)

            mapped_data["attributes"] = mapped_attributes

        return mapped_data
