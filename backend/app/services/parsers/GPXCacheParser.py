# backend/app/services/parsers/GPXCacheParser.py
# Parses a GPX file (from a file path) to extract structured geocaches (metadata, attributes).

import html
from pathlib import Path
from typing import Any

from lxml import etree

from app.services.parsers.HTMLSanitizer import HTMLSanitizer


class GPXCacheParser:
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
        self.caches: list[dict] = []
        self.sanitizer = HTMLSanitizer()

    def parse(self) -> list[dict]:
        """Parse the GPX file and populate `self.caches`.

        Description:
            - Iterates over `//gpx:wpt` waypoints and looks for the `groundspeak:cache` sub-element.\n
            - For each final cache (`_is_final_waypoint`), extracts useful fields
              (GC, title, coords, type, size, owner, D/T, country/state, sanitized HTML
              description, GSAK favorites, notes, dates, attributes via `_parse_attributes`).\n
            - Appends each dict to `self.caches`.

        Args:
            None

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
                cache = {
                    "GC": self.find_text_deep(wpt, "gpx:name"),
                    "title": self.find_text_deep(wpt, "gpx:desc"),
                    "latitude": float(wpt.attrib["lat"]),
                    "longitude": float(wpt.attrib["lon"]),
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
                    "favorites": int(self.find_text_deep(wpt, "gsak:FavPoints") or 0),
                    "notes": self.find_text_deep(wpt, "gsak:GcNote"),
                    "placed_date": self.find_text_deep(wpt, "gpx:time"),
                    "found_date": self.find_text_deep(wpt, "gsak:UserFound"),
                    "attributes": self._parse_attributes(cache_elem),
                }
                self.caches.append(cache)

        return self.caches

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
        for attr in cache_elem.xpath(
            "groundspeak:attributes/groundspeak:attribute", namespaces=self.namespaces
        ):
            attrs.append(
                {
                    "id": int(attr.get("id")),
                    "is_positive": attr.get("inc") == "1",
                    "name": attr.text.strip() if attr.text else "",
                }
            )

        return attrs

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

    def get_caches(self) -> list[dict]:
        """Retrieve the list of already-extracted caches.

        Args:
            None

        Returns:
            list[dict]: Current value of `self.caches`.
        """
        return self.caches

    def find_text_deep(self, element, tag: str) -> str:
        """Find text via relative XPath (`.//{tag}`).

        Description:
            Executes `element.xpath(f".//{tag}", namespaces=self.namespaces)` and returns
            the first text found (stripped) or an empty string.

        Args:
            element: Starting element for the search.
            tag (str): Prefix-qualified XPath tag (e.g. `gpx:name`).

        Returns:
            str: Text found, or empty string.
        """
        found = element.xpath(f".//{tag}", namespaces=self.namespaces)
        return found[0].text.strip() if found and len(found) and found[0].text else ""
