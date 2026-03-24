"""Tests for MultiFormatGPXParser.parse() and related methods (unit)."""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from app.services.parsers.MultiFormatGPXParser import MultiFormatGPXParser

# ---------------------------------------------------------------------------
# GPX content builders
# ---------------------------------------------------------------------------

_CGEO_FULL_WPT = """\
  <wpt lat="48.8566" lon="2.3522">
    <name>GC12345</name>
    <desc>Test Cache</desc>
    <time>2020-06-15T00:00:00Z</time>
    <groundspeak:cache>
      <groundspeak:type>Traditional Cache</groundspeak:type>
      <groundspeak:container>Regular</groundspeak:container>
      <groundspeak:owner>TestUser</groundspeak:owner>
      <groundspeak:difficulty>2.5</groundspeak:difficulty>
      <groundspeak:terrain>3.0</groundspeak:terrain>
      <groundspeak:country>France</groundspeak:country>
      <groundspeak:state>Ile-de-France</groundspeak:state>
      <groundspeak:long_description></groundspeak:long_description>
      <groundspeak:attributes>
        <groundspeak:attribute id="7" inc="1">Dogs</groundspeak:attribute>
        <groundspeak:attribute id="8" inc="0">Bikes</groundspeak:attribute>
      </groundspeak:attributes>
    </groundspeak:cache>
    <gsak:FavPoints>10</gsak:FavPoints>
    <gsak:GcNote>My note</gsak:GcNote>
    <gsak:UserFound>2024-06-01</gsak:UserFound>
  </wpt>"""


def _cgeo_gpx(wpt_content: str = _CGEO_FULL_WPT) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.0" creator="cgeo"\n'
        '  xmlns="http://www.topografix.com/GPX/1/0"\n'
        '  xmlns:groundspeak="http://www.groundspeak.com/cache/1/0/1"\n'
        '  xmlns:gsak="http://www.gsak.net/xmlv1/6">\n' + wpt_content + "\n</gpx>"
    )


def _pq_gpx(wpt_content: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.0" creator="Groundspeak Pocket Query"\n'
        '  xmlns="http://www.topografix.com/GPX/1/0"\n'
        '  xmlns:groundspeak="http://www.groundspeak.com/cache/1/0">\n' + wpt_content + "\n</gpx>"
    )


def _make_parser(tmp_path: Path, content: str, fmt: str = "auto") -> MultiFormatGPXParser:
    gpx_file = tmp_path / "test.gpx"
    gpx_file.write_text(content, encoding="utf-8")
    return MultiFormatGPXParser(gpx_file, format_type=fmt)


# ---------------------------------------------------------------------------
# parse() — cgeo format
# ---------------------------------------------------------------------------


class TestParseCgeo:
    def test_parse_returns_one_cache(self, tmp_path):
        parser = _make_parser(tmp_path, _cgeo_gpx())
        caches = parser.parse()
        assert len(caches) == 1

    def test_parse_extracts_gc_and_title(self, tmp_path):
        parser = _make_parser(tmp_path, _cgeo_gpx())
        cache = parser.parse()[0]
        assert cache["GC"] == "GC12345"
        assert cache["title"] == "Test Cache"

    def test_parse_extracts_coordinates(self, tmp_path):
        parser = _make_parser(tmp_path, _cgeo_gpx())
        cache = parser.parse()[0]
        assert cache["latitude"] == pytest.approx(48.8566)
        assert cache["longitude"] == pytest.approx(2.3522)

    def test_parse_extracts_difficulty_terrain(self, tmp_path):
        parser = _make_parser(tmp_path, _cgeo_gpx())
        cache = parser.parse()[0]
        assert cache["difficulty"] == "2.5"
        assert cache["terrain"] == "3.0"

    def test_parse_extracts_owner_country_state(self, tmp_path):
        parser = _make_parser(tmp_path, _cgeo_gpx())
        cache = parser.parse()[0]
        assert cache["owner"] == "TestUser"
        assert cache["country"] == "France"
        assert cache["state"] == "Ile-de-France"

    def test_parse_extracts_gsak_fields(self, tmp_path):
        parser = _make_parser(tmp_path, _cgeo_gpx())
        cache = parser.parse()[0]
        assert cache["favorites"] == 10
        assert cache["notes"] == "My note"
        assert cache["found_date"] == "2024-06-01"

    def test_parse_extracts_attributes(self, tmp_path):
        parser = _make_parser(tmp_path, _cgeo_gpx())
        cache = parser.parse()[0]
        attrs = cache["attributes"]
        assert len(attrs) == 2
        assert attrs[0] == {"id": 7, "is_positive": True, "name": "Dogs"}
        assert attrs[1] == {"id": 8, "is_positive": False, "name": "Bikes"}

    def test_parse_skips_wpt_without_cache_elem(self, tmp_path):
        wpt_no_cache = """\
  <wpt lat="48.0" lon="2.0">
    <name>GC99999</name>
  </wpt>"""
        parser = _make_parser(tmp_path, _cgeo_gpx(wpt_no_cache))
        caches = parser.parse()
        assert caches == []

    def test_parse_empty_gpx_returns_empty(self, tmp_path):
        empty = _cgeo_gpx("")
        parser = _make_parser(tmp_path, empty)
        assert parser.parse() == []

    def test_get_caches_returns_same_as_parse(self, tmp_path):
        parser = _make_parser(tmp_path, _cgeo_gpx())
        caches = parser.parse()
        assert parser.get_caches() is caches


