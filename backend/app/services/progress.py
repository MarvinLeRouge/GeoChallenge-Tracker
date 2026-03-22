# backend/app/services/progress.py
# Computes progress snapshots per UserChallenge, updates statuses, and provides history access.

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from app.core.utils import now, utcnow
from app.db.mongodb import get_collection
from app.services.query_builder import compile_and_only

# ---------- Helpers ----------


async def _ensure_uc_owned(user_id: ObjectId, uc_id: ObjectId) -> dict[str, Any]:
    """Verify that the UC belongs to the given user.

    Description:
        Checks the existence of `user_challenges[_id=uc_id, user_id=user_id]`. Raises if not owned.

    Args:
        user_id (ObjectId): User identifier.
        uc_id (ObjectId): UserChallenge identifier.

    Returns:
        dict: Minimal document (_id) if authorized.

    Raises:
        PermissionError: If the UC does not belong to the user (or does not exist).
    """
    ucs = await get_collection("user_challenges")
    row = await ucs.find_one({"_id": uc_id, "user_id": user_id}, {"_id": 1})
    if not row:
        raise PermissionError("UserChallenge not found or not owned by user")
    return row


async def _get_tasks_for_uc(uc_id: ObjectId) -> list[dict[str, Any]]:
    """Retrieve tasks for a UC (sorted).

    Args:
        uc_id (ObjectId): UserChallenge identifier.

    Returns:
        list[dict]: Tasks sorted by `order`, then `_id`.
    """
    coll_uctasks = await get_collection("user_challenge_tasks")
    cursor = coll_uctasks.find({"user_challenge_id": uc_id}).sort([("order", 1), ("_id", 1)])
    result = await cursor.to_list(length=None)
    return result


async def _attr_id_by_cache_attr_id(cache_attribute_id: int) -> ObjectId | None:
    """Resolve the ObjectId of a cache attribute by its global numeric ID.

    Args:
        cache_attribute_id (int): Global numeric identifier (e.g. 71).

    Returns:
        ObjectId | None: `cache_attributes` document reference or None.
    """
    coll_attrs = await get_collection("cache_attributes")
    row = await coll_attrs.find_one({"cache_attribute_id": cache_attribute_id}, {"_id": 1})
    return row["_id"] if row else None


async def _count_found_caches_matching(user_id: ObjectId, match_caches: dict[str, Any]) -> int:
    """Count a user’s found caches matching given `caches.*` conditions.

    Description:
        Pipeline: filters by `user_id` on `found_caches`, `$lookup` into `caches`, `$unwind`,
        applies `match_caches` conditions on `cache.*`, then `$count`.

    Args:
        user_id (ObjectId): Target user.
        match_caches (dict): AND conditions on `caches` fields.

    Returns:
        int: Number of matching found caches.
    """
    fc = await get_collection("found_caches")
    pipeline: list[Mapping[str, Any]] = [
        {"$match": {"user_id": user_id}},
        {
            "$lookup": {
                "from": "caches",
                "localField": "cache_id",
                "foreignField": "_id",
                "as": "cache",
            }
        },
        {"$unwind": "$cache"},
    ]

    # Apply match on cache.*
    conds: list[Mapping[str, Any]] = []
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
    cursor = fc.aggregate(pipeline, allowDiskUse=False)
    rows = await cursor.to_list(length=None)
    return int(rows[0]["current_count"]) if rows else 0


async def _aggregate_total(
    user_id: ObjectId, match_caches: dict[str, Any], spec: dict[str, Any]
) -> int:
    """Compute an aggregated sum (difficulty, terrain, diff+terr, altitude).

    Description:
        Filters via `match_caches` then sums the requested metric:
        - `difficulty` → sum of difficulties
        - `terrain` → sum of terrains
        - `diff_plus_terr` → sum of (difficulty + terrain)
        - `altitude` → sum of altitudes

    Args:
        user_id (ObjectId): User.
        match_caches (dict): AND conditions on `caches`.
        spec (dict): Aggregate specification (`{‘kind’: ..., ‘min_total’: int}`).

    Returns:
        int: Aggregated total (0 if `kind` is unknown).
    """
    fc = await get_collection("found_caches")
    pipeline: list[Mapping[str, Any]] = [
        {"$match": {"user_id": user_id}},
        {
            "$lookup": {
                "from": "caches",
                "localField": "cache_id",
                "foreignField": "_id",
                "as": "cache",
            }
        },
        {"$unwind": "$cache"},
    ]
    # Apply match on cache.*
    conds: list[Mapping[str, Any]] = []
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
        score_expr = {
            "$add": [
                {"$ifNull": ["$cache.difficulty", 0]},
                {"$ifNull": ["$cache.terrain", 0]},
            ]
        }
    elif k == "altitude":
        score_expr = {"$ifNull": ["$cache.elevation", 0]}
    else:
        return 0

    pipeline += [
        {"$project": {"score": score_expr}},
        {"$group": {"_id": None, "total": {"$sum": "$score"}}},
    ]
    cursor = fc.aggregate(pipeline, allowDiskUse=False)
    rows = await cursor.to_list(length=None)
    return int(rows[0]["total"]) if rows else 0


