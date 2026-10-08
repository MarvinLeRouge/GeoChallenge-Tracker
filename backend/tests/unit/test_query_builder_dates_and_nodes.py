"""Tests for query_builder module: _mk_date and _flatten_and_nodes (unit tests - no DB required)."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from app.services.query_builder import _flatten_and_nodes, _mk_date


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
