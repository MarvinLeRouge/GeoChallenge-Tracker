"""Tests for app/services/gpx_import/cache_validator.py."""

from __future__ import annotations

import datetime as dt

import pytest

from app.services.gpx_import.cache_validator import CacheValidator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID = {
    "GC": "GC12345",
    "title": "Test Cache",
    "lat": 48.85,
    "lon": 2.35,
}


def _v(**kwargs):
    """Return a valid base dict merged with overrides."""
    return {**_VALID, **kwargs}


# ---------------------------------------------------------------------------
# validate_cache_data — GC code
# ---------------------------------------------------------------------------


class TestValidateCacheDataGcCode:
    def test_raises_when_gc_missing(self):
        v = CacheValidator()
        with pytest.raises(ValueError, match="GC code"):
            v.validate_cache_data({"title": "x", "lat": 1.0, "lon": 1.0})

    def test_raises_when_gc_invalid(self):
        v = CacheValidator()
        with pytest.raises(ValueError, match="Invalid GC code"):
            v.validate_cache_data({"GC": "INVALID", "lat": 1.0, "lon": 1.0})

    def test_gc_non_string_is_invalid(self):
        v = CacheValidator()
        with pytest.raises(ValueError):
            v.validate_cache_data({"GC": 12345, "lat": 1.0, "lon": 1.0})

    def test_valid_gc_passes(self):
        v = CacheValidator()
        result = v.validate_cache_data(_v())
        assert result["GC"] == "GC12345"


# ---------------------------------------------------------------------------
# validate_cache_data — title
# ---------------------------------------------------------------------------


class TestValidateCacheDataTitle:
    def test_missing_title_filled_in_non_strict(self):
        v = CacheValidator()
        data = _v()
        del data["title"]
        result = v.validate_cache_data(data)
        assert result["title"] == "Cache GC12345"

    def test_missing_title_raises_in_strict_mode(self):
        v = CacheValidator(strict_mode=True)
        data = _v()
        del data["title"]
        with pytest.raises(ValueError, match="title"):
            v.validate_cache_data(data)


# ---------------------------------------------------------------------------
# _validate_coordinates
# ---------------------------------------------------------------------------


class TestValidateCoordinates:
    def test_raises_when_lat_missing(self):
        v = CacheValidator()
        with pytest.raises(ValueError, match="lat/lon"):
            v.validate_cache_data({"GC": "GC12345", "title": "T", "lon": 2.35})

    def test_raises_when_lon_missing(self):
        v = CacheValidator()
        with pytest.raises(ValueError, match="lat/lon"):
            v.validate_cache_data({"GC": "GC12345", "title": "T", "lat": 48.85})

    def test_raises_when_coords_not_numbers(self):
        v = CacheValidator()
        with pytest.raises(ValueError, match="numbers"):
            v.validate_cache_data(_v(lat="not_a_number"))

    def test_raises_when_lat_out_of_range(self):
        v = CacheValidator()
        with pytest.raises(ValueError, match="latitude"):
            v.validate_cache_data(_v(lat=91.0))

    def test_raises_when_lon_out_of_range(self):
        v = CacheValidator()
        with pytest.raises(ValueError, match="longitude"):
            v.validate_cache_data(_v(lon=181.0))

    def test_zero_zero_raises_in_strict_mode(self):
        v = CacheValidator(strict_mode=True)
        with pytest.raises(ValueError, match="0,0"):
            v.validate_cache_data(_v(lat=0.0, lon=0.0))

    def test_zero_zero_removes_coords_in_non_strict(self):
        v = CacheValidator()
        result = v.validate_cache_data(_v(lat=0.0, lon=0.0))
        assert "lat" not in result
        assert "lon" not in result


# ---------------------------------------------------------------------------
# _validate_difficulty_terrain
# ---------------------------------------------------------------------------


class TestValidateDifficultyTerrain:
    def test_raises_when_not_a_number(self):
        v = CacheValidator()
        with pytest.raises(ValueError, match="number"):
            v.validate_cache_data(_v(difficulty="hard"))

    def test_raises_when_out_of_range(self):
        v = CacheValidator()
        with pytest.raises(ValueError, match="between 1.0 and 5.0"):
            v.validate_cache_data(_v(difficulty=6.0))

    def test_rounds_to_nearest_half(self):
        v = CacheValidator()
        result = v.validate_cache_data(_v(difficulty=2.3))
        assert result["difficulty"] == 2.5

    def test_none_value_is_skipped(self):
        v = CacheValidator()
        result = v.validate_cache_data(_v())
        assert "difficulty" not in result