async def _nth_found_date(user_id: ObjectId, match_caches: dict[str, Any], n: int) -> date | None:
    if n <= 0:
        return None
    fc = await get_collection("found_caches")
    pipeline: list[Mapping[str, Any]] = [
        {"$match": {"user_id": user_id}},
        {
            "$lookup": {
                "from": "caches",
                "localField": "cache_id",
                "foreignField": "_id",
                "as": "cache",
            }
        },
        {"$unwind": "$cache"},
    ]
    and_conds: list[Mapping[str, Any]] = []
    for field, cond in match_caches.items():
        if isinstance(cond, list):
            for c in cond:
                and_conds.append({f"cache.{field}": c})
        else:
            and_conds.append({f"cache.{field}": cond})
    if and_conds:
        pipeline.append({"$match": {"$and": and_conds}})
    pipeline += [
        {"$sort": {"found_date": ASCENDING}},
        {"$skip": max(0, n - 1)},
        {"$limit": 1},
        {"$project": {"_id": 0, "found_date": 1}},
    ]
    cursor = fc.aggregate(pipeline, allowDiskUse=False)
    rows = await cursor.to_list(length=1)
    return rows[0]["found_date"] if rows else None


# convenience alias
async def _first_found_date(user_id: ObjectId, match_caches: dict[str, Any]) -> date | None:
    return await _nth_found_date(user_id, match_caches, 1)


# ---------- Public API ----------


