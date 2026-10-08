"""Tests for GPXCacheParser, including its utility methods (unit tests - no DB required)."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from lxml import etree

from app.services.parsers.GPXCacheParser import GPXCacheParser


class TestGPXCacheParser:
    """Test GPXCacheParser component (single-format GPX parsing)."""

    def test_parser_initialization(self):
        """Test GPXCacheParser initializes correctly."""
        gpx_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.0" creator="cgeo">
  <wpt lat="48.8566" lon="2.3522">
    <name>GC12345</name>
  </wpt>
</gpx>"""

        with tempfile.NamedTemporaryFile(suffix=".gpx", delete=False) as f:
            f.write(gpx_content)
            temp_path = Path(f.name)

        try:
            parser = GPXCacheParser(temp_path)

            assert parser.gpx_file == temp_path
            assert parser.caches == []
            assert parser.namespaces is not None
            assert "gpx" in parser.namespaces
            assert "groundspeak" in parser.namespaces
        finally:
            temp_path.unlink()

    def test_parse_basic_gpx(self):
        """Test parsing of basic GPX file."""
        gpx_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.0" creator="cgeo" xmlns="http://www.topografix.com/GPX/1/0" xmlns:groundspeak="http://www.groundspeak.com/cache/1/0/1">
  <wpt lat="48.8566" lon="2.3522">
    <name>GC12345</name>
    <desc>Test Cache</desc>
    <groundspeak:cache id="12345" available="True" archived="False">
      <groundspeak:name>Test Cache</groundspeak:name>
      <groundspeak:type>Traditional Cache</groundspeak:type>
      <groundspeak:container>Regular</groundspeak:container>
      <groundspeak:owner>TestOwner</groundspeak:owner>
      <groundspeak:difficulty>2.5</groundspeak:difficulty>
      <groundspeak:terrain>3.0</groundspeak:terrain>
      <groundspeak:country>France</groundspeak:country>
      <groundspeak:state>Ile-de-France</groundspeak:state>
      <groundspeak:long_description html="True">Test description</groundspeak:long_description>
    </groundspeak:cache>
  </wpt>
</gpx>"""

        with tempfile.NamedTemporaryFile(suffix=".gpx", delete=False) as f:
            f.write(gpx_content)
            temp_path = Path(f.name)

        try:
            parser = GPXCacheParser(temp_path)
            caches = parser.parse()

            assert len(caches) >= 1
            cache = caches[0]
            assert cache["GC"] == "GC12345"
            assert cache["latitude"] == 48.8566
            assert cache["longitude"] == 2.3522
        finally:
            temp_path.unlink()

    def test_parse_gpx_with_attributes(self):
        """Test parsing GPX with cache attributes."""
        gpx_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.0" creator="cgeo" xmlns="http://www.topografix.com/GPX/1/0" xmlns:groundspeak="http://www.groundspeak.com/cache/1/0/1">
  <wpt lat="48.8566" lon="2.3522">
    <name>GC12345</name>
    <desc>Test Cache</desc>
    <groundspeak:cache id="12345" available="True" archived="False">
      <groundspeak:name>Test Cache</groundspeak:name>
      <groundspeak:type>Traditional Cache</groundspeak:type>
      <groundspeak:container>Regular</groundspeak:container>
      <groundspeak:owner>TestOwner</groundspeak:owner>
      <groundspeak:difficulty>2.5</groundspeak:difficulty>
      <groundspeak:terrain>3.0</groundspeak:terrain>
      <groundspeak:country>France</groundspeak:country>
      <groundspeak:state>Ile-de-France</groundspeak:state>
      <groundspeak:long_description html="True">Test description</groundspeak:long_description>
      <groundspeak:attributes>
        <groundspeak:attribute id="1" inc="1">Dogs allowed</groundspeak:attribute>
        <groundspeak:attribute id="8" inc="1">Scenic view</groundspeak:attribute>
      </groundspeak:attributes>
    </groundspeak:cache>
  </wpt>
</gpx>"""

        with tempfile.NamedTemporaryFile(suffix=".gpx", delete=False) as f:
            f.write(gpx_content)
            temp_path = Path(f.name)

        try:
            parser = GPXCacheParser(temp_path)
            caches = parser.parse()

            assert len(caches) >= 1
            cache = caches[0]
            assert "attributes" in cache
            assert len(cache["attributes"]) >= 2
        finally:
            temp_path.unlink()

    def test_parse_gpx_multiple_waypoints(self):
        """Test parsing GPX with multiple cache waypoints."""
        gpx_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.0" creator="cgeo" xmlns="http://www.topografix.com/GPX/1/0" xmlns:groundspeak="http://www.groundspeak.com/cache/1/0/1">
  <wpt lat="48.8566" lon="2.3522">
    <name>GC12345</name>
    <desc>Cache 1</desc>
    <groundspeak:cache id="12345" available="True" archived="False">
      <groundspeak:name>Cache 1</groundspeak:name>
      <groundspeak:type>Traditional Cache</groundspeak:type>
      <groundspeak:container>Regular</groundspeak:container>
      <groundspeak:owner>Owner1</groundspeak:owner>
      <groundspeak:difficulty>2.0</groundspeak:difficulty>
      <groundspeak:terrain>2.0</groundspeak:terrain>
      <groundspeak:country>France</groundspeak:country>
      <groundspeak:long_description html="True">Desc 1</groundspeak:long_description>
    </groundspeak:cache>
  </wpt>
  <wpt lat="48.8600" lon="2.3600">
    <name>GC12346</name>
    <desc>Cache 2</desc>
    <groundspeak:cache id="12346" available="True" archived="False">
      <groundspeak:name>Cache 2</groundspeak:name>
      <groundspeak:type>Multi-cache Cache</groundspeak:type>
      <groundspeak:container>Small</groundspeak:container>
      <groundspeak:owner>Owner2</groundspeak:owner>
      <groundspeak:difficulty>3.0</groundspeak:difficulty>
      <groundspeak:terrain>3.0</groundspeak:terrain>
      <groundspeak:country>France</groundspeak:country>
      <groundspeak:long_description html="True">Desc 2</groundspeak:long_description>
    </groundspeak:cache>
  </wpt>