# ---------------------------------------------------------------------------
# _validate_owner
# ---------------------------------------------------------------------------


class TestValidateOwner:
    def test_none_owner_is_skipped(self):
        v = CacheValidator()
        result = v.validate_cache_data(_v())
        assert "owner" not in result

    def test_non_string_owner_is_converted(self):
        v = CacheValidator()
        result = v.validate_cache_data(_v(owner=42))
        assert result["owner"] == "42"

    def test_blank_owner_is_removed(self):
        v = CacheValidator()
        result = v.validate_cache_data(_v(owner="   "))
        assert "owner" not in result

    def test_owner_too_long_raises(self):
        v = CacheValidator()
        with pytest.raises(ValueError, match="too long"):
            v.validate_cache_data(_v(owner="x" * 101))

    def test_valid_owner_is_stripped(self):
        v = CacheValidator()
        result = v.validate_cache_data(_v(owner="  Alice  "))
        assert result["owner"] == "Alice"


# ---------------------------------------------------------------------------
# _validate_dates
# ---------------------------------------------------------------------------


class TestValidateDates:
    def test_raises_when_placed_at_not_datetime(self):
        v = CacheValidator()
        with pytest.raises(ValueError, match="datetime"):
            v.validate_cache_data(_v(placed_at="2024-01-01"))

    def test_raises_when_placed_at_in_future(self):
        v = CacheValidator()
        future = dt.datetime.utcnow() + dt.timedelta(days=1)
        with pytest.raises(ValueError, match="future"):
            v.validate_cache_data(_v(placed_at=future))

    def test_old_date_removed_in_non_strict(self):
        v = CacheValidator()
        old = dt.datetime(1999, 1, 1)
        result = v.validate_cache_data(_v(placed_at=old))
        assert "placed_at" not in result

    def test_old_date_raises_in_strict_mode(self):
        v = CacheValidator(strict_mode=True)
        old = dt.datetime(1999, 1, 1)
        with pytest.raises(ValueError, match="too old"):
            v.validate_cache_data(_v(placed_at=old))

    def test_valid_date_passes(self):
        v = CacheValidator()
        placed = dt.datetime(2020, 6, 1)
        result = v.validate_cache_data(_v(placed_at=placed))
        assert result["placed_at"] == placed


# ---------------------------------------------------------------------------
# _validate_favorites
# ---------------------------------------------------------------------------


class TestValidateFavorites:
    def test_none_is_skipped(self):
        v = CacheValidator()
        result = v.validate_cache_data(_v())
        assert "favorites" not in result

    def test_string_int_is_coerced(self):
        v = CacheValidator()
        result = v.validate_cache_data(_v(favorites="42"))
        assert result["favorites"] == 42

    def test_invalid_string_raises(self):
        v = CacheValidator()
        with pytest.raises(ValueError, match="integer"):
            v.validate_cache_data(_v(favorites="not_a_number"))

    def test_negative_raises(self):
        v = CacheValidator()
        with pytest.raises(ValueError, match="negative"):
            v.validate_cache_data(_v(favorites=-1))

    def test_too_high_capped_in_non_strict(self):
        v = CacheValidator()
        result = v.validate_cache_data(_v(favorites=99999))
        assert result["favorites"] == 10000

    def test_too_high_raises_in_strict_mode(self):
        v = CacheValidator(strict_mode=True)
        with pytest.raises(ValueError, match="too high"):
            v.validate_cache_data(_v(favorites=99999))


# ---------------------------------------------------------------------------
# _validate_status
# ---------------------------------------------------------------------------


class TestValidateStatus:
    def test_missing_status_defaults_to_active(self):
        v = CacheValidator()
        result = v.validate_cache_data(_v())
        assert result["status"] == "active"

    def test_unknown_status_defaults_to_active(self):
        v = CacheValidator()
        result = v.validate_cache_data(_v(status="unknown_val"))
        assert result["status"] == "active"

    def test_non_string_status_is_lowercased(self):
        v = CacheValidator()
        result = v.validate_cache_data(_v(status=123))
        assert result["status"] == "active"  # "123" is not valid → defaults to active

    def test_valid_status_disabled(self):
        v = CacheValidator()
        result = v.validate_cache_data(_v(status="DISABLED"))
        assert result["status"] == "disabled"

    def test_valid_status_archived(self):
        v = CacheValidator()
        result = v.validate_cache_data(_v(status="archived"))
        assert result["status"] == "archived"


