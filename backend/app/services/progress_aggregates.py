"""DB-backed aggregate/count/date-lookup helpers for progress.py.

Description:
    Extracted for module-size reasons. These functions are individually mocked
    by name in several tests (patch("app.services.progress_aggregates.X")), so
    progress.py must call them via the module object (`progress_aggregates.X(...)`)
    rather than a `from ... import X` binding, to keep that patching effective.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING

from app.db.mongodb import get_collection
from app.services.progress_snapshot_helpers import (
    _build_base_match_pipeline,
    _build_score_expression,
)


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


async def _aggregate_distinct_countries(fc: Any, pipeline: list[Mapping[str, Any]]) -> int:
    """Count distinct `cache.country_id` values matched by `pipeline`.

    Args:
        fc (Any): `found_caches` collection.
        pipeline (list[Mapping]): Base match pipeline.

    Returns:
        int: Distinct country count.
    """
    full_pipeline = pipeline + [
        {"$group": {"_id": "$cache.country_id"}},
        {"$count": "total"},
    ]
    cursor = fc.aggregate(full_pipeline, allowDiskUse=False)
    rows = await cursor.to_list(length=None)
    return int(rows[0]["total"]) if rows else 0


async def _aggregate_dt_matrix(
    fc: Any, pipeline: list[Mapping[str, Any]], spec: dict[str, Any]
) -> int:
    """Count the number of distinct D/T cells covered, up to `spec`'s max bounds.

    Args:
        fc (Any): `found_caches` collection.
        pipeline (list[Mapping]): Base match pipeline.
        spec (dict): Aggregate spec with `max_difficulty`/`max_terrain`.

    Returns:
        int: Number of covered D/T matrix cells.
    """
    max_d = float(spec.get("max_difficulty", 5.0))
    max_t = float(spec.get("max_terrain", 5.0))
    d_values = [round(1.0 + i * 0.5, 1) for i in range(round((max_d - 1.0) / 0.5) + 1)]
    t_values = [round(1.0 + i * 0.5, 1) for i in range(round((max_t - 1.0) / 0.5) + 1)]

    full_pipeline = pipeline + [
        {
            "$group": {
                "_id": {
                    "d": "$cache.difficulty",
                    "t": "$cache.terrain",
                }
            }
        },
    ]
    cursor = fc.aggregate(full_pipeline, allowDiskUse=False)
    rows = await cursor.to_list(length=None)
    found_cells: set[tuple[float, float]] = set()
    for r in rows:
        d = r["_id"].get("d")
        t = r["_id"].get("t")
        if d is not None and t is not None:
            found_cells.add((round(float(d), 1), round(float(t), 1)))
    return sum(1 for d in d_values for t in t_values if (d, t) in found_cells)


async def _aggregate_score_sum(
    fc: Any, pipeline: list[Mapping[str, Any]], score_expr: Mapping[str, Any]
) -> int:
    """Sum a per-document score expression over the matched found caches.

    Args:
        fc (Any): `found_caches` collection.
        pipeline (list[Mapping]): Base match pipeline.
        score_expr (Mapping): `$project` expression computing the per-doc score.

    Returns:
        int: Summed total.
    """
    full_pipeline = pipeline + [
        {"$project": {"score": score_expr}},
        {"$group": {"_id": None, "total": {"$sum": "$score"}}},
    ]
    cursor = fc.aggregate(full_pipeline, allowDiskUse=False)
    rows = await cursor.to_list(length=None)
    return int(rows[0]["total"]) if rows else 0


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
    pipeline = _build_base_match_pipeline(user_id, match_caches)

    k = spec["kind"]

    if k == "distinct_countries":
        return await _aggregate_distinct_countries(fc, pipeline)

    if k == "dt_matrix":
        return await _aggregate_dt_matrix(fc, pipeline, spec)

    score_expr = _build_score_expression(k)
    if score_expr is None:
        return 0

    return await _aggregate_score_sum(fc, pipeline, score_expr)


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
