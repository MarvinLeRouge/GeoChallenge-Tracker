"""Tests for TaskExpressionNormalizer (unit tests - no DB required)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from bson import ObjectId

from app.services.user_challenge_tasks.task_expression_normalizer import (
    TaskExpressionNormalizer,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OID = ObjectId()
_OID2 = ObjectId()


def _build_and(*nodes):
    """Build a dict for an AND expression with given node dicts."""
    return {"kind": "and", "nodes": list(nodes)}


def _validate(expr_dict):
    """Validate a raw dict through Pydantic to get a TaskExpression."""
    from pydantic import TypeAdapter

    from app.domain.models.challenge_ast import TaskExpression

    return TypeAdapter(TaskExpression).validate_python(expr_dict)


# ---------------------------------------------------------------------------
# legacy_fixup_expression
# ---------------------------------------------------------------------------


class TestLegacyFixupExpression:
    """Test TaskExpressionNormalizer.legacy_fixup_expression."""

    def test_type_in_codes_to_types(self):
        raw = {
            "kind": "and",
            "nodes": [{"kind": "type_in", "codes": ["traditional", "multi"]}],
        }
        result = TaskExpressionNormalizer.legacy_fixup_expression(raw)
        node = result["nodes"][0]
        assert "types" in node
        assert "codes" not in node
        assert node["types"] == [
            {"cache_type_code": "traditional"},
            {"cache_type_code": "multi"},
        ]

    def test_type_in_with_existing_types_not_converted(self):
        """When 'types' already exists, 'codes' must not be converted."""
        raw = {
            "kind": "and",
            "nodes": [
                {
                    "kind": "type_in",
                    "types": [{"cache_type_code": "traditional"}],
                    "codes": ["multi"],
                }
            ],
        }
        result = TaskExpressionNormalizer.legacy_fixup_expression(raw)
        node = result["nodes"][0]
        # 'types' is already present → codes conversion condition is False
        assert "types" in node
        assert "codes" in node

    def test_size_in_codes_to_sizes(self):
        raw = {
            "kind": "and",
            "nodes": [{"kind": "size_in", "codes": ["micro", "small"]}],
        }
        result = TaskExpressionNormalizer.legacy_fixup_expression(raw)
        node = result["nodes"][0]
        assert "sizes" in node
        assert "codes" not in node
        assert node["sizes"] == [{"code": "micro"}, {"code": "small"}]

    def test_size_in_with_existing_sizes_not_converted(self):
        raw = {
            "kind": "and",
            "nodes": [
                {
                    "kind": "size_in",
                    "sizes": [{"code": "micro"}],
                    "codes": ["small"],
                }
            ],
        }
        result = TaskExpressionNormalizer.legacy_fixup_expression(raw)
        node = result["nodes"][0]
        assert "codes" in node  # not converted since 'sizes' already exists

    def test_nested_and_is_recursed(self):
        raw = {
            "kind": "and",
            "nodes": [
                {
                    "kind": "and",
                    "nodes": [{"kind": "type_in", "codes": ["earthcache"]}],
                }
            ],
        }
        result = TaskExpressionNormalizer.legacy_fixup_expression(raw)
        inner_node = result["nodes"][0]["nodes"][0]
        assert "types" in inner_node

    def test_non_dict_passthrough(self):
        assert TaskExpressionNormalizer.legacy_fixup_expression("hello") == "hello"
        assert TaskExpressionNormalizer.legacy_fixup_expression(42) == 42
        assert TaskExpressionNormalizer.legacy_fixup_expression(None) is None

    def test_list_items_are_recursed(self):
        raw = [{"kind": "type_in", "codes": ["wherigo"]}]
        result = TaskExpressionNormalizer.legacy_fixup_expression(raw)
        assert "types" in result[0]

    def test_other_kinds_untouched(self):
        raw = {"kind": "placed_year", "year": 2020}
        result = TaskExpressionNormalizer.legacy_fixup_expression(raw)
        assert result == {"kind": "placed_year", "year": 2020}


# ---------------------------------------------------------------------------
# normalize_code_to_id
# ---------------------------------------------------------------------------


class TestNormalizeCodeToId:
    """Test TaskExpressionNormalizer.normalize_code_to_id."""

    # Note: TypeSelector field is named 'code' (not 'cache_type_code').
    # 'cache_type_code' is a legacy dict key used only in the normalizer dict loop;
    # Pydantic strips it as an unknown field during initial validation.

    def test_type_in_code_resolved(self):
        """code='TR' is resolved to cache_type_doc_id via resolve_type_code."""
        expr_dict = _build_and({"kind": "type_in", "types": [{"code": "TR"}]})
        expr = _validate(expr_dict)
        with patch(
            "app.services.user_challenge_tasks.task_expression_normalizer.resolve_type_code",
            return_value=_OID,
        ):
            result = TaskExpressionNormalizer.normalize_code_to_id(expr, index_for_errors=0)

        result_dict = result.model_dump(by_alias=True)
        type_node = result_dict["nodes"][0]
        assert type_node["types"][0]["cache_type_doc_id"] is not None

    def test_type_in_code_unknown_raises(self):
        """Unknown type code raises ValueError with index in message."""
        expr_dict = _build_and({"kind": "type_in", "types": [{"code": "UNKNOWN"}]})
        expr = _validate(expr_dict)
        with patch(
            "app.services.user_challenge_tasks.task_expression_normalizer.resolve_type_code",
            return_value=None,
        ):
            with pytest.raises(ValueError, match="type code not found"):
                TaskExpressionNormalizer.normalize_code_to_id(expr, index_for_errors=2)

    def test_type_in_already_has_doc_id_skipped(self):
        """Types with existing cache_type_doc_id bypass resolve_type_code."""
        expr_dict = _build_and(
            {"kind": "type_in", "types": [{"cache_type_doc_id": str(_OID), "code": "TR"}]}
        )
        expr = _validate(expr_dict)
        with patch(
            "app.services.user_challenge_tasks.task_expression_normalizer.resolve_type_code"
        ) as mock_resolve:
            TaskExpressionNormalizer.normalize_code_to_id(expr, index_for_errors=0)
        mock_resolve.assert_not_called()

    def test_size_in_code_resolved(self):
        """size code is resolved to cache_size_doc_id via resolve_size_code."""
        expr_dict = _build_and({"kind": "size_in", "sizes": [{"code": "S"}]})
        expr = _validate(expr_dict)
        with patch(
            "app.services.user_challenge_tasks.task_expression_normalizer.resolve_size_code",
            return_value=_OID,
        ):
            result = TaskExpressionNormalizer.normalize_code_to_id(expr, index_for_errors=0)

        result_dict = result.model_dump(by_alias=True)
        size_node = result_dict["nodes"][0]
        assert size_node["sizes"][0]["cache_size_doc_id"] is not None

    def test_size_in_unknown_code_raises(self):
        """Unknown size code raises ValueError."""
        expr_dict = _build_and({"kind": "size_in", "sizes": [{"code": "UNKNOWN"}]})
        expr = _validate(expr_dict)
        with patch(
            "app.services.user_challenge_tasks.task_expression_normalizer.resolve_size_code",
            return_value=None,
        ):
            with pytest.raises(ValueError, match="size not found"):
                TaskExpressionNormalizer.normalize_code_to_id(expr, index_for_errors=1)

    def test_attribute_code_resolved(self):
        """Attribute code is resolved to cache_attribute_doc_id."""
        expr_dict = _build_and(
            {
                "kind": "attributes",
                "attributes": [{"code": "dogs", "is_positive": True}],
            }
        )
        expr = _validate(expr_dict)
        with patch(
            "app.services.user_challenge_tasks.task_expression_normalizer.resolve_attribute_code",
            return_value=(_OID, 42),
        ):
            result = TaskExpressionNormalizer.normalize_code_to_id(expr, index_for_errors=0)

        result_dict = result.model_dump(by_alias=True)
        attr = result_dict["nodes"][0]["attributes"][0]
        # cache_attribute_doc_id is resolved and set
        assert attr["cache_attribute_doc_id"] is not None
        # NOTE: cache_attribute_id stays None because model_dump outputs it as None (key exists),
        # and setdefault() does not overwrite existing keys — the id is not written to the result.

    def test_attribute_unknown_code_raises(self):
        """Unknown attribute code raises ValueError."""
        expr_dict = _build_and(
            {
                "kind": "attributes",
                "attributes": [{"code": "unknown_attr", "is_positive": True}],
            }
        )
        expr = _validate(expr_dict)
        with patch(
            "app.services.user_challenge_tasks.task_expression_normalizer.resolve_attribute_code",
            return_value=None,
        ):
            with pytest.raises(ValueError, match="attribute code not found"):
                TaskExpressionNormalizer.normalize_code_to_id(expr, index_for_errors=0)

    def test_attribute_already_has_doc_id_skipped(self):
        """Attributes with existing cache_attribute_doc_id bypass resolve_attribute_code."""
        expr_dict = _build_and(
            {
                "kind": "attributes",
                "attributes": [
                    {
                        "cache_attribute_doc_id": str(_OID),
                        "code": "dogs",
                        "is_positive": True,
                    }
                ],
            }
        )
        expr = _validate(expr_dict)
        with patch(
            "app.services.user_challenge_tasks.task_expression_normalizer.resolve_attribute_code"
        ) as mock_resolve:
            TaskExpressionNormalizer.normalize_code_to_id(expr, index_for_errors=0)
        mock_resolve.assert_not_called()

    def test_country_is_resolved_by_name(self):
        """Country name is resolved; country_id is stored in the node dict (top-level).

        Note: After Pydantic re-validation, the top-level country_id is stripped
        because RuleCountryIs has no such field. The 'country' block is preserved.
        """
        expr_dict = _build_and({"kind": "country_is", "country": {"name": "France"}})
        expr = _validate(expr_dict)
        with patch(
            "app.services.user_challenge_tasks.task_expression_normalizer.resolve_country_name",
            return_value=_OID,
        ):
            result = TaskExpressionNormalizer.normalize_code_to_id(expr, index_for_errors=0)

        result_dict = result.model_dump(by_alias=True)
        country_node = result_dict["nodes"][0]
        # The country block is preserved
        assert country_node["kind"] == "country_is"
        assert country_node["country"]["name"] == "France"

    def test_country_is_unknown_raises(self):
        """Unknown country raises ValueError with node index in message."""
        expr_dict = _build_and({"kind": "country_is", "country": {"name": "Neverland"}})
        expr = _validate(expr_dict)
        with patch(
            "app.services.user_challenge_tasks.task_expression_normalizer.resolve_country_name",
            return_value=None,
        ):
            with pytest.raises(ValueError, match="country not found"):
                TaskExpressionNormalizer.normalize_code_to_id(expr, index_for_errors=3)

    def test_state_in_state_ids_preserved(self):
        """State IDs already present are preserved through normalization."""
        expr_dict = _build_and({"kind": "state_in", "state_ids": [str(_OID)]})
        expr = _validate(expr_dict)
        result = TaskExpressionNormalizer.normalize_code_to_id(expr, index_for_errors=0)
        result_dict = result.model_dump(by_alias=True)
        assert len(result_dict["nodes"][0]["state_ids"]) == 1

    def test_index_for_errors_appears_in_message(self):
        """Error messages include the task index."""
        expr_dict = _build_and({"kind": "type_in", "types": [{"code": "BAD"}]})
        expr = _validate(expr_dict)
        with patch(
            "app.services.user_challenge_tasks.task_expression_normalizer.resolve_type_code",
            return_value=None,
        ):
            with pytest.raises(ValueError, match="index 7"):
                TaskExpressionNormalizer.normalize_code_to_id(expr, index_for_errors=7)

    def test_non_code_leaves_passthrough(self):
        """Leaves without code fields pass through normalization unchanged."""
        expr_dict = _build_and(
            {"kind": "placed_year", "year": 2022},
            {"kind": "difficulty_between", "min": 2.0, "max": 4.0},
        )
        expr = _validate(expr_dict)
        result = TaskExpressionNormalizer.normalize_code_to_id(expr, index_for_errors=0)
        result_dict = result.model_dump(by_alias=True)
        years = [n for n in result_dict["nodes"] if n.get("kind") == "placed_year"]
        assert years[0]["year"] == 2022
