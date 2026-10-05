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

    if k == "distinct_countries":
        pipeline += [
            {"$group": {"_id": "$cache.country_id"}},
            {"$count": "total"},
        ]
        cursor = fc.aggregate(pipeline, allowDiskUse=False)
        rows = await cursor.to_list(length=None)
        return int(rows[0]["total"]) if rows else 0

    if k == "dt_matrix":
        max_d = float(spec.get("max_difficulty", 5.0))
        max_t = float(spec.get("max_terrain", 5.0))
        d_values = [round(1.0 + i * 0.5, 1) for i in range(round((max_d - 1.0) / 0.5) + 1)]
        t_values = [round(1.0 + i * 0.5, 1) for i in range(round((max_t - 1.0) / 0.5) + 1)]
        pipeline += [
            {
                "$group": {
                    "_id": {
                        "d": "$cache.difficulty",
                        "t": "$cache.terrain",
                    }
                }
            },
        ]
        cursor = fc.aggregate(pipeline, allowDiskUse=False)
        rows = await cursor.to_list(length=None)
        found_cells: set[tuple[float, float]] = set()
        for r in rows:
            d = r["_id"].get("d")
            t = r["_id"].get("t")
            if d is not None and t is not None:
                found_cells.add((round(float(d), 1), round(float(t), 1)))
        covered = sum(1 for d in d_values for t in t_values if (d, t) in found_cells)
        return covered

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


async def _get_cached_completed_snapshot(
    uc_id: ObjectId, force: bool, uc_status: str | None, uc_computed_status: str | None
) -> dict[str, Any] | None:
    """Return the last persisted snapshot if the UC is already completed and not forced.

    Description:
        Mirrors the short-circuit at the top of `evaluate_progress`: when the UC is
        already `completed` and `force` is False, no recalculation is needed. Returns
        `None` when a snapshot should be (re)computed, either because the UC isn't
        completed, `force` is True, or no snapshot exists yet.

    Args:
        uc_id (ObjectId): UserChallenge.
        force (bool): Force recalculation even if the UC is completed.
        uc_status (str | None): Declared UC status.
        uc_computed_status (str | None): Computed UC status.

    Returns:
        dict | None: The last snapshot, or None if evaluation should proceed.
    """
    if force or not (uc_computed_status == "completed" or uc_status == "completed"):
        return None
    coll_progress = await get_collection("progress")
    return await coll_progress.find_one(
        {"user_challenge_id": uc_id}, sort=[("checked_at", -1), ("created_at", -1)]
    )


