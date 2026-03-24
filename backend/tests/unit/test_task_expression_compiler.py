"""Tests for TaskExpressionCompiler (unit tests - no DB required)."""

from __future__ import annotations

from datetime import date

import pytest
from bson import ObjectId
from pydantic import TypeAdapter

from app.domain.models.challenge_ast import (
    AttributeSelector,
    CountrySelector,
    RuleAggSumDifficultyAtLeast,
    RuleAggSumTerrainAtLeast,
    RuleAttributes,
    RuleCountryIs,
    RuleDifficultyBetween,
    RulePlacedAfter,
    RulePlacedBefore,
    RulePlacedYear,
    RuleSizeIn,
    RuleStateIn,
    RuleTerrainBetween,
    RuleTypeIn,
    SizeSelector,
    TaskAnd,
    TaskExpression,
    TaskNot,
    TaskOr,
    TypeSelector,
)
from app.services.user_challenge_tasks.task_expression_compiler import (
    TaskExpressionCompiler,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OID = ObjectId()
_OID2 = ObjectId()
_OID3 = ObjectId()


def _validate(expr_dict) -> TaskExpression:
    return TypeAdapter(TaskExpression).validate_python(expr_dict)


# ---------------------------------------------------------------------------
# is_aggregate_kind
# ---------------------------------------------------------------------------


class TestIsAggregateKind:
    """Test TaskExpressionCompiler.is_aggregate_kind."""

    @pytest.mark.parametrize(
        "kind",
        [
            "aggregate_sum_difficulty_at_least",
            "aggregate_sum_terrain_at_least",
            "aggregate_sum_diff_plus_terr_at_least",
            "aggregate_sum_altitude_at_least",
            "aggregate_count_distinct_countries_at_least",
            "aggregate_dt_matrix_complete",
        ],
    )
    def test_known_aggregates(self, kind):
        assert TaskExpressionCompiler.is_aggregate_kind(kind) is True

    @pytest.mark.parametrize(
        "kind",
        [
            "type_in",
            "size_in",
            "placed_year",
            "difficulty_between",
            "country_is",
            "and",
            "or",
            "not",
            "unknown",
        ],
    )
    def test_non_aggregates(self, kind):
        assert TaskExpressionCompiler.is_aggregate_kind(kind) is False


# ---------------------------------------------------------------------------
# has_country_is_in_and
# ---------------------------------------------------------------------------


class TestHasCountryIsInAnd:
    """Test TaskExpressionCompiler.has_country_is_in_and."""

    def test_direct_country_is(self):
        country_node = RuleCountryIs(country=CountrySelector(country_id=1, name="France"))
        assert TaskExpressionCompiler.has_country_is_in_and([country_node]) is True

    def test_no_country_is(self):
        year_node = RulePlacedYear(year=2020)
        assert TaskExpressionCompiler.has_country_is_in_and([year_node]) is False

    def test_nested_and_with_country_is(self):
        country_node = RuleCountryIs(country=CountrySelector(country_id=1, name="France"))
        inner_and = TaskAnd(nodes=[country_node])
        assert TaskExpressionCompiler.has_country_is_in_and([inner_and]) is True

    def test_empty_list(self):
        assert TaskExpressionCompiler.has_country_is_in_and([]) is False

    def test_mixed_nodes_country_present(self):
        year_node = RulePlacedYear(year=2020)
        country_node = RuleCountryIs(country=CountrySelector(name="Germany"))
        assert TaskExpressionCompiler.has_country_is_in_and([year_node, country_node]) is True

    def test_deeply_nested_and_with_country(self):
        country_node = RuleCountryIs(country=CountrySelector(name="Spain"))
        inner_and = TaskAnd(nodes=[country_node])
        outer_and = TaskAnd(nodes=[inner_and])
        assert TaskExpressionCompiler.has_country_is_in_and([outer_and]) is True


# ---------------------------------------------------------------------------
# walk_expression_tree
# ---------------------------------------------------------------------------


class TestWalkExpressionTree:
    """Test TaskExpressionCompiler.walk_expression_tree.

    NOTE: walk_expression_tree is a generator function (contains yield).
    The leaf case uses `return [(kind, node, None)]` which, in a generator,
    terminates the generator without yielding the list. As a result, leaf
    nodes produce no items when iterated. This is a known design issue in
    the original implementation.
    """

    def test_leaf_directly_yields_itself(self):
        """Leaf nodes yield themselves when walked directly."""
        leaf = RulePlacedYear(year=2020)
        items = list(TaskExpressionCompiler.walk_expression_tree(leaf))
        assert len(items) == 1
        assert items[0][0] == "placed_year"

    def test_and_yields_leaf_children(self):
        year_node = RulePlacedYear(year=2020)
        diff_node = RuleDifficultyBetween(min=2.0, max=4.0)
        and_expr = TaskAnd(nodes=[year_node, diff_node])
        items = list(TaskExpressionCompiler.walk_expression_tree(and_expr))
        kinds = [k for k, _, _ in items]
        assert "placed_year" in kinds

    def test_or_yields_leaf_children(self):
        year_node = RulePlacedYear(year=2020)
        or_expr = TaskOr(nodes=[year_node])
        items = list(TaskExpressionCompiler.walk_expression_tree(or_expr))
        kinds = [k for k, _, _ in items]
        assert "placed_year" in kinds

    def test_not_wraps_with_not_parent(self):
        year_node = RulePlacedYear(year=2020)
        not_expr = TaskNot(node=year_node)
        items = list(TaskExpressionCompiler.walk_expression_tree(not_expr))
        parents = [pk for _, _, pk in items]
        assert "not" in parents

    def test_empty_and_yields_nothing(self):
        and_expr = TaskAnd(nodes=[])
        items = list(TaskExpressionCompiler.walk_expression_tree(and_expr))
        assert items == []


# ---------------------------------------------------------------------------
# compile_expression_to_cache_match
# ---------------------------------------------------------------------------


class TestCompileExpressionToCacheMatch:
    """Test TaskExpressionCompiler.compile_expression_to_cache_match."""

    def test_placed_year(self):
        leaf = RulePlacedYear(year=2022)
        and_expr = TaskAnd(nodes=[leaf])
        result = TaskExpressionCompiler.compile_expression_to_cache_match(and_expr)
        assert "$and" in result
        assert {"placed_year": 2022} in result["$and"]

    def test_placed_before(self):
        leaf = RulePlacedBefore(date=date(2020, 1, 1))
        and_expr = TaskAnd(nodes=[leaf])
        result = TaskExpressionCompiler.compile_expression_to_cache_match(and_expr)
        clauses = result["$and"]
        placed_at_clause = next(c for c in clauses if "placed_at" in c)
        assert "$lt" in placed_at_clause["placed_at"]

    def test_placed_after(self):
        leaf = RulePlacedAfter(date=date(2015, 6, 1))
        and_expr = TaskAnd(nodes=[leaf])
        result = TaskExpressionCompiler.compile_expression_to_cache_match(and_expr)
        clauses = result["$and"]
        placed_at_clause = next(c for c in clauses if "placed_at" in c)
        assert "$gt" in placed_at_clause["placed_at"]

    def test_difficulty_between(self):
        leaf = RuleDifficultyBetween(min=2.5, max=4.5)
        and_expr = TaskAnd(nodes=[leaf])
        result = TaskExpressionCompiler.compile_expression_to_cache_match(and_expr)
        clauses = result["$and"]
        diff_clause = next(c for c in clauses if "difficulty" in c)
        assert diff_clause["difficulty"] == {"$gte": 2.5, "$lte": 4.5}

    def test_terrain_between(self):
        leaf = RuleTerrainBetween(min=1.0, max=3.0)
        and_expr = TaskAnd(nodes=[leaf])
        result = TaskExpressionCompiler.compile_expression_to_cache_match(and_expr)
        clauses = result["$and"]
        terrain_clause = next(c for c in clauses if "terrain" in c)
        assert terrain_clause["terrain"] == {"$gte": 1.0, "$lte": 3.0}

    def test_state_in(self):
        leaf = RuleStateIn(state_ids=[_OID, _OID2])
        and_expr = TaskAnd(nodes=[leaf])
        result = TaskExpressionCompiler.compile_expression_to_cache_match(and_expr)
        clauses = result["$and"]
        state_clause = next(c for c in clauses if "state_id" in c)
        assert "$in" in state_clause["state_id"]
        assert _OID in state_clause["state_id"]["$in"]

    def test_state_in_empty_ids_produces_no_clause(self):
        """An empty state_ids list yields an empty sub-filter which is stripped."""
        leaf = RuleStateIn(state_ids=[])
        and_expr = TaskAnd(nodes=[leaf])
        result = TaskExpressionCompiler.compile_expression_to_cache_match(and_expr)
        # Empty dict → filtered → $and is empty or result is {}
        assert result == {} or result.get("$and") == []

    def test_attributes_with_doc_id(self):
        attr = AttributeSelector(cache_attribute_doc_id=_OID, is_positive=True)
        leaf = RuleAttributes(attributes=[attr])
        and_expr = TaskAnd(nodes=[leaf])
        result = TaskExpressionCompiler.compile_expression_to_cache_match(and_expr)
        clauses = result["$and"]
        # attributes leaf produces {"$and": [...]} itself
        attr_clause = next(c for c in clauses if "$and" in c)
        inner = attr_clause["$and"][0]
        assert "attributes" in inner
        assert inner["attributes"]["$elemMatch"]["is_positive"] is True

    def test_attributes_negative(self):
        attr = AttributeSelector(cache_attribute_doc_id=_OID, is_positive=False)
        leaf = RuleAttributes(attributes=[attr])
        and_expr = TaskAnd(nodes=[leaf])
        result = TaskExpressionCompiler.compile_expression_to_cache_match(and_expr)
        clauses = result["$and"]
        attr_clause = next(c for c in clauses if "$and" in c)
        inner = attr_clause["$and"][0]
        assert inner["attributes"]["$elemMatch"]["is_positive"] is False

    def test_attributes_with_numeric_id_fallback(self):
        """When no doc_id, numeric cache_attribute_id is used."""
        attr = AttributeSelector(cache_attribute_id=42, is_positive=True)
        leaf = RuleAttributes(attributes=[attr])
        and_expr = TaskAnd(nodes=[leaf])
        result = TaskExpressionCompiler.compile_expression_to_cache_match(and_expr)
        clauses = result["$and"]
        attr_clause = next(c for c in clauses if "$and" in c)
        inner = attr_clause["$and"][0]
        assert inner["attributes"]["$elemMatch"]["cache_attribute_id"] == 42

    def test_aggregate_leaves_produce_empty_filter(self):
        agg = RuleAggSumDifficultyAtLeast(min_total=50)
        and_expr = TaskAnd(nodes=[agg])
        result = TaskExpressionCompiler.compile_expression_to_cache_match(and_expr)
        # Aggregate leaves produce {} → stripped from $and → result is empty
        assert result == {} or result.get("$and") == [] or result.get("$and") is None

    def test_multiple_aggregates_all_stripped(self):
        agg1 = RuleAggSumDifficultyAtLeast(min_total=50)
        agg2 = RuleAggSumTerrainAtLeast(min_total=30)
        and_expr = TaskAnd(nodes=[agg1, agg2])
        result = TaskExpressionCompiler.compile_expression_to_cache_match(and_expr)
        assert not result or result.get("$and") == []

    def test_or_expression(self):
        leaf1 = RulePlacedYear(year=2020)
        leaf2 = RulePlacedYear(year=2021)
        or_expr = TaskOr(nodes=[leaf1, leaf2])
        result = TaskExpressionCompiler.compile_expression_to_cache_match(or_expr)
        assert "$or" in result
        assert len(result["$or"]) == 2

    def test_not_expression(self):
        leaf = RulePlacedYear(year=2020)
        not_expr = TaskNot(node=leaf)
        result = TaskExpressionCompiler.compile_expression_to_cache_match(not_expr)
        assert "$nor" in result
        assert len(result["$nor"]) == 1

    def test_nested_and_with_or(self):
        leaf1 = RulePlacedYear(year=2020)
        leaf2 = RuleDifficultyBetween(min=2.0, max=4.0)
        or_inner = TaskOr(nodes=[leaf1])
        and_expr = TaskAnd(nodes=[or_inner, leaf2])
        result = TaskExpressionCompiler.compile_expression_to_cache_match(and_expr)
        assert "$and" in result
        parts = result["$and"]
        kinds_present = set()
        for p in parts:
            if "$or" in p:
                kinds_present.add("or")
            if "difficulty" in p:
                kinds_present.add("difficulty")
        assert "or" in kinds_present
        assert "difficulty" in kinds_present

    def test_empty_and_returns_empty(self):
        and_expr = TaskAnd(nodes=[])
        result = TaskExpressionCompiler.compile_expression_to_cache_match(and_expr)
        assert result == {}

    def test_type_in_no_ids_produces_empty(self):
        """TypeIn without type_ids (no post-normalization) yields empty dict."""
        leaf = RuleTypeIn(types=[TypeSelector(code="TR")])
        and_expr = TaskAnd(nodes=[leaf])
        result = TaskExpressionCompiler.compile_expression_to_cache_match(and_expr)
        # No type_ids populated → empty leaf dict → stripped from $and
        assert result == {} or result.get("$and") == []

    def test_size_in_no_ids_produces_empty(self):
        """SizeIn without size_ids (no post-normalization) yields empty dict."""
        leaf = RuleSizeIn(sizes=[SizeSelector(code="S")])
        and_expr = TaskAnd(nodes=[leaf])
        result = TaskExpressionCompiler.compile_expression_to_cache_match(and_expr)
        assert result == {} or result.get("$and") == []

    def test_country_is(self):
        leaf = RuleCountryIs(country=CountrySelector(country_id=42, name="France"))
        and_expr = TaskAnd(nodes=[leaf])
        result = TaskExpressionCompiler.compile_expression_to_cache_match(and_expr)
        clauses = result["$and"]
        country_clause = next(c for c in clauses if "country_id" in c)
        assert country_clause["country_id"] == 42
