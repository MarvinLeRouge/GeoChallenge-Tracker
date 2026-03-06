"""Tests for Challenge Services components (unit tests - no DB required)."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.domain.models.challenge_ast import (
    AttributeSelector,
    CountrySelector,
    RuleAggSumAltitudeAtLeast,
    RuleAggSumDifficultyAtLeast,
    RuleAggSumDiffPlusTerrAtLeast,
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
    StateSelector,
    TaskAnd,
    TaskExpression,
    TaskNot,
    TaskOr,
    TypeSelector,
    UCAnd,
    UCLogic,
    UCNot,
    UCOr,
)


class TestASTBase:
    """Test ASTBase component (base class for all AST nodes)."""

    def test_ast_base_allows_arbitrary_types(self):
        """Test that ASTBase allows arbitrary types like PyObjectId."""
        # ASTBase is a base class, we test through a subclass
        selector = TypeSelector()
        assert selector is not None


class TestSelectors:
    """Test AST selector components."""

    def test_type_selector_with_doc_id(self):
        """Test TypeSelector with cache_type_doc_id."""
        from bson import ObjectId

        doc_id = ObjectId()
        selector = TypeSelector(cache_type_doc_id=doc_id)

        assert selector.cache_type_doc_id == doc_id
        assert selector.cache_type_id is None
        assert selector.code is None

    def test_type_selector_with_id(self):
        """Test TypeSelector with cache_type_id."""
        selector = TypeSelector(cache_type_id=5)

        assert selector.cache_type_id == 5
        assert selector.cache_type_doc_id is None

    def test_type_selector_with_code(self):
        """Test TypeSelector with code."""
        selector = TypeSelector(code="whereigo")

        assert selector.code == "whereigo"

    def test_size_selector(self):
        """Test SizeSelector."""
        selector = SizeSelector(
            cache_size_doc_id="507f1f77bcf86cd799439011", cache_size_id=3, code="regular"
        )

        assert selector.cache_size_id == 3
        assert selector.code == "regular"

    def test_state_selector(self):
        """Test StateSelector."""
        selector = StateSelector(state_id=42, name="Washington")

        assert selector.state_id == 42
        assert selector.name == "Washington"

    def test_country_selector(self):
        """Test CountrySelector."""
        selector = CountrySelector(country_id=1, name="France")

        assert selector.country_id == 1
        assert selector.name == "France"

    def test_attribute_selector(self):
        """Test AttributeSelector."""
        from bson import ObjectId

        doc_id = ObjectId()
        selector = AttributeSelector(
            cache_attribute_doc_id=doc_id, cache_attribute_id=71, code="picnic", is_positive=True
        )

        assert selector.cache_attribute_id == 71
        assert selector.code == "picnic"
        assert selector.is_positive is True


class TestRuleClasses:
    """Test AST rule components."""

    def test_rule_type_in(self):
        """Test RuleTypeIn with multiple types."""
        rule = RuleTypeIn(types=[TypeSelector(code="traditional"), TypeSelector(code="multi")])

        assert rule.kind == "type_in"
        assert len(rule.types) == 2

    def test_rule_size_in(self):
        """Test RuleSizeIn with multiple sizes."""
        rule = RuleSizeIn(sizes=[SizeSelector(code="small"), SizeSelector(code="regular")])

        assert rule.kind == "size_in"
        assert len(rule.sizes) == 2

    def test_rule_placed_year_valid(self):
        """Test RulePlacedYear with valid year."""
        rule = RulePlacedYear(year=2024)

        assert rule.kind == "placed_year"
        assert rule.year == 2024

    def test_rule_placed_year_out_of_range(self):
        """Test RulePlacedYear rejects year out of range."""
        with pytest.raises(ValidationError):
            RulePlacedYear(year=1950)  # Before 1999

    def test_rule_placed_before(self):
        """Test RulePlacedBefore."""
        rule = RulePlacedBefore(date=date(2020, 1, 1))

        assert rule.kind == "placed_before"
        assert rule.date == date(2020, 1, 1)

    def test_rule_placed_after(self):
        """Test RulePlacedAfter."""
        rule = RulePlacedAfter(date=date(2023, 6, 15))

        assert rule.kind == "placed_after"
        assert rule.date == date(2023, 6, 15)

    def test_rule_state_in(self):
        """Test RuleStateIn with state IDs."""
        from bson import ObjectId

        state_ids = [ObjectId(), ObjectId()]
        rule = RuleStateIn(state_ids=state_ids)

        assert rule.kind == "state_in"
        assert len(rule.state_ids) == 2

    def test_rule_country_is(self):
        """Test RuleCountryIs."""
        country = CountrySelector(name="Belgium")
        rule = RuleCountryIs(country=country)

        assert rule.kind == "country_is"
        assert rule.country.name == "Belgium"

    def test_rule_difficulty_between_valid(self):
        """Test RuleDifficultyBetween with valid range."""
        rule = RuleDifficultyBetween(min=1.5, max=4.0)

        assert rule.kind == "difficulty_between"
        assert rule.min == 1.5
        assert rule.max == 4.0

    def test_rule_difficulty_between_invalid_range(self):
        """Test RuleDifficultyBetween rejects invalid range."""
        with pytest.raises(ValidationError):
            RuleDifficultyBetween(min=6.0, max=7.0)  # Out of 1.0-5.0 range

    def test_rule_terrain_between(self):
        """Test RuleTerrainBetween."""
        rule = RuleTerrainBetween(min=2.0, max=5.0)

        assert rule.kind == "terrain_between"
        assert rule.min == 2.0
        assert rule.max == 5.0

    def test_rule_attributes(self):
        """Test RuleAttributes with multiple attributes."""
        attrs = [
            AttributeSelector(code="dogs", is_positive=True),
            AttributeSelector(code="climbing", is_positive=False),
        ]
        rule = RuleAttributes(attributes=attrs)

        assert rule.kind == "attributes"
        assert len(rule.attributes) == 2


class TestAggregateRules:
    """Test aggregate rule components."""

    def test_rule_agg_sum_difficulty(self):
        """Test RuleAggSumDifficultyAtLeast."""
        rule = RuleAggSumDifficultyAtLeast(min_total=50)

        assert rule.kind == "aggregate_sum_difficulty_at_least"
        assert rule.min_total == 50

    def test_rule_agg_sum_terrain(self):
        """Test RuleAggSumTerrainAtLeast."""
        rule = RuleAggSumTerrainAtLeast(min_total=40)

        assert rule.kind == "aggregate_sum_terrain_at_least"
        assert rule.min_total == 40

    def test_rule_agg_sum_diff_plus_terr(self):
        """Test RuleAggSumDiffPlusTerrAtLeast."""
        rule = RuleAggSumDiffPlusTerrAtLeast(min_total=100)

        assert rule.kind == "aggregate_sum_diff_plus_terr_at_least"
        assert rule.min_total == 100

    def test_rule_agg_sum_altitude(self):
        """Test RuleAggSumAltitudeAtLeast."""
        rule = RuleAggSumAltitudeAtLeast(min_total=5000)

        assert rule.kind == "aggregate_sum_altitude_at_least"
        assert rule.min_total == 5000


class TestLogicalNodes:
    """Test logical AND/OR/NOT nodes."""

    def test_task_and_single_rule(self):
        """Test TaskAnd with single rule."""
        rule = RulePlacedYear(year=2024)
        and_node = TaskAnd(nodes=[rule])

        assert and_node.kind == "and"
        assert len(and_node.nodes) == 1

    def test_task_and_multiple_rules(self):
        """Test TaskAnd with multiple rules."""
        rules = [RulePlacedYear(year=2024), RuleDifficultyBetween(min=1.0, max=3.0)]
        and_node = TaskAnd(nodes=rules)

        assert len(and_node.nodes) == 2

    def test_task_or(self):
        """Test TaskOr with multiple rules."""
        rules = [
            RuleTypeIn(types=[TypeSelector(code="traditional")]),
            RuleTypeIn(types=[TypeSelector(code="multi")]),
        ]
        or_node = TaskOr(nodes=rules)

        assert or_node.kind == "or"
        assert len(or_node.nodes) == 2

    def test_task_not(self):
        """Test TaskNot with single rule."""
        rule = RulePlacedBefore(date=date(2020, 1, 1))
        not_node = TaskNot(node=rule)

        assert not_node.kind == "not"
        assert not_node.node.kind == "placed_before"

    def test_nested_and_or(self):
        """Test nested AND/OR structure."""
        inner_or = TaskOr(
            nodes=[
                RuleTypeIn(types=[TypeSelector(code="traditional")]),
                RuleTypeIn(types=[TypeSelector(code="multi")]),
            ]
        )

        outer_and = TaskAnd(nodes=[inner_or, RuleDifficultyBetween(min=1.0, max=5.0)])

        assert outer_and.kind == "and"
        assert len(outer_and.nodes) == 2
        assert outer_and.nodes[0].kind == "or"


class TestUCLogic:
    """Test UserChallenge logic components."""

    def test_uc_and(self):
        """Test UCAnd with task IDs."""
        from bson import ObjectId

        task_ids = [ObjectId(), ObjectId()]
        uc_and = UCAnd(task_ids=task_ids)

        assert uc_and.kind == "and"
        assert len(uc_and.task_ids) == 2

    def test_uc_or(self):
        """Test UCOr with task IDs."""
        from bson import ObjectId

        task_ids = [ObjectId(), ObjectId(), ObjectId()]
        uc_or = UCOr(task_ids=task_ids)

        assert uc_or.kind == "or"
        assert len(uc_or.task_ids) == 3

    def test_uc_not(self):
        """Test UCNot with single task ID."""
        from bson import ObjectId

        task_id = ObjectId()
        uc_not = UCNot(task_id=task_id)

        assert uc_not.kind == "not"
        assert uc_not.task_id == task_id


class TestTaskExpressionType:
    """Test TaskExpression union type."""

    def test_task_expression_with_rule(self):
        """Test TaskExpression accepts Rule classes."""
        rule: TaskExpression = RulePlacedYear(year=2024)
        assert rule is not None

    def test_task_expression_with_and(self):
        """Test TaskExpression accepts TaskAnd."""
        and_node: TaskExpression = TaskAnd(nodes=[RulePlacedYear(year=2024)])
        assert and_node is not None

    def test_task_expression_with_or(self):
        """Test TaskExpression accepts TaskOr."""
        or_node: TaskExpression = TaskOr(nodes=[RulePlacedYear(year=2024)])
        assert or_node is not None

    def test_task_expression_with_not(self):
        """Test TaskExpression accepts TaskNot."""
        not_node: TaskExpression = TaskNot(node=RulePlacedYear(year=2024))
        assert not_node is not None


class TestUCLogicType:
    """Test UCLogic union type."""

    def test_uc_logic_and(self):
        """Test UCLogic accepts UCAnd."""
        from bson import ObjectId

        uc_and: UCLogic = UCAnd(task_ids=[ObjectId()])
        assert uc_and is not None

    def test_uc_logic_or(self):
        """Test UCLogic accepts UCOr."""
        from bson import ObjectId

        uc_or: UCLogic = UCOr(task_ids=[ObjectId()])
        assert uc_or is not None

    def test_uc_logic_not(self):
        """Test UCLogic accepts UCNot."""
        from bson import ObjectId

        uc_not: UCLogic = UCNot(task_id=ObjectId())
        assert uc_not is not None
