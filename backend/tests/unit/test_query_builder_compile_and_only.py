"""Tests for query_builder module: compile_and_only (unit tests - no DB required)."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import patch

from bson import ObjectId

from app.services.query_builder import compile_and_only

_OID = ObjectId()


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
