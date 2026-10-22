# backend/app/services/parsers/GPXCacheParser.py
# Parses a GPX file (from a file path) to extract structured geocaches (metadata, attributes).

import html
from pathlib import Path
from typing import Any

from app.services.parsers.base_gpx_parser import BaseGPXParser


class GPXCacheParser(BaseGPXParser):
    """GPX geocache parser.

    Description:
        Reads a GPX file (schemas `gpx`, `groundspeak`, `gsak`) and extracts a
        list of caches ready for import: GC code, title, coordinates, type,
        size, owner, D/T, country/state, sanitized HTML description, favorites,
        notes, dates (placed / found), attributes, etc.

    Attributes:
        gpx_file (Path): Path to the GPX file.
        namespaces (dict): XML namespace prefixes used for XPath queries.
        caches (list[dict]): Results accumulated after `parse()`.
        sanitizer (HTMLSanitizer): HTML sanitizer for the long description.
    """

    def __init__(self, gpx_file: Path):
        """Initialize the GPX parser.

        Description:
            Stores the path to the GPX file, initializes the expected namespaces,
            and prepares internal structures (cache list, HTML sanitizer).

        Args:
            gpx_file (Path): Path to the GPX file to parse.

        Returns:
            None
        """
        self.gpx_file = gpx_file
        self.namespaces = {
            "gpx": "http://www.topografix.com/GPX/1/0",
            "groundspeak": "http://www.groundspeak.com/cache/1/0/1",
            "gsak": "http://www.gsak.net/xmlv1/6",
        }
        super().__init__()

    def _extract_cache_data(self, wpt: Any, cache_elem: Any) -> dict:
        """Build the cache dict for one final waypoint.

        Description:
            Base fields (see `BaseGPXParser._build_base_cache_fields`) plus the
            fields specific to this parser: coordinates (required, raises if
            missing), GSAK favorites, notes, and found date.

        Args:
            wpt: The waypoint XML element.
            cache_elem: The groundspeak cache XML element.

        Returns:
            dict: Cache fields ready for import.
        """
        cache = self._build_base_cache_fields(wpt, cache_elem)
        cache["latitude"] = float(wpt.attrib["lat"])
        cache["longitude"] = float(wpt.attrib["lon"])
        cache["favorites"] = int(self.find_text_deep(wpt, "gsak:FavPoints") or 0)
        cache["notes"] = self.find_text_deep(wpt, "gsak:GcNote")
        cache["found_date"] = self.find_text_deep(wpt, "gsak:UserFound")
        return cache

    def _has_corrected_coordinates(self, wpt_elem) -> bool:
        """Indicate whether the cache has corrected coordinates (placeholder).

        Description:
            Detector for corrected coordinates (e.g. a solved mystery cache). Implementation
            is intentionally minimal; the return value can be refined as needed.

        Args:
            wpt_elem: `<gpx:wpt>` XML element.

        Returns:
            bool: True if corrected coordinates are detected, otherwise False.
        """

        return wpt_elem.find("gsak:corrected", namespaces=self.namespaces) is not None

    def _has_found_log(self, cache_elem) -> bool:
        """Check for the presence of a "Found it" log entry.

        Description:
            Searches for a `groundspeak:log` node whose `type` text equals "Found it".

        Args:
            cache_elem: `<groundspeak:cache>` XML element.

        Returns:
            bool: True if at least one "Found it" log is present, otherwise False.
        """
        for log in cache_elem.xpath("groundspeak:logs/groundspeak:log", namespaces=self.namespaces):
            log_type = self._text(log.find("groundspeak:type", namespaces=self.namespaces))
            if log_type.lower() == "found it":
                return True
        return False

    def _was_found(self, wpt_elem) -> bool:
        """Determine whether the cache has a GSAK "UserFound" indicator.

        Description:
            Checks for the presence of a `gsak:UserFound`/`gsak:userfound` field indicating
            that the cache was logged as found by the user on the GSAK side.

        Args:
            wpt_elem: `<gpx:wpt>` XML element.

        Returns:
            bool: True if the indicator is present, otherwise False.
        """
        return wpt_elem.find("gsak:userfound", namespaces=self.namespaces) is not None

    def _text(self, element, default: str = "") -> str:
        """Read the text of an element (stripped), with a default value.

        Args:
            element: XML element or None.
            default (str): Default value if text is absent.

        Returns:
            str: Stripped text content.
        """
        return element.text.strip() if element is not None and element.text else default

    def _html(self, element, default: str = "") -> str:
        """Read HTML text and unescape it.

        Description:
            Returns `html.unescape(element.text.strip())` if the element is present.

        Args:
            element: XML element or None.
            default (str): Default value if empty.

        Returns:
            str: Unescaped HTML (or empty string).
        """
        return html.unescape(element.text.strip()) if element is not None and element.text else ""
