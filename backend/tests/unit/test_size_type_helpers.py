"""Tests for size_helpers and type_helpers (unit tests - no DB required)."""

from __future__ import annotations

from bson import ObjectId

from app.services.size_helpers import _normalize_name as _normalize_name_size
from app.services.size_helpers import get_size_by_name
from app.services.type_helpers import _normalize_name as _normalize_name_type
from app.services.type_helpers import get_type_by_name

_OID_MICRO = ObjectId()
_OID_SMALL = ObjectId()
_OID_MYSTERY = ObjectId()
_OID_TRADITIONAL = ObjectId()

_SIZES = {
    "micro": _OID_MICRO,
    "small": _OID_SMALL,
}

_TYPES = {
    "traditional": _OID_TRADITIONAL,
    "mystery": _OID_MYSTERY,
}


# ---------------------------------------------------------------------------
# _normalize_name (shared logic)
# ---------------------------------------------------------------------------


class TestNormalizeName:
    def test_none_returns_empty(self):
        assert _normalize_name_size(None) == ""
        assert _normalize_name_type(None) == ""

    def test_strips_whitespace(self):
        assert _normalize_name_size("  Micro  ") == "micro"

    def test_casefolded(self):
        assert _normalize_name_type("MYSTERY") == "mystery"

    def test_empty_string(self):
        assert _normalize_name_size("") == ""


# ---------------------------------------------------------------------------
# get_size_by_name
# ---------------------------------------------------------------------------


class TestGetSizeByName:
    def test_exact_match(self):
        result = get_size_by_name("Micro", _SIZES)
        assert result == _OID_MICRO

    def test_case_insensitive_match(self):
        result = get_size_by_name("SMALL", _SIZES)
        assert result == _OID_SMALL

    def test_partial_match_db_name_in_query(self):
        # "micro" is in "micro canister" → partial match
        sizes = {"micro": _OID_MICRO}
        result = get_size_by_name("micro canister", sizes)
        assert result == _OID_MICRO

    def test_partial_match_query_in_db_name(self):
        # "sma" is in "small"
        sizes = {"smallish": _OID_SMALL}
        result = get_size_by_name("sma", sizes)
        assert result == _OID_SMALL

    def test_no_match_returns_none(self):
        result = get_size_by_name("gigantic", _SIZES)
        assert result is None

    def test_none_input_partial_matches_first_entry(self):
        """None normalizes to '' which matches every db_name via partial match.
        The first entry in the dict is returned — this is an edge case of the
        empty-string partial match ('\\'' in 'micro' is always True)."""
        result = get_size_by_name(None, _SIZES)
        # empty string is always a substring of any db_name → returns first entry
        assert result is not None

    def test_none_dict_returns_none(self):
        result = get_size_by_name("micro", None)
        assert result is None

    def test_empty_dict_returns_none(self):
        result = get_size_by_name("micro", {})
        assert result is None


# ---------------------------------------------------------------------------
# get_type_by_name
# ---------------------------------------------------------------------------


class TestGetTypeByName:
    def test_exact_match(self):
        result = get_type_by_name("traditional", _TYPES)
        assert result == _OID_TRADITIONAL

    def test_case_insensitive_match(self):
        result = get_type_by_name("Traditional", _TYPES)
        assert result == _OID_TRADITIONAL

    def test_partial_match(self):
        # "traditional" is in "Traditional Cache"
        types = {"traditional cache": _OID_TRADITIONAL}
        result = get_type_by_name("traditional", types)
        assert result == _OID_TRADITIONAL

    def test_synonym_unknown_resolves_to_mystery(self):
        """'unknown' type resolves via synonym to 'mystery'."""
        result = get_type_by_name("Unknown Cache", _TYPES)
        assert result == _OID_MYSTERY

    def test_synonym_exact_unknown(self):
        result = get_type_by_name("unknown", _TYPES)
        assert result == _OID_MYSTERY

    def test_no_match_returns_none(self):
        result = get_type_by_name("letterbox", _TYPES)
        assert result is None

    def test_none_input_partial_matches_first_entry(self):
        """Same empty-string partial match edge case as get_size_by_name."""
        result = get_type_by_name(None, _TYPES)
        assert result is not None

    def test_none_dict_returns_none(self):
        result = get_type_by_name("traditional", None)
        assert result is None
