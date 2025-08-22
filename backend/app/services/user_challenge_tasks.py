# backend/app/services/user_challenge_tasks.py

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime
from bson import ObjectId
import re
from pydantic import BaseModel, Field, ValidationError, TypeAdapter
from app.core.bson_utils import PyObjectId
from app.db.mongodb import get_collection

# ==== AST imports (must match your models) ====
from app.models.challenge_ast import (
    TaskExpression,
    TaskAnd, TaskOr, TaskNot,
    RuleTypeIn, RuleSizeIn, RulePlacedYear, RulePlacedBefore, RulePlacedAfter,
    RuleStateIn, RuleCountryIs, RuleDifficultyBetween, RuleTerrainBetween,
    RuleAttributes,
    # Aggregate leaves
    RuleAggSumDifficultyAtLeast, RuleAggSumTerrainAtLeast,
    RuleAggSumDiffPlusTerrAtLeast, RuleAggSumAltitudeAtLeast,
)

# ==== DTO-like models used by services ====
class PatchTaskItem(BaseModel):
    _id: Optional[PyObjectId] = None
    user_challenge_id: PyObjectId
    order: int = 0
    expression: TaskExpression
    constraints: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None

# --------------------------------------------------------------------------------------
# Helpers (validation + referentials) — unified & extended to support aggregate rules
# --------------------------------------------------------------------------------------

def _exists_id(coll_name: str, oid: ObjectId) -> bool:
    if not isinstance(oid, ObjectId):
        try:
            oid = ObjectId(str(oid))
        except Exception:
            return False
    return get_collection(coll_name).count_documents({"_id": oid}, limit=1) == 1

def _exists_attribute_id(attr_id: int) -> bool:
    return get_collection("cache_attributes").count_documents(
        {"cache_attribute_id": int(attr_id)}, limit=1
    ) >= 1

def _walk_expr(expr: TaskExpression):
    """Yield (kind, node, parent_kind) for structure validation."""
    if isinstance(expr, (TaskAnd, TaskOr)):
        parent = expr.kind
        for child in expr.nodes:
            for k, n, pk in _walk_expr(child):
                yield (k, n, pk if pk is not None else parent)
        return
    if isinstance(expr, TaskNot):
        for k, n, pk in _walk_expr(expr.node):
            yield (k, n, "not")
        return
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
    Extended validation:
    - referentials (types, sizes, states, country, attributes)
    - numeric ranges
    - aggregates: AND-only (not under OR/NOT), at most 1 aggregate per task
    """
    errors: List[str] = []
    aggregate_count = 0

    for kind, node, parent in _walk_expr(expr):
        if _is_aggregate_kind(kind):
            aggregate_count += 1
            if parent in ("or", "not"):
                errors.append(f"{kind}: aggregate rules are only supported under AND (not under {parent})")
            # check min_total presence & type via Pydantic already; nothing else here
            continue

        if kind == "type_in":
            for oid in node.type_ids:
                if not _exists_id("cache_types", oid):
                    errors.append(f"type_in: unknown cache_type id '{oid}'")
        elif kind == "size_in":
            for oid in node.size_ids:
                if not _exists_id("cache_sizes", oid):
                    errors.append(f"size_in: unknown cache_size id '{oid}'")
        elif kind == "state_in":
            for oid in node.state_ids:
                if not _exists_id("states", oid):
                    errors.append(f"state_in: unknown state id '{oid}'")
        elif kind == "country_is":
            if not _exists_id("countries", node.country_id):
                errors.append(f"country_is: unknown country id '{node.country_id}'")
        elif kind == "attributes":
            for i, a in enumerate(node.attributes):
                if not _exists_attribute_id(a.cache_attribute_id):
                    errors.append(f"attributes[{i}].cache_attribute_id unknown '{a.cache_attribute_id}'")
        elif kind in ("difficulty_between", "terrain_between"):
            if node.min > node.max:
                errors.append(f"{kind}: min must be <= max")
        # placed_year/before/after validated by pydantic types

    if aggregate_count > 1:
        errors.append("Only a single aggregate rule is supported per task (MVP)")

    return errors

# --------------------------------------------------------------------------------------
# Public API kept from BEFORE: list_tasks / put_tasks / validate_only
# --------------------------------------------------------------------------------------

def list_tasks(user_id: ObjectId, uc_id: ObjectId) -> Dict[str, Any]:
    coll = get_collection("user_challenge_tasks")
    cur = coll.find(
        {"user_challenge_id": uc_id},
        sort=[("order", 1), ("_id", 1)]
    )

    items: List[Dict[str, Any]] = []
    for d in cur:
        # title est requis côté TaskOut -> fallback si absent
        title = d.get("title") or "Untitled task"
        items.append({
            "id": d["_id"],  # TaskOut.id (PyObjectId géré par tes encoders)
            "order": d.get("order", 0),
            "title": title,
            "expression": d.get("expression"),
            "constraints": d.get("constraints", {}),
            "status": d.get("status"),                  # optionnel dans TaskOut
            "metrics": d.get("metrics"),
            "progress": d.get("progress"),
            "last_evaluated_at": d.get("last_evaluated_at"),
            "updated_at": d.get("updated_at"),
            "created_at": d.get("created_at"),
        })

    return items

def validate_only(user_id: ObjectId, uc_id: ObjectId, tasks_payload: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate without writing. Returns { ok: bool, errors: [...] }.
    """
    def _mk_err(index: int, field: str, code: str, message: str) -> Dict[str, Any]:
        return {"index": index, "field": field, "code": code, "message": message}

    try:
        _validate_tasks_payload(user_id, uc_id, tasks_payload)

        return {"ok": True, "errors": []}
    except ValidationError as e:
        # Pydantic validation of the AST structure / types
        msg = "; ".join([err.get("msg", "validation error") for err in getattr(e, "errors", lambda: [])()] or [str(e)])

        return {"ok": False, "errors": [_mk_err(0, "expression", "pydantic_validation_error", msg)]}
    except Exception as e:
        # Our _validate_tasks_payload raises ValueError with messages like "invalid expression at index i: ...",
        # or "constraints.min_count ... (index i)". Extract the index if present.
        s = str(e)
        m = re.search(r"index\s+(\d+)", s)
        idx = int(m.group(1)) if m else 0
        # Try to infer the field mentioned in the message, default to expression
        field = "constraints" if "constraints" in s else "expression"
        code = "invalid_expression" if "expression" in s else "invalid_payload"

        return {"ok": False, "errors": [_mk_err(idx, field, code, s)]}