def _build_done_override_snapshot(
    t: dict[str, Any], title: str, order: int, status: str, min_count: int
) -> dict[str, Any]:
    """Build the snapshot for a task already marked `done` by the user (no recompute).

    Args:
        t (dict): Task document.
        title (str): Task title.
        order (int): Task order.
        status (str): Current task status (always "done" when called).
        min_count (int): Task's `min_count` constraint.

    Returns:
        dict: Task snapshot.
    """
    return {
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


def _build_unsupported_snapshot(
    t: dict[str, Any],
    title: str,
    order: int,
    sig: str,
    notes: list[str],
    min_count: int,
) -> dict[str, Any]:
    """Build the snapshot for a task whose expression isn't supported for progress.

    Args:
        t (dict): Task document.
        title (str): Task title.
        order (int): Task order.
        sig (str): Compiled expression signature.
        notes (list[str]): Compilation notes/warnings.
        min_count (int): Task's `min_count` constraint.

    Returns:
        dict: Task snapshot.
    """
    return {
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


async def _compute_aggregate_fields(
    user_id: ObjectId, match_caches: dict[str, Any], agg_spec: dict[str, Any] | None
) -> tuple[int | None, int | None, float | None, str | None]:
    """Compute the aggregate total/target/percent/unit for a task, if it has an aggregate spec.

    Args:
        user_id (ObjectId): User.
        match_caches (dict): Compiled AND conditions on `caches`.
        agg_spec (dict | None): Aggregate specification, or None if the task has none.

    Returns:
        tuple: `(aggregate_total, aggregate_target, aggregate_percent, aggregate_unit)`,
            all None when `agg_spec` is None.
    """
    if not agg_spec:
        return None, None, None, None

    aggregate_total = await _aggregate_total(user_id, match_caches, agg_spec)
    aggregate_target = int(agg_spec.get("min_total", 0)) or None
    if aggregate_target and aggregate_target > 0:
        aggregate_percent = max(
            0.0,
            min(100.0, 100.0 * (float(aggregate_total) / float(aggregate_target))),
        )
    else:
        aggregate_percent = None

    agg_kind = agg_spec.get("kind")
    if agg_kind == "altitude":
        aggregate_unit = "meters"
    elif agg_kind == "distinct_countries":
        aggregate_unit = "countries"
    elif agg_kind == "dt_matrix":
        aggregate_unit = "cells"
    else:
        aggregate_unit = "points"

    return aggregate_total, aggregate_target, aggregate_percent, aggregate_unit


def _resolve_new_task_status(
    min_count: int,
    current: int,
    agg_spec: dict[str, Any] | None,
    aggregate_total: int | None,
    aggregate_target: int | None,
    status: str,
) -> str:
    """Resolve whether a task becomes `done`, based on its count and aggregate constraints.

    Description:
        A task is `done` when the found-cache count meets `min_count` (if set) AND the
        aggregate total meets its target (if set). Handles pure-aggregate tasks where
        `min_count == 0`.

    Args:
        min_count (int): Task's `min_count` constraint.
        current (int): Current matching found-cache count.
        agg_spec (dict | None): Aggregate specification, or None.
        aggregate_total (int | None): Computed aggregate total.
        aggregate_target (int | None): Aggregate target.
        status (str): Current task status, kept unchanged if not done.

    Returns:
        str: `"done"` or the unchanged `status`.
    """
    count_ok = (min_count == 0) or (current >= min_count)
    agg_ok = (
        (not agg_spec)
        or (not aggregate_target)
        or (aggregate_total is not None and aggregate_total >= aggregate_target)
    )
    return "done" if (count_ok and agg_ok) else status


async def _persist_task_status_if_changed(
    coll_uctasks: Any, task_id: ObjectId, status: str, new_status: str
) -> None:
    """Persist the task's new status, unless it was already `done`.

    Args:
        coll_uctasks (Any): `user_challenge_tasks` collection.
        task_id (ObjectId): Task id.
        status (str): Status before this evaluation.
        new_status (str): Status resolved by this evaluation.
    """
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


def _resolve_final_percent(
    agg_spec: dict[str, Any] | None,
    min_count: int,
    count_percent: float,
    aggregate_percent: float | None,
) -> float:
    """Resolve the task's final percent from its count and/or aggregate percent.

    Description (MVP rule):
        - Both count and aggregate constraints -> `min(count_percent, aggregate_percent)`.
        - Only count -> `count_percent`.
        - Only aggregate -> `aggregate_percent` (or 0 if None).

    Args:
        agg_spec (dict | None): Aggregate specification, or None.
        min_count (int): Task's `min_count` constraint.
        count_percent (float): Percent based on `min_count`.
        aggregate_percent (float | None): Percent based on the aggregate target.

    Returns:
        float: Final percent for the task.
    """
    if agg_spec and min_count > 0:
        return min(count_percent, (aggregate_percent or 0.0))
    if agg_spec and min_count == 0:
        return aggregate_percent or 0.0
    return count_percent


async def _persist_task_progress_dates(
    user_id: ObjectId,
    coll_uctasks: Any,
    t: dict[str, Any],
    match_caches: dict[str, Any],
    min_count: int,
    current: int,
) -> None:
    """Persist `start_found_at`/`completed_at` on the task, mutating `t` in place.

    Description:
        - `start_found_at`: date of the first matching found cache, set once.
        - `completed_at`: date of the `min_count`-th matching find, set when reached and
          cleared if it was set but no longer valid.

    Args:
        user_id (ObjectId): User.
        coll_uctasks (Any): `user_challenge_tasks` collection.
        t (dict): Task document, mutated in place.
        match_caches (dict): Compiled AND conditions on `caches`.
        min_count (int): Task's `min_count` constraint.
        current (int): Current matching found-cache count.
    """
    task_id = t["_id"]

    # start_found_at: first matching found cache
    start_dt = await _first_found_date(user_id, match_caches)
    if start_dt and not t.get("start_found_at"):
        await coll_uctasks.update_one(
            {"_id": task_id},
            {"$set": {"start_found_at": start_dt, "updated_at": utcnow()}},
        )
        t["start_found_at"] = start_dt  # in-memory update for subsequent use

    # completed_at: date of the min_count-th matching find
    completed_dt = None
    if min_count > 0 and current >= min_count:
        completed_dt = await _nth_found_date(user_id, match_caches, min_count)

    # persist the date if reached, or clear it if it was set but no longer valid
    if completed_dt:
        if t.get("completed_at") != completed_dt:
            await coll_uctasks.update_one(
                {"_id": task_id},
                {"$set": {"completed_at": completed_dt, "updated_at": utcnow()}},
            )
            t["completed_at"] = completed_dt
    else:
        if t.get("completed_at") is not None:
            await coll_uctasks.update_one(
                {"_id": task_id},
                {"$set": {"completed_at": None, "updated_at": utcnow()}},
            )
            t["completed_at"] = None


def _build_supported_snapshot(
    t: dict[str, Any],
    title: str,
    order: int,
    sig: str,
    min_count: int,
    current: int,
    final_percent: float,
    agg_spec: dict[str, Any] | None,
    aggregate_total: int | None,
    aggregate_target: int | None,
    aggregate_unit: str | None,
    notes: list[str],
    ms: int,
) -> dict[str, Any]:
    """Build the snapshot for a fully evaluated, supported task.

    Args:
        t (dict): Task document (its current `status` is read from it).
        title (str): Task title.
        order (int): Task order.
        sig (str): Compiled expression signature.
        min_count (int): Task's `min_count` constraint.
        current (int): Current matching found-cache count.
        final_percent (float): Resolved final percent.
        agg_spec (dict | None): Aggregate specification, or None.
        aggregate_total (int | None): Computed aggregate total.
        aggregate_target (int | None): Aggregate target.
        aggregate_unit (str | None): Aggregate unit label.
        notes (list[str]): Compilation notes/warnings.
        ms (int): Evaluation duration in milliseconds.

    Returns:
        dict: Task snapshot.
    """
    return {
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


async def _evaluate_supported_task(
    user_id: ObjectId,
    coll_uctasks: Any,
    t: dict[str, Any],
    title: str,
    order: int,
    status: str,
    min_count: int,
    sig: str,
    match_caches: dict[str, Any],
    agg_spec: dict[str, Any] | None,
    notes: list[str],
) -> dict[str, Any]:
    """Fully evaluate a supported task: count, aggregate, status, percent, dates, snapshot.

    Args:
        user_id (ObjectId): User.
        coll_uctasks (Any): `user_challenge_tasks` collection.
        t (dict): Task document, mutated in place (`status`, progress dates).
        title (str): Task title.
        order (int): Task order.
        status (str): Status before this evaluation.
        min_count (int): Task's `min_count` constraint.
        sig (str): Compiled expression signature.
        match_caches (dict): Compiled AND conditions on `caches`.
        agg_spec (dict | None): Aggregate specification, or None.
        notes (list[str]): Compilation notes/warnings.

    Returns:
        dict: Task snapshot.
    """
    tic = utcnow()
    current = await _count_found_caches_matching(user_id, match_caches)
    ms = int((utcnow() - tic).total_seconds() * 1000)

    bounded = min(current, min_count) if min_count > 0 else current
    count_percent = (100.0 * (bounded / min_count)) if min_count > 0 else 100.0

    (
        aggregate_total,
        aggregate_target,
        aggregate_percent,
        aggregate_unit,
    ) = await _compute_aggregate_fields(user_id, match_caches, agg_spec)

    new_status = _resolve_new_task_status(
        min_count, current, agg_spec, aggregate_total, aggregate_target, status
    )
    task_id = t["_id"]
    t["status"] = new_status
    await _persist_task_status_if_changed(coll_uctasks, task_id, status, new_status)

    final_percent = _resolve_final_percent(agg_spec, min_count, count_percent, aggregate_percent)

    await _persist_task_progress_dates(user_id, coll_uctasks, t, match_caches, min_count, current)

    return _build_supported_snapshot(
        t,
        title,
        order,
        sig,
        min_count,
        current,
        final_percent,
        agg_spec,
        aggregate_total,
        aggregate_target,
        aggregate_unit,
        notes,
        ms,
    )


def _compute_aggregate_percent(
    snapshots: list[dict[str, Any]], sum_current: int, sum_min: int
) -> float:
    """Compute the UC-level aggregate percent from its task snapshots.

    Description:
        Weighted by `min_count` when any task has one, otherwise the average of
        task-level percents (handles pure-aggregate tasks where `min_count == 0`).

    Args:
        snapshots (list[dict]): Task snapshots.
        sum_current (int): Sum of bounded current counts across count-based tasks.
        sum_min (int): Sum of `min_count` across tasks.

    Returns:
        float: Aggregate percent, rounded to 1 decimal.
    """
    if sum_min > 0:
        return round(100.0 * (sum_current / sum_min), 1)
    supported_snaps = [s for s in snapshots if s.get("supported_for_progress")]
    if not supported_snaps:
        return 0.0
    return round(sum(s["percent"] for s in supported_snaps) / len(supported_snaps), 1)


async def _finalize_uc_status(
    coll_uc: Any,
    uc_id: ObjectId,
    uc_computed_status: str | None,
    tasks_done: int,
    tasks_supported: int,
    progress_snapshot: dict[str, Any],
) -> None:
    """Mark the UC `completed` if all supported tasks are done, else persist progress only.

    Args:
        coll_uc (Any): `user_challenges` collection.
        uc_id (ObjectId): UserChallenge.
        uc_computed_status (str | None): Computed UC status before this evaluation.
        tasks_done (int): Number of supported tasks marked `done`.
        tasks_supported (int): Number of supported tasks.
        progress_snapshot (dict): Progress summary to persist on the UC document.
    """
    if (uc_computed_status != "completed") and (tasks_done == tasks_supported):
        await coll_uc.update_one(
            {"_id": uc_id},
            {
                "$set": {
                    "computed_status": "completed",
                    "status": "completed",
                    "progress": progress_snapshot,
                    "updated_at": utcnow(),
                }
            },
        )
    else:
        # Always persist the latest progress snapshot on the UC document so the
        # detail view can display current progress without an extra query.
        await coll_uc.update_one(
            {"_id": uc_id},
            {"$set": {"progress": progress_snapshot, "updated_at": utcnow()}},
        )


async def _evaluate_task(
    user_id: ObjectId, coll_uctasks: Any, t: dict[str, Any], force: bool
) -> dict[str, Any]:
    """Evaluate a single task and return its snapshot.

    Description:
        Dispatches to the "done override" snapshot (user already marked it done and not
        forced), the "unsupported" snapshot (expression can't be compiled for progress),
        or a full evaluation via `_evaluate_supported_task`.

    Args:
        user_id (ObjectId): User.
        coll_uctasks (Any): `user_challenge_tasks` collection.
        t (dict): Task document, possibly mutated in place by a full evaluation.
        force (bool): Force recalculation even if the task is already `done`.

    Returns:
        dict: Task snapshot.
    """
    min_count = int((t.get("constraints") or {}).get("min_count") or 0)
    title = t.get("title") or "Task"
    order = int(t.get("order") or 0)
    status = (t.get("status") or "todo").lower()
    expr = t.get("expression") or {}

    if status == "done" and not force:
        return _build_done_override_snapshot(t, title, order, status, min_count)

    sig, match_caches, supported, notes, agg_spec = compile_and_only(expr)
    if not supported:
        return _build_unsupported_snapshot(t, title, order, sig, notes, min_count)

    return await _evaluate_supported_task(
        user_id,
        coll_uctasks,
        t,
        title,
        order,
        status,
        min_count,
        sig,
        match_caches,
        agg_spec,
        notes,
    )


def _accumulate_task_totals(
    snap: dict[str, Any], totals: tuple[int, int, int, int]
) -> tuple[int, int, int, int]:
    """Fold one task snapshot into the UC-level running totals.

    Args:
        snap (dict): Task snapshot.
        totals (tuple): `(sum_current, sum_min, tasks_supported, tasks_done)` so far.

    Returns:
        tuple: Updated `(sum_current, sum_min, tasks_supported, tasks_done)`.
    """
    sum_current, sum_min, tasks_supported, tasks_done = totals
    if not snap["supported_for_progress"]:
        return totals

    min_count = snap["min_count"]
    tasks_supported += 1
    sum_min += max(0, min_count)
    bounded_for_sum = (
        min(snap["current_count"], min_count) if min_count > 0 else snap["current_count"]
    )
    sum_current += bounded_for_sum
    # A task is done when its status is "done" (handles both count-based
    # and pure-aggregate tasks where min_count == 0).
    if snap.get("status") == "done":
        tasks_done += 1

    return sum_current, sum_min, tasks_supported, tasks_done


async def evaluate_progress(user_id: ObjectId, uc_id: ObjectId, force=False) -> dict[str, Any]:
    """Evaluate tasks for a UC and insert a progress snapshot.

    Description:
        - Verifies UC ownership (`_ensure_uc_owned`).\n
        - If `force=False` and the UC is already `completed`, returns the last snapshot (if any).\n
        - Evaluates each task (`_evaluate_task`) and folds its snapshot into the running
          totals (`_accumulate_task_totals`).\n
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

    cached = await _get_cached_completed_snapshot(uc_id, force, uc_status, uc_computed_status)
    if cached:
        return cached  # same shape as persisted snapshots

    for t in tasks:
        snap = await _evaluate_task(user_id, coll_uctasks, t, force)
        sum_current, sum_min, tasks_supported, tasks_done = _accumulate_task_totals(
            snap, (sum_current, sum_min, tasks_supported, tasks_done)
        )
        snapshots.append(snap)

    aggregate_percent = _compute_aggregate_percent(snapshots, sum_current, sum_min)

    progress_snapshot = {
        "percent": aggregate_percent,
        "tasks_done": tasks_done,
        "tasks_total": tasks_supported,
        "checked_at": now(),
    }
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
    await _finalize_uc_status(
        coll_uc, uc_id, uc_computed_status, tasks_done, tasks_supported, progress_snapshot
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
