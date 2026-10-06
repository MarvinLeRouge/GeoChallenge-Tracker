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
from app.services.zones.zone_assigner import assign_zones_to_caches

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

    async def _enrich_and_persist_caches(
        self,
        caches_data: list[dict[str, Any]],
        found_caches_data: list[dict[str, Any]],
        import_mode: str,
        user_id: ObjectId | None,
        fetch_elevation: bool,
        force_update_attributes: bool,
        stats: dict[str, Any],
    ) -> None:
        """Run geocoding/elevation/zone enrichment then persist caches and found caches.

        Description:
            Steps 4-7 of the import pipeline. Mutates `stats` in place with the
            resulting persistence counters.

        Args:
            caches_data: Parsed cache entries.
            found_caches_data: Parsed found-cache entries.
            import_mode: 'both' | 'all' | 'found'.
            user_id: User id (for found-cache persistence).
            fetch_elevation: Whether to enrich with elevation data.
            force_update_attributes: Force attribute update on persistence.
            stats: Import statistics, mutated in place.
        """
        if caches_data:
            logger_import.info(
                "Geocoding fallback for caches without country", extra={"step": "geocoding"}
            )
            await self._enrich_with_geocoding(caches_data)

        if fetch_elevation and caches_data:
            logger_import.info("Fetching elevation data", extra={"step": "elevation"})
            await self._enrich_with_elevation(caches_data)

        if caches_data:
            logger_import.info("Assigning administrative zones", extra={"step": "zones"})
            await self._assign_zones(caches_data)

        if caches_data and import_mode in ["both", "all", "found"]:
            cache_stats = await self.cache_persister.persist_caches(
                caches_data, force_update_attributes=force_update_attributes
            )
            stats["nb_inserted_caches"] = cache_stats["inserted"]
            stats["nb_existing_caches"] = cache_stats["updated"]

        if found_caches_data and import_mode in ["both", "found"] and user_id:
            logger_import.info("Persisting found caches", extra={"step": "found_persistence"})
            found_stats = await self.cache_persister.persist_found_caches(
                found_caches_data, user_id
            )
            stats["nb_inserted_found_caches"] = found_stats["inserted"]
            stats["nb_updated_found_caches"] = found_stats["updated"]

    @staticmethod
    def _apply_new_referential_counts(
        stats: dict[str, Any], before: dict[str, int], after: dict[str, int]
    ) -> None:
        """Record how many new countries/states were created during this import.

        Args:
            stats: Import statistics, mutated in place.
            before: Referential counts captured before the import.
            after: Referential counts captured after the import.
        """
        stats["nb_new_countries"] = after.get("countries", 0) - before.get("countries", 0)
        stats["nb_new_states"] = after.get("states", 0) - before.get("states", 0)

    @staticmethod
    def _log_import_summary(
        filename: str | None,
        payload: bytes,
        caches_data: list[dict[str, Any]],
        stats: dict[str, Any],
    ) -> None:
        """Log a detailed JSON summary of the import for later inspection.

        Args:
            filename: Original filename, if any.
            payload: Raw uploaded payload (used for its size).
            caches_data: Parsed cache entries.
            stats: Import statistics.
        """
        logger_import.info(
            "GPX import completed successfully", extra={"stats": stats, "step": "completed"}
        )

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

    async def _flag_unfound_import(self, user_id: ObjectId | None, stats: dict[str, Any]) -> None:
        """Flag the user if this import brought in new caches that are not yet found.

        Args:
            user_id: User id, or None for admin-only imports.
            stats: Import statistics (uses total vs found counts).
        """
        not_found_count = stats["nb_total_items"] - (
            stats["nb_inserted_found_caches"] + stats["nb_updated_found_caches"]
        )
        if not (user_id and not_found_count > 0):
            return

        from app.core.utils import utcnow  # local import to avoid circular dependency

        await self.db.users.update_one(
            {"_id": user_id},
            {"$set": {"last_not_found_import_at": utcnow()}},
        )
        logger_import.info(
            "[targets] %d unfound cache(s) imported — last_not_found_import_at updated",
            not_found_count,
        )

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
        if import_mode not in ["all", "found", "both"]:
            raise ValueError(
                f"Invalid import mode: {import_mode}. Expected 'all', 'found', or 'both'"
            )
        stats: dict[str, Any] = {
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
            logger_import.info("Starting GPX import", extra={"step": "file_handling"})
            gpx_paths = await self._materialize_files(payload, filename)
            stats["nb_gpx_files"] = len(gpx_paths)

            logger_import.info("Loading referentials", extra={"step": "referentials"})
            await self.referential_mapper.load_all_referentials()

            ref_counts_before = await self.cache_persister.get_referential_counts()

            logger_import.info("Processing GPX files", extra={"step": "parsing"})
            caches_data, found_caches_data = await self._process_gpx_files(
                gpx_paths, import_mode, force_update_attributes
            )
            stats["nb_total_items"] = len(caches_data)

            await self._enrich_and_persist_caches(
                caches_data,
                found_caches_data,
                import_mode,
                user_id,
                fetch_elevation,
                force_update_attributes,
                stats,
            )

            ref_counts_after = await self.cache_persister.get_referential_counts()
            self._apply_new_referential_counts(stats, ref_counts_before, ref_counts_after)

            self._log_import_summary(filename, payload, caches_data, stats)

            await self._flag_unfound_import(user_id, stats)

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

    async def _process_single_gpx_item(
        self, raw_item: dict[str, Any], import_mode: str, gpx_path: Path
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Process one raw GPX waypoint into (cache, found_cache) data, if applicable.

        Description:
            Normalizes, maps referentials, validates, and filters by `import_mode`. Any
            exception is logged and swallowed, yielding `(None, None)` for that item.

        Args:
            raw_item: Raw waypoint dict from the GPX parser.
            import_mode: Import mode.
            gpx_path: Source file path, used only for logging context.

        Returns:
            tuple: `(validated_cache or None, validated_found or None)`.
        """
        try:
            # Map field names for compatibility with data normalizer
            # The parser provides 'GC' but the normalizer expects 'gc_code'
            mapped_item = raw_item.copy()
            if "GC" in mapped_item:
                mapped_item["gc_code"] = mapped_item["GC"]

            # Extraire et normaliser les métadonnées de cache
            cache_metadata = self.data_normalizer.extract_cache_metadata(mapped_item)

            if not cache_metadata.get("GC"):
                return None, None  # Skip if no GC code

            # Extract found cache data if present
            found_metadata = self.data_normalizer.extract_found_metadata(raw_item)

            # Now that metadata is extracted, filter according to import mode
            # Create a combined object for validation
            combined_data = {**cache_metadata, **(found_metadata or {})}

            if not self.data_normalizer.is_valid_for_import_mode(combined_data, import_mode):
                return None, None

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
            cache_result = validated_cache if import_mode in ["both", "all", "found"] else None
            found_result = (
                validated_found if validated_found and import_mode in ["both", "found"] else None
            )
            return cache_result, found_result

        except Exception as e:
            logger_import.warning(
                f"Error processing item: {e}",
                extra={"item_gc": raw_item.get("gc_code"), "file": str(gpx_path)},
            )
            return None, None

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
        caches_data: list[dict[str, Any]] = []
        found_caches_data: list[dict[str, Any]] = []

        for raw_item in raw_items:
            cache, found = await self._process_single_gpx_item(raw_item, import_mode, gpx_path)
            if cache is not None:
                caches_data.append(cache)
            if found is not None:
                found_caches_data.append(found)

        return caches_data, found_caches_data

    async def _assign_zones(self, caches_data: list[dict[str, Any]]) -> None:
        await assign_zones_to_caches(caches_data)

    @staticmethod
    def _extract_coordinates_for_elevation(
        caches_data: list[dict[str, Any]],
    ) -> list[tuple[float, float] | None]:
        """Extract (lat, lon) per cache, or None when coordinates are missing.

        Args:
            caches_data: Cache entries to read coordinates from.

        Returns:
            list: One `(lat, lon)` or `None` per entry in `caches_data`, same order.
        """
        coordinates: list[tuple[float, float] | None] = []
        for cache_data in caches_data:
            if cache_data.get("lat") is not None and cache_data.get("lon") is not None:
                coordinates.append((cache_data["lat"], cache_data["lon"]))
            else:
                coordinates.append(None)
        return coordinates

    @staticmethod
    def _apply_elevations(caches_data: list[dict[str, Any]], elevations: list[Any]) -> None:
        """Apply fetched elevations onto `caches_data`, mutating it in place.

        Args:
            caches_data: Cache entries to enrich.
            elevations: Elevation values, aligned by index with `caches_data`.
        """
        for i, cache_data in enumerate(caches_data):
            if i < len(elevations) and elevations[i] is not None:
                elevation_val = elevations[i]
                if elevation_val is not None:
                    cache_data["elevation"] = int(elevation_val)

    async def _enrich_with_elevation(self, caches_data: list[dict[str, Any]]) -> None:
        """Enrich caches with elevation data.

        Args:
            caches_data: List of cache data to enrich.
        """
        if not caches_data:
            return

        # Extract coordinates
        coordinates = self._extract_coordinates_for_elevation(caches_data)

        # Fetch elevations
        try:
            # Filter valid coordinates for the elevation API
            valid_coordinates = [coord for coord in coordinates if coord is not None]
            if not valid_coordinates:
                return

            elevations = await fetch_elevations(valid_coordinates)

            # Apply elevations
            self._apply_elevations(caches_data, elevations)

        except Exception as e:
            logger_import.warning(f"Elevation fetch failed: {e}")
            # Continue without elevation on error

    @staticmethod
    def _find_geocoding_candidates(
        caches_data: list[dict[str, Any]],
    ) -> list[tuple[int, dict[str, Any]]]:
        """Find caches with coordinates but no resolved country, candidates for geocoding.

        Args:
            caches_data: Cache entries to scan.

        Returns:
            list[tuple[int, dict]]: `(index, cache)` pairs eligible for geocoding.
        """
        return [
            (i, c)
            for i, c in enumerate(caches_data)
            if c.get("lat") is not None and c.get("lon") is not None and c.get("country_id") is None
        ]

    async def _resolve_geocoding_candidate(
        self, cache_data: dict[str, Any], geo: tuple[str, str | None] | None
    ) -> bool:
        """Resolve and apply one geocoded (country, state) pair onto a cache, in place.

        Args:
            cache_data: Cache entry to update in place.
            geo: `(country_name, state_name)` from Nominatim, or None if geocoding failed.

        Returns:
            bool: True if the cache was successfully resolved, False otherwise.
        """
        if geo is None:
            return False

        country_name, state_name = geo
        country_id, state_id = await self.referential_mapper.ensure_country_and_state(
            country_name, state_name
        )

        if country_id is None:
            return False

        cache_data["country_id"] = country_id
        if state_id is not None:
            cache_data["state_id"] = state_id
        return True

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
        candidates = self._find_geocoding_candidates(caches_data)

        if not candidates:
            return

        logger_import.info(
            "Nominatim geocoding fallback for %d caches without country", len(candidates)
        )

        points = [(float(c["lat"]), float(c["lon"])) for _, c in candidates]
        geo_results, http_stats = await geocoding_nominatim.fetch_batch(points)

        resolved = failed = 0
        for (_idx, cache_data), geo in zip(candidates, geo_results):
            if await self._resolve_geocoding_candidate(cache_data, geo):
                resolved += 1
            else:
                failed += 1

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