# ---------------------------------------------------------------------------
# parse() — pocket_query format
# ---------------------------------------------------------------------------


class TestParsePocketQuery:
    _PQ_WPT_SINGLE_LOG = """\
  <wpt lat="51.5074" lon="-0.1278">
    <name>GC67890</name>
    <desc>London Cache</desc>
    <time>2019-01-01T00:00:00Z</time>
    <groundspeak:cache>
      <groundspeak:type>Traditional Cache</groundspeak:type>
      <groundspeak:container>Small</groundspeak:container>
      <groundspeak:owner>PQUser</groundspeak:owner>
      <groundspeak:difficulty>1.5</groundspeak:difficulty>
      <groundspeak:terrain>2.0</groundspeak:terrain>
      <groundspeak:long_description>A fine cache</groundspeak:long_description>
      <groundspeak:logs>
        <groundspeak:log>
          <groundspeak:type>Found it</groundspeak:type>
          <groundspeak:date>2024-05-20</groundspeak:date>
        </groundspeak:log>
      </groundspeak:logs>
    </groundspeak:cache>
  </wpt>"""

    _PQ_WPT_MULTI_LOG = """\
  <wpt lat="51.5074" lon="-0.1278">
    <name>GC11111</name>
    <desc>Multi Log Cache</desc>
    <time>2019-01-01T00:00:00Z</time>
    <groundspeak:cache>
      <groundspeak:type>Traditional Cache</groundspeak:type>
      <groundspeak:container>Regular</groundspeak:container>
      <groundspeak:owner>Owner</groundspeak:owner>
      <groundspeak:difficulty>2.0</groundspeak:difficulty>
      <groundspeak:terrain>2.0</groundspeak:terrain>
      <groundspeak:long_description></groundspeak:long_description>
      <groundspeak:logs>
        <groundspeak:log>
          <groundspeak:type>Write note</groundspeak:type>
          <groundspeak:date>2024-01-01</groundspeak:date>
        </groundspeak:log>
        <groundspeak:log>
          <groundspeak:type>Found it</groundspeak:type>
          <groundspeak:date>2024-05-20</groundspeak:date>
        </groundspeak:log>
      </groundspeak:logs>
    </groundspeak:cache>
  </wpt>"""

    _PQ_WPT_NO_LOGS = """\
  <wpt lat="51.0" lon="0.0">
    <name>GC22222</name>
    <desc>No Logs</desc>
    <time>2019-01-01T00:00:00Z</time>
    <groundspeak:cache>
      <groundspeak:type>Traditional Cache</groundspeak:type>
      <groundspeak:container>Regular</groundspeak:container>
      <groundspeak:long_description></groundspeak:long_description>
    </groundspeak:cache>
  </wpt>"""

    def test_parse_single_log_extracts_found_date(self, tmp_path):
        parser = _make_parser(tmp_path, _pq_gpx(self._PQ_WPT_SINGLE_LOG))
        cache = parser.parse()[0]
        # Single log in pocket_query → date used directly
        assert cache["found_date"] is not None
        assert "2024-05-20" in cache["found_date"]

    def test_parse_multi_log_finds_found_it(self, tmp_path):
        parser = _make_parser(tmp_path, _pq_gpx(self._PQ_WPT_MULTI_LOG))
        cache = parser.parse()[0]
        assert cache["found_date"] == "2024-05-20"

    def test_parse_no_logs_found_date_is_none(self, tmp_path):
        parser = _make_parser(tmp_path, _pq_gpx(self._PQ_WPT_NO_LOGS))
        cache = parser.parse()[0]
        assert cache["found_date"] is None

    def test_parse_pq_favorites_defaults_zero(self, tmp_path):
        parser = _make_parser(tmp_path, _pq_gpx(self._PQ_WPT_NO_LOGS))
        cache = parser.parse()[0]
        assert cache["favorites"] == 0
        assert cache["notes"] is None