async def evaluate_progress(user_id: ObjectId, uc_id: ObjectId, force=False) -> dict[str, Any]:
    """Evaluate tasks for a UC and insert a progress snapshot.

    Description:
        - Verifies UC ownership (`_ensure_uc_owned`).\n
        - If `force=False` and the UC is already `completed`, returns the last snapshot (if any).\n
        - For each task, compiles the expression (`compile_and_only`), counts matching found caches,
          optionally updates the task status, and computes aggregates and percentage.\n
        - Computes the global aggregate and creates a `progress` document. If all supported tasks are `done`,
          updates `user_challenges` to `completed` (both declared and computed statuses).

    Args:
        user_id (ObjectId): User.
        uc_id (ObjectId): UserChallenge.
        force (bool): Force recalculation even if the UC is completed.

    Returns:
        dict: Inserted snapshot document (with `id` added for the response).
    """
    await _ensure_uc_owned(user_id, uc_id)
    tasks = await _get_tasks_for_uc(uc_id)
    coll_uctasks = await get_collection("user_challenge_tasks")
    snapshots: list[dict[str, Any]] = []
    sum_current = 0
    sum_min = 0
    tasks_supported = 0
    tasks_done = 0
    coll_uc = await get_collection("user_challenges")
    uc_statuses = await coll_uc.find_one({"_id": uc_id}, {"status": 1, "computed_status": 1})
    uc_status = (uc_statuses or {}).get("status")
    uc_computed_status = (uc_statuses or {}).get("computed_status")
    if (not force) and (uc_computed_status == "completed" or uc_status == "completed"):
        # Return the last existing snapshot without recalculating or inserting
        coll_progress = await get_collection("progress")
        last = await coll_progress.find_one(
            {"user_challenge_id": uc_id}, sort=[("checked_at", -1), ("created_at", -1)]
        )
        if last:
            return last  # same shape as persisted snapshots
        # If no snapshot exists yet, fall through to normal calculation

    for t in tasks:
        min_count = int((t.get("constraints") or {}).get("min_count") or 0)
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
                current = await _count_found_caches_matching(user_id, match_caches)
                ms = int((utcnow() - tic).total_seconds() * 1000)

                # base percent on min_count
                bounded = min(current, min_count) if min_count > 0 else current
                count_percent = (100.0 * (bounded / min_count)) if min_count > 0 else 100.0
                new_status = "done" if current >= min_count else status
                task_id = t["_id"]
                t["status"] = new_status
                if status != "done":
                    await coll_uctasks.update_one(
                        {"_id": task_id},
                        {
                            "$set": {
                                "status": new_status,
                                "last_evaluated_at": utcnow(),
                                "updated_at": utcnow(),
                            }
                        },
                    )

                # aggregate handling
                aggregate_total = None
                aggregate_target = None
                aggregate_percent = None
                aggregate_unit = None
                if agg_spec:
                    aggregate_total = await _aggregate_total(user_id, match_caches, agg_spec)
                    aggregate_target = int(agg_spec.get("min_total", 0)) or None
                    if aggregate_target and aggregate_target > 0:
                        aggregate_percent = max(
                            0.0,
                            min(
                                100.0,
                                100.0 * (float(aggregate_total) / float(aggregate_target)),
                            ),
                        )
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
                    final_percent = aggregate_percent or 0.0
                else:
                    final_percent = count_percent

                # --- progress dates persisted on the task ---
                task_id = t["_id"]
                min_count = int((t.get("constraints") or {}).get("min_count") or 0)

                # 2.1 start_found_at: first matching found cache
                start_dt = await _first_found_date(user_id, match_caches)
                if start_dt and not t.get("start_found_at"):
                    await coll_uctasks.update_one(
                        {"_id": task_id},
                        {"$set": {"start_found_at": start_dt, "updated_at": utcnow()}},
                    )
                    t["start_found_at"] = start_dt  # in-memory update for subsequent use

                # 2.2 completed_at: date of the min_count-th matching find
                completed_dt = None
                if min_count > 0 and current >= min_count:
                    completed_dt = await _nth_found_date(user_id, match_caches, min_count)

                # persist the date if reached, or clear it if it was set but no longer valid
                if completed_dt:
                    if t.get("completed_at") != completed_dt:
                        await coll_uctasks.update_one(
                            {"_id": task_id},
                            {
                                "$set": {
                                    "completed_at": completed_dt,
                                    "updated_at": utcnow(),
                                }
                            },
                        )
                        t["completed_at"] = completed_dt
                else:
                    if t.get("completed_at") is not None:
                        await coll_uctasks.update_one(
                            {"_id": task_id},
                            {"$set": {"completed_at": None, "updated_at": utcnow()}},
                        )
                        t["completed_at"] = None

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
                        None
                        if not agg_spec
                        else {
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
            bounded_for_sum = (
                min(snap["current_count"], min_count) if min_count > 0 else snap["current_count"]
            )
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
    if (uc_computed_status != "completed") and (tasks_done == tasks_supported):
        new_status = "completed"
        await coll_uc.update_one(
            {"_id": uc_id},
            {
                "$set": {
                    "computed_status": new_status,
                    "status": new_status,
                    "updated_at": utcnow(),
                }
            },
        )
    coll_progress = await get_collection("progress")
    await coll_progress.insert_one(doc)
    # enrich for response
    doc["id"] = str(doc.get("_id")) if "_id" in doc else None

    return doc


async def get_latest_and_history(
    user_id: ObjectId,
    uc_id: ObjectId,
    limit: int = 10,
    before: datetime | None = None,
) -> dict[str, Any]:
    """Retrieve the latest snapshot and a short history.

    Description:
        Fetches up to `limit` snapshots (descending order), returns the most recent one and a
        summarized history (date + aggregate). `before` enables backward pagination.

    Args:
        user_id (ObjectId): User.
        uc_id (ObjectId): UserChallenge.
        limit (int): Maximum history size (≥1).
        before (datetime | None): Exclusive time cursor.

    Returns:
        dict: `{‘latest’: dict | None, ‘history’: list[dict]}`.
    """
    q: dict[str, Any] = {}
    await _ensure_uc_owned(user_id, uc_id)
    coll = await get_collection("progress")
    q = {"user_challenge_id": uc_id}
    if before:
        q["checked_at"] = {"$lt": before}
    cursor = coll.find(q).sort([("checked_at", DESCENDING)]).limit(limit)
    items = await cursor.to_list(length=limit)
    latest = items[0] if items else None
    history = items[1:] if len(items) > 1 else []

    # --- enrich 'latest' with per-task ETA + global ETA ---
    if latest:
        # map (task_id -> {start_found_at, completed_at, current min_count})
        tasks_coll = await get_collection("user_challenge_tasks")
        cursor = tasks_coll.find(
            {"user_challenge_id": uc_id},
            {"_id": 1, "start_found_at": 1, "completed_at": 1, "constraints": 1},
        )
        tdocs = await cursor.to_list(length=None)

        dates_by_tid: dict[ObjectId, dict[str, Any]] = {
            d["_id"]: {
                "start": d.get("start_found_at"),
                "done": d.get("completed_at"),
                "min_count": int((d.get("constraints") or {}).get("min_count") or 0),
            }
            for d in tdocs
        }

        # compute per-task ETA from the 'latest' snapshot relative to today
        now_dt = now()
        eta_values: list[datetime] = []
        for it in latest.get("tasks") or []:
            tid = it.get("task_id")
            current_count = int(it.get("current_count") or 0)
            # min_count: snapshot value takes precedence, fallback to task doc
            min_c = int(it.get("min_count") or dates_by_tid.get(tid, {}).get("min_count") or 0)
            info = dates_by_tid.get(tid) or {}
            start = info.get("start")
            done = info.get("done")

            eta = None
            if done:
                # completed -> ETA is fixed
                # found_date is a 'date'; normalize to 'datetime' for the response
                eta = datetime(done.year, done.month, done.day)  # 00:00 local/UTC per now()
            elif start and current_count >= 1 and min_c > 0:
                # in progress -> extrapolation
                # speed = (cur - 1) / days elapsed since the first find
                elapsed_days = max((now_dt.date() - start.date()).days, 1)
                speed = float(current_count - 1) / float(elapsed_days)
                remaining = max(0, min_c - current_count)
                if speed > 0.0 and remaining > 0:
                    eta_days = int(math.ceil(remaining / speed))
                    eta_date = now_dt.date() + timedelta(days=eta_days)
                    eta = datetime(eta_date.year, eta_date.month, eta_date.day)
                # otherwise eta = None

            # inject per-task ETA into the 'latest' object (for DTO)
            it["estimated_completion_at"] = eta

            if eta:
                eta_values.append(eta)

        # global ETA = max of non-None ETAs
        latest.setdefault("aggregate", {})
        latest["estimated_completion_at"] = max(eta_values) if eta_values else None

    def _summarize(d: dict[str, Any]) -> dict[str, Any]:
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


async def evaluate_new_progress(
    user_id: ObjectId,
    *,
    include_pending: bool = False,
    limit: int = 50,
    since: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate a first snapshot for UCs that have no progress yet.

    Description:
        Selects the user’s UCs with status `accepted` (and `pending` if requested),
        optionally created since `since`, **skips** those already having `progress`,
        then evaluates up to `limit` items.

    Args:
        user_id (ObjectId): User.
        include_pending (bool): Include `pending` UCs.
        limit (int): Maximum number of UCs to process.
        since (datetime | None): Creation date filter.

    Returns:
        dict: `{‘evaluated_count’: int, ‘skipped_count’: int, ‘uc_ids’: list[str]}`.
    """
    ucs = await get_collection("user_challenges")
    progress = await get_collection("progress")

    st = ["accepted"] + (["pending"] if include_pending else [])
    q: dict[str, Any] = {"user_id": user_id, "status": {"$in": st}}
    if since:
        q["created_at"] = {"$gte": since}

    # candidates
    cursor = ucs.find(q, {"_id": 1}).sort([("_id", ASCENDING)]).limit(limit * 3)
    cand = await cursor.to_list(length=limit * 3)
    uc_ids = [c["_id"] for c in cand]

    # remove those already in progress
    if not uc_ids:
        return {"evaluated_count": 0, "skipped_count": 0, "uc_ids": []}
    cursor = progress.find({"user_challenge_id": {"$in": uc_ids}}, {"user_challenge_id": 1})
    present = {d["user_challenge_id"] async for d in cursor}
    todo = [uc_id for uc_id in uc_ids if uc_id not in present][:limit]

    evaluated_ids: list[str] = []
    for uc_id in todo:
        await evaluate_progress(user_id, uc_id)
        evaluated_ids.append(str(uc_id))

    return {
        "evaluated_count": len(evaluated_ids),
        "skipped_count": len(uc_ids) - len(evaluated_ids),
        "uc_ids": evaluated_ids,
    }
