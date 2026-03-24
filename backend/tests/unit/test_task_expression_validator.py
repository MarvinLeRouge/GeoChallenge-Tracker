"""Tests for TaskExpressionValidator (unit tests - no DB required)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId
from pydantic import TypeAdapter

from app.domain.models.challenge_ast import (
    RuleDifficultyBetween,
    RulePlacedYear,
    TaskAnd,
)
from app.services.user_challenge_tasks.task_expression_validator import (
    TaskExpressionValidator,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OID = ObjectId()

# validate_tasks_payload expects the TypeAdapter *class* (it calls TypeAdapter(TaskExpression) internally)
_TA = TypeAdapter


def _identity_preprocess(expr_raw: Any) -> Any:
    return expr_raw


def _identity_normalize(expr_model: Any, index_for_errors: int = 0) -> Any:
    return expr_model


# ---------------------------------------------------------------------------
# validate_task_expression
# ---------------------------------------------------------------------------


class TestValidateTaskExpression:
    """Test TaskExpressionValidator.validate_task_expression.

    NOTE: Most validation branches are unreachable because walk_expression_tree
    is a generator that uses 'return list' for leaf nodes (known bug in compiler).
    Only the aggregate_count > 1 check and the state_in co-validation survive
    the iteration — but even those require walk_expression_tree to yield items.
    In practice, ALL expressions currently return [] (no errors).
    """

    def test_empty_and_returns_no_errors(self):
        validator = TaskExpressionValidator()
        expr = TaskAnd(nodes=[])
        errors = validator.validate_task_expression(expr)
        assert errors == []

    def test_valid_expression_returns_no_errors(self):
        validator = TaskExpressionValidator()
        leaf = RulePlacedYear(year=2022)
        expr = TaskAnd(nodes=[leaf])
        errors = validator.validate_task_expression(expr)
        assert errors == []

    def test_difficulty_min_exceeds_max_detected(self):
        validator = TaskExpressionValidator()
        leaf = RuleDifficultyBetween(min=4.0, max=2.0)
        expr = TaskAnd(nodes=[leaf])
        errors = validator.validate_task_expression(expr)
        assert any("min" in e and "max" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_tasks_payload — structural / early-exit checks
# ---------------------------------------------------------------------------


class TestValidateTasksPayload:
    """Test TaskExpressionValidator.validate_tasks_payload."""

    def test_empty_list_raises(self):
        validator = TaskExpressionValidator()
        with pytest.raises(ValueError, match="non-empty list"):
            validator.validate_tasks_payload(
                "uid", "uc_id", [], _identity_normalize, _identity_preprocess, _TA
            )

    def test_none_list_raises(self):
        validator = TaskExpressionValidator()
        with pytest.raises(ValueError, match="non-empty list"):
            validator.validate_tasks_payload(
                "uid",
                "uc_id",
                None,
                _identity_normalize,
                _identity_preprocess,
                _TA,  # type: ignore[arg-type]
            )

    def test_missing_expression_raises(self):
        validator = TaskExpressionValidator()
        payload = [{"order": 0}]  # no 'expression' key
        with pytest.raises(ValueError, match="expression"):
            validator.validate_tasks_payload(
                "uid", "uc_id", payload, _identity_normalize, _identity_preprocess, _TA
            )

    def test_duplicate_order_raises(self):
        validator = TaskExpressionValidator()
        expr_raw = {"kind": "and", "nodes": [{"kind": "placed_year", "year": 2022}]}
        payload = [
            {"order": 1, "expression": expr_raw},
            {"order": 1, "expression": expr_raw},  # duplicate
        ]
        with pytest.raises(ValueError, match="duplicate order"):
            validator.validate_tasks_payload(
                "uid", "uc_id", payload, _identity_normalize, _identity_preprocess, _TA
            )

    def test_invalid_pydantic_expression_raises(self):
        validator = TaskExpressionValidator()
        payload = [{"order": 0, "expression": {"kind": "totally_unknown_kind"}}]
        with pytest.raises(ValueError, match="invalid expression at index 0"):
            validator.validate_tasks_payload(
                "uid", "uc_id", payload, _identity_normalize, _identity_preprocess, _TA
            )

    def test_negative_min_count_raises(self):
        validator = TaskExpressionValidator()
        expr_raw = {"kind": "and", "nodes": [{"kind": "placed_year", "year": 2022}]}
        payload = [{"order": 0, "expression": expr_raw, "constraints": {"min_count": -1}}]
        with pytest.raises(ValueError, match="min_count"):
            validator.validate_tasks_payload(
                "uid", "uc_id", payload, _identity_normalize, _identity_preprocess, _TA
            )

    def test_zero_min_count_accepted(self):
        validator = TaskExpressionValidator()
        expr_raw = {"kind": "and", "nodes": [{"kind": "placed_year", "year": 2022}]}
        payload = [{"order": 0, "expression": expr_raw, "constraints": {"min_count": 0}}]
        # Must not raise
        validator.validate_tasks_payload(
            "uid", "uc_id", payload, _identity_normalize, _identity_preprocess, _TA
        )

    def test_valid_payload_no_constraints_passes(self):
        validator = TaskExpressionValidator()
        expr_raw = {"kind": "and", "nodes": [{"kind": "placed_year", "year": 2022}]}
        payload = [{"order": 0, "expression": expr_raw}]
        # Must not raise
        validator.validate_tasks_payload(
            "uid", "uc_id", payload, _identity_normalize, _identity_preprocess, _TA
        )

    def test_multiple_items_different_orders_pass(self):
        validator = TaskExpressionValidator()
        expr_raw = {"kind": "and", "nodes": [{"kind": "placed_year", "year": 2022}]}
        payload = [
            {"order": 0, "expression": expr_raw},
            {"order": 1, "expression": expr_raw},
        ]
        validator.validate_tasks_payload(
            "uid", "uc_id", payload, _identity_normalize, _identity_preprocess, _TA
        )

    def test_normalize_func_error_wraps_as_value_error(self):
        """If normalize_func raises, it must be wrapped as ValueError."""
        validator = TaskExpressionValidator()
        expr_raw = {"kind": "and", "nodes": [{"kind": "placed_year", "year": 2022}]}
        payload = [{"order": 0, "expression": expr_raw}]

        def failing_normalize(expr: Any, index_for_errors: int = 0) -> Any:
            raise ValueError("type code not found")

        with pytest.raises(ValueError, match="invalid expression at index 0"):
            validator.validate_tasks_payload(
                "uid", "uc_id", payload, failing_normalize, _identity_preprocess, _TA
            )


# ---------------------------------------------------------------------------
# validate_only_format_response
# ---------------------------------------------------------------------------


class TestValidateOnlyFormatResponse:
    """Test TaskExpressionValidator.validate_only_format_response."""

    def test_success_returns_ok_true(self):
        validator = TaskExpressionValidator()
        expr_raw = {"kind": "and", "nodes": [{"kind": "placed_year", "year": 2022}]}
        payload = [{"order": 0, "expression": expr_raw}]
        result = validator.validate_only_format_response(
            "uid", "uc_id", payload, _identity_normalize, _identity_preprocess, _TA
        )
        assert result["ok"] is True
        assert result["errors"] == []

    def test_value_error_returns_ok_false(self):
        validator = TaskExpressionValidator()
        payload = []  # triggers "non-empty list" ValueError
        result = validator.validate_only_format_response(
            "uid", "uc_id", payload, _identity_normalize, _identity_preprocess, _TA
        )
        assert result["ok"] is False
        assert len(result["errors"]) >= 1
        error = result["errors"][0]
        assert "code" in error
        assert "message" in error

    def test_expression_error_sets_expression_field(self):
        validator = TaskExpressionValidator()
        expr_raw = {"kind": "and", "nodes": [{"kind": "placed_year", "year": 2022}]}
        payload = [{"order": 0, "expression": expr_raw}]

        def failing_normalize(expr: Any, index_for_errors: int = 0) -> Any:
            raise ValueError(f"invalid expression at index {index_for_errors}: bad type")

        result = validator.validate_only_format_response(
            "uid", "uc_id", payload, failing_normalize, _identity_preprocess, _TA
        )
        assert result["ok"] is False
        error = result["errors"][0]
        assert error["field"] == "expression"
        assert error["index"] == 0

    def test_constraints_error_sets_constraints_field(self):
        validator = TaskExpressionValidator()
        expr_raw = {"kind": "and", "nodes": [{"kind": "placed_year", "year": 2022}]}
        payload = [{"order": 0, "expression": expr_raw, "constraints": {"min_count": -5}}]
        result = validator.validate_only_format_response(
            "uid", "uc_id", payload, _identity_normalize, _identity_preprocess, _TA
        )
        assert result["ok"] is False
        error = result["errors"][0]
        assert error["field"] == "constraints"

    def test_pydantic_error_branch(self):
        """Trigger the Pydantic-error branch (lines 213-222) by mocking validate_tasks_payload."""
        from pydantic import TypeAdapter as PA
        from pydantic import ValidationError

        try:
            PA(int).validate_python("not-an-int")
        except ValidationError as e:
            pydantic_err = e

        validator = TaskExpressionValidator()
        with patch.object(validator, "validate_tasks_payload", side_effect=pydantic_err):
            result = validator.validate_only_format_response(
                "uid", "uc_id", [{}], _identity_normalize, _identity_preprocess, _TA
            )
        assert result["ok"] is False
        assert result["errors"][0]["code"] == "pydantic_validation_error"


# ---------------------------------------------------------------------------
# validate_task_expression — mocked walk to cover unreachable branches
# ---------------------------------------------------------------------------


class TestValidateTaskExpressionMockedWalk:
    """Cover branches that require the compiler's walk to yield specific kinds.

    walk_expression_tree has a known bug (return list instead of yield) for leaf
    nodes, making those branches unreachable in production. We mock the walk.
    """

    def _validator_with_walk(self, walk_results):
        validator = TaskExpressionValidator()
        validator.compiler.walk_expression_tree = MagicMock(return_value=iter(walk_results))
        return validator

    def test_type_in_unknown_id_reports_error(self):
        oid = ObjectId()
        type_sel = MagicMock(cache_type_doc_id=oid)
        node = MagicMock()
        node.types = [type_sel]
        validator = self._validator_with_walk([("type_in", node, "and")])
        with patch(
            "app.services.user_challenge_tasks.task_expression_validator.exists_id",
            return_value=False,
        ):
            errors = validator.validate_task_expression(TaskAnd(nodes=[]))
        assert any("type_in" in e for e in errors)

    def test_type_in_known_id_no_error(self):
        oid = ObjectId()
        type_sel = MagicMock(cache_type_doc_id=oid)
        node = MagicMock()
        node.types = [type_sel]
        validator = self._validator_with_walk([("type_in", node, "and")])
        with patch(
            "app.services.user_challenge_tasks.task_expression_validator.exists_id",
            return_value=True,
        ):
            errors = validator.validate_task_expression(TaskAnd(nodes=[]))
        assert errors == []

    def test_size_in_unknown_id_reports_error(self):
        oid = ObjectId()
        size_sel = MagicMock(cache_size_doc_id=oid)
        node = MagicMock()
        node.sizes = [size_sel]
        validator = self._validator_with_walk([("size_in", node, "and")])
        with patch(
            "app.services.user_challenge_tasks.task_expression_validator.exists_id",
            return_value=False,
        ):
            errors = validator.validate_task_expression(TaskAnd(nodes=[]))
        assert any("size_in" in e for e in errors)

    def test_country_is_unknown_id_reports_error(self):
        node = MagicMock()
        node.country.country_id = ObjectId()
        validator = self._validator_with_walk([("country_is", node, "and")])
        with patch(
            "app.services.user_challenge_tasks.task_expression_validator.exists_id",
            return_value=False,
        ):
            errors = validator.validate_task_expression(TaskAnd(nodes=[]))
        assert any("country_is" in e for e in errors)

    def test_state_in_unknown_id_reports_error(self):
        node = MagicMock()
        node.state_ids = [ObjectId()]
        validator = self._validator_with_walk([("state_in", node, "and")])
        with patch(
            "app.services.user_challenge_tasks.task_expression_validator.exists_id",
            return_value=False,
        ):
            errors = validator.validate_task_expression(TaskAnd(nodes=[]))
        assert any("state_in" in e for e in errors)

    def test_state_in_without_country_is_reports_error(self):
        node = MagicMock()
        node.state_ids = [ObjectId()]
        # TaskAnd with no country_is sibling
        expr = TaskAnd(nodes=[])
        validator = TaskExpressionValidator()
        validator.compiler.walk_expression_tree = MagicMock(
            return_value=iter([("state_in", node, "and")])
        )
        with patch(
            "app.services.user_challenge_tasks.task_expression_validator.exists_id",
            return_value=True,
        ):
            with patch.object(validator.compiler, "has_country_is_in_and", return_value=False):
                errors = validator.validate_task_expression(expr)
        assert any("country_is" in e for e in errors)

    def test_attributes_unknown_id_reports_error(self):
        attr = MagicMock()
        attr.cache_attribute_id = 999
        node = MagicMock()
        node.attributes = [attr]
        validator = self._validator_with_walk([("attributes", node, "and")])
        with patch(
            "app.services.user_challenge_tasks.task_expression_validator.exists_attribute_id",
            return_value=False,
        ):
            errors = validator.validate_task_expression(TaskAnd(nodes=[]))
        assert any("attributes" in e for e in errors)

    def test_difficulty_between_min_exceeds_max(self):
        node = MagicMock()
        node.min = 4.0
        node.max = 2.0
        validator = self._validator_with_walk([("difficulty_between", node, "and")])
        errors = validator.validate_task_expression(TaskAnd(nodes=[]))
        assert any("min" in e for e in errors)

    def test_aggregate_under_or_reports_error(self):
        node = MagicMock()
        validator = self._validator_with_walk([("aggregate_count_caches", node, "or")])
        validator.compiler.is_aggregate_kind = MagicMock(return_value=True)
        errors = validator.validate_task_expression(TaskAnd(nodes=[]))
        assert any("aggregate" in e.lower() for e in errors)

    def test_multiple_aggregates_reports_error(self):
        node = MagicMock()
        validator = self._validator_with_walk(
            [
                ("aggregate_count_caches", node, "and"),
                ("aggregate_sum_terrain", node, "and"),
            ]
        )
        validator.compiler.is_aggregate_kind = MagicMock(return_value=True)
        errors = validator.validate_task_expression(TaskAnd(nodes=[]))
        assert any("aggregate" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# validate_tasks_payload — line 158: errors from validate_task_expression
# ---------------------------------------------------------------------------


class TestValidateTasksPayloadWithExpressionErrors:
    def test_expression_errors_raises_value_error(self):
        """Mock validate_task_expression to return errors → triggers line 158."""
        validator = TaskExpressionValidator()
        with patch.object(validator, "validate_task_expression", return_value=["some error"]):
            expr_raw = {"kind": "and", "nodes": [{"kind": "placed_year", "year": 2022}]}
            payload = [{"order": 0, "expression": expr_raw}]
            with pytest.raises(ValueError, match="invalid"):
                validator.validate_tasks_payload(
                    "uid", "uc_id", payload, _identity_normalize, _identity_preprocess, _TA
                )
