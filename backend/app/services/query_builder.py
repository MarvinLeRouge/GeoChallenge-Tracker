# backend/app/services/query_builder.py
# Transforms a canonical expression (AND-only) into MongoDB conditions for the `caches` collection.

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from bson import ObjectId

from app.services.referentials_cache import (
    resolve_attribute_code,
    resolve_country_name,
    resolve_size_code,
    resolve_size_name,
    resolve_state_name,
    resolve_type_code,
)

# NOTE: we do not depend on Pydantic models here: we receive an already-canonicalized "expression" dict
# (see services/user_challenge_tasks.put_tasks which stores the canonicalized expression).


def _mk_date(dt_or_str: Any) -> datetime:
    """Normalize various date formats to `datetime`.

    Description:
        Accepts `datetime`, `date` or `str` (ISO or `YYYY-MM-DD`). Raises `ValueError` for invalid formats.

    Args:
        dt_or_str (Any): Date/time value to convert.

    Returns:
        datetime: Normalized date.
    """
    if isinstance(dt_or_str, datetime):
        return dt_or_str
    if isinstance(dt_or_str, date):
        return datetime(dt_or_str.year, dt_or_str.month, dt_or_str.day)
    if isinstance(dt_or_str, str):
        if len(dt_or_str) == 10:
            y, m, d = (int(x) for x in dt_or_str.split("-"))
            return datetime(y, m, d)
        return datetime.fromisoformat(dt_or_str)
    raise ValueError(f"Invalid date: {dt_or_str!r}")


