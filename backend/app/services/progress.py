# backend/app/services/progress.py

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from app.db.mongodb import get_collection
from app.core.utils import now
from app.services.referentials_cache import _resolve_attribute_code, _resolve_type_code, _resolve_size_code, _resolve_size_name

# ---------- Helpers ----------

def _ensure_uc_owned(user_id: ObjectId, uc_id: ObjectId) -> Dict[str, Any]:
    ucs = get_collection("user_challenges")
    row = ucs.find_one({"_id": uc_id, "user_id": user_id}, {"_id": 1})
    if not row:
        raise PermissionError("UserChallenge not found or not owned by user")
    return row

def _get_tasks_for_uc(uc_id: ObjectId) -> List[Dict[str, Any]]:
    coll = get_collection("user_challenge_tasks")
    return list(coll.find({"user_challenge_id": uc_id}).sort([("order", 1), ("_id", 1)]))

def _attr_id_by_cache_attr_id(cache_attribute_id: int) -> Optional[ObjectId]:
    row = get_collection("cache_attributes").find_one(
        {"cache_attribute_id": cache_attribute_id}, {"_id": 1}
    )
    return row["_id"] if row else None

def _mk_date(dt_or_str: Any) -> datetime:
    # Accept date, datetime, or ISO string
    if isinstance(dt_or_str, datetime):
        return dt_or_str
    if isinstance(dt_or_str, date):
        # interpret as midnight
        return datetime(dt_or_str.year, dt_or_str.month, dt_or_str.day)
    if isinstance(dt_or_str, str):
        try:
            # allow date-only or datetime formats
            if len(dt_or_str) == 10:
                y, m, d = [int(x) for x in dt_or_str.split("-")]
                return datetime(y, m, d)
            return datetime.fromisoformat(dt_or_str)
        except Exception:
            pass
    raise ValueError(f"Invalid date value: {dt_or_str!r}")

