"""Tests for query_builder module (unit tests - no DB required)."""

from __future__ import annotations

import json
from datetime import date, datetime
from unittest.mock import patch

import pytest
from bson import ObjectId

from app.services.query_builder import (
    _compile_leaf_to_cache_pairs,
    _extract_aggregate_spec,
    _flatten_and_nodes,
    _mk_date,
    compile_and_only,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OID = ObjectId()
_OID2 = ObjectId()


def _patch_resolvers(**kwargs):
    """Patch all six referential resolver functions at once."""
    defaults = {
        "resolve_type_code": None,
        "resolve_size_code": None,
        "resolve_size_name": None,
        "resolve_country_name": None,
        "resolve_state_name": (None, "not found"),
        "resolve_attribute_code": None,
    }
    defaults.update(kwargs)

    def _make_patch(name, return_value):
        return patch(
            f"app.services.query_builder.{name}",
            return_value=return_value,
        )

    return [_make_patch(k, v) for k, v in defaults.items()]


# ---------------------------------------------------------------------------
# _mk_date
# ---------------------------------------------------------------------------


class TestMkDate:
    """Test _mk_date normalization."""

    def test_datetime_passthrough(self):
        dt = datetime(2024, 6, 15, 12, 0, 0)
        assert _mk_date(dt) is dt

    def test_date_to_datetime(self):
        d = date(2024, 6, 15)
        result = _mk_date(d)
        assert isinstance(result, datetime)
        assert result == datetime(2024, 6, 15)

    def test_string_short_format(self):
        result = _mk_date("2024-06-15")
        assert isinstance(result, datetime)
        assert result == datetime(2024, 6, 15)

    def test_string_iso_format(self):
        result = _mk_date("2024-06-15T12:30:00")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.hour == 12

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Invalid date"):
            _mk_date(12345)

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError):
            _mk_date("not-a-date")


# ---------------------------------------------------------------------------
# _flatten_and_nodes
# ---------------------------------------------------------------------------


class TestFlattenAndNodes:
    """Test _flatten_and_nodes tree flattening."""

    def test_leaf_returns_self(self):
        leaf = {"kind": "placed_year", "year": 2020}
        result = _flatten_and_nodes(leaf)
        assert result == [leaf]

    def test_simple_and(self):
        leaf1 = {"kind": "placed_year", "year": 2020}
        leaf2 = {"kind": "placed_year", "year": 2021}
        expr = {"kind": "and", "nodes": [leaf1, leaf2]}
        result = _flatten_and_nodes(expr)
        assert result == [leaf1, leaf2]

    def test_nested_and(self):
        leaf1 = {"kind": "placed_year", "year": 2020}
        leaf2 = {"kind": "placed_year", "year": 2021}
        leaf3 = {"kind": "placed_year", "year": 2022}
        inner = {"kind": "and", "nodes": [leaf2, leaf3]}
        expr = {"kind": "and", "nodes": [leaf1, inner]}
        result = _flatten_and_nodes(expr)
        assert result == [leaf1, leaf2, leaf3]

    def test_or_returns_none(self):
        expr = {
            "kind": "or",
            "nodes": [{"kind": "placed_year", "year": 2020}],
        }
        assert _flatten_and_nodes(expr) is None

    def test_not_returns_none(self):
        expr = {
            "kind": "not",
            "node": {"kind": "placed_year", "year": 2020},
        }
        assert _flatten_and_nodes(expr) is None

    def test_and_containing_or_returns_none(self):
        or_node = {
            "kind": "or",
            "nodes": [{"kind": "placed_year", "year": 2020}],
        }
        expr = {"kind": "and", "nodes": [or_node]}
        assert _flatten_and_nodes(expr) is None

    def test_empty_and(self):
        expr = {"kind": "and", "nodes": []}
        assert _flatten_and_nodes(expr) == []

    def test_and_with_no_nodes_key(self):
        expr = {"kind": "and"}
        assert _flatten_and_nodes(expr) == []


# ---------------------------------------------------------------------------
# _extract_aggregate_spec
# ---------------------------------------------------------------------------


