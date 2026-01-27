# backend/app/services/gpx_import/gpx_import_service.py
# Service principal d'import GPX avec orchestration des composants.

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.logging_config import get_loggers
from app.services.elevation_retrieval import fetch as fetch_elevations
from app.services.parsers.MultiFormatGPXParser import MultiFormatGPXParser

from .cache_persister import CachePersister
from .cache_validator import CacheValidator
from .data_normalizer import DataNormalizer
from .file_handler import FileHandler
from .referential_mapper import ReferentialMapper

logger_main = logger_import = get_loggers()[0]


class GpxImportService:
    """Service principal d'import GPX.

    Description:
        Service principal qui orchestre l'import complet de fichiers GPX :
        - Gestion des fichiers (ZIP/GPX)
        - Parsing et normalisation des données
        - Validation métier
        - Mapping des référentiels
        - Enrichissement (élévation)
        - Persistance optimisée
    """

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        uploads_dir: Path | None = None,
        strict_validation: bool = False,
    ):
        """Initialiser le service d'import.

        Args:
            db: Instance de base de données MongoDB.
            uploads_dir: Répertoire de stockage des uploads.
            strict_validation: Mode de validation strict.
        """
        self.db = db

        # Initialiser les composants
        self.file_handler = FileHandler(uploads_dir)
        self.data_normalizer = DataNormalizer()
        self.cache_validator = CacheValidator(strict_validation)
        self.referential_mapper = ReferentialMapper(db)
        self.cache_persister = CachePersister(db)

        # Parser GPX sera initialisé par fichier
        self.gpx_parser = None

    async def import_gpx_payload(
        self,
        payload: bytes,
        filename: str | None = None,
        user_id: ObjectId | None = None,
        import_mode: str = "both",
        fetch_elevation: bool = False,
    ) -> dict[str, Any]:
        """Importer un payload GPX/ZIP complet.

        Args:
            payload: Données du fichier (GPX ou ZIP).
            filename: Nom de fichier optionnel.
            user_id: ID de l'utilisateur (pour les trouvailles).
            import_mode: Mode d'import ('both', 'all', 'found').
            fetch_elevation: Enrichir avec les données d'élévation.

        Returns:
            dict: Statistiques d'import détaillées.
        """
        # Valider que le mode d'import est valide
        if import_mode not in ["all", "found", "both"]:
            raise ValueError(
                f"Invalid import mode: {import_mode}. Expected 'all', 'found', or 'both'"
            )
        stats = {
            "nb_gpx_files": 0,
            "nb_inserted_caches": 0,
            "nb_existing_caches": 0,
            "nb_inserted_found_caches": 0,
            "nb_updated_found_caches": 0,
            "nb_new_countries": 0,
            "nb_new_states": 0,
            "nb_total_items": 0,
            "nb_discarded_items": 0,
        }

        try:
            # Étape 1: Matérialisation des fichiers
            logger_import.info("Starting GPX import", extra={"step": "file_handling"})
            gpx_paths = await self._materialize_files(payload, filename)
            stats["nb_gpx_files"] = len(gpx_paths)

            # Étape 2: Chargement des référentiels
            logger_import.info("Loading referentials", extra={"step": "referentials"})
            await self.referential_mapper.load_all_referentials()

            # Compter les référentiels avant import
            ref_counts_before = await self.cache_persister.get_referential_counts()

            # Étape 3: Parsing et traitement
            logger_import.info("Processing GPX files", extra={"step": "parsing"})
            caches_data, found_caches_data = await self._process_gpx_files(gpx_paths, import_mode)

            stats["nb_total_items"] = len(caches_data)

            # Étape 4: Enrichissement élévation (optionnel)
            if fetch_elevation and caches_data:
                logger_import.info("Fetching elevation data", extra={"step": "elevation"})
                await self._enrich_with_elevation(caches_data)

            # Étape 5: Persistance des caches (dans tous les modes sauf si vide)
            if caches_data and import_mode in ["both", "all", "found"]:
                cache_stats = await self.cache_persister.persist_caches(caches_data)
                stats["nb_inserted_caches"] = cache_stats["inserted"]
                stats["nb_existing_caches"] = cache_stats["updated"]

            # Étape 6: Persistance des trouvailles (seulement pour les modes appropriés)
            if found_caches_data and import_mode in ["both", "found"] and user_id:
                logger_import.info("Persisting found caches", extra={"step": "found_persistence"})
                found_stats = await self.cache_persister.persist_found_caches(
                    found_caches_data, user_id
                )
                stats["nb_inserted_found_caches"] = found_stats["inserted"]
                stats["nb_updated_found_caches"] = found_stats["updated"]

            # Étape 7: Calcul des nouveaux référentiels
            ref_counts_after = await self.cache_persister.get_referential_counts()
            stats["nb_new_countries"] = ref_counts_after.get(
                "countries", 0
            ) - ref_counts_before.get("countries", 0)
            stats["nb_new_states"] = ref_counts_after.get("states", 0) - ref_counts_before.get(
                "states", 0
            )

            logger_import.info(
                "GPX import completed successfully", extra={"stats": stats, "step": "completed"}
            )

            # Log détaillé des informations d'import dans le fichier JSON
            _, _, data_logger = get_loggers()
            total_attributes = 0
            if caches_data:
                total_attributes = sum(
                    len(cache.get("attributes", []))
                    for cache in caches_data
                    if isinstance(cache, dict) and "attributes" in cache
                )

            import_summary = {
                "filename": filename,
                "file_size": len(payload),
                "total_items": stats["nb_total_items"],
                "total_caches": len(caches_data),
                "total_attributes": total_attributes,
                "response_summary": stats,
            }

            data_logger.log_data("gpx_import", import_summary)

        finally:
            # Nettoyage des fichiers temporaires
            if "gpx_paths" in locals():
                self.file_handler.cleanup_files(gpx_paths)

        return stats

    async def _materialize_files(self, payload: bytes, filename: str | None) -> list[Path]:
        """Matérialiser les fichiers GPX depuis le payload.

        Args:
            payload: Données du fichier.
            filename: Nom de fichier optionnel.

        Returns:
            list[Path]: Liste des chemins des fichiers GPX.
        """
        return self.file_handler.materialize_files(payload, filename)

    async def _process_gpx_files(
        self,
        gpx_paths: list[Path],
        import_mode: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Traiter tous les fichiers GPX.

        Args:
            gpx_paths: Liste des chemins des fichiers GPX.
            import_mode: Mode d'import.

        Returns:
            tuple: (caches_data, found_caches_data).
        """
        all_caches_data: list[dict[str, Any]] = []
        all_found_caches_data: list[dict[str, Any]] = []

        # Traiter les fichiers en parallèle (avec limite)
        semaphore = asyncio.Semaphore(5)  # Max 5 fichiers simultanés

        async def process_single_file(
            gpx_path: Path,
        ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            async with semaphore:
                return await self._process_single_gpx_file(gpx_path, import_mode)

        # Lancer le traitement en parallèle
        tasks = [process_single_file(path) for path in gpx_paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Agréger les résultats
        for result in results:
            if isinstance(result, Exception):
                logger_import.warning(f"Error processing GPX file: {result}")
                continue

            if isinstance(result, tuple) and len(result) == 2:
                caches_data, found_caches_data = result
                all_caches_data.extend(caches_data)
                all_found_caches_data.extend(found_caches_data)

        return all_caches_data, all_found_caches_data

    async def _process_single_gpx_file(
        self,
        gpx_path: Path,
        import_mode: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Traiter un fichier GPX individuel.

        Args:
            gpx_path: Chemin du fichier GPX.
            import_mode: Mode d'import.

        Returns:
            tuple: (caches_data, found_caches_data).
        """
        # Valider le fichier
        self.file_handler.validate_gpx_file(gpx_path)

        # Parser le fichier GPX
        gpx_parser = MultiFormatGPXParser(gpx_path)
        raw_items = gpx_parser.parse()
        caches_data = []
        found_caches_data = []

        for raw_item in raw_items:
            try:
                # Map field names for compatibility with data normalizer
                # The parser provides 'GC' but the normalizer expects 'gc_code'
                mapped_item = raw_item.copy()
                if "GC" in mapped_item:
                    mapped_item["gc_code"] = mapped_item["GC"]

                # Extraire et normaliser les métadonnées de cache
                cache_metadata = self.data_normalizer.extract_cache_metadata(mapped_item)

                if not cache_metadata.get("GC"):
                    continue  # Ignorer si pas de code GC

                # Extraire les données de trouvaille si présentes
                found_metadata = self.data_normalizer.extract_found_metadata(raw_item)

                # Maintenant que les métadonnées sont extraites, on peut filtrer selon le mode d'import
                # On crée un objet combiné pour la validation
                combined_data = {**cache_metadata, **(found_metadata or {})}

                if not self.data_normalizer.is_valid_for_import_mode(combined_data, import_mode):
                    continue

                # Mapper les référentiels
                cache_data = await self.referential_mapper.map_cache_referentials(cache_metadata)

                # Valider les données de cache
                validated_cache = self.cache_validator.validate_cache_data(cache_data)

                validated_found = None

                if found_metadata:
                    validated_found = self.cache_validator.validate_found_data(found_metadata)
                    # Ajouter le code GC
                    validated_found["GC"] = validated_cache["GC"]

                # Valider la cohérence
                self.cache_validator.validate_import_consistency(
                    validated_cache, validated_found, import_mode
                )

                # Ajouter aux résultats
                # Les caches sont traitées dans tous les modes sauf si vide
                if import_mode in ["both", "all", "found"]:
                    caches_data.append(validated_cache)

                if validated_found and import_mode in ["both", "found"]:
                    found_caches_data.append(validated_found)

            except Exception as e:
                logger_import.warning(
                    f"Error processing item: {e}",
                    extra={"item_gc": raw_item.get("gc_code"), "file": str(gpx_path)},
                )
                continue

        return caches_data, found_caches_data

    async def _enrich_with_elevation(self, caches_data: list[dict[str, Any]]) -> None:
        """Enrichir les caches avec les données d'élévation.

        Args:
            caches_data: Liste des données de caches à enrichir.
        """
        if not caches_data:
            return

        # Extraire les coordonnées
        coordinates: list[tuple[float, float] | None] = []
        for cache_data in caches_data:
            if cache_data.get("lat") is not None and cache_data.get("lon") is not None:
                coordinates.append((cache_data["lat"], cache_data["lon"]))
            else:
                coordinates.append(None)

        # Récupérer les élévations
        try:
            # Filtrer les coordonnées valides pour l'API d'élévation
            valid_coordinates = [coord for coord in coordinates if coord is not None]
            if not valid_coordinates:
                return

            elevations = await fetch_elevations(valid_coordinates)

            # Appliquer les élévations
            for i, cache_data in enumerate(caches_data):
                if i < len(elevations) and elevations[i] is not None:
                    elevation_val = elevations[i]
                    if elevation_val is not None:
                        cache_data["elevation"] = int(elevation_val)

        except Exception as e:
            logger_import.warning(f"Elevation fetch failed: {e}")
            # Continue sans élévation en cas d'erreur

    async def get_import_statistics(self, user_id: ObjectId | None = None) -> dict[str, Any]:
        """Récupérer les statistiques d'import pour un utilisateur.

        Args:
            user_id: ID de l'utilisateur (optionnel).

        Returns:
            dict: Statistiques d'import.
        """
        stats = {}

        # Compter les caches totales
        coll_caches = self.db.caches
        stats["total_caches"] = await coll_caches.count_documents({})

        # Compter les trouvailles si utilisateur fourni
        if user_id:
            coll_found = self.db.found_caches
            stats["user_found_caches"] = await coll_found.count_documents({"user_id": user_id})

        # Compter les référentiels
        ref_counts = await self.cache_persister.get_referential_counts()
        stats.update(ref_counts)

        return stats
