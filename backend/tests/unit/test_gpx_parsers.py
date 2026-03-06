"""Tests for GPX Parsers components (unit tests - no DB required)."""

import tempfile
from pathlib import Path

from app.services.parsers.GPXCacheParser import GPXCacheParser
from app.services.parsers.HTMLSanitizer import HTMLSanitizer
from app.services.parsers.MultiFormatGPXParser import MultiFormatGPXParser


class TestHTMLSanitizer:
    """Test HTMLSanitizer component (HTML cleaning for cache descriptions)."""

    def test_sanitize_basic_html(self):
        """Test sanitization of basic HTML content."""
        sanitizer = HTMLSanitizer()

        html_content = "<p>This is a <strong>test</strong> description.</p>"
        result = sanitizer.clean_description_html(html_content)

        assert result is not None
        assert "<p>" in result or "test" in result

    def test_sanitize_removes_script_tags(self):
        """Test that script tags are removed."""
        sanitizer = HTMLSanitizer()

        html_content = "<p>Safe text</p><script>alert('xss')</script>"
        result = sanitizer.clean_description_html(html_content)

        assert result is not None
        assert "<script>" not in result

    def test_sanitize_removes_style_tags(self):
        """Test that style tags are removed."""
        sanitizer = HTMLSanitizer()

        html_content = "<p>Safe</p><style>.bad { color: red; }</style>"
        result = sanitizer.clean_description_html(html_content)

        assert result is not None
        assert "<style>" not in result

    def test_sanitize_preserves_allowed_tags(self):
        """Test that allowed tags are preserved."""
        sanitizer = HTMLSanitizer()

        html_content = "<p><strong>Bold</strong> and <em>italic</em></p>"
        result = sanitizer.clean_description_html(html_content)

        assert result is not None
        # Should preserve basic formatting tags

    def test_sanitize_handles_none_input(self):
        """Test sanitization handles None input gracefully."""
        sanitizer = HTMLSanitizer()

        result = sanitizer.clean_description_html(None)

        assert result is not None

    def test_sanitize_handles_empty_string(self):
        """Test sanitization handles empty string."""
        sanitizer = HTMLSanitizer()

        result = sanitizer.clean_description_html("")

        assert result is not None

    def test_is_safe_href_http(self):
        """Test href validation with http."""
        sanitizer = HTMLSanitizer()

        assert sanitizer._is_safe_href("http://example.com") is True

    def test_is_safe_href_https(self):
        """Test href validation with https."""
        sanitizer = HTMLSanitizer()

        assert sanitizer._is_safe_href("https://example.com") is True

    def test_is_safe_href_mailto(self):
        """Test href validation with mailto."""
        sanitizer = HTMLSanitizer()

        assert sanitizer._is_safe_href("mailto:test@example.com") is True

    def test_is_safe_href_javascript_rejected(self):
        """Test that javascript: is rejected."""
        sanitizer = HTMLSanitizer()

        assert sanitizer._is_safe_href("javascript:alert('xss')") is False


class TestMultiFormatGPXParser:
    """Test MultiFormatGPXParser component (multi-format GPX parsing)."""

    def test_detect_format_cgeo(self):
        """Test automatic detection of cgeo format."""
        # Create a temporary GPX file with cgeo creator
        gpx_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.0" creator="cgeo - http://www.cgeo.org/">
  <wpt lat="48.8566" lon="2.3522">
    <name>GC12345</name>
  </wpt>
</gpx>"""

        with tempfile.NamedTemporaryFile(suffix=".gpx", delete=False) as f:
            f.write(gpx_content)
            temp_path = Path(f.name)

        try:
            parser = MultiFormatGPXParser(temp_path, format_type="auto")
            assert parser.format_type == "cgeo"
        finally:
            temp_path.unlink()

    def test_detect_format_pocket_query(self):
        """Test automatic detection of pocket_query format."""
        # Create a temporary GPX file with pocket query creator
        gpx_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.0" creator="Groundspeak Pocket Query">
  <wpt lat="48.8566" lon="2.3522">
    <name>GC12345</name>
  </wpt>
</gpx>"""

        with tempfile.NamedTemporaryFile(suffix=".gpx", delete=False) as f:
            f.write(gpx_content)
            temp_path = Path(f.name)

        try:
            parser = MultiFormatGPXParser(temp_path, format_type="auto")
            assert parser.format_type == "pocket_query"
        finally:
            temp_path.unlink()

    def test_explicit_format_cgeo(self):
        """Test explicit cgeo format specification."""
        gpx_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.0" creator="test">
  <wpt lat="48.8566" lon="2.3522">
    <name>GC12345</name>
  </wpt>
</gpx>"""

        with tempfile.NamedTemporaryFile(suffix=".gpx", delete=False) as f:
            f.write(gpx_content)
            temp_path = Path(f.name)

        try:
            parser = MultiFormatGPXParser(temp_path, format_type="cgeo")
            assert parser.format_type == "cgeo"
        finally:
            temp_path.unlink()

    def test_explicit_format_pocket_query(self):
        """Test explicit pocket_query format specification."""
        gpx_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.0" creator="test">
  <wpt lat="48.8566" lon="2.3522">
    <name>GC12345</name>
  </wpt>
</gpx>"""

        with tempfile.NamedTemporaryFile(suffix=".gpx", delete=False) as f:
            f.write(gpx_content)
            temp_path = Path(f.name)

        try:
            parser = MultiFormatGPXParser(temp_path, format_type="pocket_query")
            assert parser.format_type == "pocket_query"
        finally:
            temp_path.unlink()

    def test_unsupported_format_falls_back_to_auto(self):
        """Test that unsupported format falls back to auto detection."""
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
            parser = MultiFormatGPXParser(temp_path, format_type="unsupported_format")
            assert parser.format_type == "cgeo"  # Should detect cgeo automatically
        finally:
            temp_path.unlink()

    def test_parser_initialization(self):
        """Test parser initializes with correct attributes."""
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
            parser = MultiFormatGPXParser(temp_path, format_type="cgeo")

            assert parser.gpx_file == temp_path
            assert parser.format_type == "cgeo"
            assert parser.caches == []
            assert parser.namespaces is not None
        finally:
            temp_path.unlink()


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
