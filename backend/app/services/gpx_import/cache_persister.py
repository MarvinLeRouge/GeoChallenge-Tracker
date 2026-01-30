# backend/app/services/gpx_import/cache_persister.py
# Service de persistance optimisée pour les caches et trouvailles.

from __future__ import annotations

from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError

from app.core.utils import now


class CachePersister:
    """Service de persistance optimisée pour les caches et trouvailles.

    Description:
        Responsable de la persistance en masse des données de caches
        et de trouvailles avec gestion des erreurs et des conflits.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialiser le service de persistance.

        Args:
            db: Instance de base de données MongoDB.
        """
        self.db = db

    async def persist_caches(
        self, caches_data: list[dict[str, Any]], force_update_attributes: bool = False
    ) -> dict[str, int]:
        """Persister les caches en base avec upsert.

        Args:
            caches_data: Liste des données de caches à persister.
            force_update_attributes: Forcer la mise à jour des attributs (admin seulement).

        Returns:
            dict: Statistiques de persistance {inserted, updated, errors}.
        """
        if not caches_data:
            return {"inserted": 0, "updated": 0, "errors": 0}

        coll_caches = self.db.caches
        operations = []
        current_time = now()

        for cache_data in caches_data:
            # Préparer l'opération d'upsert
            filter_query = {"GC": cache_data["GC"]}

            # Données à insérer/mettre à jour
            update_doc = {
                "$set": {
                    **cache_data,
                    "updated_at": current_time,
                },
                "$setOnInsert": {
                    "created_at": current_time,
                },
            }

            # Si force_update_attributes est activé, on remplace les attributs même s'ils existent
            if force_update_attributes and "attributes" in cache_data:
                update_doc["$set"]["attributes"] = cache_data["attributes"]

            operations.append(UpdateOne(filter_query, update_doc, upsert=True))

        # Exécuter les opérations en lot
        try:
            result = await coll_caches.bulk_write(operations, ordered=False)
            return {
                "inserted": result.upserted_count,
                "updated": result.modified_count,
                "errors": 0,
            }
        except BulkWriteError as e:
            # Gérer les erreurs partielles
            inserted = e.details.get("nUpserted", 0)
            updated = e.details.get("nModified", 0)
            errors = len(e.details.get("writeErrors", []))

            return {
                "inserted": inserted,
                "updated": updated,
                "errors": errors,
            }

    async def persist_found_caches(
        self, found_caches_data: list[dict[str, Any]], user_id: ObjectId
    ) -> dict[str, int]:
        """Persister les trouvailles en base avec upsert.

        Args:
            found_caches_data: Liste des données de trouvailles.
            user_id: ID de l'utilisateur qui a trouvé les caches.

        Returns:
            dict: Statistiques de persistance {inserted, updated, errors}.
        """
        if not found_caches_data:
            return {"inserted": 0, "updated": 0, "errors": 0}

        coll_found = self.db.found_caches
        operations = []
        current_time = now()

        for found_data in found_caches_data:
            # Rechercher l'ID de la cache par code GC
            cache_id = await self._get_cache_id_by_gc(found_data["GC"])
            if not cache_id:
                continue  # Ignorer si cache non trouvée

            # Préparer l'opération d'upsert
            filter_query = {
                "user_id": user_id,
                "cache_id": cache_id,
            }

            # Données à insérer/mettre à jour
            update_doc = {
                "$setOnInsert": {
                    "found_date": found_data["found_date"],
                    "created_at": current_time,
                },
                "$set": {
                    "updated_at": current_time,
                },
            }

            # Gérer les notes (optionnelles)
            if "notes" in found_data:
                if found_data["notes"] is None:
                    update_doc["$unset"] = {"notes": ""}
                else:
                    update_doc["$set"]["notes"] = found_data["notes"]

            operations.append(UpdateOne(filter_query, update_doc, upsert=True))

        # Exécuter les opérations en lot
        try:
            result = await coll_found.bulk_write(operations, ordered=False)
            return {
                "inserted": result.upserted_count,
                "updated": result.modified_count,
                "errors": 0,
            }
        except BulkWriteError as e:
            # Gérer les erreurs partielles
            inserted = e.details.get("nUpserted", 0)
            updated = e.details.get("nModified", 0)
            errors = len(e.details.get("writeErrors", []))

            return {
                "inserted": inserted,
                "updated": updated,
                "errors": errors,
            }

    async def _get_cache_id_by_gc(self, gc_code: str) -> ObjectId | None:
        """Récupérer l'ID d'une cache par son code GC.

        Args:
            gc_code: Code GC de la cache.

        Returns:
            ObjectId | None: ID de la cache ou None si non trouvée.
        """
        coll_caches = self.db.caches
        cache_doc = await coll_caches.find_one({"GC": gc_code}, {"_id": 1})
        return cache_doc["_id"] if cache_doc else None

    async def get_existing_caches_by_gc(self, gc_codes: list[str]) -> dict[str, ObjectId]:
        """Récupérer les IDs des caches existantes par codes GC.

        Args:
            gc_codes: Liste des codes GC à chercher.

        Returns:
            dict: Mapping GC_code -> ObjectId pour les caches existantes.
        """
        if not gc_codes:
            return {}

        coll_caches = self.db.caches
        cursor = coll_caches.find({"GC": {"$in": gc_codes}}, {"_id": 1, "GC": 1})

        result = {}
        async for doc in cursor:
            result[doc["GC"]] = doc["_id"]

        return result

    async def count_existing_found_caches(self, user_id: ObjectId, gc_codes: list[str]) -> int:
        """Compter les trouvailles existantes pour un utilisateur.

        Args:
            user_id: ID de l'utilisateur.
            gc_codes: Liste des codes GC à vérifier.

        Returns:
            int: Nombre de trouvailles existantes.
        """
        if not gc_codes:
            return 0

        # Récupérer les IDs des caches
        cache_ids_map = await self.get_existing_caches_by_gc(gc_codes)
        cache_ids = list(cache_ids_map.values())

        if not cache_ids:
            return 0

        coll_found = self.db.found_caches
        return await coll_found.count_documents(
            {
                "user_id": user_id,
                "cache_id": {"$in": cache_ids},
            }
        )

    async def get_referential_counts(self) -> dict[str, int]:
        """Récupérer les compteurs de référentiels pour statistiques.

        Returns:
            dict: Compteurs par collection.
        """
        results = {}

        collections = ["countries", "states", "cache_types", "cache_sizes"]

        for collection_name in collections:
            collection = getattr(self.db, collection_name)
            count = await collection.count_documents({})
            results[collection_name] = count

        return results

    async def cleanup_temp_data(self, gc_codes: list[str]) -> None:
        """Nettoyer les données temporaires si nécessaire.

        Args:
            gc_codes: Codes GC traités (pour logs/debug).
        """
        # Pour l'instant, pas de nettoyage spécifique
        # Peut être étendu pour gérer des collections temporaires
        pass