# ---------------------------------------------------------------------------
# validate_found_data
# ---------------------------------------------------------------------------


class TestValidateFoundData:
    def _found(self, **kwargs):
        base = {"found_date": dt.datetime(2024, 1, 1)}
        base.update(kwargs)
        return base

    def test_raises_when_found_date_missing(self):
        v = CacheValidator()
        with pytest.raises(ValueError, match="found_date"):
            v.validate_found_data({})

    def test_raises_when_found_date_not_datetime(self):
        v = CacheValidator()
        with pytest.raises(ValueError, match="datetime"):
            v.validate_found_data({"found_date": "2024-01-01"})

    def test_raises_when_found_date_in_future(self):
        v = CacheValidator()
        with pytest.raises(ValueError, match="future"):
            v.validate_found_data({"found_date": dt.datetime.utcnow() + dt.timedelta(days=1)})

    def test_old_found_date_ignored_in_non_strict(self):
        v = CacheValidator()
        result = v.validate_found_data({"found_date": dt.datetime(1999, 1, 1)})
        assert result["found_date"].year == 1999  # not removed, just not raised

    def test_old_found_date_raises_in_strict_mode(self):
        v = CacheValidator(strict_mode=True)
        with pytest.raises(ValueError, match="too old"):
            v.validate_found_data({"found_date": dt.datetime(1999, 1, 1)})

    def test_notes_none_is_kept(self):
        v = CacheValidator()
        result = v.validate_found_data(self._found(notes=None))
        assert result["notes"] is None

    def test_non_string_notes_converted(self):
        v = CacheValidator()
        result = v.validate_found_data(self._found(notes=42))
        assert result["notes"] == "42"

    def test_long_notes_truncated_in_non_strict(self):
        v = CacheValidator()
        result = v.validate_found_data(self._found(notes="x" * 5000))
        assert len(result["notes"]) == 4000

    def test_long_notes_raises_in_strict_mode(self):
        v = CacheValidator(strict_mode=True)
        with pytest.raises(ValueError, match="too long"):
            v.validate_found_data(self._found(notes="x" * 5000))

    def test_valid_found_data_passes(self):
        v = CacheValidator()
        result = v.validate_found_data(self._found(notes="Great cache!"))
        assert result["notes"] == "Great cache!"


# ---------------------------------------------------------------------------
# validate_import_consistency
# ---------------------------------------------------------------------------


class TestValidateImportConsistency:
    def test_raises_when_found_mode_without_found_data(self):
        v = CacheValidator()
        with pytest.raises(ValueError, match="found_date"):
            v.validate_import_consistency({"GC": "GC12345"}, None, "found")

    def test_raises_when_found_date_before_placed_at(self):
        v = CacheValidator()
        cache = {"GC": "GC12345", "placed_at": dt.datetime(2020, 6, 1)}
        found = {"found_date": dt.datetime(2019, 1, 1)}
        with pytest.raises(ValueError, match="before placed_at"):
            v.validate_import_consistency(cache, found, "cache")

    def test_raises_when_gc_codes_mismatch(self):
        v = CacheValidator()
        cache = {"GC": "GC12345"}
        found = {"GC": "GC99999", "found_date": dt.datetime(2024, 1, 1)}
        with pytest.raises(ValueError, match="mismatch"):
            v.validate_import_consistency(cache, found, "cache")

    def test_passes_when_consistent(self):
        v = CacheValidator()
        cache = {"GC": "GC12345", "placed_at": dt.datetime(2020, 1, 1)}
        found = {"GC": "GC12345", "found_date": dt.datetime(2024, 1, 1)}
        v.validate_import_consistency(cache, found, "found")  # should not raise

    def test_passes_when_no_found_data_in_cache_mode(self):
        v = CacheValidator()
        v.validate_import_consistency({"GC": "GC12345"}, None, "cache")  # should not raise