class TestExtractAggregateSpec:
    """Test _extract_aggregate_spec aggregate extraction."""

    def test_no_aggregate(self):
        leaves = [{"kind": "placed_year", "year": 2020}]
        agg, remaining = _extract_aggregate_spec(leaves)
        assert agg is None
        assert remaining == leaves

    def test_difficulty_aggregate(self):
        agg_leaf = {"kind": "aggregate_sum_difficulty_at_least", "min_total": 50}
        leaves = [{"kind": "placed_year", "year": 2020}, agg_leaf]
        agg, remaining = _extract_aggregate_spec(leaves)
        assert agg == {"kind": "difficulty", "min_total": 50}
        assert remaining == [{"kind": "placed_year", "year": 2020}]

    def test_terrain_aggregate(self):
        agg_leaf = {"kind": "aggregate_sum_terrain_at_least", "min_total": 30}
        agg, _ = _extract_aggregate_spec([agg_leaf])
        assert agg == {"kind": "terrain", "min_total": 30}

    def test_diff_plus_terr_aggregate(self):
        agg_leaf = {"kind": "aggregate_sum_diff_plus_terr_at_least", "min_total": 100}
        agg, _ = _extract_aggregate_spec([agg_leaf])
        assert agg == {"kind": "diff_plus_terr", "min_total": 100}

    def test_altitude_aggregate(self):
        agg_leaf = {"kind": "aggregate_sum_altitude_at_least", "min_total": 5000}
        agg, _ = _extract_aggregate_spec([agg_leaf])
        assert agg == {"kind": "altitude", "min_total": 5000}

    def test_distinct_countries_aggregate(self):
        agg_leaf = {"kind": "aggregate_count_distinct_countries_at_least", "min_total": 10}
        agg, _ = _extract_aggregate_spec([agg_leaf])
        assert agg == {"kind": "distinct_countries", "min_total": 10}

    def test_dt_matrix_aggregate_default(self):
        agg_leaf = {"kind": "aggregate_dt_matrix_complete"}
        agg, _ = _extract_aggregate_spec([agg_leaf])
        assert agg is not None
        assert agg["kind"] == "dt_matrix"
        assert agg["max_difficulty"] == 5.0
        assert agg["max_terrain"] == 5.0
        # 5.0 -> n = round((5.0-1.0)/0.5)+1 = 9, 9*9 = 81
        assert agg["min_total"] == 81

    def test_dt_matrix_aggregate_custom(self):
        agg_leaf = {
            "kind": "aggregate_dt_matrix_complete",
            "max_difficulty": 3.0,
            "max_terrain": 2.0,
        }
        agg, _ = _extract_aggregate_spec([agg_leaf])
        assert agg is not None
        # n_d = round((3.0-1.0)/0.5)+1 = 5, n_t = round((2.0-1.0)/0.5)+1 = 3
        assert agg["min_total"] == 5 * 3

    def test_only_first_aggregate_is_kept(self):
        agg1 = {"kind": "aggregate_sum_difficulty_at_least", "min_total": 50}
        agg2 = {"kind": "aggregate_sum_terrain_at_least", "min_total": 30}
        agg, remaining = _extract_aggregate_spec([agg1, agg2])
        assert agg == {"kind": "difficulty", "min_total": 50}
        # Second aggregate is dropped from remaining but not moved to agg
        assert len(remaining) == 0

    def test_aggregate_missing_min_total_ignored(self):
        agg_leaf = {"kind": "aggregate_sum_difficulty_at_least"}  # no min_total
        agg, remaining = _extract_aggregate_spec([agg_leaf])
        assert agg is None
        assert remaining == []  # leaf was consumed but agg is None


# ---------------------------------------------------------------------------
# _compile_leaf_to_cache_pairs
# ---------------------------------------------------------------------------


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

    # --- unknown kind ---

    def test_unknown_kind_returns_empty(self):
        leaf = {"kind": "unknown_rule"}
        pairs = _compile_leaf_to_cache_pairs(leaf)
        assert pairs == []


# ---------------------------------------------------------------------------
# compile_and_only
# ---------------------------------------------------------------------------


class TestCompileAndOnly:
    """Test compile_and_only end-to-end compilation."""

    def test_or_expression_unsupported(self):
        expr = {"kind": "or", "nodes": [{"kind": "placed_year", "year": 2020}]}
        sig, match, supported, notes, agg = compile_and_only(expr)
        assert supported is False
        assert "or/not" in notes[0]
        assert match == {}
        assert agg is None

    def test_not_expression_unsupported(self):
        expr = {"kind": "not", "node": {"kind": "placed_year", "year": 2020}}
        sig, match, supported, notes, agg = compile_and_only(expr)
        assert supported is False

    def test_simple_placed_year(self):
        expr = {"kind": "and", "nodes": [{"kind": "placed_year", "year": 2020}]}
        sig, match, supported, notes, agg = compile_and_only(expr)
        assert supported is True
        assert notes == []
        assert agg is None
        assert "placed_at" in match
        assert match["placed_at"]["$gte"] == datetime(2020, 1, 1)

    def test_difficulty_range(self):
        expr = {"kind": "difficulty_between", "min": 3.0, "max": 5.0}
        sig, match, supported, notes, agg = compile_and_only(expr)
        assert supported is True
        assert "difficulty" in match
        assert match["difficulty"] == {"$gte": 3.0, "$lte": 5.0}

    def test_with_aggregate(self):
        expr = {
            "kind": "and",
            "nodes": [
                {"kind": "placed_year", "year": 2020},
                {"kind": "aggregate_sum_difficulty_at_least", "min_total": 50},
            ],
        }
        sig, match, supported, notes, agg = compile_and_only(expr)
        assert supported is True
        assert agg == {"kind": "difficulty", "min_total": 50}
        assert "placed_at" in match
        # aggregate leaf must NOT appear in match
        assert "aggregate_sum_difficulty_at_least" not in str(match)

    def test_signature_is_deterministic(self):
        expr = {"kind": "placed_year", "year": 2020}
        sig1, *_ = compile_and_only(expr)
        sig2, *_ = compile_and_only(expr)
        assert sig1 == sig2
        assert sig1.startswith("and:")

    def test_signature_is_json(self):
        expr = {"kind": "placed_year", "year": 2021}
        sig, *_ = compile_and_only(expr)
        json_part = sig[len("and:") :]
        data = json.loads(json_part)
        assert "leaves" in data

    def test_multiple_fields_merged(self):
        expr = {
            "kind": "and",
            "nodes": [
                {"kind": "difficulty_between", "min": 2.0, "max": 4.0},
                {"kind": "terrain_between", "min": 1.0, "max": 3.0},
            ],
        }
        sig, match, supported, notes, agg = compile_and_only(expr)
        assert "difficulty" in match
        assert "terrain" in match

    def test_type_in_with_code(self):
        expr = {"kind": "type_in", "types": [{"cache_type_code": "TR"}]}
        with patch("app.services.query_builder.resolve_type_code", return_value=_OID):
            sig, match, supported, notes, agg = compile_and_only(expr)
        assert "type_id" in match
        assert _OID in match["type_id"]["$in"]
