# backend/app/services/parsers/MultiFormatGPXParser.py
# Parses a GPX file in multiple formats (cgeo, pocket query, etc.) to extract structured geocaches.

from pathlib import Path
from typing import Any, Optional

from lxml import etree

from app.services.parsers.base_gpx_parser import BaseGPXParser


class MultiFormatGPXParser(BaseGPXParser):
    """Multi-format GPX geocache parser.

    Description:
        Reads a GPX file in various formats (cgeo, pocket query) and extracts a
        list of caches ready for import: GC code, title, coordinates, type,
        size, owner, D/T, country/state, sanitized HTML description, favorites,
        notes, dates (placed / found), attributes, etc.

    Attributes:
        gpx_file (Path): Path to the GPX file.
        format_type (str): Specified or detected format (‘cgeo’, ‘pocket_query’, etc.).
        namespaces (dict): XML namespace prefixes used for XPath queries.
        caches (list[dict]): Results accumulated after `parse`.
        sanitizer (HTMLSanitizer): HTML sanitizer for the long description.
    """

    def __init__(self, gpx_file: Path, format_type: str = "auto"):
        """Initialize the multi-format GPX parser.

        Args:
            gpx_file (Path): Path to the GPX file to parse.
            format_type (str): Format type to use — 'auto' for automatic detection,
                               'cgeo' or 'pocket_query' to force a specific format.

        Returns:
            None
        """
        self.gpx_file = gpx_file

        if format_type == "auto":
            self.format_type = self._detect_format()
        else:
            # Validate that the requested format is supported
            if format_type in ["cgeo", "pocket_query"]:
                self.format_type = format_type
            else:
                # Unsupported format; fall back to automatic detection
                self.format_type = self._detect_format()

        # Set namespaces based on the detected or specified format
        self.namespaces = self._get_namespaces_for_format(self.format_type)

        super().__init__()

    @staticmethod
    def _detect_format_from_creator(creator: str) -> str | None:
        """Detect the format from the GPX file's `creator` attribute."""
        if "cgeo" in creator or "c:geo" in creator:
            return "cgeo"
        return None

    @staticmethod
    def _detect_format_from_schema_location(schema_location: str, creator: str) -> str | None:
        """Detect the format from the XSI schemaLocation (and creator for Pocket Query)."""
        if "cgeo" in schema_location:
            return "cgeo"
        if "pocket query" in schema_location or "pocket query" in creator:
            return "pocket_query"
        return None

    @staticmethod
    def _detect_format_from_groundspeak_namespace(root: Any) -> str | None:
        """Detect the format from the groundspeak cache namespace URI/version."""
        for _prefix, uri in root.nsmap.items():
            if "groundspeak.com/cache" in uri:
                if "1/0/1" in uri:
                    return "cgeo"
                if "1/0" in uri:
                    return "pocket_query"
        return None

    @staticmethod
    def _detect_format_from_text_content(root: Any) -> str | None:
        """Last-resort format detection by searching the serialized XML text."""
        root_text = etree.tostring(root, encoding="unicode", method="xml").lower()
        if "c:geo" in root_text:
            return "cgeo"
        if "pocket query" in root_text:
            return "pocket_query"
        return None

    def _detect_format(self) -> str:
        """Detect the GPX format by reading root metadata.

        Description:
            Detects the format based on the creator attribute or schema URLs
            present in the root element.

        Returns:
            str: Detected format ('cgeo' or 'pocket_query').
        """
        try:
            tree = etree.parse(str(self.gpx_file))
            root = tree.getroot()

            # Check the file creator
            creator = root.get("creator", "").lower()
            detected = self._detect_format_from_creator(creator)
            if detected:
                return detected

            # Check schema URLs
            schema_location = root.get(
                "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation", ""
            ).lower()
            detected = self._detect_format_from_schema_location(schema_location, creator)
            if detected:
                return detected

            # Check the groundspeak namespace if present in the root element
            detected = self._detect_format_from_groundspeak_namespace(root)
            if detected:
                return detected

            # Last resort: search in the text content
            detected = self._detect_format_from_text_content(root)
            if detected:
                return detected

        except Exception:
            # Error during format detection; continue with automatic detection
            pass

        # Default: assume cgeo
        return "cgeo"

    def _get_namespaces_for_format(self, format_type: str) -> dict[str, str]:
        """Return the appropriate namespaces for a given format."""
        if format_type == "cgeo":
            return {
                "gpx": "http://www.topografix.com/GPX/1/0",
                "groundspeak": "http://www.groundspeak.com/cache/1/0/1",
                "gsak": "http://www.gsak.net/xmlv1/6",
            }
        elif format_type == "pocket_query":
            return {
                "gpx": "http://www.topografix.com/GPX/1/0",
                "groundspeak": "http://www.groundspeak.com/cache/1/0",  # 1/0 instead of 1/0/1
            }
        else:
            # Unknown format; fall back to cgeo defaults
            return {
                "gpx": "http://www.topografix.com/GPX/1/0",
                "groundspeak": "http://www.groundspeak.com/cache/1/0/1",
                "gsak": "http://www.gsak.net/xmlv1/6",
            }

    def _build_base_cache_fields(self, wpt: Any, cache_elem: Any) -> dict[str, Any]:
        """Build the cache fields common to all GPX formats.

        Description:
            Starts from `BaseGPXParser._build_base_cache_fields` and adds the
            coordinates, read defensively (missing `lat`/`lon` attributes
            yield `None` rather than raising, unlike `GPXCacheParser`).

        Args:
            wpt: The waypoint XML element.
            cache_elem: The groundspeak cache XML element.

        Returns:
            dict: Base cache fields.
        """
        cache = super()._build_base_cache_fields(wpt, cache_elem)
        cache["latitude"] = float(wpt.attrib["lat"]) if "lat" in wpt.attrib else None
        cache["longitude"] = float(wpt.attrib["lon"]) if "lon" in wpt.attrib else None
        return cache

    def _apply_cgeo_fields(self, cache: dict[str, Any], wpt: Any) -> None:
        """Add cgeo/GSAK-specific fields to `cache`, mutating it in place.

        Args:
            cache: Cache dict to enrich.
            wpt: The waypoint XML element.
        """
        cache["favorites"] = int(self.find_text_deep(wpt, "gsak:FavPoints") or 0)
        cache["notes"] = self.find_text_deep(wpt, "gsak:GcNote")
        cache["found_date"] = self.find_text_deep(wpt, "gsak:UserFound")

    def _resolve_event_found_date(
        self, wpt: Any, found_date: str | None, cache_type: str
    ) -> str | None:
        """Fall back to the placed date as the found date, for event-type caches.

        Args:
            wpt: The waypoint XML element.
            found_date: Found date already resolved from logs (if any).
            cache_type: Lowercased cache type.

        Returns:
            str | None: The resolved found date.
        """
        if found_date or "event" not in cache_type:
            return found_date

        # Use the placed date as the found date for event caches
        # Try the direct <time> field first, then gpx:time
        event_time = self.find_text_deep(wpt, "time") or self.find_text_deep(wpt, "gpx:time")
        if not event_time:
            return found_date

        if not event_time.endswith("Z"):
            event_time += "Z"
        return event_time

    def _apply_pocket_query_fields(self, cache: dict[str, Any], wpt: Any, cache_elem: Any) -> None:
        """Add pocket-query-specific fields to `cache`, mutating it in place.

        Args:
            cache: Cache dict to enrich.
            wpt: The waypoint XML element.
            cache_elem: The groundspeak cache XML element.
        """
        # For now, initialize with default values
        # Can be improved by looking for additional format-specific fields
        cache["favorites"] = 0  # Pocket queries do not carry GSAK FavPoints
        cache["notes"] = None

        # Check whether logs are available in the pocket query format
        found_date = self._extract_found_date_from_logs(cache_elem)

        # For event-type caches, if no found date is available,
        # use the placed date (time) as the found date
        raw_cache_type = cache.get("cache_type", "")

        # Ensure it is a string before calling .lower()
        if isinstance(raw_cache_type, str):
            cache_type = raw_cache_type.lower()
        else:
            # Convert to str if it is another type (float, list, etc.)
            cache_type = str(raw_cache_type).lower()

        cache["found_date"] = self._resolve_event_found_date(wpt, found_date, cache_type)

    def _extract_cache_data(self, wpt, cache_elem) -> dict:
        """Extract cache data according to the detected format."""
        cache = self._build_base_cache_fields(wpt, cache_elem)

        # Add format-specific fields
        if self.format_type == "cgeo":
            # Fields specific to the cgeo format (with GSAK)
            self._apply_cgeo_fields(cache, wpt)
        elif self.format_type == "pocket_query":
            # Fields specific to the pocket query format
            self._apply_pocket_query_fields(cache, wpt, cache_elem)

        return cache

    def _extract_found_date_from_logs(self, cache_elem) -> Optional[str]:
        """Attempt to extract the found date from logs in the pocket query format."""
        # Retrieve all logs for the cache
        logs = cache_elem.xpath("groundspeak:logs/groundspeak:log", namespaces=self.namespaces)

        # If no logs, return None
        if not logs:
            return None

        # If there is a single log and the format is pocket query, use its date as found_date
        if self.format_type == "pocket_query" and len(logs) == 1:
            date = self.find_text_deep(logs[0], "groundspeak:date")
            if date:
                # Ensure the date ends with Z if needed
                if not date.endswith("Z"):
                    date += "Z"
                return date

        # For all formats, search for "found" log types
        # in reverse chronological order (most recent first)
        logs_sorted = sorted(
            logs, key=lambda x: self.find_text_deep(x, "groundspeak:date"), reverse=True
        )

        for log in logs_sorted:
            log_type = self.find_text_deep(log, "groundspeak:type")
            if log_type and "found" in log_type.lower():
                date = self.find_text_deep(log, "groundspeak:date")
                if date:
                    return date
        return None
