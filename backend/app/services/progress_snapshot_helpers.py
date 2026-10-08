"""Pure, non-DB helper functions for progress.py (pipeline/snapshot building,
percent/status resolution). Extracted for module-size reasons; none of these
are individually mocked by tests, so moving them is behavior-neutral.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from bson import ObjectId

from app.core.utils import now


def _build_base_match_pipeline(
    user_id: ObjectId, match_caches: dict[str, Any]
) -> list[Mapping[str, Any]]:
    """Build the common found_caches -> caches lookup/match pipeline prefix.

    Args:
        user_id (ObjectId): User.
        match_caches (dict): AND conditions on `caches`.

    Returns:
        list[Mapping]: Pipeline stages, ending with the AND match (if any).
    """
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
    conds: list[Mapping[str, Any]] = []
    for field, cond in match_caches.items():
        if isinstance(cond, list):
            for c in cond:
                conds.append({f"cache.{field}": c})
        else:
            conds.append({f"cache.{field}": cond})
    if conds:
        pipeline.append({"$match": {"$and": conds}})
    return pipeline


def _build_score_expression(kind: str) -> Mapping[str, Any] | None:
    """Build the Mongo `$project` score expression for a simple sum-aggregate kind.

    Args:
        kind (str): `difficulty` | `terrain` | `diff_plus_terr` | `altitude`.

    Returns:
        Mapping | None: The score expression, or None for an unknown kind.
    """
    if kind == "difficulty":
        return {"$ifNull": ["$cache.difficulty", 0]}
    if kind == "terrain":
        return {"$ifNull": ["$cache.terrain", 0]}
    if kind == "diff_plus_terr":
        return {
            "$add": [
                {"$ifNull": ["$cache.difficulty", 0]},
                {"$ifNull": ["$cache.terrain", 0]},
            ]
        }
    if kind == "altitude":
        return {"$ifNull": ["$cache.elevation", 0]}
    return None


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


def _estimate_task_completion(
    current_count: int, min_c: int, info: dict[str, Any], now_dt: datetime
) -> datetime | None:
    """Estimate a task's completion date from its progress so far.

    Description:
        Fixed to the recorded completion date if already done; otherwise
        extrapolated from the find rate since the first find, if in progress.

    Args:
        current_count (int): Current matching found-cache count.
        min_c (int): Task's `min_count` constraint.
        info (dict): `{"start": ..., "done": ...}` from `_load_task_progress_dates`.
        now_dt (datetime): Reference "now" for extrapolation.

    Returns:
        datetime | None: Estimated completion date, or None if not estimable.
    """
    start = info.get("start")
    done = info.get("done")

    if done:
        # completed -> ETA is fixed
        # found_date is a 'date'; normalize to 'datetime' for the response
        return datetime(done.year, done.month, done.day)  # 00:00 local/UTC per now()

    if start and current_count >= 1 and min_c > 0:
        # in progress -> extrapolation
        # speed = (cur - 1) / days elapsed since the first find
        elapsed_days = max((now_dt.date() - start.date()).days, 1)
        speed = float(current_count - 1) / float(elapsed_days)
        remaining = max(0, min_c - current_count)
        if speed > 0.0 and remaining > 0:
            eta_days = int(math.ceil(remaining / speed))
            eta_date = now_dt.date() + timedelta(days=eta_days)
            return datetime(eta_date.year, eta_date.month, eta_date.day)
        # otherwise eta = None

    return None


def _summarize_progress_snapshot(d: dict[str, Any]) -> dict[str, Any]:
    """Summarize a history snapshot to its `checked_at` + `aggregate` fields.

    Args:
        d (dict): Full progress snapshot document.

    Returns:
        dict: `{"checked_at": ..., "aggregate": ...}`.
    """
    return {
        "checked_at": d["checked_at"],
        "aggregate": d["aggregate"],
    }
