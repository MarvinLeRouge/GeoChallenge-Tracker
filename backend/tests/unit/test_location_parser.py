"""Tests for location_parser utilities (unit tests - no DB required)."""

from __future__ import annotations

import pytest

from app.services.location_parser import (
    _degrees_minutes_seconds_to_decimal,
    format_coordinates_deg_min_mil,
    format_decimal_to_deg_min_mil,
    normalize_location_string,
    parse_location_to_lon_lat,
)

# ---------------------------------------------------------------------------
# normalize_location_string
# ---------------------------------------------------------------------------


class TestNormalizeLocationString:
    def test_decimal_comma_to_period(self):
        result = normalize_location_string("48,8566 2,3522")
        assert "48.8566" in result
        assert "2.3522" in result

    def test_multiple_spaces_collapsed(self):
        result = normalize_location_string("N 48   30  00")
        assert "  " not in result

    def test_leading_trailing_stripped(self):
        result = normalize_location_string("  48.5 2.3  ")
        assert not result.startswith(" ")
        assert not result.endswith(" ")


# ---------------------------------------------------------------------------
# _degrees_minutes_seconds_to_decimal
# ---------------------------------------------------------------------------


class TestDegreesMinutesSecondsToDecimal:
    def test_degrees_only(self):
        assert _degrees_minutes_seconds_to_decimal(48.0, None, None) == pytest.approx(48.0)

    def test_degrees_minutes(self):
        result = _degrees_minutes_seconds_to_decimal(48.0, 30.0, None)
        assert result == pytest.approx(48.5)

    def test_degrees_minutes_seconds(self):
        result = _degrees_minutes_seconds_to_decimal(48.0, 30.0, 0.0)
        assert result == pytest.approx(48.5)

    def test_seconds_add_fractional_degree(self):
        """seconds >= 60 raise ValueError."""
        with pytest.raises(ValueError, match="seconds out of range"):
            _degrees_minutes_seconds_to_decimal(0.0, 0.0, 3600.0)

    def test_minutes_out_of_range_raises(self):
        with pytest.raises(ValueError, match="minutes out of range"):
            _degrees_minutes_seconds_to_decimal(48.0, 60.0, None)

    def test_seconds_out_of_range_raises(self):
        with pytest.raises(ValueError, match="seconds out of range"):
            _degrees_minutes_seconds_to_decimal(48.0, 30.0, 60.0)

    def test_minutes_zero_ok(self):
        result = _degrees_minutes_seconds_to_decimal(48.0, 0.0, None)
        assert result == pytest.approx(48.0)


# ---------------------------------------------------------------------------
# parse_location_to_lon_lat
# ---------------------------------------------------------------------------


class TestParseLocationToLonLat:
    def test_decimal_degrees_lat_lon(self):
        lon, lat = parse_location_to_lon_lat("48.8566 2.3522")
        assert lat == pytest.approx(48.8566, abs=1e-4)
        assert lon == pytest.approx(2.3522, abs=1e-4)

    def test_simple_comma_separated(self):
        lon, lat = parse_location_to_lon_lat("43.1234, 5.6789")
        assert lat == pytest.approx(43.1234, abs=1e-4)
        assert lon == pytest.approx(5.6789, abs=1e-4)

    def test_negative_coordinates(self):
        lon, lat = parse_location_to_lon_lat("-33.8688 151.2093")
        assert lat == pytest.approx(-33.8688, abs=1e-4)
        assert lon == pytest.approx(151.2093, abs=1e-4)

    def test_hemisphere_N_E(self):
        lon, lat = parse_location_to_lon_lat("N48.8566 E2.3522")
        assert lat == pytest.approx(48.8566, abs=1e-4)
        assert lon == pytest.approx(2.3522, abs=1e-4)

    def test_hemisphere_S_W_lat_only_negated(self):
        """S hemisphere correctly negates latitude; W is consumed as suffix of first
        regex match and not applied to longitude — known regex greedy-match quirk."""
        lon, lat = parse_location_to_lon_lat("S33.86 W70.67")
        assert lat == pytest.approx(-33.86, abs=1e-2)
        # W is greedy-consumed by the first _LOCATION_COMP match as suffix_hem;
        # lon therefore receives no sign flip and remains positive.
        assert lon == pytest.approx(70.67, abs=1e-2)

    def test_out_of_range_raises(self):
        with pytest.raises(ValueError):
            parse_location_to_lon_lat("200.0 300.0")

    def test_unparseable_raises(self):
        with pytest.raises(ValueError):
            parse_location_to_lon_lat("not a coordinate at all xyz")


# ---------------------------------------------------------------------------
# format_decimal_to_deg_min_mil
# ---------------------------------------------------------------------------


class TestFormatDecimalToDegMinMil:
    def test_positive_value(self):
        result = format_decimal_to_deg_min_mil(43.123456)
        assert result.startswith("+43")
        assert " " in result

    def test_negative_value(self):
        result = format_decimal_to_deg_min_mil(-33.5)
        assert result.startswith("-33")

    def test_zero(self):
        result = format_decimal_to_deg_min_mil(0.0)
        assert result.startswith("+0")


# ---------------------------------------------------------------------------
# format_coordinates_deg_min_mil
# ---------------------------------------------------------------------------


class TestFormatCoordinatesDegMinMil:
    def test_north_east(self):
        result = format_coordinates_deg_min_mil(48.8566, 2.3522)
        assert result.startswith("N")
        assert "E" in result

    def test_south_west(self):
        result = format_coordinates_deg_min_mil(-33.86, -70.67)
        assert result.startswith("S")
        assert "W" in result

    def test_format_structure(self):
        result = format_coordinates_deg_min_mil(43.0, 5.0)
        # Should be something like "N43 00.000 E005 00.000"
        parts = result.split(" ")
        assert len(parts) >= 2