def put_tasks(user_id: ObjectId, uc_id: ObjectId, tasks_payload: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Idempotent PUT of tasks for a given user_challenge.
    - Validates expressions (including aggregates)
    - Replaces existing tasks set (by uc_id) with new set (ordered)
    - Returns {"items": [TaskOut, ...]} to match TasksListResponse
    """
    # Validate first (raises on error)
    _validate_tasks_payload(user_id, uc_id, tasks_payload)

    coll = get_collection("user_challenge_tasks")
    # Strategy: delete existing tasks for uc_id, then insert the new list (ordered)
    coll.delete_many({"user_challenge_id": uc_id})

    # Prepare docs
    to_insert = []
    now = datetime.utcnow()
    for i, item in enumerate(tasks_payload):
        # id facultatif dans l'entrée (update); sinon on génère
        _maybe_id = item.get("id") or item.get("_id")
        doc_id = ObjectId(str(_maybe_id)) if _maybe_id else ObjectId()

        # title requis côté TaskOut -> fallback propre
        title = item.get("title") or f"Task #{i+1}"

        doc = {
            "_id": doc_id,
            "user_challenge_id": uc_id,
            "order": int(item.get("order", i)),
            "title": title,
            "expression": item["expression"],
            "constraints": item.get("constraints", {}),
            "status": item.get("status") or "todo",
            "metrics": item.get("metrics", {}),
            "notes": item.get("notes"),
            "last_evaluated_at": None,
            "created_at": now,
            "updated_at": now,
        }
        to_insert.append(doc)

    if to_insert:
        coll.insert_many(to_insert, ordered=True)

    # Read-back in order and map to TaskOut shape (id, order, title, ...)
    cur = coll.find({"user_challenge_id": uc_id}).sort([("order", 1), ("_id", 1)])
    items: List[Dict[str, Any]] = []
    for d in cur:
        items.append({
            "id": d["_id"],  # TaskOut.id: PyObjectId (laisser l'ObjectId, FastAPI saura l’encoder)
            "order": d.get("order", 0),
            "title": d.get("title"),
            "expression": d.get("expression"),
            "constraints": d.get("constraints", {}),
            "status": d.get("status"),
            "metrics": d.get("metrics"),
            "progress": d.get("progress"),
            "last_evaluated_at": d.get("last_evaluated_at"),
            "updated_at": d.get("updated_at"),
            "created_at": d.get("created_at"),
        })

    return items

# --------------------------------------------------------------------------------------
# Internal validation utils (payload-level)
# --------------------------------------------------------------------------------------

def _validate_tasks_payload(user_id: ObjectId, uc_id: ObjectId, tasks_payload: List[Dict[str, Any]]) -> None:
    """
    Raises Exception on first error; used by both validate_only & put_tasks.
    """
    if not isinstance(tasks_payload, list) or len(tasks_payload) == 0:
        raise ValueError("tasks_payload must be a non-empty list")

    # Validate & collect expressions
    seen_orders = set()
    for i, item in enumerate(tasks_payload):
        # order uniqueness / monotonicity (basic check)
        order_val = int(item.get("order", i))
        if order_val in seen_orders:
            raise ValueError(f"duplicate order '{order_val}' in tasks payload")
        seen_orders.add(order_val)

        # pydantic-parse expression first (will ensure structure & types)
        expr_raw = item.get("expression")
        if expr_raw is None:
            raise ValueError("each task must have an 'expression'")
        try:
            # TaskExpression est un Union[...] -> utiliser un TypeAdapter en v2
            expr_model = TypeAdapter(TaskExpression).validate_python(expr_raw)
        except ValidationError as e:
            raise ValueError(f"invalid expression at index {i}: {e}")

        # NEW: extended validation (aggregates + referentials)
        errs = validate_task_expression(expr_model)
        if errs:
            raise ValueError(f"expression at index {i} invalid: {errs}")

        # constraints basic sanity (min_count >= 0 if provided)
        constraints = item.get("constraints") or {}
        if "min_count" in constraints:
            try:
                mc = int(constraints["min_count"])
                if mc < 0:
                    raise ValueError
            except Exception:
                raise ValueError(f"constraints.min_count must be a non-negative integer (index {i})")

    # Optional: verify uc_id belongs to user? (depends on your security model)
    # get_collection("user_challenges").find_one({"_id": uc_id, "user_id": user_id}) ...

