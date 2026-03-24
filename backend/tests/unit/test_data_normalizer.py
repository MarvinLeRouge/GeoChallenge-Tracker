"""Tests for DataNormalizer (unit — pure static methods)."""

from __future__ import annotations

import datetime as dt

import pytest

from app.services.gpx_import.data_normalizer import DataNormalizer

N = DataNormalizer


# ---------------------------------------------------------------------------
# parse_datetime_iso8601 — fallback / edge paths not yet covered
# ---------------------------------------------------------------------------


class TestParseDatetimeIso8601Extra:
    def test_with_space_separator(self):
        result = N.parse_datetime_iso8601("2024-01-15 14:30:45")
        assert result == dt.datetime(2024, 1, 15, 14, 30, 45)

    def test_date_only(self):
        result = N.parse_datetime_iso8601("2024-01-15")
        assert result == dt.datetime(2024, 1, 15, 0, 0, 0)

    def test_with_microseconds_no_z(self):
        result = N.parse_datetime_iso8601("2024-01-15T14:30:45.123")
        assert result is not None
        assert result.year == 2024

    def test_totally_invalid_string(self):
        N.parse_datetime_iso8601("not-a-date")
        # Either None or a parsed value — depends on dateutil availability.
        # We just assert no exception is raised.

    def test_empty_string(self):
        assert N.parse_datetime_iso8601("") is None

    def test_none_input(self):
        assert N.parse_datetime_iso8601(None) is None

    def test_non_standard_with_dot_and_z(self):
        # Seven-digit fractional seconds: won't match strptime %f (max 6 digits)
        # Falls through to the fallback branch (line 73)
        result = N.parse_datetime_iso8601("2024-01-15T14:30:45.1234567Z")
        # dateutil may or may not be installed; either None or a valid datetime
        assert result is None or isinstance(result, dt.datetime)


# ---------------------------------------------------------------------------
# normalize_coordinates
# ---------------------------------------------------------------------------


class TestNormalizeCoordinates:
    def test_valid_floats(self):
        lat, lon = N.normalize_coordinates(48.8566, 2.3522)
        assert lat == pytest.approx(48.8566)
        assert lon == pytest.approx(2.3522)

    def test_valid_strings(self):
        lat, lon = N.normalize_coordinates("48.8566", "2.3522")
        assert lat == pytest.approx(48.8566)
        assert lon == pytest.approx(2.3522)

    def test_none_lat(self):
        assert N.normalize_coordinates(None, 2.3522) == (None, None)

    def test_none_lon(self):
        assert N.normalize_coordinates(48.8566, None) == (None, None)

    def test_lat_out_of_range(self):
        assert N.normalize_coordinates(91.0, 2.3522) == (None, None)

    def test_lon_out_of_range(self):
        assert N.normalize_coordinates(48.8566, 181.0) == (None, None)

    def test_negative_valid(self):
        lat, lon = N.normalize_coordinates(-33.86, -70.67)
        assert lat == pytest.approx(-33.86)
        assert lon == pytest.approx(-70.67)

    def test_boundary_values(self):
        assert N.normalize_coordinates(90.0, 180.0) == (pytest.approx(90.0), pytest.approx(180.0))
        assert N.normalize_coordinates(-90.0, -180.0) == (
            pytest.approx(-90.0),
            pytest.approx(-180.0),
        )

    def test_invalid_string(self):
        assert N.normalize_coordinates("not-a-number", 2.3522) == (None, None)


# ---------------------------------------------------------------------------
# normalize_difficulty_terrain
# ---------------------------------------------------------------------------


class TestNormalizeDifficultyTerrain:
    def test_valid_float(self):
        assert N.normalize_difficulty_terrain(2.5) == 2.5

    def test_valid_string(self):
        assert N.normalize_difficulty_terrain("3.0") == 3.0

    def test_rounds_to_half(self):
        assert N.normalize_difficulty_terrain(2.3) == 2.5
        assert N.normalize_difficulty_terrain(2.2) == 2.0

    def test_none_returns_none(self):
        assert N.normalize_difficulty_terrain(None) is None

    def test_below_range(self):
        assert N.normalize_difficulty_terrain(0.5) is None

    def test_above_range(self):
        assert N.normalize_difficulty_terrain(5.5) is None

    def test_boundary_1(self):
        assert N.normalize_difficulty_terrain(1.0) == 1.0

    def test_boundary_5(self):
        assert N.normalize_difficulty_terrain(5.0) == 5.0

    def test_invalid_string(self):
        assert N.normalize_difficulty_terrain("bad") is None


# ---------------------------------------------------------------------------
# normalize_gc_code
# ---------------------------------------------------------------------------


class TestNormalizeGcCode:
    def test_valid_gc_code(self):
        assert N.normalize_gc_code("GC12345") == "GC12345"

    def test_lowercase_normalized(self):
        assert N.normalize_gc_code("gc12345") == "GC12345"

    def test_with_leading_spaces(self):
        assert N.normalize_gc_code("  GC12345  ") == "GC12345"

    def test_invalid_prefix(self):
        assert N.normalize_gc_code("TB12345") is None

    def test_empty_string(self):
        assert N.normalize_gc_code("") is None

    def test_none(self):
        assert N.normalize_gc_code(None) is None

    def test_with_special_chars(self):
        assert N.normalize_gc_code("GC!#@$") is None

    def test_alphanumeric_code(self):
        assert N.normalize_gc_code("GCABCDE") == "GCABCDE"