def _flatten_and_nodes(expr: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Recursively flatten `AND` nodes into a list of leaves.

    Description:
        Returns `None` if the expression contains `OR`/`NOT` nodes (unsupported by the AND-only compiler).

    Args:
        expr (dict): Canonical AST expression.

    Returns:
        list[dict] | None: Leaves if pure AND, otherwise None.
    """
    kind = expr.get("kind")
    if kind == "and":
        out: list[dict[str, Any]] = []
        for n in expr.get("nodes") or []:
            sub = _flatten_and_nodes(n) if isinstance(n, dict) else [n]
            if sub is None:
                return None
            out.extend(sub)
        return out
    if kind in ("or", "not"):
        return None
    return [expr]  # leaf


def _extract_aggregate_spec(
    leaves: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Extract the aggregate specification and the cache-level leaves.

    Description:
        Detects the **first** aggregate leaf among:
        - `aggregate_sum_difficulty_at_least`
        - `aggregate_sum_terrain_at_least`
        - `aggregate_sum_diff_plus_terr_at_least`
        - `aggregate_sum_altitude_at_least`
        Returns `(agg_spec, leaves_without_aggregate)`.

    Args:
        leaves (list[dict]): AND leaves.

    Returns:
        tuple[dict | None, list[dict]]: Aggregate spec (or None) and remaining leaves.
    """
    agg = None
    cache_leaves: list[dict[str, Any]] = []
    for lf in leaves:
        k = lf.get("kind")
        if k in (
            "aggregate_sum_difficulty_at_least",
            "aggregate_sum_terrain_at_least",
            "aggregate_sum_diff_plus_terr_at_least",
            "aggregate_sum_altitude_at_least",
            "aggregate_count_distinct_countries_at_least",
            "aggregate_dt_matrix_complete",
        ):
            if agg is None:
                if k == "aggregate_sum_difficulty_at_least" and lf.get("min_total") is not None:
                    agg = {"kind": "difficulty", "min_total": int(lf["min_total"])}
                elif k == "aggregate_sum_terrain_at_least" and lf.get("min_total") is not None:
                    agg = {"kind": "terrain", "min_total": int(lf["min_total"])}
                elif (
                    k == "aggregate_sum_diff_plus_terr_at_least" and lf.get("min_total") is not None
                ):
                    agg = {"kind": "diff_plus_terr", "min_total": int(lf["min_total"])}
                elif k == "aggregate_sum_altitude_at_least" and lf.get("min_total") is not None:
                    agg = {"kind": "altitude", "min_total": int(lf["min_total"])}
                elif (
                    k == "aggregate_count_distinct_countries_at_least"
                    and lf.get("min_total") is not None
                ):
                    agg = {"kind": "distinct_countries", "min_total": int(lf["min_total"])}
                elif k == "aggregate_dt_matrix_complete":
                    max_d = float(lf.get("max_difficulty", 5.0))
                    max_t = float(lf.get("max_terrain", 5.0))
                    n_d = round((max_d - 1.0) / 0.5) + 1
                    n_t = round((max_t - 1.0) / 0.5) + 1
                    agg = {
                        "kind": "dt_matrix",
                        "max_difficulty": max_d,
                        "max_terrain": max_t,
                        "min_total": n_d * n_t,
                    }
        else:
            cache_leaves.append(lf)
    return agg, cache_leaves


def _compile_leaf_to_cache_pairs(leaf: dict[str, Any]) -> list[tuple[str, Any]]:
    """Compile an AST leaf into `(field, condition)` pairs on `caches`.

    Description:
        Supports in particular:
        - `type_in`, `size_in` (resolution via reference data/aliases)
        - `country_is`, `state_in`
        - `placed_year`, `placed_before`, `placed_after`
        - `difficulty_between`, `terrain_between`
        - `attributes` (±, `attributes.$elemMatch`)

    Args:
        leaf (dict): Individual leaf.

    Returns:
        list[tuple[str, Any]]: `(field, condition)` pairs to merge with AND.
    """
    k = leaf.get("kind")
    out: list[tuple[str, Any]] = []

    oids: list[ObjectId] = []
    if k == "type_in":
        # 1) canonique: types: [{cache_type_doc_id | cache_type_id | cache_type_code | code}]
        for t in leaf.get("types") or []:
            oid = t.get("cache_type_doc_id")
            if oid:
                try:
                    oids.append(ObjectId(str(oid)))
                except Exception:
                    pass
                continue
            type_code = t.get("cache_type_code") or t.get("code")
            if type_code:
                resolved = resolve_type_code(type_code)
                if resolved:
                    oids.append(resolved)

        # 2) legacy: codes: ["wherigo", ...]
        for code in leaf.get("codes") or []:
            oid = resolve_type_code(code)
            if oid:
                oids.append(oid)

        # 3) legacy: type_ids: [<oid>, ...]
        for tid in leaf.get("type_ids") or []:
            try:
                oids.append(ObjectId(str(tid)))
            except Exception:
                pass

        if oids:
            out.append(("type_id", {"$in": list(dict.fromkeys(oids))}))
        return out

    if k == "size_in":
        # 1) canonique: sizes: [{cache_size_doc_id | cache_size_id | code | name}]
        for s in leaf.get("sizes") or []:
            oid = s.get("cache_size_doc_id")
            if oid:
                try:
                    oids.append(ObjectId(str(oid)))
                except Exception:
                    pass
                continue
            if s.get("code"):
                resolved = resolve_size_code(s["code"])
                if resolved:
                    oids.append(ObjectId(str(resolved)))
                    continue
            if s.get("name"):
                resolved = resolve_size_name(s["name"])
                if resolved:
                    oids.append(ObjectId(str(resolved)))

        # 2) legacy: codes: ["micro", ...]
        for code in leaf.get("codes") or []:
            oid = resolve_size_code(code)
            if oid:
                oids.append(ObjectId(str(oid)))

        # 3) legacy: names: ["micro", ...]
        for nm in leaf.get("names") or []:
            oid = resolve_size_name(nm)
            if oid:
                oids.append(ObjectId(str(oid)))

        # 3) legacy: size_ids: [<oid>, ...]
        for sid in leaf.get("size_ids") or []:
            try:
                oids.append(ObjectId(str(sid)))
            except Exception:
                pass

        if oids:
            out.append(("size_id", {"$in": list(dict.fromkeys(oids))}))
        return out

    if k == "country_is":
        # Accept leaf.country_id OR leaf.country.{code|name}
        cid = leaf.get("country_id")
        if not cid:
            c = leaf.get("country") or {}
            if c.get("code"):
                # Country cache is indexed by ‘name’; here we only have name => try name first,
                # otherwise extend referentials_cache to handle code if needed.
                # If countries have no "code", use resolve_country_name only.
                cid = resolve_country_name(c.get("name") or c.get("code", ""))
            elif c.get("name"):
                cid = resolve_country_name(c["name"])
        if cid:
            out.append(("country_id", cid))
        else:
            # impossible clause -> 0 matches (avoid false positives)
            out.append(("_id", ObjectId()))  # impossible _id
        return out

    if k == "state_in":
        # Accepts state_ids OR states[{name}] (with country propagated via sibling)
        ids: list[ObjectId] = list(leaf.get("state_ids") or [])

        for s in leaf.get("states") or []:
            sid = s.get("state_id")
            if not sid and s.get("name"):
                # on passe le country_id du leaf s’il est déjà là
                country_id = leaf.get("country_id") or (leaf.get("country") or {}).get("country_id")
                sid, _err = resolve_state_name(s["name"], country_id=country_id)
            if sid:
                try:
                    ids.append(ObjectId(str(sid)))
                except Exception:
                    pass

        if ids:
            out.append(("state_id", {"$in": list(dict.fromkeys(ids))}))
        else:
            out.append(("_id", ObjectId()))  # clause impossible
        return out

    if k == "placed_year":
        y = int(leaf.get("year", 0))
        start = datetime(y, 1, 1)
        end = datetime(y + 1, 1, 1)
        out.append(("placed_at", {"$gte": start, "$lt": end}))
        return out

    if k == "placed_before":
        out.append(("placed_at", {"$lt": _mk_date(leaf.get("date"))}))
        return out

    if k == "placed_after":
        out.append(("placed_at", {"$gt": _mk_date(leaf.get("date"))}))
        return out

    if k == "difficulty_between":
        out.append(("difficulty", {"$gte": float(leaf["min"]), "$lte": float(leaf["max"])}))
        return out

    if k == "terrain_between":
        out.append(("terrain", {"$gte": float(leaf["min"]), "$lte": float(leaf["max"])}))
        return out

    if k == "attributes":
        # Canonical: [{"cache_attribute_doc_id"| "cache_attribute_id" | "code", "is_positive": bool}]
        attrs = leaf.get("attributes") or []
        for a in attrs:
            is_pos = bool(a.get("is_positive", True))
            attr_oid = a.get("cache_attribute_doc_id") or a.get("attribute_doc_id")
            if not attr_oid and a.get("code"):
                res = resolve_attribute_code(a["code"])
                attr_oid = res[0] if res else None

            if attr_oid:
                out.append(
                    (
                        "attributes",
                        {
                            "$elemMatch": {
                                "attribute_doc_id": ObjectId(str(attr_oid)),
                                "is_positive": is_pos,
                            }
                        },
                    )
                )
            else:
                out.append(("_id", ObjectId()))  # clause impossible

        # legacy: "codes": ["picnic", "challenge"] (positifs)
        for code in leaf.get("codes") or []:
            res = resolve_attribute_code(code)
            if res and res[0]:
                out.append(
                    (
                        "attributes",
                        {
                            "$elemMatch": {
                                "attribute_doc_id": ObjectId(str(res[0])),
                                "is_positive": True,
                            }
                        },
                    )
                )
            else:
                out.append(("_id", ObjectId()))

        return out

    return out


def compile_and_only(
    expr: dict[str, Any],
) -> tuple[str, dict[str, Any], bool, list[str], dict[str, Any] | None]:
    """Compile an AND expression into Mongo filters on `caches.*`.

    Description:
        - Rejects `OR`/`NOT` (`supported=False`, notes).
        - Extracts an optional aggregate (diff/terr/diff+terr/altitude).
        - Compiles each leaf into `(field, condition)` pairs and merges by field (AND).
        - Generates a stable expression signature (`"and:" + json.dumps(leaves)`).

    Args:
        expr (dict): Canonical expression.

    Returns:
        tuple:
            str: Compiled signature.
            dict: `match_caches` — AND conditions per field.
            bool: `supported` — True if pure AND.
            list[str]: `notes` — warnings/reasons for non-support.
            dict | None: `aggregate_spec` — aggregate specification.
    """
    leaves = _flatten_and_nodes(expr)
    if leaves is None:
        return ("unsupported:or-not", {}, False, ["or/not unsupported in MVP"], None)

    agg_spec, cache_leaves = _extract_aggregate_spec(leaves)
    parts: list[tuple[str, Any]] = []
    for lf in cache_leaves:
        parts.extend(_compile_leaf_to_cache_pairs(lf))

    # merge (AND): group by field; if multiple conditions for the same field -> AND-ed list
    match: dict[str, Any] = {}
    for field, cond in parts:
        if field in match:
            if not isinstance(match[field], list):
                match[field] = [match[field]]
            match[field].append(cond)
        else:
            match[field] = cond

    try:
        import json

        signature = "and:" + json.dumps({"leaves": cache_leaves}, default=str, sort_keys=True)
    except Exception:
        signature = "and:compiled"

    return (signature, match, True, [], agg_spec)
