# backend/app/services/parsers/base_gpx_parser.py
# Shared behavior for GPX geocache parsers (lxml-based), factored out of
# GPXCacheParser and MultiFormatGPXParser to remove duplication between them.

from pathlib import Path
from typing import Any

from lxml import etree

from app.services.parsers.HTMLSanitizer import HTMLSanitizer


class BaseGPXParser:
    """Shared behavior for GPX geocache parsers.

    Description:
        Hosts the XML tree walk common to every GPX parser (`parse`), the
        helpers used to read waypoint data (`find_text_deep`,
        `_parse_attributes`, `_build_base_cache_fields`), and the final
        waypoint filter (`_is_final_waypoint`). Subclasses must set
        `self.gpx_file` and `self.namespaces` before calling `parse()`, and
        must implement `_extract_cache_data` to build the per-cache dict
        (base fields plus whatever is specific to their format).

    Attributes:
        gpx_file (Path): Path to the GPX file (set by the subclass).
        namespaces (dict): XML namespace prefixes used for XPath queries
            (set by the subclass).
        caches (list[dict]): Results accumulated after `parse()`.
        sanitizer (HTMLSanitizer): HTML sanitizer for the long description.
    """

    gpx_file: Path
    namespaces: dict[str, str]

    def __init__(self) -> None:
        """Initialize the shared parser state (cache list, HTML sanitizer).

        Returns:
            None
        """
        self.caches: list[dict] = []
        self.sanitizer = HTMLSanitizer()

    def parse(self) -> list[dict]:
        """Parse the GPX file and populate `self.caches`.

        Description:
            - Iterates over `//gpx:wpt` waypoints and looks for the `groundspeak:cache` sub-element.\n
            - For each final cache (`_is_final_waypoint`), delegates to
              `_extract_cache_data` to build the cache dict.\n
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
                cache = self._extract_cache_data(wpt, cache_elem)
                self.caches.append(cache)

        return self.caches

    def _extract_cache_data(self, wpt: Any, cache_elem: Any) -> dict:
        """Build the cache dict for one final waypoint (format-specific).

        Args:
            wpt: The waypoint XML element.
            cache_elem: The groundspeak cache XML element.

        Returns:
            dict: Cache fields ready for import.
        """
        raise NotImplementedError

    def _build_base_cache_fields(self, wpt: Any, cache_elem: Any) -> dict[str, Any]:
        """Build the cache fields common to every GPX format.

        Description:
            Excludes `latitude`/`longitude` and the found-date-related fields
            (favorites, notes, found_date), which differ enough between
            formats (missing-attribute handling, source of the found date)
            that each subclass builds them itself.

        Args:
            wpt: The waypoint XML element.
            cache_elem: The groundspeak cache XML element.

        Returns:
            dict: Base cache fields.
        """
        return {
            "GC": self.find_text_deep(wpt, "gpx:name"),
            "title": self.find_text_deep(wpt, "gpx:desc"),
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

    def _parse_attributes(self, cache_elem: Any) -> list[dict]:
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

    def _is_final_waypoint(self, cache_elem: Any) -> bool:
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

    def find_text_deep(self, element: Any, tag: str) -> str:
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

    def get_caches(self) -> list[dict]:
        """Retrieve the list of already-extracted caches.

        Args:
            None

        Returns:
            list[dict]: Current value of `self.caches`.
        """
        return self.caches