</gpx>"""

        with tempfile.NamedTemporaryFile(suffix=".gpx", delete=False) as f:
            f.write(gpx_content)
            temp_path = Path(f.name)

        try:
            parser = GPXCacheParser(temp_path)
            caches = parser.parse()

            assert len(caches) >= 2
            assert caches[0]["GC"] == "GC12345"
            assert caches[1]["GC"] == "GC12346"
        finally:
            temp_path.unlink()

    def test_parse_gpx_with_favorites(self):
        """Test parsing GPX with GSAK favorites."""
        gpx_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.0" creator="cgeo" xmlns="http://www.topografix.com/GPX/1/0" xmlns:groundspeak="http://www.groundspeak.com/cache/1/0/1" xmlns:gsak="http://www.gsak.net/xmlv1/6">
  <wpt lat="48.8566" lon="2.3522">
    <name>GC12345</name>
    <desc>Test Cache</desc>
    <groundspeak:cache id="12345" available="True" archived="False">
      <groundspeak:name>Test Cache</groundspeak:name>
      <groundspeak:type>Traditional Cache</groundspeak:type>
      <groundspeak:container>Regular</groundspeak:container>
      <groundspeak:owner>TestOwner</groundspeak:owner>
      <groundspeak:difficulty>2.5</groundspeak:difficulty>
      <groundspeak:terrain>3.0</groundspeak:terrain>
      <groundspeak:country>France</groundspeak:country>
      <groundspeak:long_description html="True">Test description</groundspeak:long_description>
    </groundspeak:cache>
    <gsak:FavPoints>42</gsak:FavPoints>
  </wpt>
</gpx>"""

        with tempfile.NamedTemporaryFile(suffix=".gpx", delete=False) as f:
            f.write(gpx_content)
            temp_path = Path(f.name)

        try:
            parser = GPXCacheParser(temp_path)
            caches = parser.parse()

            assert len(caches) >= 1
            cache = caches[0]
            assert cache.get("favorites") == 42
        finally:
            temp_path.unlink()


class TestGPXCacheParserUtilityMethods:
    """Unit tests for GPXCacheParser internal helpers."""

    def _make_parser(self, tmp_path):
        """Create a GPXCacheParser with a dummy path (no real file needed for helpers)."""
        dummy = tmp_path / "dummy.gpx"
        dummy.write_bytes(b"<gpx/>")
        return GPXCacheParser(dummy)

    def test_parse_raises_when_xpath_not_list(self, tmp_path):
        """Line 70: raise ValueError when XPath does not return a list."""
        dummy = tmp_path / "dummy.gpx"
        dummy.write_bytes(b"<gpx/>")
        parser = GPXCacheParser(dummy)

        mock_tree = MagicMock()
        mock_tree.xpath.return_value = "not-a-list"
        with patch("app.services.parsers.GPXCacheParser.etree") as mock_etree:
            mock_etree.parse.return_value = mock_tree
            with pytest.raises(ValueError, match="XPath"):
                parser.parse()

    def test_parse_skips_wpt_without_cache_element(self, tmp_path):
        """Line 75: wpt without groundspeak:cache is skipped (continue)."""
        gpx = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.0" xmlns="http://www.topografix.com/GPX/1/0">
  <wpt lat="48.0" lon="2.0">
    <name>GCTEST</name>
  </wpt>