def _flatten_and_nodes(expr: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """Return list of leaf nodes if expression is AND-only; otherwise None."""
    if not isinstance(expr, dict):
        return None
    kind = expr.get("kind")
    if kind == "and":
        nodes = expr.get("nodes") or []
        leaves: List[Dict[str, Any]] = []
        for n in nodes:
            sub = _flatten_and_nodes(n)
            if sub is None:
                return None
            leaves.extend(sub)
        return leaves
    elif kind in ("or", "not"):
        return None
    else:
        # assume leaf
        return [expr]

def _extract_aggregate_spec(leaves: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (aggregate_spec, cache_leaves). Only one aggregate leaf supported (MVP)."""
    agg = None
    cache_leaves: List[Dict[str, Any]] = []
    for lf in leaves:
        k = lf.get("kind")
        if k in (
            "aggregate_sum_difficulty_at_least",
            "aggregate_sum_terrain_at_least",
            "aggregate_sum_diff_plus_terr_at_least",
            "aggregate_sum_altitude_at_least",
        ):
            if agg is None:
                if "min_total" not in lf or lf["min_total"] is None:
                    # ignore malformed aggregate leaf
                    continue
                if k == "aggregate_sum_difficulty_at_least":
                    agg = {"kind": "difficulty", "min_total": int(lf["min_total"])}
                elif k == "aggregate_sum_terrain_at_least":
                    agg = {"kind": "terrain", "min_total": int(lf["min_total"])}
                elif k == "aggregate_sum_diff_plus_terr_at_least":
                    agg = {"kind": "diff_plus_terr", "min_total": int(lf["min_total"])}
                elif k == "aggregate_sum_altitude_at_least":
                    agg = {"kind": "altitude", "min_total": int(lf["min_total"])}
            # ignore additional aggregate leaves (handled in validator)
        else:
            cache_leaves.append(lf)
    return agg, cache_leaves

def _compile_leaf_to_cache_match(leaf: Dict[str, Any]) -> List[Tuple[str, Any]]:
    """Return list of (field, condition) pairs to be AND'ed together, targeting the 'cache.' namespace."""
    k = leaf.get("kind")
    out: List[Tuple[str, Any]] = []
    if k == "type_in":
        ids = leaf.get("type_ids") or []
        if not ids and leaf.get("codes"):
            for code in leaf.get("codes"):
                id = _resolve_type_code(code)
                if id:
                    ids.append(id)
        out.append(("type_id", {"$in": ids}))
    elif k == "size_in":
        ids = leaf.get("size_ids") or []
        if not ids and leaf.get("codes"):
            for code in leaf.get("codes"):
                id = _resolve_size_code(code)
                if id:
                    ids.append(id)
        out.append(("size_id", {"$in": ids}))
    elif k == "country_is":
        cid = leaf.get("country_id")
        if cid:
            out.append(("country_id", cid))
    elif k == "state_in":
        ids = leaf.get("state_ids") or []
        out.append(("state_id", {"$in": ids}))
    elif k == "placed_year":
        y = leaf.get("year") or leaf.get("value")
        if y is not None:
            y = int(y)
            start = datetime(y, 1, 1)
            end = datetime(y + 1, 1, 1)
            out.append(("placed_at", {"$gte": start, "$lt": end}))
    elif k == "placed_before":
        d = leaf.get("date") or leaf.get("value")
        if d is not None:
            out.append(("placed_at", {"$lt": _mk_date(d)}))
    elif k == "placed_after":
        d = leaf.get("date") or leaf.get("value")
        if d is not None:
            out.append(("placed_at", {"$gt": _mk_date(d)}))
    elif k == "difficulty_between":
        lo = leaf.get("min"); hi = leaf.get("max")
        if lo is not None and hi is not None:
            out.append(("difficulty", {"$gte": float(lo), "$lte": float(hi)}))
    elif k == "terrain_between":
        lo = leaf.get("min"); hi = leaf.get("max")
        if lo is not None and hi is not None:
            out.append(("terrain", {"$gte": float(lo), "$lte": float(hi)}))
    elif k == "attributes":
        # expect 'attributes': [{cache_attribute_id, is_positive, attribute_doc_id?}]
        attrs = leaf.get("attributes") or []
        print("attrs", attrs)
        for a in attrs:
            attr_doc_id = a.get("cache_attribute_doc_id")
            if not attr_doc_id and a.get("code"):
                attr_doc_id, _ = _resolve_attribute_code(a.get("code"))
            if not attr_doc_id:

                # can't resolve: leave no condition (won't match anything)
                # better to add impossible match to ensure count==0
                out.append(("attributes", {"$elemMatch": {"attribute_doc_id": ObjectId(), "is_positive": True}}))
            else:
                out.append(("attributes", {"$elemMatch": {
                    "attribute_doc_id": attr_doc_id,
                    "is_positive": bool(a.get("is_positive", True))
                }}))
    # unknown leaves are ignored (safe default)
    print("_compile_leaf_to_cache_match", "leaf", leaf, "out", out)
    return out

def _compile_and_only(expr: Dict[str, Any]) -> Tuple[str, Dict[str, Any], bool, List[str], Optional[Dict[str, Any]]]:
    """
    Returns: (signature, MATCH_CACHES, supported, notes, aggregate_spec)
    - signature: stable-ish string
    - MATCH_CACHES: dict fields without the 'cache.' prefix
    - supported: False if OR/NOT present
    - notes: diagnostics
    - aggregate_spec: optional dict like {'kind':'difficulty','min_total':30000}
    """
    leaves = _flatten_and_nodes(expr)
    if leaves is None:
        return ("unsupported:or-not", {}, False, ["or/not unsupported in MVP"], None)
    parts: List[Tuple[str, Any]] = []
    # extract aggregate and keep only cache leaves for matching
    agg_spec, cache_leaves = _extract_aggregate_spec(leaves)
    leaves = cache_leaves
    for lf in leaves:
        parts.extend(_compile_leaf_to_cache_match(lf))
    # Build $and in dict form
    match: Dict[str, Any] = {}
    for field, cond in parts:
        key = field  # will be prefixed by 'cache.' later in pipeline
        if key in match:
            if not isinstance(match[key], list):
                match[key] = [match[key]]
            match[key].append(cond)
        else:
            match[key] = cond
    # signature = sorted keys + repr of values (simple)
    try:
        import json as _json
        signature = "and:" + _json.dumps({"leaves": leaves}, default=str, sort_keys=True)
    except Exception:
        signature = "and:compiled"
    return (signature, match, True, [], agg_spec)

def _count_found_caches_matching(user_id: ObjectId, match_caches: Dict[str, Any]) -> int:
    fc = get_collection("found_caches")
    pipeline: List[Dict[str, Any]] = [
        {"$match": {"user_id": user_id}},
        {"$lookup": {
            "from": "caches",
            "localField": "cache_id",
            "foreignField": "_id",
            "as": "cache"
        }},
        {"$unwind": "$cache"},
    ]
    # Apply match on cache.*
    conds: List[Dict[str, Any]] = []
    for field, cond in match_caches.items():
        if isinstance(cond, list):
            # multiple conditions for the same field => all must hold
            for c in cond:
                conds.append({f"cache.{field}": c})
        else:
            conds.append({f"cache.{field}": cond})
    if conds:
        pipeline.append({"$match": {"$and": conds}})
    pipeline.append({"$count": "current_count"})
    rows = list(fc.aggregate(pipeline, allowDiskUse=False))
    return int(rows[0]["current_count"]) if rows else 0

def _aggregate_total(user_id: ObjectId, match_caches: Dict[str, Any], spec: Dict[str, Any]) -> int:
    """Compute aggregate total according to spec over user's found caches matching the filters."""
    fc = get_collection("found_caches")
    pipeline: List[Dict[str, Any]] = [
        {"$match": {"user_id": user_id}},
        {"$lookup": {
            "from": "caches",
            "localField": "cache_id",
            "foreignField": "_id",
            "as": "cache"
        }},
        {"$unwind": "$cache"},
    ]
    # Apply match on cache.*
    conds: List[Dict[str, Any]] = []
    for field, cond in match_caches.items():
        if isinstance(cond, list):
            for c in cond:
                conds.append({f"cache.{field}": c})
        else:
            conds.append({f"cache.{field}": cond})
    if conds:
        pipeline.append({"$match": {"$and": conds}})

    k = spec["kind"]
    if k == "difficulty":
        score_expr = {"$ifNull": ["$cache.difficulty", 0]}
    elif k == "terrain":
        score_expr = {"$ifNull": ["$cache.terrain", 0]}
    elif k == "diff_plus_terr":
        score_expr = {"$add": [
            {"$ifNull": ["$cache.difficulty", 0]},
            {"$ifNull": ["$cache.terrain", 0]},
        ]}
    elif k == "altitude":
        score_expr = {"$ifNull": ["$cache.elevation", 0]}
    else:
        return 0

    pipeline += [
        {"$project": {"score": score_expr}},
        {"$group": {"_id": None, "total": {"$sum": "$score"}}},
    ]
    rows = list(fc.aggregate(pipeline, allowDiskUse=False))
    return int(rows[0]["total"]) if rows else 0

# ---------- Public API ----------

def evaluate_progress(user_id: ObjectId, uc_id: ObjectId) -> Dict[str, Any]:
    """Evaluate tasks for a UC and insert a snapshot in 'progress'."""
    _ensure_uc_owned(user_id, uc_id)
    tasks = _get_tasks_for_uc(uc_id)
    snapshots: List[Dict[str, Any]] = []
    sum_current = 0
    sum_min = 0
    tasks_supported = 0
    tasks_done = 0

    for t in tasks:
        min_count = int(((t.get("constraints") or {}).get("min_count") or 0))
        title = t.get("title") or "Task"
        order = int(t.get("order") or 0)
        status = (t.get("status") or "todo").lower()
        expr = t.get("expression") or {}

        if status == "done":
            snap = {
                "task_id": t["_id"],
                "order": order,
                "title": title,
                "supported_for_progress": True,
                "compiled_signature": "override:done",
                "min_count": min_count,
                "current_count": min_count,
                "percent": 100.0,
                "notes": ["user override: done"],
                "evaluated_in_ms": 0,
                "last_evaluated_at": now(),
                "updated_at": t.get("updated_at"),
                "created_at": t.get("created_at"),
            }
        else:
            sig, match_caches, supported, notes, agg_spec = _compile_and_only(expr)
            if not supported:
                snap = {
                    "task_id": t["_id"],
                    "order": order,
                    "title": title,
                    "supported_for_progress": False,
                    "compiled_signature": sig,
                    "min_count": min_count,
                    "current_count": 0,
                    "percent": 0.0,
                    "notes": notes,
                    "evaluated_in_ms": 0,
                    "last_evaluated_at": now(),
                    "updated_at": t.get("updated_at"),
                    "created_at": t.get("created_at"),
                }
            else:
                tic = datetime.utcnow()
                current = _count_found_caches_matching(user_id, match_caches)
                ms = int((datetime.utcnow() - tic).total_seconds() * 1000)

                # base percent on min_count
                bounded = min(current, min_count) if min_count > 0 else current
                count_percent = (100.0 * (bounded / min_count)) if min_count > 0 else 100.0

                # aggregate handling
                aggregate_total = None
                aggregate_target = None
                aggregate_percent = None
                aggregate_unit = None
                if agg_spec:
                    aggregate_total = _aggregate_total(user_id, match_caches, agg_spec)
                    aggregate_target = int(agg_spec.get("min_total", 0)) or None
                    if aggregate_target and aggregate_target > 0:
                        aggregate_percent = max(0.0, min(100.0, 100.0 * (float(aggregate_total) / float(aggregate_target))))
                    else:
                        aggregate_percent = None
                    # unit: altitude -> meters, otherwise points
                    aggregate_unit = "meters" if agg_spec.get("kind") == "altitude" else "points"

                # final percent rule (MVP):
                # - if both count & aggregate constraints exist -> percent = min(count_percent, aggregate_percent)
                # - if only count -> count_percent
                # - if only aggregate -> aggregate_percent or 0 if None
                if agg_spec and min_count > 0:
                    final_percent = min(count_percent, (aggregate_percent or 0.0))
                elif agg_spec and min_count == 0:
                    final_percent = (aggregate_percent or 0.0)
                else:
                    final_percent = count_percent

                snap = {
                    "task_id": t["_id"],
                    "order": order,
                    "title": title,
                    "supported_for_progress": True,
                    "compiled_signature": sig,
                    "min_count": min_count,
                    "current_count": current,
                    "percent": final_percent,
                    # per-task aggregate block for DTO:
                    "aggregate": (
                        None if not agg_spec else {
                            "total": aggregate_total,
                            "target": aggregate_target or 0,
                            "unit": aggregate_unit or "points",
                        }
                    ),
                    "notes": notes,
                    "evaluated_in_ms": ms,
                    "last_evaluated_at": now(),
                    "updated_at": t.get("updated_at"),
                    "created_at": t.get("created_at"),
                }

        if snap["supported_for_progress"]:
            tasks_supported += 1
            sum_min += max(0, min_count)
            bounded_for_sum = min(snap["current_count"], min_count) if min_count > 0 else snap["current_count"]
            sum_current += bounded_for_sum
            if bounded_for_sum >= min_count and min_count > 0:
                tasks_done += 1

        snapshots.append(snap)

    aggregate_percent = (100.0 * (sum_current / sum_min)) if sum_min > 0 else 0.0
    doc = {
        "user_challenge_id": uc_id,
        "checked_at": now(),
        "aggregate": {
            "percent": aggregate_percent,
            "tasks_done": tasks_done,
            "tasks_total": tasks_supported,
            "checked_at": now(),
        },
        "tasks": snapshots,
        "message": None,
        "engine_version": "mvp-and-agg-1",
        "created_at": now(),
    }
    get_collection("progress").insert_one(doc)
    # enrich for response
    doc["id"] = str(doc.get("_id")) if "_id" in doc else None
    return doc

def get_latest_and_history(
    user_id: ObjectId,
    uc_id: ObjectId,
    limit: int = 10,
    before: Optional[datetime] = None,
) -> Dict[str, Any]:
    _ensure_uc_owned(user_id, uc_id)
    coll = get_collection("progress")
    q = {"user_challenge_id": uc_id}
    if before:
        q["checked_at"] = {"$lt": before}
    cur = coll.find(q).sort([("checked_at", DESCENDING)]).limit(limit)
    items = list(cur)
    latest = items[0] if items else None
    history = items[1:] if len(items) > 1 else []
    def _summarize(d: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "checked_at": d["checked_at"],
            "aggregate": d["aggregate"],
        }
    res = {
        "latest": latest,
        "history": [_summarize(h) for h in history],
    }
    if latest and "_id" in latest:
        latest["id"] = str(latest["_id"])
    return res

def evaluate_new_progress(
    user_id: ObjectId,
    *,
    include_pending: bool = False,
    limit: int = 50,
    since: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Evaluate first snapshot for UC that have none yet (accepted by default)."""
    ucs = get_collection("user_challenges")
    progress = get_collection("progress")

    st = ["accepted"] + (["pending"] if include_pending else [])
    q: Dict[str, Any] = {"user_id": user_id, "status": {"$in": st}}
    if since:
        q["created_at"] = {"$gte": since}

    # candidates
    cand = list(ucs.find(q, {"_id": 1}).sort([("_id", ASCENDING)]).limit(limit*3))
    uc_ids = [c["_id"] for c in cand]

    # remove those already in progress
    if not uc_ids:
        return {"evaluated_count": 0, "skipped_count": 0, "uc_ids": []}
    present = set(d["user_challenge_id"] for d in progress.find({"user_challenge_id": {"$in": uc_ids}}, {"user_challenge_id": 1}))
    todo = [uc_id for uc_id in uc_ids if uc_id not in present][:limit]

    evaluated_ids: List[str] = []
    for uc_id in todo:
        evaluate_progress(user_id, uc_id)
        evaluated_ids.append(str(uc_id))

    return {
        "evaluated_count": len(evaluated_ids),
        "skipped_count": len(uc_ids) - len(evaluated_ids),
        "uc_ids": evaluated_ids,
    }