# ---------------------------------------------------------------------------
# _get_namespaces_for_format — unknown branch
# ---------------------------------------------------------------------------


class TestGetNamespacesForFormat:
    def test_unknown_format_returns_cgeo_defaults(self, tmp_path):
        parser = _make_parser(tmp_path, _cgeo_gpx(), fmt="cgeo")
        ns = parser._get_namespaces_for_format("totally_unknown")
        assert "gpx" in ns
        assert "groundspeak" in ns
        assert "gsak" in ns


# ---------------------------------------------------------------------------
# _detect_format — nsmap fallback paths
# ---------------------------------------------------------------------------


class TestDetectFormatViaNamespace:
    def test_detects_cgeo_via_nsmap_101(self, tmp_path):
        """creator neutral, but groundspeak namespace contains '1/0/1' → cgeo."""
        content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<gpx version="1.0" creator="some_unknown_app"\n'
            '  xmlns="http://www.topografix.com/GPX/1/0"\n'
            '  xmlns:groundspeak="http://www.groundspeak.com/cache/1/0/1">\n'
            "</gpx>"
        )
        parser = _make_parser(tmp_path, content)
        assert parser.format_type == "cgeo"

    def test_detects_pq_via_nsmap_10(self, tmp_path):
        """creator neutral, groundspeak namespace contains '1/0' (not '1/0/1') → pocket_query."""
        content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<gpx version="1.0" creator="some_other_app"\n'
            '  xmlns="http://www.topografix.com/GPX/1/0"\n'
            '  xmlns:groundspeak="http://www.groundspeak.com/cache/1/0">\n'
            "</gpx>"
        )
        parser = _make_parser(tmp_path, content)
        assert parser.format_type == "pocket_query"

    def test_detects_cgeo_via_text_content(self, tmp_path):
        """No creator/schema/nsmap hint, but body text contains 'c:geo'."""
        content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<gpx version="1.0" creator="mystery_app"\n'
            '  xmlns="http://www.topografix.com/GPX/1/0">\n'
            "  <!-- exported by c:geo -->\n"
            "</gpx>"
        )
        parser = _make_parser(tmp_path, content)
        assert parser.format_type == "cgeo"

    def test_detect_format_error_falls_back_to_cgeo(self, tmp_path):
        """Non-parseable file → exception caught → default 'cgeo'."""
        gpx_file = tmp_path / "bad.gpx"
        gpx_file.write_bytes(b"this is not xml at all <<<")
        parser = MultiFormatGPXParser(gpx_file, format_type="auto")
        assert parser.format_type == "cgeo"


# ---------------------------------------------------------------------------
# find_text_deep — not-found path
# ---------------------------------------------------------------------------


class TestFindTextDeep:
    def test_returns_empty_when_element_absent(self, tmp_path):
        parser = _make_parser(tmp_path, _cgeo_gpx(), fmt="cgeo")
        tree = etree.parse(str(tmp_path / "test.gpx"))
        root = tree.getroot()
        # Tag that does not exist in the root element
        result = parser.find_text_deep(root, "gpx:nonexistent_tag")
        assert result == ""

    def test_returns_empty_when_text_is_none(self, tmp_path):
        parser = _make_parser(tmp_path, _cgeo_gpx(), fmt="cgeo")
        tree = etree.parse(str(tmp_path / "test.gpx"))
        root = tree.getroot()
        # <groundspeak:long_description></groundspeak:long_description> exists with None text
        result = parser.find_text_deep(root, "groundspeak:long_description")
        assert result == ""