# ---------------------------------------------------------------------------
# is_valid_for_import_mode
# ---------------------------------------------------------------------------


class TestIsValidForImportMode:
    def test_both_mode_always_valid(self):
        assert N.is_valid_for_import_mode({}, "both") is True

    def test_all_mode_always_valid(self):
        assert N.is_valid_for_import_mode({}, "all") is True

    def test_found_mode_with_date(self):
        assert N.is_valid_for_import_mode({"found_date": "2024-01-01"}, "found") is True

    def test_found_mode_without_date(self):
        assert N.is_valid_for_import_mode({}, "found") is False

    def test_unknown_mode_returns_false(self):
        assert N.is_valid_for_import_mode({}, "caches") is False


# ---------------------------------------------------------------------------
# clean_html_content
# ---------------------------------------------------------------------------


class TestCleanHtmlContent:
    def test_strips_html_tags(self):
        result = N.clean_html_content("<p>Hello <b>World</b></p>")
        assert result == "Hello World"

    def test_none_returns_none(self):
        assert N.clean_html_content(None) is None

    def test_empty_returns_none(self):
        assert N.clean_html_content("") is None

    def test_only_tags_returns_none(self):
        assert N.clean_html_content("<br/><hr/>") is None

    def test_plain_text_unchanged(self):
        assert N.clean_html_content("plain text") == "plain text"

    def test_strips_surrounding_whitespace(self):
        result = N.clean_html_content("  <p>  text  </p>  ")
        assert result == "text"


# ---------------------------------------------------------------------------
# extract_cache_metadata
# ---------------------------------------------------------------------------


class TestExtractCacheMetadata:
    def _full_raw(self) -> dict:
        return {
            "gc_code": "GC12345",
            "title": "Test Cache",
            "description": "<p>desc</p>",
            "url": "https://example.com",
            "latitude": 48.8566,
            "longitude": 2.3522,
            "difficulty": "2.5",
            "terrain": "3.0",
            "placed_date": "2020-06-15T00:00:00Z",
            "owner": "TestUser",
            "favorites": "10",
            "status": "active",
            "attributes": [1, 2, 3],
        }

    def test_full_extraction(self):
        result = N.extract_cache_metadata(self._full_raw())
        assert result["GC"] == "GC12345"
        assert result["title"] == "Test Cache"
        assert result["lat"] == pytest.approx(48.8566)
        assert result["lon"] == pytest.approx(2.3522)
        assert result["difficulty"] == 2.5
        assert result["terrain"] == 3.0
        assert result["owner"] == "TestUser"
        assert result["favorites"] == 10
        assert result["status"] == "active"
        assert result["attributes"] == [1, 2, 3]
        assert result["loc"] == {"type": "Point", "coordinates": [2.3522, 48.8566]}

    def test_invalid_gc_code_omitted(self):
        raw = self._full_raw()
        raw["gc_code"] = "INVALID"
        result = N.extract_cache_metadata(raw)
        assert "GC" not in result

    def test_invalid_coordinates_omitted(self):
        raw = self._full_raw()
        raw["latitude"] = 999
        result = N.extract_cache_metadata(raw)
        assert "lat" not in result
        assert "lon" not in result
        assert "loc" not in result

    def test_invalid_difficulty_omitted(self):
        raw = self._full_raw()
        raw["difficulty"] = "99.0"
        result = N.extract_cache_metadata(raw)
        assert "difficulty" not in result

    def test_invalid_favorites_omitted(self):
        raw = self._full_raw()
        raw["favorites"] = "not-a-number"
        result = N.extract_cache_metadata(raw)
        assert "favorites" not in result

    def test_unknown_status_omitted(self):
        raw = self._full_raw()
        raw["status"] = "unknown"
        result = N.extract_cache_metadata(raw)
        assert "status" not in result

    def test_missing_optional_fields(self):
        result = N.extract_cache_metadata({"gc_code": "GC99999"})
        assert result["GC"] == "GC99999"
        assert "title" not in result
        assert "lat" not in result

    def test_no_description_omitted(self):
        raw = self._full_raw()
        raw["description"] = ""
        result = N.extract_cache_metadata(raw)
        assert "description_html" not in result


# ---------------------------------------------------------------------------
# extract_found_metadata
# ---------------------------------------------------------------------------


class TestExtractFoundMetadata:
    def test_valid_with_notes(self):
        raw = {
            "found_date": "2024-06-01T12:00:00Z",
            "notes": "<p>Great cache!</p>",
        }
        result = N.extract_found_metadata(raw)
        assert result is not None
        assert isinstance(result["found_date"], dt.datetime)
        assert result["notes"] == "Great cache!"

    def test_valid_without_notes(self):
        raw = {"found_date": "2024-06-01T12:00:00Z"}
        result = N.extract_found_metadata(raw)
        assert result is not None
        assert "notes" not in result

    def test_no_found_date_returns_none(self):
        assert N.extract_found_metadata({}) is None

    def test_invalid_found_date_returns_none(self):
        assert N.extract_found_metadata({"found_date": "not-a-date"}) is None

    def test_empty_notes_omitted(self):
        raw = {"found_date": "2024-06-01T12:00:00Z", "notes": ""}
        result = N.extract_found_metadata(raw)
        assert result is not None
        assert "notes" not in result
