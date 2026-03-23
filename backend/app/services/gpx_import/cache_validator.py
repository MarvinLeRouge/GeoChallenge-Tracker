# backend/app/services/gpx_import/cache_validator.py
# Business validation of cache data.

from __future__ import annotations

import re
from typing import Any


class CacheValidator:
    """Cache business validation service.

    Description:
        Responsible for enforcing business rules
        on caches before database persistence.
    """

    def __init__(self, strict_mode: bool = False):
        """Initialize the validator.

        Args:
            strict_mode: Strict mode (reject incomplete data).
        """
        self.strict_mode = strict_mode

    def validate_cache_data(self, cache_data: dict[str, Any]) -> dict[str, Any]:
        """Validate and clean cache data.

        Args:
            cache_data: Cache data to validate.

        Returns:
            dict: Validated and cleaned cache data.

        Raises:
            ValueError: If the data is invalid.
        """
        validated = cache_data.copy()

        # Required: GC code
        if not validated.get("GC"):
            raise ValueError("Missing required GC code")

        if not self._validate_gc_code(validated["GC"]):
            raise ValueError(f"Invalid GC code: {validated['GC']}")

        # Required: title
        if not validated.get("title"):
            if self.strict_mode:
                raise ValueError("Missing required title")
            validated["title"] = f"Cache {validated['GC']}"

        # Validate coordinates
        self._validate_coordinates(validated)

        # Validate difficulty/terrain
        self._validate_difficulty_terrain(validated)

        # Validate owner
        self._validate_owner(validated)

        # Validate dates
        self._validate_dates(validated)

        # Validate favorites
        self._validate_favorites(validated)

        # Validate status
        self._validate_status(validated)

        return validated

    def _validate_gc_code(self, gc_code: str) -> bool:
        """Validate a GC code.

        Args:
            gc_code: GC code to validate.

        Returns:
            bool: True if valid.
        """
        if not isinstance(gc_code, str):
            return False

        # GCxxxxx format (at least 3 characters after GC)
        pattern = r"^GC[A-Z0-9]{3,}$"
        return bool(re.match(pattern, gc_code.upper()))

    def _validate_coordinates(self, cache_data: dict[str, Any]) -> None:
        """Validate coordinates.

        Args:
            cache_data: Cache data to validate.

        Raises:
            ValueError: If coordinates are invalid.
        """
        lat = cache_data.get("lat")
        lon = cache_data.get("lon")

        if lat is None or lon is None:
            raise ValueError("Missing coordinates (lat/lon required)")

        # Type validation
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            raise ValueError("Coordinates must be numbers")

        # Bounds validation
        if not (-90 <= lat <= 90):
            raise ValueError(f"Invalid latitude: {lat} (must be between -90 and 90)")

        if not (-180 <= lon <= 180):
            raise ValueError(f"Invalid longitude: {lon} (must be between -180 and 180)")

        # Reject null/invalid coordinates (0, 0)
        if lat == 0.0 and lon == 0.0:
            if self.strict_mode:
                raise ValueError("Invalid coordinates (0,0)")
            # In non-strict mode, remove invalid coordinates
            cache_data.pop("lat", None)
            cache_data.pop("lon", None)
            cache_data.pop("loc", None)

    def _validate_difficulty_terrain(self, cache_data: dict[str, Any]) -> None:
        """Validate difficulty and terrain.

        Args:
            cache_data: Cache data to validate.

        Raises:
            ValueError: If values are invalid.
        """
        for field in ["difficulty", "terrain"]:
            value = cache_data.get(field)
            if value is None:
                continue

            if not isinstance(value, (int, float)):
                raise ValueError(f"{field} must be a number")

            if not (1.0 <= value <= 5.0):
                raise ValueError(f"{field} must be between 1.0 and 5.0, got {value}")

            # Round to nearest 0.5
            cache_data[field] = round(value * 2) / 2.0

    def _validate_owner(self, cache_data: dict[str, Any]) -> None:
        """Validate the owner.

        Args:
            cache_data: Cache data to validate.

        Raises:
            ValueError: If the owner is invalid.
        """
        owner = cache_data.get("owner")
        if owner is None:
            return

        if not isinstance(owner, str):
            cache_data["owner"] = str(owner)

        # Clean the owner name
        owner_clean = cache_data["owner"].strip()
        if not owner_clean:
            cache_data.pop("owner", None)
            return

        # Check length
        if len(owner_clean) > 100:
            raise ValueError("Owner name too long (max 100 characters)")

        cache_data["owner"] = owner_clean

    def _validate_dates(self, cache_data: dict[str, Any]) -> None:
        """Validate dates.

        Args:
            cache_data: Cache data to validate.

        Raises:
            ValueError: If dates are invalid.
        """
        import datetime as dt

        # Validate placed_at
        placed_at = cache_data.get("placed_at")
        if placed_at is not None:
            if not isinstance(placed_at, dt.datetime):
                raise ValueError("placed_at must be a datetime object")

            # Reject future dates
            if placed_at > dt.datetime.utcnow():
                raise ValueError("placed_at cannot be in the future")

            # Reject dates before 2000
            if placed_at.year < 2000:
                if self.strict_mode:
                    raise ValueError("placed_at seems too old (before 2000)")
                cache_data.pop("placed_at", None)

    def _validate_favorites(self, cache_data: dict[str, Any]) -> None:
        """Validate the favorites count.

        Args:
            cache_data: Cache data to validate.

        Raises:
            ValueError: If the count is invalid.
        """
        favorites = cache_data.get("favorites")
        if favorites is None:
            return

        if not isinstance(favorites, int):
            try:
                favorites = int(favorites)
                cache_data["favorites"] = favorites
            except (ValueError, TypeError) as e:
                raise ValueError("favorites must be an integer") from e

        if favorites < 0:
            raise ValueError("favorites cannot be negative")

        # Reasonable upper bound
        if favorites > 10000:
            if self.strict_mode:
                raise ValueError("favorites count seems too high")
            cache_data["favorites"] = 10000

    def _validate_status(self, cache_data: dict[str, Any]) -> None:
        """Validate the cache status.

        Args:
            cache_data: Cache data to validate.
        """
        status = cache_data.get("status")
        if status is None:
            cache_data["status"] = "active"  # default value
            return

        if not isinstance(status, str):
            cache_data["status"] = str(status).lower()
        else:
            cache_data["status"] = status.lower()

        # Allowed values
        valid_statuses = ["active", "disabled", "archived"]
        if cache_data["status"] not in valid_statuses:
            cache_data["status"] = "active"  # default value

    def validate_found_data(self, found_data: dict[str, Any]) -> dict[str, Any]:
        """Validate found cache data.

        Args:
            found_data: Found cache data to validate.

        Returns:
            dict: Validated found cache data.

        Raises:
            ValueError: If the data is invalid.
        """
        validated = found_data.copy()

        # Required: found date
        if not validated.get("found_date"):
            raise ValueError("Missing required found_date")

        import datetime as dt

        if not isinstance(validated["found_date"], dt.datetime):
            raise ValueError("found_date must be a datetime object")

        # Reject future dates
        if validated["found_date"] > dt.datetime.utcnow():
            raise ValueError("found_date cannot be in the future")

        # Reject dates before 2000
        if validated["found_date"].year < 2000:
            if self.strict_mode:
                raise ValueError("found_date seems too old (before 2000)")

        # Validate notes (optional)
        if "notes" in validated:
            notes = validated["notes"]
            if notes is not None:
                if not isinstance(notes, str):
                    validated["notes"] = str(notes)

                # Enforce maximum length
                if len(validated["notes"]) > 4000:
                    if self.strict_mode:
                        raise ValueError("Notes too long (max 4000 characters)")
                    validated["notes"] = validated["notes"][:4000]

        return validated

    def validate_import_consistency(
        self, cache_data: dict[str, Any], found_data: dict[str, Any] | None, import_mode: str
    ) -> None:
        """Validate consistency between cache and found data.

        Args:
            cache_data: Cache data.
            found_data: Found cache data (optional).
            import_mode: Import mode.

        Raises:
            ValueError: If the data is inconsistent.
        """
        # Enforce import mode contract
        if import_mode == "found" and found_data is None:
            raise ValueError("found mode requires found_date")

        # If found data is present, validate date consistency
        if found_data and cache_data.get("placed_at"):
            if found_data["found_date"] < cache_data["placed_at"]:
                raise ValueError("found_date cannot be before placed_at")

        # Verify GC codes match (when found data carries an external GC)
        if found_data and "GC" in found_data:
            if found_data["GC"] != cache_data.get("GC"):
                raise ValueError("GC code mismatch between cache and found data")
