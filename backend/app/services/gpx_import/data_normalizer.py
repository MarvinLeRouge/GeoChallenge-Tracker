# backend/app/services/gpx_import/data_normalizer.py
# Normalization and parsing of GPX data.

from __future__ import annotations

import datetime as dt
import re
from typing import Any


class DataNormalizer:
    """GPX data normalization service.

    Description:
        Responsible for parsing and normalizing data
        extracted from GPX files (dates, coordinates, types, etc.).
    """

    @staticmethod
    def normalize_name(name: str | None) -> str:
        """Normalize a name (referentials, filenames, etc.).

        Args:
            name: Name to normalize.

        Returns:
            str: Normalized name.
        """
        if not name:
            return ""

        # Keep only alphanumeric characters
        normalized = re.sub(r"[^a-z0-9]", "", name.lower())
        return normalized

    @staticmethod
    def parse_datetime_iso8601(date_str: str | None) -> dt.datetime | None:
        """Parse a date in ISO8601 format.

        Args:
            date_str: Date string to parse.

        Returns:
            datetime | None: Parsed date or None on failure.
        """
        if not date_str:
            return None

        # Supported formats
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",  # 2023-05-15T14:30:45.123Z
            "%Y-%m-%dT%H:%M:%SZ",  # 2023-05-15T14:30:45Z
            "%Y-%m-%dT%H:%M:%S.%f",  # 2023-05-15T14:30:45.123
            "%Y-%m-%dT%H:%M:%S",  # 2023-05-15T14:30:45
            "%Y-%m-%d %H:%M:%S",  # 2023-05-15 14:30:45
            "%Y-%m-%d",  # 2023-05-15
        ]

        # Clean the string
        date_str = date_str.strip()

        # Try each format
        for fmt in formats:
            try:
                return dt.datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # Fallback: manual parsing for non-standard formats
        try:
            # Strip milliseconds if present
            if "." in date_str and date_str.endswith("Z"):
                date_str = date_str.split(".")[0] + "Z"

            # Parse with dateutil if available
            try:
                from dateutil import parser  # type: ignore[import-untyped]

                return parser.parse(date_str)
            except ImportError:
                pass
        except ValueError:
            pass

        return None

    @staticmethod
    def normalize_coordinates(
        lat: str | float | None, lon: str | float | None
    ) -> tuple[float | None, float | None]:
        """Normalize and validate coordinates.

        Args:
            lat: Latitude (string or float).
            lon: Longitude (string or float).

        Returns:
            tuple: Normalized (latitude, longitude) or (None, None).
        """
        try:
            if lat is None or lon is None:
                return None, None

            # Convert to float
            lat_float = float(lat)
            lon_float = float(lon)

            # Validate bounds
            if not (-90 <= lat_float <= 90):
                return None, None
            if not (-180 <= lon_float <= 180):
                return None, None

            return lat_float, lon_float

        except (ValueError, TypeError):
            return None, None

    @staticmethod
    def normalize_difficulty_terrain(value: str | float | None) -> float | None:
        """Normalize a difficulty or terrain value.

        Args:
            value: Value to normalize.

        Returns:
            float | None: Value between 1.0 and 5.0 or None.
        """
        if value is None:
            return None

        try:
            float_val = float(value)

            # Validate bounds
            if not (1.0 <= float_val <= 5.0):
                return None

            # Round to nearest 0.5
            return round(float_val * 2) / 2.0

        except (ValueError, TypeError):
            return None

    @staticmethod
    def normalize_gc_code(gc_code: str | None) -> str | None:
        """Normalize a GC code.

        Args:
            gc_code: Raw GC code.

        Returns:
            str | None: Normalized GC code or None.
        """
        if not gc_code:
            return None

        # Strip and uppercase
        cleaned = gc_code.strip().upper()

        # Validate GCxxxxx format
        if not re.match(r"^GC[A-Z0-9]+$", cleaned):
            return None

        return cleaned

    @staticmethod
    def is_valid_for_import_mode(cache_data: dict[str, Any], import_mode: str) -> bool:
        """Check whether a cache is valid for the given import mode.

        Args:
            cache_data: Cache data.
            import_mode: Import mode ('found', 'caches', 'both').

        Returns:
            bool: True if the cache should be imported.
        """
        # Always import in 'both' mode
        if import_mode == "both":
            return True

        # For 'found' mode, require a found date
        if import_mode == "found":
            return cache_data.get("found_date") is not None

        # For 'all' mode, no restriction
        if import_mode == "all":
            return True

        return False

    @staticmethod
    def clean_html_content(content: str | None) -> str | None:
        """Clean HTML content (descriptions, logs, etc.).

        Args:
            content: Raw HTML content.

        Returns:
            str | None: Cleaned content or None.
        """
        if not content:
            return None

        # Strip basic HTML tags
        # Note: For more robust cleaning, use HTMLSanitizer
        cleaned = re.sub(r"<[^>]+>", "", content)
        cleaned = cleaned.strip()

        return cleaned if cleaned else None

    @staticmethod
    def extract_cache_metadata(raw_data: dict[str, Any]) -> dict[str, Any]:
        """Extract and normalize cache metadata.

        Args:
            raw_data: Raw cache data.

        Returns:
            dict: Normalized metadata.
        """
        metadata: dict[str, Any] = {}

        # GC code (required)
        gc_code = DataNormalizer.normalize_gc_code(raw_data.get("gc_code"))
        if gc_code:
            metadata["GC"] = gc_code

        # Title
        if raw_data.get("title"):
            metadata["title"] = str(raw_data["title"]).strip()

        # Description — parser may provide either "description" (raw) or "description_html" (pre-cleaned)
        description = DataNormalizer.clean_html_content(
            raw_data.get("description") or raw_data.get("description_html")
        )
        if description:
            metadata["description_html"] = description

        # URL
        if raw_data.get("url"):
            metadata["url"] = str(raw_data["url"]).strip()

        # Coordinates
        lat, lon = DataNormalizer.normalize_coordinates(
            raw_data.get("latitude"), raw_data.get("longitude")
        )
        if lat is not None and lon is not None:
            metadata["lat"] = lat
            metadata["lon"] = lon
            # GeoJSON for geographic index
            metadata["loc"] = {"type": "Point", "coordinates": [lon, lat]}

        # Difficulty and terrain
        difficulty = DataNormalizer.normalize_difficulty_terrain(raw_data.get("difficulty"))
        if difficulty is not None:
            metadata["difficulty"] = difficulty

        terrain = DataNormalizer.normalize_difficulty_terrain(raw_data.get("terrain"))
        if terrain is not None:
            metadata["terrain"] = terrain

        # Placement date
        placed_date = DataNormalizer.parse_datetime_iso8601(raw_data.get("placed_date"))
        if placed_date:
            metadata["placed_at"] = placed_date

        # Owner
        if raw_data.get("owner"):
            metadata["owner"] = str(raw_data["owner"]).strip()

        # Favorites
        try:
            favorites = int(raw_data.get("favorites", 0))
            if favorites >= 0:
                metadata["favorites"] = favorites
        except (ValueError, TypeError):
            pass

        # Status
        status = raw_data.get("status", "active").lower()
        if status in ["active", "disabled", "archived"]:
            metadata["status"] = status

        # Country / state (string names — resolved to ObjectIds by map_cache_referentials)
        if raw_data.get("country"):
            metadata["country"] = str(raw_data["country"]).strip()
        if raw_data.get("state"):
            metadata["state"] = str(raw_data["state"]).strip()

        # Attributes (if present)
        if "attributes" in raw_data and isinstance(raw_data["attributes"], list):
            metadata["attributes"] = raw_data["attributes"]

        return metadata

    @staticmethod
    def extract_found_metadata(raw_data: dict[str, Any]) -> dict[str, Any] | None:
        """Extract found cache metadata.

        Args:
            raw_data: Raw data including found cache information.

        Returns:
            dict | None: Found cache metadata or None.
        """
        found_date = DataNormalizer.parse_datetime_iso8601(raw_data.get("found_date"))
        if not found_date:
            return None

        metadata: dict[str, Any] = {
            "found_date": found_date,
        }

        # Log notes
        notes = DataNormalizer.clean_html_content(raw_data.get("notes"))
        if notes:
            metadata["notes"] = notes

        return metadata