</gpx>"""
        gpx_file = tmp_path / "test.gpx"
        gpx_file.write_bytes(gpx)
        parser = GPXCacheParser(gpx_file)
        caches = parser.parse()
        assert caches == []

    def test_has_corrected_coordinates_false(self, tmp_path):
        """Line 145: returns False when no gsak:corrected element."""
        parser = self._make_parser(tmp_path)
        wpt = etree.fromstring('<wpt xmlns:gsak="http://www.gsak.net/xmlv1/6" lat="0" lon="0"/>')
        assert parser._has_corrected_coordinates(wpt) is False

    def test_has_corrected_coordinates_true(self, tmp_path):
        """Line 145: returns True when gsak:corrected element is present."""
        parser = self._make_parser(tmp_path)
        wpt = etree.fromstring(
            '<wpt xmlns:gsak="http://www.gsak.net/xmlv1/6" lat="0" lon="0"><gsak:corrected/></wpt>'
        )
        assert parser._has_corrected_coordinates(wpt) is True

    def test_has_found_log_false(self, tmp_path):
        """Lines 159-163: returns False when no Found-it log."""
        parser = self._make_parser(tmp_path)
        cache_elem = etree.fromstring(
            '<cache xmlns:groundspeak="http://www.groundspeak.com/cache/1/0/1">'
            "<groundspeak:logs>"
            "<groundspeak:log><groundspeak:type>Didn't find it</groundspeak:type></groundspeak:log>"
            "</groundspeak:logs>"
            "</cache>"
        )
        assert parser._has_found_log(cache_elem) is False

    def test_has_found_log_true(self, tmp_path):
        """Lines 159-163: returns True when a Found-it log is present."""
        parser = self._make_parser(tmp_path)
        cache_elem = etree.fromstring(
            '<cache xmlns:groundspeak="http://www.groundspeak.com/cache/1/0/1">'
            "<groundspeak:logs>"
            "<groundspeak:log><groundspeak:type>Found it</groundspeak:type></groundspeak:log>"
            "</groundspeak:logs>"
            "</cache>"
        )
        assert parser._has_found_log(cache_elem) is True

    def test_was_found_false(self, tmp_path):
        """Line 178: returns False when no gsak:userfound element."""
        parser = self._make_parser(tmp_path)
        wpt = etree.fromstring('<wpt xmlns:gsak="http://www.gsak.net/xmlv1/6" lat="0" lon="0"/>')
        assert parser._was_found(wpt) is False

    def test_was_found_true(self, tmp_path):
        """Line 178: returns True when gsak:userfound element is present."""
        parser = self._make_parser(tmp_path)
        wpt = etree.fromstring(
            '<wpt xmlns:gsak="http://www.gsak.net/xmlv1/6" lat="0" lon="0">'
            "<gsak:userfound>2024-01-01</gsak:userfound>"
            "</wpt>"
        )
        assert parser._was_found(wpt) is True

    def test_text_returns_stripped_text(self, tmp_path):
        """Line 205: _text returns stripped text."""
        parser = self._make_parser(tmp_path)
        elem = etree.fromstring("<item>  hello  </item>")
        assert parser._text(elem) == "hello"

    def test_text_returns_default_for_none(self, tmp_path):
        """Line 205: _text returns default when element is None."""
        parser = self._make_parser(tmp_path)
        assert parser._text(None, default="fallback") == "fallback"

    def test_text_returns_default_for_empty_text(self, tmp_path):
        """Line 205: _text returns default when text is empty/None."""
        parser = self._make_parser(tmp_path)
        elem = etree.fromstring("<item/>")
        assert parser._text(elem, default="x") == "x"

    def test_html_returns_unescaped_text(self, tmp_path):
        """Line 220: _html returns unescaped HTML."""
        parser = self._make_parser(tmp_path)
        elem = etree.fromstring("<item>&lt;p&gt;hello&lt;/p&gt;</item>")
        assert parser._html(elem) == "<p>hello</p>"

    def test_html_returns_empty_for_none(self, tmp_path):
        """Line 220: _html returns empty string when element is None."""
        parser = self._make_parser(tmp_path)
        assert parser._html(None) == ""

    def test_get_caches_returns_list(self, tmp_path):
        """Line 231: get_caches returns self.caches."""
        parser = self._make_parser(tmp_path)
        assert parser.get_caches() == []
        parser.caches = [{"GC": "GC1"}]
        assert parser.get_caches() == [{"GC": "GC1"}]
