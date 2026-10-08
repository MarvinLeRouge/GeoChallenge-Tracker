"""Tests for query_builder module: _compile_leaf_to_cache_pairs (unit tests - no DB required)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from bson import ObjectId

from app.services.query_builder import _compile_leaf_to_cache_pairs

_OID = ObjectId()


class TestCompileLeafToCachePairs:
    """Test _compile_leaf_to_cache_pairs compilation."""

    # --- type_in ---

    def test_type_in_canonical_doc_id(self):
        leaf = {"kind": "type_in", "types": [{"cache_type_doc_id": str(_OID)}]}
        pairs = _compile_leaf_to_cache_pairs(leaf)
        assert len(pairs) == 1
        field, cond = pairs[0]
        assert field == "type_id"
        assert ObjectId(str(_OID)) in cond["$in"]

    def test_type_in_code_resolved(self):
        leaf = {"kind": "type_in", "types": [{"cache_type_code": "TR"}]}
        with patch("app.services.query_builder.resolve_type_code", return_value=_OID):
            pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][0] == "type_id"
        assert _OID in pairs[0][1]["$in"]

    def test_type_in_code_unresolved_skipped(self):
        leaf = {"kind": "type_in", "types": [{"cache_type_code": "UNKNOWN"}]}
        with patch("app.services.query_builder.resolve_type_code", return_value=None):
            pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs == []

    def test_type_in_legacy_codes(self):
        leaf = {"kind": "type_in", "codes": ["traditional"]}
        with patch("app.services.query_builder.resolve_type_code", return_value=_OID):
            pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][0] == "type_id"

    def test_type_in_deduplicates(self):
        leaf = {
            "kind": "type_in",
            "types": [{"cache_type_code": "TR"}],
            "codes": ["TR"],
        }
        with patch("app.services.query_builder.resolve_type_code", return_value=_OID):
            pairs = _compile_leaf_to_cache_pairs(leaf)
        # Both resolve to the same OID → should deduplicate
        assert len(pairs[0][1]["$in"]) == 1

    def test_type_in_invalid_canonical_doc_id_skipped(self):
        leaf = {"kind": "type_in", "types": [{"cache_type_doc_id": "not-an-oid"}]}
        pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs == []

    def test_type_in_invalid_legacy_type_id_skipped(self):
        leaf = {"kind": "type_in", "type_ids": ["not-an-oid"]}
        pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs == []

    # --- size_in ---

    def test_size_in_canonical_doc_id(self):
        leaf = {"kind": "size_in", "sizes": [{"cache_size_doc_id": str(_OID)}]}
        pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][0] == "size_id"

    def test_size_in_by_code(self):
        leaf = {"kind": "size_in", "sizes": [{"code": "S"}]}
        with patch("app.services.query_builder.resolve_size_code", return_value=_OID):
            pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][0] == "size_id"

    def test_size_in_by_name(self):
        leaf = {"kind": "size_in", "sizes": [{"name": "Small"}]}
        with patch("app.services.query_builder.resolve_size_name", return_value=_OID):
            pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][0] == "size_id"

    def test_size_in_unresolved_skipped(self):
        leaf = {"kind": "size_in", "sizes": [{"code": "UNKNOWN"}]}
        with patch("app.services.query_builder.resolve_size_code", return_value=None):
            pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs == []

    def test_size_in_invalid_canonical_doc_id_skipped(self):
        leaf = {"kind": "size_in", "sizes": [{"cache_size_doc_id": "not-an-oid"}]}
        pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs == []

    def test_size_in_legacy_code_resolved(self):
        leaf = {"kind": "size_in", "codes": ["S"]}
        with patch("app.services.query_builder.resolve_size_code", return_value=_OID):
            pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][0] == "size_id"
        assert _OID in pairs[0][1]["$in"]

    def test_size_in_legacy_name_resolved(self):
        leaf = {"kind": "size_in", "names": ["Small"]}
        with patch("app.services.query_builder.resolve_size_name", return_value=_OID):
            pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][0] == "size_id"
        assert _OID in pairs[0][1]["$in"]

    def test_size_in_legacy_size_ids_valid(self):
        leaf = {"kind": "size_in", "size_ids": [str(_OID)]}
        pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][0] == "size_id"
        assert _OID in pairs[0][1]["$in"]

    def test_size_in_legacy_size_ids_invalid_skipped(self):
        leaf = {"kind": "size_in", "size_ids": ["not-an-oid"]}
        pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs == []

    # --- country_is ---

    def test_country_is_with_country_id(self):
        leaf = {"kind": "country_is", "country_id": _OID}
        pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0] == ("country_id", _OID)

    def test_country_is_resolved_by_name(self):
        leaf = {"kind": "country_is", "country": {"name": "France"}}
        with patch("app.services.query_builder.resolve_country_name", return_value=_OID):
            pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0] == ("country_id", _OID)

    def test_country_is_unresolved_impossible_clause(self):
        leaf = {"kind": "country_is", "country": {"name": "Unknown Country"}}
        with patch("app.services.query_builder.resolve_country_name", return_value=None):
            pairs = _compile_leaf_to_cache_pairs(leaf)
        # Should return an impossible _id clause
        assert pairs[0][0] == "_id"

    def test_country_is_resolved_by_code_only(self):
        leaf = {"kind": "country_is", "country": {"code": "FR"}}
        with patch(
            "app.services.query_builder.resolve_country_name", return_value=_OID
        ) as mock_resolve:
            pairs = _compile_leaf_to_cache_pairs(leaf)
        mock_resolve.assert_called_once_with("FR")
        assert pairs[0] == ("country_id", _OID)

    # --- state_in ---

    def test_state_in_with_state_ids(self):
        leaf = {"kind": "state_in", "state_ids": [_OID]}
        pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][0] == "state_id"

    def test_state_in_resolved_by_name(self):
        leaf = {"kind": "state_in", "states": [{"name": "Île-de-France"}]}
        with patch(
            "app.services.query_builder.resolve_state_name",
            return_value=(_OID, None),
        ):
            pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][0] == "state_id"

    def test_state_in_unresolved_impossible_clause(self):
        leaf = {"kind": "state_in", "states": []}
        pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][0] == "_id"

    def test_state_in_resolved_name_invalid_oid_impossible_clause(self):
        leaf = {"kind": "state_in", "states": [{"name": "Foo"}]}
        with patch(
            "app.services.query_builder.resolve_state_name",
            return_value=("not-an-oid", None),
        ):
            pairs = _compile_leaf_to_cache_pairs(leaf)
        # Invalid ObjectId is swallowed, so no id is collected → impossible clause
        assert pairs[0][0] == "_id"

    # --- placed_year ---

    def test_placed_year(self):
        leaf = {"kind": "placed_year", "year": 2020}
        pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][0] == "placed_at"
        cond = pairs[0][1]
        assert cond["$gte"] == datetime(2020, 1, 1)
        assert cond["$lt"] == datetime(2021, 1, 1)

    # --- placed_before / placed_after ---

    def test_placed_before(self):
        leaf = {"kind": "placed_before", "date": "2020-01-01"}
        pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][0] == "placed_at"
        assert "$lt" in pairs[0][1]

    def test_placed_after(self):
        leaf = {"kind": "placed_after", "date": "2020-01-01"}
        pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][0] == "placed_at"
        assert "$gt" in pairs[0][1]

    # --- difficulty_between / terrain_between ---

    def test_difficulty_between(self):
        leaf = {"kind": "difficulty_between", "min": 2.0, "max": 4.0}
        pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][0] == "difficulty"
        assert pairs[0][1] == {"$gte": 2.0, "$lte": 4.0}

    def test_terrain_between(self):
        leaf = {"kind": "terrain_between", "min": 1.5, "max": 3.5}
        pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][0] == "terrain"
        assert pairs[0][1] == {"$gte": 1.5, "$lte": 3.5}

    # --- attributes ---

    def test_attributes_with_doc_id(self):
        leaf = {
            "kind": "attributes",
            "attributes": [{"cache_attribute_doc_id": str(_OID), "is_positive": True}],
        }
        pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][0] == "attributes"
        assert "$elemMatch" in pairs[0][1]
        assert pairs[0][1]["$elemMatch"]["is_positive"] is True

    def test_attributes_by_code(self):
        leaf = {
            "kind": "attributes",
            "attributes": [{"code": "dogs", "is_positive": True}],
        }
        with patch(
            "app.services.query_builder.resolve_attribute_code",
            return_value=(_OID, 1),
        ):
            pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][0] == "attributes"

    def test_attributes_unresolved_impossible_clause(self):
        leaf = {
            "kind": "attributes",
            "attributes": [{"code": "unknown_attr", "is_positive": True}],
        }
        with patch("app.services.query_builder.resolve_attribute_code", return_value=None):
            pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][0] == "_id"

    def test_attributes_negative(self):
        leaf = {
            "kind": "attributes",
            "attributes": [{"cache_attribute_doc_id": str(_OID), "is_positive": False}],
        }
        pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][1]["$elemMatch"]["is_positive"] is False

    def test_attributes_legacy_codes(self):
        leaf = {"kind": "attributes", "codes": ["picnic"]}
        with patch(
            "app.services.query_builder.resolve_attribute_code",
            return_value=(_OID, 5),
        ):
            pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][0] == "attributes"
        assert pairs[0][1]["$elemMatch"]["is_positive"] is True

    def test_attributes_legacy_codes_unresolved_impossible_clause(self):
        leaf = {"kind": "attributes", "codes": ["unknown_attr"]}
        with patch("app.services.query_builder.resolve_attribute_code", return_value=None):
            pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs[0][0] == "_id"

    # --- unknown kind ---

    def test_unknown_kind_returns_empty(self):
        leaf = {"kind": "unknown_rule"}
        pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs == []
