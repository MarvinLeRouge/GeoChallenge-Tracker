from __future__ import annotations
from typing import Any, List, Tuple
from bson import ObjectId

from app.db.mongodb import get_collection
from app.models.challenge_ast import (
    TaskExpression, TaskAnd, TaskOr, TaskNot,
    RuleAttributes
)

# --- existing helpers in your file are preserved ---
# Below: aggregate-aware validation helpers to allow AND-only aggregate leaves.

def _exists_id(coll_name: str, _id: ObjectId) -> bool:
    return get_collection(coll_name).find_one({"_id": _id}, {"_id": 1}) is not None

def _exists_attribute_id(cache_attribute_id: int) -> bool:
    return get_collection("attributes").find_one({"id": cache_attribute_id}, {"_id": 1}) is not None

def _walk_expr(expr: TaskExpression):
    if isinstance(expr, (TaskAnd, TaskOr)):
        parent = expr.kind
        for ch in expr.nodes:
            for k, n, pk in _walk_expr(ch):
                yield (k, n, pk if pk else parent)
        return
    if isinstance(expr, TaskNot):
        for k, n, pk in _walk_expr(expr.node):
            yield (k, n, "not")
        return
    # leaf
    return [(expr.kind, expr, None)]

def _is_aggregate_kind(kind: str) -> bool:
    return kind in (
        "aggregate_sum_difficulty_at_least",
        "aggregate_sum_terrain_at_least",
        "aggregate_sum_diff_plus_terr_at_least",
        "aggregate_sum_altitude_at_least",
    )

def validate_task_expression(expr: TaskExpression) -> List[str]:
    """
    Validate referentials and structure for a TaskExpression, including aggregate leaves.
    Rules (MVP):
      - aggregate leaves allowed only under AND (not under OR/NOT)
      - at most one aggregate leaf per task
      - standard referential checks for cache-level leaves
    """
    errors: List[str] = []
    aggregate_count = 0

    for kind, node, parent in _walk_expr(expr):
        if _is_aggregate_kind(kind):
            aggregate_count += 1
            if parent in ("or", "not"):
                errors.append(f"{kind}: aggregate rules are only supported under AND (not under {parent})")
            continue

        if kind == "type_in":
            for oid in getattr(node, "type_ids", []):
                if not _exists_id("cache_types", oid):
                    errors.append(f"type_in: unknown cache_type id '{oid}'")
        elif kind == "size_in":
            for oid in getattr(node, "size_ids", []):
                if not _exists_id("cache_sizes", oid):
                    errors.append(f"size_in: unknown cache_size id '{oid}'")
        elif kind == "state_in":
            for oid in getattr(node, "state_ids", []):
                if not _exists_id("states", oid):
                    errors.append(f"state_in: unknown state id '{oid}'")
        elif kind == "country_is":
            cid = getattr(node, "country_id", None)
            if cid and not _exists_id("countries", cid):
                errors.append(f"country_is: unknown country id '{cid}'")
        elif kind == "attributes":
            for i, a in enumerate(getattr(node, "attributes", [])):
                if not _exists_attribute_id(a.cache_attribute_id):
                    errors.append(f"attributes[{i}].cache_attribute_id unknown '{a.cache_attribute_id}'")
        elif kind in ("difficulty_between", "terrain_between"):
            if node.min > node.max:
                errors.append(f"{kind}: min must be <= max")

    if aggregate_count > 1:
        errors.append("Only a single aggregate rule is supported per task (MVP)")

    return errors
