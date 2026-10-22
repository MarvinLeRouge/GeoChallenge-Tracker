# backend/app/services/mongo_pipeline_helpers.py
# Tiny pure helpers shared by progress and targets aggregation pipelines
# (found_caches -> caches lookups), extracted to remove duplication between
# progress_snapshot_helpers.py, progress_aggregates.py, and
# app/services/targets/target_evaluator.py.

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def build_cache_and_conditions(match_conditions: dict[str, Any]) -> list[Mapping[str, Any]]:
    """Build `$and` conditions on `cache.*` fields from a flat match dict.

    Description:
        Each value can be a single condition or a list of conditions for the
        same field (all of which must hold), mirroring the canonical
        expression format used across the codebase.

    Args:
        match_conditions (dict): AND conditions on `caches` fields.

    Returns:
        list[Mapping]: `{"cache.<field>": <condition>}` entries, one per
            condition (empty if `match_conditions` is empty).
    """
    conds: list[Mapping[str, Any]] = []
    for field, cond in match_conditions.items():
        if isinstance(cond, list):
            for c in cond:
                conds.append({f"cache.{field}": c})
        else:
            conds.append({f"cache.{field}": cond})
    return conds


def extract_rounded_dt_cells(rows: list[dict[str, Any]]) -> set[tuple[float, float]]:
    """Extract (difficulty, terrain) pairs from grouped rows, rounded to 1 decimal.

    Args:
        rows: Grouped `{"_id": {"d": ..., "t": ...}}` rows.

    Returns:
        set[tuple[float, float]]: Rounded (difficulty, terrain) pairs found
            in `rows` (skips rows missing either value).
    """
    cells: set[tuple[float, float]] = set()
    for r in rows:
        d = r["_id"].get("d")
        t = r["_id"].get("t")
        if d is not None and t is not None:
            cells.add((round(float(d), 1), round(float(t), 1)))
    return cells
