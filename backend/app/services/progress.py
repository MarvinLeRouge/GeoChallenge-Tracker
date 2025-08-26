# backend/app/services/progress.py

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from app.db.mongodb import get_collection
from app.core.utils import *
from app.services.query_builder import compile_and_only

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

def evaluate_progress(user_id: ObjectId, uc_id: ObjectId, force = False) -> Dict[str, Any]:
    """Evaluate tasks for a UC and insert a snapshot in 'progress'."""
    _ensure_uc_owned(user_id, uc_id)
    tasks = _get_tasks_for_uc(uc_id)
    snapshots: List[Dict[str, Any]] = []
    sum_current = 0
    sum_min = 0
    tasks_supported = 0
    tasks_done = 0
    uc_statuses = get_collection("user_challenges").find_one(
        {"_id": uc_id},
        {"status": 1, "computed_status": 1 }
    )
    uc_status = (uc_statuses or {}).get("status")
    uc_computed_status = (uc_statuses or {}).get("computed_status")
    if (not force) and (uc_computed_status == "completed" or uc_status == "completed"):
        # Renvoyer le dernier snapshot existant, sans recalcul ni insertion
        last = get_collection("progress").find_one(
            {"user_challenge_id": uc_id},
            sort=[("checked_at", -1), ("created_at", -1)]
        )
        if last:
            return last  # même shape que vos snapshots persistés
        # S'il n'y a pas encore de snapshot, on retombe sur le calcul normal

    for t in tasks:
        min_count = int(((t.get("constraints") or {}).get("min_count") or 0))
        title = t.get("title") or "Task"
        order = int(t.get("order") or 0)
        status = (t.get("status") or "todo").lower()
        expr = t.get("expression") or {}

        if status == "done" and not force:
            snap = {
                "task_id": t["_id"],
                "order": order,
                "title": title,
                "status": status,
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
            sig, match_caches, supported, notes, agg_spec = compile_and_only(expr)
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
                tic = utcnow()
                current = _count_found_caches_matching(user_id, match_caches)
                ms = int((utcnow() - tic).total_seconds() * 1000)

                # base percent on min_count
                bounded = min(current, min_count) if min_count > 0 else current
                count_percent = (100.0 * (bounded / min_count)) if min_count > 0 else 100.0
                new_status = ("done" if current >= min_count else status)
                task_id = t["_id"]
                t["status"] = new_status
                if status != "done":
                    get_collection("user_challenge_tasks").update_one(
                        {"_id": task_id},
                        {"$set": {
                            "status": new_status,
                            "last_evaluated_at": utcnow(),
                            "updated_at": utcnow(),
                        }}
                    )

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
                    "status": t["status"],
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
    aggregate_percent = round(aggregate_percent, 1)
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
        "created_at": now(),
    }
    if(uc_computed_status != "completed") and (tasks_done == tasks_supported):
        new_status = "completed"
        get_collection("user_challenges").update_one(
            {"_id": uc_id},
            {"$set": {
                "computed_status": new_status,
                "status": new_status,
                "updated_at": utcnow(),
            }}
        )
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

