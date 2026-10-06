# backend/app/services/query_builder.py
# Transforms a canonical expression (AND-only) into MongoDB conditions for the `caches` collection.

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable

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


def _build_difficulty_agg_spec(lf: dict[str, Any]) -> dict[str, Any] | None:
    """Build the aggregate spec for `aggregate_sum_difficulty_at_least`."""
    if lf.get("min_total") is None:
        return None
    return {"kind": "difficulty", "min_total": int(lf["min_total"])}


def _build_terrain_agg_spec(lf: dict[str, Any]) -> dict[str, Any] | None:
    """Build the aggregate spec for `aggregate_sum_terrain_at_least`."""
    if lf.get("min_total") is None:
        return None
    return {"kind": "terrain", "min_total": int(lf["min_total"])}


def _build_diff_plus_terr_agg_spec(lf: dict[str, Any]) -> dict[str, Any] | None:
    """Build the aggregate spec for `aggregate_sum_diff_plus_terr_at_least`."""
    if lf.get("min_total") is None:
        return None
    return {"kind": "diff_plus_terr", "min_total": int(lf["min_total"])}


def _build_altitude_agg_spec(lf: dict[str, Any]) -> dict[str, Any] | None:
    """Build the aggregate spec for `aggregate_sum_altitude_at_least`."""
    if lf.get("min_total") is None:
        return None
    return {"kind": "altitude", "min_total": int(lf["min_total"])}


def _build_distinct_countries_agg_spec(lf: dict[str, Any]) -> dict[str, Any] | None:
    """Build the aggregate spec for `aggregate_count_distinct_countries_at_least`."""
    if lf.get("min_total") is None:
        return None
    return {"kind": "distinct_countries", "min_total": int(lf["min_total"])}


def _build_dt_matrix_agg_spec(lf: dict[str, Any]) -> dict[str, Any]:
    """Build the aggregate spec for `aggregate_dt_matrix_complete`."""
    max_d = float(lf.get("max_difficulty", 5.0))
    max_t = float(lf.get("max_terrain", 5.0))
    n_d = round((max_d - 1.0) / 0.5) + 1
    n_t = round((max_t - 1.0) / 0.5) + 1
    return {
        "kind": "dt_matrix",
        "max_difficulty": max_d,
        "max_terrain": max_t,
        "min_total": n_d * n_t,
    }


# Dispatch table for `_extract_aggregate_spec`, keyed by leaf `kind`.
_AGGREGATE_SPEC_BUILDERS: dict[str, Callable[[dict[str, Any]], dict[str, Any] | None]] = {
    "aggregate_sum_difficulty_at_least": _build_difficulty_agg_spec,
    "aggregate_sum_terrain_at_least": _build_terrain_agg_spec,
    "aggregate_sum_diff_plus_terr_at_least": _build_diff_plus_terr_agg_spec,
    "aggregate_sum_altitude_at_least": _build_altitude_agg_spec,
    "aggregate_count_distinct_countries_at_least": _build_distinct_countries_agg_spec,
    "aggregate_dt_matrix_complete": _build_dt_matrix_agg_spec,
}


