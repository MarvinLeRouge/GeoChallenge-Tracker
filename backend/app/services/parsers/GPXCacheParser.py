# backend/app/services/parsers/GPXCacheParser.py

from lxml import etree
from pathlib import Path
from typing import List, Dict
import html
from app.services.parsers.HTMLSanitizer import HTMLSanitizer

class GPXCacheParser:
    
    def __init__(self, gpx_file: Path):
        self.gpx_file = gpx_file
        self.namespaces = {
            "gpx": "http://www.topografix.com/GPX/1/0",
            "groundspeak": "http://www.groundspeak.com/cache/1/0/1",
            "gsak": "http://www.gsak.net/xmlv1/6",
        }
        self.caches: List[Dict] = []
        self.sanitizer = HTMLSanitizer()
    
    def test(self):
        tree = etree.parse(str(self.gpx_file))
        for elem in tree.getroot().iter():
            print(elem.tag)

    def parse(self):
        tree = etree.parse(str(self.gpx_file))
        for wpt in tree.xpath("//gpx:wpt", namespaces=self.namespaces):
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
                    "description_html": self.sanitizer.clean_description_html(self.find_text_deep(wpt, "groundspeak:long_description")),
                    "favorites": int(self.find_text_deep(wpt, "gsak:FavPoints") or 0),
                    "notes": self.find_text_deep(wpt, "gsak:GcNote"),
                    "placed_date": self.find_text_deep(wpt, "gpx:time"),
                    "found_date": self.find_text_deep(wpt, "gsak:UserFound"),
                    "attributes": self._parse_attributes(cache_elem)
                }
                self.caches.append(cache)

        return self.caches


    def _parse_attributes(self, cache_elem) -> List[Dict]:
        attrs = []
        for attr in cache_elem.xpath("groundspeak:attributes/groundspeak:attribute", namespaces=self.namespaces):
            attrs.append({
                "id": int(attr.get("id")),
                "is_positive": attr.get("inc") == "1",
                "name": attr.text.strip() if attr.text else ""
            })

        return attrs

    def _has_corrected_coordinates(self, wpt_elem) -> bool:
        """True if cache has corrected coordinates (mystery solved)"""
        gsak_infos = wpt_elem.find("gsak:wptExtension", None)
        if gsak_infos is not None:
            print(gsak_infos)
        #return wpt_elem.find("gsak:corrected", namespaces=self.namespaces) is not None

    def _has_found_log(self, cache_elem) -> bool:
        """Returns True if a 'Found it' log is present"""
        for log in cache_elem.xpath("groundspeak:logs/groundspeak:log", namespaces=self.namespaces):
            log_type = self._text(log.find("groundspeak:type", namespaces=self.namespaces))
            if log_type.lower() == "found it":
                return True
        return False

    def _was_found(self, wpt_elem) -> bool:
        """Returns True if cache has gsak:UserFound property"""
        return wpt_elem.find("gsak:userfound", namespaces=self.namespaces) is not None

    def _is_final_waypoint(self, cache_elem) -> bool:
        """You can refine logic here if needed. Placeholder returns True always."""
        return True

    def _text(self, element, default="") -> str:
        return element.text.strip() if element is not None and element.text else default

    def _html(self, element, default="") -> str:
        return html.unescape(element.text.strip()) if element is not None and element.text else ""

    def get_caches(self) -> List[Dict]:
        return self.caches

    def find_text_deep(self, element, tag):
        found = element.xpath(f".//{tag}", namespaces=self.namespaces)
        return found[0].text.strip() if found and len(found) and found[0].text else ""
