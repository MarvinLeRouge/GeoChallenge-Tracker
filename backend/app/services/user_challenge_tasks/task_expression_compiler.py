# backend/app/services/user_challenge_tasks/task_expression_compiler.py
# AST expression compilation to MongoDB filters — exact preservation of the logic.

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.domain.models.challenge_ast import (
    RuleCountryIs,
    TaskAnd,
    TaskExpression,
    TaskNot,
    TaskOr,
)


class TaskExpressionCompiler:
    """AST expression compiler to MongoDB filters.

    Description:
        Exact preservation of the existing compile_expression_to_cache_match logic.
        No behavioral changes — purely code reorganization.
    """

    @staticmethod
    def compile_expression_to_cache_match(expr: TaskExpression) -> dict[str, Any]:
        """Compile an AST expression to a Mongo `caches` filter.

        Description:
            FUNCTION IDENTICAL TO THE ORIGINAL — handles AND/OR/NOT for supported leaves;
            ignores aggregate leaves (handled elsewhere).

        Args:
            expr: Already-validated Pydantic expression.

        Returns:
            dict: Mongo filter (may contain `$and/$or/$nor`).
        """

        def _leaf_to_match(leaf: Any) -> dict[str, Any]:
            k = getattr(leaf, "kind", None)

            if k == "type_in":
                # canonical: node.type_ids (list of OIDs)
                ids = [oid for oid in (getattr(leaf, "type_ids", None) or [])]
                return {"type_id": {"$in": ids}} if ids else {}

            if k == "size_in":
                ids = [oid for oid in (getattr(leaf, "size_ids", None) or [])]
                return {"size_id": {"$in": ids}} if ids else {}

            if k == "placed_year":
                y = int(leaf.year)
                return {"placed_year": y}

            if k == "placed_before":
                d = leaf.date
                return {"placed_at": {"$lt": d}}

            if k == "placed_after":
                d = leaf.date
                return {"placed_at": {"$gt": d}}

            if k == "difficulty_between":
                return {"difficulty": {"$gte": leaf.min, "$lte": leaf.max}}

            if k == "terrain_between":
                return {"terrain": {"$gte": leaf.min, "$lte": leaf.max}}

            if k == "country_is":
                return {"country_id": leaf.country_id}

            if k == "state_in":
                ids = [oid for oid in (getattr(leaf, "state_ids", None) or [])]
                return {"state_id": {"$in": ids}} if ids else {}

            if k == "attributes":
                # AND-ed list of attributes (all must match)
                clauses: list[dict[str, Any]] = []
                for a in leaf.attributes:
                    # prefer cache_attribute_doc_id if present, otherwise numeric id
                    attr_doc_id = getattr(a, "cache_attribute_doc_id", None) or getattr(
                        a, "attribute_doc_id", None
                    )
                    num_id = getattr(a, "cache_attribute_id", None)
                    is_pos = bool(getattr(a, "is_positive", True))
                    sub: dict[str, Any] = {"attributes": {"$elemMatch": {"is_positive": is_pos}}}
                    if attr_doc_id:
                        sub["attributes"]["$elemMatch"]["attribute_doc_id"] = attr_doc_id
                    elif num_id is not None:
                        sub["attributes"]["$elemMatch"]["cache_attribute_id"] = int(num_id)
                    # if only "code" is present => forbidden here (must have been normalized first)
                    clauses.append(sub)
                return {"$and": clauses} if clauses else {}

            # Aggregates: do not participate in the "cache" filter (computed by progress/metrics)
            if k in {
                "aggregate_sum_difficulty_at_least",
                "aggregate_sum_terrain_at_least",
                "aggregate_sum_diff_plus_terr_at_least",
                "aggregate_sum_altitude_at_least",
            }:
                return {}

            # Default: no filter
            return {}

        def _node(expr_node: Any) -> dict[str, Any]:
            if isinstance(expr_node, TaskAnd):
                parts = [_node(n) for n in expr_node.nodes]
                parts = [p for p in parts if p]  # strip empties
                return {"$and": parts} if parts else {}

            if isinstance(expr_node, TaskOr):
                parts = [_node(n) for n in expr_node.nodes]
                parts = [p for p in parts if p]
                return {"$or": parts} if parts else {}

            if isinstance(expr_node, TaskNot):
                inner = _node(expr_node.node)
                return {"$nor": [inner]} if inner else {}

            # Leaf
            return _leaf_to_match(expr_node)

        return _node(expr)

    @staticmethod
    def has_country_is_in_and(nodes: Iterable[Any]) -> bool:
        """Test whether a `country_is` node is present in an AND.

        FUNCTION IDENTICAL TO THE ORIGINAL _has_country_is.

        Args:
            nodes: Sibling nodes.

        Returns:
            bool: True if `country_is` is found.
        """
        for n in nodes:
            if isinstance(n, RuleCountryIs):
                return True
            # If nested AND, check recursively
            if isinstance(n, TaskAnd) and TaskExpressionCompiler.has_country_is_in_and(n.nodes):
                return True
        return False

    @staticmethod
    def walk_expression_tree(expr: TaskExpression):
        """Iterate (kind, node, parent_kind) for structural validation purposes.

        FUNCTION IDENTICAL TO THE ORIGINAL _walk_expr.

        Args:
            expr: Expression to traverse.

        Returns:
            Iterable[tuple[str, Any, str|None]]: Triplets (kind, node, parent).
        """
        if isinstance(expr, (TaskAnd, TaskOr)):
            parent = expr.kind
            for child in expr.nodes:
                for k, n, pk in TaskExpressionCompiler.walk_expression_tree(child):
                    yield (k, n, pk if pk is not None else parent)
            return
        if isinstance(expr, TaskNot):
            for k, n, _pk in TaskExpressionCompiler.walk_expression_tree(expr.node):
                yield (k, n, "not")
            return
        return [(expr.kind, expr, None)]

    @staticmethod
    def is_aggregate_kind(kind: str) -> bool:
        """Indicate whether `kind` corresponds to an aggregate leaf.

        FUNCTION IDENTICAL TO THE ORIGINAL _is_aggregate_kind.

        Args:
            kind: Rule name.

        Returns:
            bool: True if aggregate.
        """
        return kind in (
            "aggregate_sum_difficulty_at_least",
            "aggregate_sum_terrain_at_least",
            "aggregate_sum_diff_plus_terr_at_least",
            "aggregate_sum_altitude_at_least",
            "aggregate_count_distinct_countries_at_least",
            "aggregate_dt_matrix_complete",
        )
