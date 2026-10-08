"""Tests for MultiFormatGPXParser (unit tests - no DB required). See also test_multi_format_gpx_parser.py for format-detection-focused coverage."""

import tempfile
from pathlib import Path

from app.services.parsers.MultiFormatGPXParser import MultiFormatGPXParser


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