def _extract_aggregate_spec(
    leaves: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Extract the aggregate specification and the cache-level leaves.

    Description:
        Detects the **first** aggregate leaf, dispatching to the builder registered in
        `_AGGREGATE_SPEC_BUILDERS` for its `kind`. Any other leaf is kept in
        `cache_leaves`; a recognized aggregate-kind leaf is always dropped from
        `cache_leaves`, even if its builder returns None (e.g. missing `min_total`).

    Args:
        leaves (list[dict]): AND leaves.

    Returns:
        tuple[dict | None, list[dict]]: Aggregate spec (or None) and remaining leaves.
    """
    agg: dict[str, Any] | None = None
    cache_leaves: list[dict[str, Any]] = []
    for lf in leaves:
        kind = lf.get("kind")
        builder = _AGGREGATE_SPEC_BUILDERS.get(kind) if isinstance(kind, str) else None
        if builder is None:
            cache_leaves.append(lf)
            continue
        if agg is None:
            agg = builder(lf)
    return agg, cache_leaves


def _resolve_type_ids_from_canonical(types: list[dict[str, Any]]) -> list[ObjectId]:
    """Resolve type ObjectIds from canonical `types` entries.

    Args:
        types (list[dict]): `{cache_type_doc_id | cache_type_code | code}` entries.

    Returns:
        list[ObjectId]: Resolved ObjectIds (invalid/unresolvable entries are skipped).
    """
    oids: list[ObjectId] = []
    for t in types:
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
    return oids


def _resolve_type_ids_from_legacy_codes(codes: list[str]) -> list[ObjectId]:
    """Resolve type ObjectIds from legacy `codes` (e.g. `["wherigo", ...]`).

    Args:
        codes (list[str]): Legacy type codes.

    Returns:
        list[ObjectId]: Resolved ObjectIds (unresolvable codes are skipped).
    """
    oids: list[ObjectId] = []
    for code in codes:
        oid = resolve_type_code(code)
        if oid:
            oids.append(oid)
    return oids


def _resolve_type_ids_from_legacy_ids(type_ids: list[Any]) -> list[ObjectId]:
    """Resolve type ObjectIds from legacy `type_ids`.

    Args:
        type_ids (list): Legacy raw ObjectId-like values.

    Returns:
        list[ObjectId]: Valid ObjectIds (invalid values are skipped).
    """
    oids: list[ObjectId] = []
    for tid in type_ids:
        try:
            oids.append(ObjectId(str(tid)))
        except Exception:
            pass
    return oids


def _compile_type_in(leaf: dict[str, Any]) -> list[tuple[str, Any]]:
    """Compile a `type_in` leaf into `(field, condition)` pairs.

    Description:
        Resolves cache types via canonical `types` entries, legacy `codes`, or legacy
        `type_ids`, deduplicating the resulting ObjectIds.

    Args:
        leaf (dict): Individual leaf.

    Returns:
        list[tuple[str, Any]]: `(field, condition)` pairs to merge with AND.
    """
    oids = [
        *_resolve_type_ids_from_canonical(leaf.get("types") or []),
        *_resolve_type_ids_from_legacy_codes(leaf.get("codes") or []),
        *_resolve_type_ids_from_legacy_ids(leaf.get("type_ids") or []),
    ]
    if oids:
        return [("type_id", {"$in": list(dict.fromkeys(oids))})]
    return []


def _resolve_size_ids_from_canonical(sizes: list[dict[str, Any]]) -> list[ObjectId]:
    """Resolve size ObjectIds from canonical `sizes` entries.

    Args:
        sizes (list[dict]): `{cache_size_doc_id | code | name}` entries.

    Returns:
        list[ObjectId]: Resolved ObjectIds (invalid/unresolvable entries are skipped).
    """
    oids: list[ObjectId] = []
    for s in sizes:
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
    return oids


def _resolve_size_ids_from_legacy_codes(codes: list[str]) -> list[ObjectId]:
    """Resolve size ObjectIds from legacy `codes` (e.g. `["micro", ...]`).

    Args:
        codes (list[str]): Legacy size codes.

    Returns:
        list[ObjectId]: Resolved ObjectIds (unresolvable codes are skipped).
    """
    oids: list[ObjectId] = []
    for code in codes:
        oid = resolve_size_code(code)
        if oid:
            oids.append(ObjectId(str(oid)))
    return oids


def _resolve_size_ids_from_legacy_names(names: list[str]) -> list[ObjectId]:
    """Resolve size ObjectIds from legacy `names` (e.g. `["micro", ...]`).

    Args:
        names (list[str]): Legacy size names.

    Returns:
        list[ObjectId]: Resolved ObjectIds (unresolvable names are skipped).
    """
    oids: list[ObjectId] = []
    for nm in names:
        oid = resolve_size_name(nm)
        if oid:
            oids.append(ObjectId(str(oid)))
    return oids


def _resolve_size_ids_from_legacy_ids(size_ids: list[Any]) -> list[ObjectId]:
    """Resolve size ObjectIds from legacy `size_ids`.

    Args:
        size_ids (list): Legacy raw ObjectId-like values.

    Returns:
        list[ObjectId]: Valid ObjectIds (invalid values are skipped).
    """
    oids: list[ObjectId] = []
    for sid in size_ids:
        try:
            oids.append(ObjectId(str(sid)))
        except Exception:
            pass
    return oids


def _compile_size_in(leaf: dict[str, Any]) -> list[tuple[str, Any]]:
    """Compile a `size_in` leaf into `(field, condition)` pairs.

    Description:
        Resolves cache sizes via canonical `sizes` entries, legacy `codes`/`names`, or
        legacy `size_ids`, deduplicating the resulting ObjectIds.

    Args:
        leaf (dict): Individual leaf.

    Returns:
        list[tuple[str, Any]]: `(field, condition)` pairs to merge with AND.
    """
    oids = [
        *_resolve_size_ids_from_canonical(leaf.get("sizes") or []),
        *_resolve_size_ids_from_legacy_codes(leaf.get("codes") or []),
        *_resolve_size_ids_from_legacy_names(leaf.get("names") or []),
        *_resolve_size_ids_from_legacy_ids(leaf.get("size_ids") or []),
    ]
    if oids:
        return [("size_id", {"$in": list(dict.fromkeys(oids))})]
    return []


def _compile_country_is(leaf: dict[str, Any]) -> list[tuple[str, Any]]:
    """Compile a `country_is` leaf into `(field, condition)` pairs.

    Description:
        Accepts `leaf.country_id` or `leaf.country.{code|name}`. Falls back to an
        impossible clause (0 matches) when the country cannot be resolved.

    Args:
        leaf (dict): Individual leaf.

    Returns:
        list[tuple[str, Any]]: `(field, condition)` pairs to merge with AND.
    """
    out: list[tuple[str, Any]] = []
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


def _resolve_state_ids(leaf: dict[str, Any], states: list[dict[str, Any]]) -> list[ObjectId]:
    """Resolve state ObjectIds from `state_ids` plus `states[{name}]` entries.

    Args:
        leaf (dict): Individual leaf (used for `state_ids` and the sibling country).
        states (list[dict]): `{state_id | name}` entries.

    Returns:
        list[ObjectId]: Valid ObjectIds (invalid/unresolvable entries are skipped).
    """
    ids: list[ObjectId] = list(leaf.get("state_ids") or [])
    for s in states:
        sid = s.get("state_id")
        if not sid and s.get("name"):
            # on passe le country_id du leaf s'il est déjà là
            country_id = leaf.get("country_id") or (leaf.get("country") or {}).get("country_id")
            sid, _err = resolve_state_name(s["name"], country_id=country_id)
        if sid:
            try:
                ids.append(ObjectId(str(sid)))
            except Exception:
                pass
    return ids


def _compile_state_in(leaf: dict[str, Any]) -> list[tuple[str, Any]]:
    """Compile a `state_in` leaf into `(field, condition)` pairs.

    Description:
        Accepts `state_ids` or `states[{name}]` (with country propagated via sibling).
        Falls back to an impossible clause (0 matches) when no state resolves.

    Args:
        leaf (dict): Individual leaf.

    Returns:
        list[tuple[str, Any]]: `(field, condition)` pairs to merge with AND.
    """
    ids = _resolve_state_ids(leaf, leaf.get("states") or [])
    if ids:
        return [("state_id", {"$in": list(dict.fromkeys(ids))})]
    return [("_id", ObjectId())]  # clause impossible


def _compile_placed_year(leaf: dict[str, Any]) -> list[tuple[str, Any]]:
    """Compile a `placed_year` leaf into `(field, condition)` pairs.

    Args:
        leaf (dict): Individual leaf.

    Returns:
        list[tuple[str, Any]]: `(field, condition)` pairs to merge with AND.
    """
    y = int(leaf.get("year", 0))
    start = datetime(y, 1, 1)
    end = datetime(y + 1, 1, 1)
    return [("placed_at", {"$gte": start, "$lt": end})]


def _compile_placed_before(leaf: dict[str, Any]) -> list[tuple[str, Any]]:
    """Compile a `placed_before` leaf into `(field, condition)` pairs.

    Args:
        leaf (dict): Individual leaf.

    Returns:
        list[tuple[str, Any]]: `(field, condition)` pairs to merge with AND.
    """
    return [("placed_at", {"$lt": _mk_date(leaf.get("date"))})]


def _compile_placed_after(leaf: dict[str, Any]) -> list[tuple[str, Any]]:
    """Compile a `placed_after` leaf into `(field, condition)` pairs.

    Args:
        leaf (dict): Individual leaf.

    Returns:
        list[tuple[str, Any]]: `(field, condition)` pairs to merge with AND.
    """
    return [("placed_at", {"$gt": _mk_date(leaf.get("date"))})]


def _compile_difficulty_between(leaf: dict[str, Any]) -> list[tuple[str, Any]]:
    """Compile a `difficulty_between` leaf into `(field, condition)` pairs.

    Args:
        leaf (dict): Individual leaf.

    Returns:
        list[tuple[str, Any]]: `(field, condition)` pairs to merge with AND.
    """
    return [("difficulty", {"$gte": float(leaf["min"]), "$lte": float(leaf["max"])})]


def _compile_terrain_between(leaf: dict[str, Any]) -> list[tuple[str, Any]]:
    """Compile a `terrain_between` leaf into `(field, condition)` pairs.

    Args:
        leaf (dict): Individual leaf.

    Returns:
        list[tuple[str, Any]]: `(field, condition)` pairs to merge with AND.
    """
    return [("terrain", {"$gte": float(leaf["min"]), "$lte": float(leaf["max"])})]


def _compile_attribute_entries(attrs: list[dict[str, Any]]) -> list[tuple[str, Any]]:
    """Compile canonical attribute entries into `attributes.$elemMatch` pairs.

    Description:
        Canonical: `[{"cache_attribute_doc_id" | "attribute_doc_id" | "code", "is_positive": bool}]`.
        An unresolvable entry falls back to an impossible clause (0 matches).

    Args:
        attrs (list[dict]): Canonical attribute entries.

    Returns:
        list[tuple[str, Any]]: `(field, condition)` pairs to merge with AND.
    """
    out: list[tuple[str, Any]] = []
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
    return out


def _compile_attribute_legacy_codes(codes: list[str]) -> list[tuple[str, Any]]:
    """Compile legacy, always-positive attribute codes into `attributes.$elemMatch` pairs.

    Description:
        Legacy: `"codes": ["picnic", "challenge"]` (always positive). An unresolvable
        code falls back to an impossible clause (0 matches).

    Args:
        codes (list[str]): Legacy attribute codes.

    Returns:
        list[tuple[str, Any]]: `(field, condition)` pairs to merge with AND.
    """
    out: list[tuple[str, Any]] = []
    for code in codes:
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


def _compile_attributes(leaf: dict[str, Any]) -> list[tuple[str, Any]]:
    """Compile an `attributes` leaf into `(field, condition)` pairs.

    Description:
        Canonical entries (`attributes: [{...}]`) and legacy `codes` (always positive)
        are both compiled to `attributes.$elemMatch` conditions. An unresolvable entry
        falls back to an impossible clause (0 matches) rather than being dropped.

    Args:
        leaf (dict): Individual leaf.

    Returns:
        list[tuple[str, Any]]: `(field, condition)` pairs to merge with AND.
    """
    return _compile_attribute_entries(
        leaf.get("attributes") or []
    ) + _compile_attribute_legacy_codes(leaf.get("codes") or [])


# Dispatch table for `_compile_leaf_to_cache_pairs`, keyed by `leaf["kind"]`.
_LEAF_COMPILERS: dict[str, Callable[[dict[str, Any]], list[tuple[str, Any]]]] = {
    "type_in": _compile_type_in,
    "size_in": _compile_size_in,
    "country_is": _compile_country_is,
    "state_in": _compile_state_in,
    "placed_year": _compile_placed_year,
    "placed_before": _compile_placed_before,
    "placed_after": _compile_placed_after,
    "difficulty_between": _compile_difficulty_between,
    "terrain_between": _compile_terrain_between,
    "attributes": _compile_attributes,
}


def _compile_leaf_to_cache_pairs(leaf: dict[str, Any]) -> list[tuple[str, Any]]:
    """Compile an AST leaf into `(field, condition)` pairs on `caches`.

    Description:
        Dispatches to the per-`kind` compiler registered in `_LEAF_COMPILERS`. Supports
        in particular:
        - `type_in`, `size_in` (resolution via reference data/aliases)
        - `country_is`, `state_in`
        - `placed_year`, `placed_before`, `placed_after`
        - `difficulty_between`, `terrain_between`
        - `attributes` (±, `attributes.$elemMatch`)
        An unknown `kind` compiles to no pairs.

    Args:
        leaf (dict): Individual leaf.

    Returns:
        list[tuple[str, Any]]: `(field, condition)` pairs to merge with AND.
    """
    kind = leaf.get("kind")
    compiler = _LEAF_COMPILERS.get(kind) if isinstance(kind, str) else None
    return compiler(leaf) if compiler else []


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
