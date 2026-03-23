# backend/app/services/gpx_import/gpx_import_service.py
# Main GPX import service with component orchestration.

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.logging_config import get_loggers
from app.services.elevation_retrieval import fetch as fetch_elevations
from app.services.parsers.MultiFormatGPXParser import MultiFormatGPXParser
from app.services.providers import geocoding_nominatim

from .cache_persister import CachePersister
from .cache_validator import CacheValidator
from .data_normalizer import DataNormalizer
from .file_handler import FileHandler
from .referential_mapper import ReferentialMapper

logger_main = logger_import = get_loggers()[0]


class GpxImportService:
    """Main GPX import service.

    Description:
        Orchestrates the complete import pipeline for GPX files:
        - File management (ZIP/GPX)
        - Data parsing and normalization
        - Business validation
        - Referential mapping
        - Enrichment (elevation)
        - Optimized persistence
    """

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        uploads_dir: Path | None = None,
        strict_validation: bool = False,
    ):
        """Initialize the import service.

        Args:
            db: MongoDB database instance.
            uploads_dir: Upload storage directory.
            strict_validation: Enable strict validation mode.
        """
        self.db = db

        # Initialize components
        self.file_handler = FileHandler(uploads_dir)
        self.data_normalizer = DataNormalizer()
        self.cache_validator = CacheValidator(strict_validation)
        self.referential_mapper = ReferentialMapper(db)
        self.cache_persister = CachePersister(db)

        # GPX parser will be initialized per file
        self.gpx_parser = None

    async def import_gpx_payload(
        self,
        payload: bytes,
        filename: str | None = None,
        user_id: ObjectId | None = None,
        import_mode: str = "both",
        fetch_elevation: bool = False,
        force_update_attributes: bool = False,
    ) -> dict[str, Any]:
        """Import a complete GPX/ZIP payload.

        Args:
            payload: File data (GPX or ZIP).
            filename: Optional filename.
            user_id: User ID (for found caches).
            import_mode: Import mode ('both', 'all', 'found').
            fetch_elevation: Enrich with elevation data.
            force_update_attributes: Force attribute update (admin only).

        Returns:
            dict: Detailed import statistics.
        """
        # Validate the import mode
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
            # Step 1: Materialize files
            logger_import.info("Starting GPX import", extra={"step": "file_handling"})
            gpx_paths = await self._materialize_files(payload, filename)
            stats["nb_gpx_files"] = len(gpx_paths)

            # Step 2: Load referentials
            logger_import.info("Loading referentials", extra={"step": "referentials"})
            await self.referential_mapper.load_all_referentials()

            # Count referentials before import
            ref_counts_before = await self.cache_persister.get_referential_counts()

            # Step 3: Parsing and processing
            logger_import.info("Processing GPX files", extra={"step": "parsing"})
            caches_data, found_caches_data = await self._process_gpx_files(
                gpx_paths, import_mode, force_update_attributes
            )

            stats["nb_total_items"] = len(caches_data)

            # Step 4: Geocoding fallback for caches missing country/state
            if caches_data:
                logger_import.info(
                    "Geocoding fallback for caches without country", extra={"step": "geocoding"}
                )
                await self._enrich_with_geocoding(caches_data)

            # Step 5: Elevation enrichment (optional)
            if fetch_elevation and caches_data:
                logger_import.info("Fetching elevation data", extra={"step": "elevation"})
                await self._enrich_with_elevation(caches_data)

            # Step 6: Cache persistence (all modes unless empty)
            if caches_data and import_mode in ["both", "all", "found"]:
                cache_stats = await self.cache_persister.persist_caches(
                    caches_data, force_update_attributes=force_update_attributes
                )
                stats["nb_inserted_caches"] = cache_stats["inserted"]
                stats["nb_existing_caches"] = cache_stats["updated"]

            # Step 7: Found cache persistence (only for applicable modes)
            if found_caches_data and import_mode in ["both", "found"] and user_id:
                logger_import.info("Persisting found caches", extra={"step": "found_persistence"})
                found_stats = await self.cache_persister.persist_found_caches(
                    found_caches_data, user_id
                )
                stats["nb_inserted_found_caches"] = found_stats["inserted"]
                stats["nb_updated_found_caches"] = found_stats["updated"]

            # Step 8: Compute new referential counts
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

            # Detailed import log in JSON file
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
            # Clean up temporary files
            if "gpx_paths" in locals():
                self.file_handler.cleanup_files(gpx_paths)

        return stats

    async def _materialize_files(self, payload: bytes, filename: str | None) -> list[Path]:
        """Materialize GPX files from the payload.

        Args:
            payload: File data.
            filename: Optional filename.

        Returns:
            list[Path]: List of GPX file paths.
        """
        return self.file_handler.materialize_files(payload, filename)

    async def _process_gpx_files(
        self,
        gpx_paths: list[Path],
        import_mode: str,
        force_update_attributes: bool = False,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Process all GPX files.

        Args:
            gpx_paths: List of GPX file paths.
            import_mode: Import mode.
            force_update_attributes: Force attribute update (admin only).

        Returns:
            tuple: (caches_data, found_caches_data).
        """
        all_caches_data: list[dict[str, Any]] = []
        all_found_caches_data: list[dict[str, Any]] = []

        # Process files in parallel (with limit)
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent files

        async def process_single_file(
            gpx_path: Path,
        ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            async with semaphore:
                return await self._process_single_gpx_file(
                    gpx_path, import_mode, force_update_attributes
                )

        # Launch parallel processing
        tasks = [process_single_file(path) for path in gpx_paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
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
        force_update_attributes: bool = False,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Process a single GPX file.

        Args:
            gpx_path: GPX file path.
            import_mode: Import mode.
            force_update_attributes: Force attribute update (admin only).

        Returns:
            tuple: (caches_data, found_caches_data).
        """
        # Validate the file
        self.file_handler.validate_gpx_file(gpx_path)

        # Parse the GPX file
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
                    continue  # Skip if no GC code

                # Extract found cache data if present
                found_metadata = self.data_normalizer.extract_found_metadata(raw_item)

                # Now that metadata is extracted, filter according to import mode
                # Create a combined object for validation
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
                    # Add the GC code
                    validated_found["GC"] = validated_cache["GC"]

                # Valider la cohérence
                self.cache_validator.validate_import_consistency(
                    validated_cache, validated_found, import_mode
                )

                # Add to results
                # Caches are processed in all modes unless empty
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
        """Enrich caches with elevation data.

        Args:
            caches_data: List of cache data to enrich.
        """
        if not caches_data:
            return

        # Extract coordinates
        coordinates: list[tuple[float, float] | None] = []
        for cache_data in caches_data:
            if cache_data.get("lat") is not None and cache_data.get("lon") is not None:
                coordinates.append((cache_data["lat"], cache_data["lon"]))
            else:
                coordinates.append(None)

        # Fetch elevations
        try:
            # Filter valid coordinates for the elevation API
            valid_coordinates = [coord for coord in coordinates if coord is not None]
            if not valid_coordinates:
                return

            elevations = await fetch_elevations(valid_coordinates)

            # Apply elevations
            for i, cache_data in enumerate(caches_data):
                if i < len(elevations) and elevations[i] is not None:
                    elevation_val = elevations[i]
                    if elevation_val is not None:
                        cache_data["elevation"] = int(elevation_val)

        except Exception as e:
            logger_import.warning(f"Elevation fetch failed: {e}")
            # Continue without elevation on error

    async def _enrich_with_geocoding(self, caches_data: list[dict[str, Any]]) -> None:
        """Enrich caches missing country/state via Nominatim reverse geocoding.

        Description:
            Collects caches that have valid coordinates but no country_id (e.g. GPX
            exported without groundspeak:country/state fields), batch-geocodes them
            via Nominatim, then resolves or creates the corresponding referential
            entries (country, state).

        Args:
            caches_data: List of cache data dicts (mutated in place).
        """
        candidates = [
            (i, c)
            for i, c in enumerate(caches_data)
            if c.get("lat") is not None and c.get("lon") is not None and c.get("country_id") is None
        ]

        if not candidates:
            return

        logger_import.info(
            "Nominatim geocoding fallback for %d caches without country", len(candidates)
        )

        points = [(float(c["lat"]), float(c["lon"])) for _, c in candidates]
        geo_results, http_stats = await geocoding_nominatim.fetch_batch(points)

        resolved = failed = 0
        for (idx, _cache_data), geo in zip(candidates, geo_results):
            if geo is None:
                failed += 1
                continue

            country_name, state_name = geo
            country_id, state_id = await self.referential_mapper.ensure_country_and_state(
                country_name, state_name
            )

            if country_id is None:
                failed += 1
                continue

            caches_data[idx]["country_id"] = country_id
            if state_id is not None:
                caches_data[idx]["state_id"] = state_id
            resolved += 1

        logger_import.info(
            "Nominatim geocoding done — resolved=%d failed=%d http_stats=%s",
            resolved,
            failed,
            http_stats,
        )

    async def get_import_statistics(self, user_id: ObjectId | None = None) -> dict[str, Any]:
        """Retrieve import statistics for a user.

        Args:
            user_id: User ID (optional).

        Returns:
            dict: Import statistics.
        """
        stats = {}

        # Count total caches
        coll_caches = self.db.caches
        stats["total_caches"] = await coll_caches.count_documents({})

        # Count found caches if user is provided
        if user_id:
            coll_found = self.db.found_caches
            stats["user_found_caches"] = await coll_found.count_documents({"user_id": user_id})

        # Count referentials
        ref_counts = await self.cache_persister.get_referential_counts()
        stats.update(ref_counts)

        return stats
