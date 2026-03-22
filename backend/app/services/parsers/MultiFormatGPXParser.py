# backend/app/services/parsers/MultiFormatGPXParser.py
# Parses a GPX file in multiple formats (cgeo, pocket query, etc.) to extract structured geocaches.

from pathlib import Path
from typing import Any, Optional

from lxml import etree


class MultiFormatGPXParser:
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

        self.caches: list[dict] = []

        # Import HTMLSanitizer locally to avoid circular dependencies
        from app.services.parsers.HTMLSanitizer import HTMLSanitizer

        self.sanitizer = HTMLSanitizer()

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
            if "cgeo" in creator or "c:geo" in creator:
                return "cgeo"

            # Check schema URLs
            schema_location = root.get(
                "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation", ""
            ).lower()
            if "cgeo" in schema_location:
                return "cgeo"

            # Check whether it is a Pocket Query
            if "pocket query" in schema_location or "pocket query" in creator:
                return "pocket_query"

            # Check the groundspeak namespace if present in the root element
            for _prefix, uri in root.nsmap.items():
                if "groundspeak.com/cache" in uri:
                    # Check the specific schema version
                    if "1/0/1" in uri:
                        return "cgeo"
                    elif "1/0" in uri:
                        return "pocket_query"

            # Last resort: search in the text content
            root_text = etree.tostring(root, encoding="unicode", method="xml").lower()
            if "c:geo" in root_text:
                return "cgeo"
            elif "pocket query" in root_text:
                return "pocket_query"

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

    def parse(self) -> list[dict]:
        """Parse the GPX according to the detected or specified format and populate `self.caches`.

        Description:
            - Iterates over `//gpx:wpt` waypoints and looks for the `groundspeak:cache` sub-element.\n
            - For each final cache (`_is_final_waypoint`), extracts useful fields
              (GC, title, coords, type, size, owner, D/T, country/state, sanitized HTML
              description, GSAK favorites, notes, dates, attributes via `_parse_attributes`).\n
            - Appends each dict to `self.caches`.

        Returns:
            list[dict]: List of structured caches ready for import.
        """
        tree = etree.parse(str(self.gpx_file))
        nodes: Any = tree.xpath("//gpx:wpt", namespaces=self.namespaces)
        if not isinstance(nodes, list):
            raise ValueError("XPath did not return nodes")

        for wpt in nodes:
            cache_elem = wpt.find("groundspeak:cache", namespaces=self.namespaces)
            if cache_elem is None:
                continue

            is_final = self._is_final_waypoint(cache_elem)
            if is_final:
                # Extraire les données en fonction du format
                cache = self._extract_cache_data(wpt, cache_elem)
                self.caches.append(cache)

        return self.caches

    def _extract_cache_data(self, wpt, cache_elem) -> dict:
        """Extract cache data according to the detected format."""
        # Start with the base fields common to all formats
        cache = {
            "GC": self.find_text_deep(wpt, "gpx:name"),
            "title": self.find_text_deep(wpt, "gpx:desc"),
            "latitude": float(wpt.attrib["lat"]) if "lat" in wpt.attrib else None,
            "longitude": float(wpt.attrib["lon"]) if "lon" in wpt.attrib else None,
            "cache_type": self.find_text_deep(wpt, "groundspeak:type"),
            "cache_size": self.find_text_deep(wpt, "groundspeak:container"),
            "owner": self.find_text_deep(wpt, "groundspeak:owner"),
            "difficulty": self.find_text_deep(wpt, "groundspeak:difficulty"),
            "terrain": self.find_text_deep(wpt, "groundspeak:terrain"),
            "country": self.find_text_deep(wpt, "groundspeak:country"),
            "state": self.find_text_deep(wpt, "groundspeak:state"),
            "description_html": self.sanitizer.clean_description_html(
                self.find_text_deep(wpt, "groundspeak:long_description")
            ),
            "placed_date": self.find_text_deep(wpt, "gpx:time"),
            "attributes": self._parse_attributes(cache_elem),
        }

        # Add format-specific fields
        if self.format_type == "cgeo":
            # Fields specific to the cgeo format (with GSAK)
            cache["favorites"] = int(self.find_text_deep(wpt, "gsak:FavPoints") or 0)
            cache["notes"] = self.find_text_deep(wpt, "gsak:GcNote")
            cache["found_date"] = self.find_text_deep(wpt, "gsak:UserFound")
        elif self.format_type == "pocket_query":
            # Fields specific to the pocket query format
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

            if not found_date and ("event" in cache_type):
                # Use the placed date as the found date for event caches
                # Try the direct <time> field first, then gpx:time
                event_time = self.find_text_deep(wpt, "time") or self.find_text_deep(
                    wpt, "gpx:time"
                )
                if event_time:
                    found_date = event_time
                    if not found_date.endswith("Z"):
                        found_date += "Z"

            cache["found_date"] = found_date

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

    def _parse_attributes(self, cache_elem) -> list[dict]:
        """Extract the attribute list from `<groundspeak:attributes>`.

        Description:
            Iterates over `groundspeak:attribute` nodes and returns
            `{id: int, is_positive: bool, name: str}` objects.

        Args:
            cache_elem: Parent `<groundspeak:cache>` XML element.

        Returns:
            list[dict]: Normalized attributes (id / inc / label).
        """
        attrs = []
        attribute_elements = cache_elem.xpath(
            "groundspeak:attributes/groundspeak:attribute", namespaces=self.namespaces
        )

        for attr in attribute_elements:
            attr_dict = {
                "id": int(attr.get("id")),
                "is_positive": attr.get("inc") == "1",
                "name": attr.text.strip() if attr.text else "",
            }
            attrs.append(attr_dict)

        return attrs

    def _is_final_waypoint(self, cache_elem) -> bool:
        """Filter final waypoints (placeholder).

        Description:
            Extension point to extract only certain waypoints (e.g. finals).
            Current implementation always returns True.

        Args:
            cache_elem: `<groundspeak:cache>` XML element.

        Returns:
            bool: True if the waypoint should be kept.
        """
        return True

    def find_text_deep(self, element, tag: str) -> str:
        """Find text via relative XPath (`.//{tag}`).

        Args:
            element: Starting element for the search.
            tag (str): Prefix-qualified XPath tag (e.g. `gpx:name`).

        Returns:
            str: Text found, or empty string.
        """
        found = element.xpath(f".//{tag}", namespaces=self.namespaces)
        return found[0].text.strip() if found and len(found) and found[0].text else ""

    def get_caches(self) -> list[dict]:
        """Retrieve the list of already-extracted caches.

        Returns:
            list[dict]: Current value of `self.caches`.
        """
        return self.caches
