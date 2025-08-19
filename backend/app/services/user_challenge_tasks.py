
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Iterable, Union
from datetime import datetime
from bson import ObjectId
from pymongo import UpdateOne

from app.db.mongodb import get_collection
from app.models.challenge_ast import TaskExpression, TaskAnd, TaskOr, TaskNot, RuleAttributes

def _now() -> datetime:
    return datetime.utcnow()

def _ensure_uc_owned(user_id: ObjectId, uc_id: ObjectId) -> Dict[str, Any]:
    ucs = get_collection("user_challenges")
    row = ucs.find_one({"_id": uc_id, "user_id": user_id}, {"_id": 1, "challenge_id": 1})
    if not row:
        raise PermissionError("UserChallenge not found or not owned by user")
    ch = get_collection("challenges").find_one({"_id": row["challenge_id"]}, {"name": 1})
    row["challenge_name"] = (ch or {}).get("name") or "Challenge"
    return row

# ---------- Validation helpers ----------

def _exists_id(coll_name: str, _id: ObjectId) -> bool:
    return get_collection(coll_name).find_one({"_id": _id}, {"_id": 1}) is not None

def _exists_attribute_id(cache_attribute_id: int) -> bool:
    return get_collection("cache_attributes").find_one({"cache_attribute_id": cache_attribute_id}, {"_id": 1}) is not None

def _walk_expr(expr: TaskExpression):
    """Yield (kind, payload) nodes for referential checks."""
    # Bool nodes
    if isinstance(expr, (TaskAnd, TaskOr)):
        for child in expr.nodes:
            yield from _walk_expr(child)
        return
    if isinstance(expr, TaskNot):
        yield from _walk_expr(expr.node)
        return
    # Leaves: use 'kind' attribute
    yield (expr.kind, expr)

def _validate_referentials_expression(expr: TaskExpression) -> List[str]:
    errors: List[str] = []
    for kind, node in _walk_expr(expr):
        if kind == "type_in":
            for oid in node.type_ids:
                if not _exists_id("cache_types", oid):
                    errors.append(f"type_in: unknown cache_type id '{oid}'")
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
        elif kind == "difficulty_between" or kind == "terrain_between":
            if node.min > node.max:
                errors.append(f"{kind}: min must be <= max")
        elif kind == "size_in":
            for oid in node.size_ids:
                if not _exists_id("cache_sizes", oid):
                    errors.append(f"size_in: unknown cache_size id '{oid}'")
        # placed_year/after/before are structurally validated by Pydantic (date/int)
    return errors

def _validate_tasks_payload(user_id: ObjectId, uc_id: ObjectId, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    _ensure_uc_owned(user_id, uc_id)
    errors_per_task: List[Dict[str, Any]] = []
    if len(tasks) > 50:
        return [{"index": -1, "errors": ["too many tasks (max 50)"]}]

    for idx, t in enumerate(tasks):
        err_list: List[str] = []

        # constraints
        constraints = t.get("constraints") or {}
        min_count = constraints.get("min_count")
        if not isinstance(min_count, int) or min_count < 1:
            err_list.append("constraints.min_count must be int >= 1")

        # status domain
        status = t.get("status")
        if status is not None and status not in ("todo", "in_progress", "done"):
            err_list.append("status must be one of: 'todo' | 'in_progress' | 'done'")

        # expression already validated by DTO typing; still re-validate defensively
        expr_payload = t.get("expression")
        try:
            expr = expr_payload if isinstance(expr_payload, dict) else None
            expr_model = TaskExpression.model_validate(expr_payload) if expr_payload is not None else None
        except Exception as e:
            err_list.append(f"expression invalid: {e}")
            expr_model = None

        if expr_model is not None:
            err_list += _validate_referentials_expression(expr_model)

        errors_per_task.append({"index": idx, "errors": err_list})

    return errors_per_task

# ---------- Public API ----------

def list_tasks(user_id: ObjectId, uc_id: ObjectId) -> List[Dict[str, Any]]:
    _ensure_uc_owned(user_id, uc_id)
    coll = get_collection("user_challenge_tasks")
    cur = coll.find({"user_challenge_id": uc_id}).sort([("order", 1), ("_id", 1)])
    out: List[Dict[str, Any]] = []
    for d in cur:
        d["id"] = str(d.pop("_id"))
        out.append(d)
    return out

def put_tasks(user_id: ObjectId, uc_id: ObjectId, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    uc = _ensure_uc_owned(user_id, uc_id)
    coll = get_collection("user_challenge_tasks")

    validation = _validate_tasks_payload(user_id, uc_id, tasks)
    flattened = [e for e in validation if e["errors"]]
    if flattened:
        raise ValueError({"validation": validation})

    existing = list(coll.find({"user_challenge_id": uc_id}))
    existing_by_id = {str(d["_id"]): d for d in existing}

    new_docs: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    now = _now()

    for idx, t in enumerate(tasks):
        doc: Dict[str, Any] = {}
        t_id = str(t.get("id")) if t.get("id") is not None else None
        if t_id:
            if t_id not in existing_by_id:
                raise ValueError({"validation": [{"index": idx, "errors": [f"id '{t_id}' not found for this user_challenge"]}]})
            doc["_id"] = existing_by_id[t_id]["_id"]
        else:
            doc["_id"] = ObjectId()

        seen_ids.add(str(doc["_id"]))
        title = t.get("title") or f"{uc['challenge_name']} - task {idx+1}"
        constraints = t.get("constraints") or {}
        expression = t.get("expression")
        status = t.get("status")

        progress = None
        metrics = None
        if status == "done":
            mc = constraints.get("min_count", 1)
            progress = {"percent": 100, "tasks_done": mc, "tasks_total": mc, "checked_at": now}
            metrics = {"current_count": mc}

        doc.update({
            "user_challenge_id": uc_id,
            "order": idx,
            "title": title,
            "expression": expression,
            "constraints": constraints,
            "status": status or "todo",
            "metrics": metrics,
            "progress": progress,
            "updated_at": now,
        })
        if not t_id:
            doc["created_at"] = now
        new_docs.append(doc)

    try:
        ops: List[UpdateOne] = []
        for d in new_docs:
            ops.append(
                UpdateOne(
                    {"_id": d["_id"], "user_challenge_id": uc_id},
                    {"$set": d, "$setOnInsert": {"created_at": d.get("created_at", now)}},
                    upsert=True
                )
            )
        if ops:
            coll.bulk_write(ops, ordered=True)

        to_delete = [d["_id"] for d in existing if str(d["_id"]) not in seen_ids]
        if to_delete:
            coll.delete_many({"_id": {"$in": to_delete}, "user_challenge_id": uc_id})

    except Exception:
        created_ids = [d["_id"] for d in new_docs if str(d["_id"]) not in existing_by_id]
        if created_ids:
            coll.delete_many({"_id": {"$in": created_ids}, "user_challenge_id": uc_id})
        for d in existing:
            coll.replace_one({"_id": d["_id"]}, d, upsert=True)
        raise

    return list_tasks(user_id, uc_id)

def validate_only(user_id: ObjectId, uc_id: ObjectId, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    _ensure_uc_owned(user_id, uc_id)
    errors = _validate_tasks_payload(user_id, uc_id, tasks)
    ok = all(len(e["errors"]) == 0 for e in errors)
    out_errors = []
    for e in errors:
        out_errors.append({
            "index": e["index"],
            "field": "",
            "code": "ok" if not e["errors"] else "invalid",
            "message": "; ".join(e["errors"]) if e["errors"] else ""
        })
    return {"ok": ok, "errors": out_errors}
