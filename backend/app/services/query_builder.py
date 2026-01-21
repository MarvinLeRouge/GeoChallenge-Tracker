# backend/app/services/query_builder.py
# Transforme une expression canonique (AND-only) en conditions MongoDB pour la collection `caches`.

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

# NOTE: on ne dépend pas des modèles Pydantic ici : on reçoit un dict "expression" déjà canonisé
# (cf. services/user_challenge_tasks.put_tasks qui stocke l'expression canonicalisée). :contentReference[oaicite:1]{index=1}


def _mk_date(dt_or_str: Any) -> datetime:
    """Normaliser divers formats de date vers `datetime`.

    Description:
        Accepte `datetime`, `date` ou `str` (ISO ou `YYYY-MM-DD`). Lève `ValueError` pour les formats invalides.

    Args:
        dt_or_str (Any): Valeur de date/heure à convertir.

    Returns:
        datetime: Date normalisée.
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
    """Aplatir récursivement les nœuds `AND` en une liste de feuilles.

    Description:
        Retourne `None` si l’expression contient des `OR`/`NOT` (non supportés par le compilateur « AND-only »).

    Args:
        expr (dict): Expression AST canonique.

    Returns:
        list[dict] | None: Feuilles si AND pur, sinon None.
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
    """Extraire la spécification d’agrégat et les feuilles « cache.* ».

    Description:
        Détecte la **première** feuille d’agrégat parmi:
        - `aggregate_sum_difficulty_at_least`
        - `aggregate_sum_terrain_at_least`
        - `aggregate_sum_diff_plus_terr_at_least`
        - `aggregate_sum_altitude_at_least`
        Retourne `(agg_spec, leaves_sans_agrégat)`.

    Args:
        leaves (list[dict]): Feuilles AND.

    Returns:
        tuple[dict | None, list[dict]]: Spéc d’agrégat (ou None) et feuilles restantes.
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
        ):
            if agg is None and lf.get("min_total") is not None:
                mt = int(lf["min_total"])
                if k == "aggregate_sum_difficulty_at_least":
                    agg = {"kind": "difficulty", "min_total": mt}
                elif k == "aggregate_sum_terrain_at_least":
                    agg = {"kind": "terrain", "min_total": mt}
                elif k == "aggregate_sum_diff_plus_terr_at_least":
                    agg = {"kind": "diff_plus_terr", "min_total": mt}
                elif k == "aggregate_sum_altitude_at_least":
                    agg = {"kind": "altitude", "min_total": mt}
        else:
            cache_leaves.append(lf)
    return agg, cache_leaves


def _compile_leaf_to_cache_pairs(leaf: dict[str, Any]) -> list[tuple[str, Any]]:
    """Compiler une feuille AST en `(champ, condition)` sur `caches`.

    Description:
        Supporte notamment:
        - `type_in`, `size_in` (résolution via référentiels/aliases)
        - `country_is`, `state_in`
        - `placed_year`, `placed_before`, `placed_after`
        - `difficulty_between`, `terrain_between`
        - `attributes` (±, `attributes.$elemMatch`)

    Args:
        leaf (dict): Feuille individuelle.

    Returns:
        list[tuple[str, Any]]: Paires `(champ, condition)` à fusionner en AND.
    """
    k = leaf.get("kind")
    out: list[tuple[str, Any]] = []

    oids: list[ObjectId] = []
    if k == "type_in":
        # 1) canonique: types: [{cache_type_doc_id | cache_type_id | cache_type_code}]
        for t in leaf.get("types") or []:
            oid = t.get("cache_type_doc_id")
            if not oid and t.get("cache_type_id") is not None:
                # numeric id non supporté nativement par le cache -> on ignore, ou ajoute si tu l’as dans cache
                pass
            if not oid and t.get("cache_type_code"):
                oid = resolve_type_code(t["cache_type_code"])
            if oid:
                oids.append(oid)

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
            if not oid and s.get("code"):
                oid = resolve_size_code(s["code"])
            if not oid and s.get("name"):
                oid = resolve_size_name(s["name"])
            if oid:
                oids.append(ObjectId(str(oid)))

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
        # Accepter leaf.country_id OU leaf.country.{code|name}
        cid = leaf.get("country_id")
        if not cid:
            c = leaf.get("country") or {}
            if c.get("code"):
                # Le cache pays est indexé par 'name'; ici on ne l’a que par name => on tente d’abord name,
                # sinon on peut étendre referentials_cache pour gérer code si tu en as.
                # Si tes pays n’ont pas "code", utilise resolve_country_name uniquement.
                cid = resolve_country_name(c.get("name") or c.get("code", ""))
            elif c.get("name"):
                cid = resolve_country_name(c["name"])
        if cid:
            out.append(("country_id", cid))
        else:
            # clause impossible -> 0 match (éviter faux positifs)
            out.append(("_id", ObjectId()))  # _id impossible
        return out

    if k == "state_in":
        # Accepte state_ids OU states[{name}] (avec country diffusable via sibling)
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
        # Canonique: [{"cache_attribute_doc_id"| "cache_attribute_id" | "code", "is_positive": bool}]
        attrs = leaf.get("attributes") or []
        for a in attrs:
            is_pos = bool(a.get("is_positive", True))
            attr_oid = a.get("cache_attribute_doc_id") or a.get("attribute_doc_id")
            if not attr_oid and a.get("cache_attribute_id") is not None:
                # le cache retourne aussi l'id numérique via resolve_attribute_code(code) si tu veux;
                # ici on reste doc_id only
                pass
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
    """Compiler une expression AND en filtres Mongo « caches.* ».

    Description:
        - Rejette `OR`/`NOT` (`supported=False`, notes).\n
        - Extrait un éventuel agrégat (diff/terr/diff+terr/altitude).\n
        - Compile chaque feuille en paires `(champ, condition)` et fusionne par champ (AND).\n
        - Génère une signature stable de l’expression (`"and:" + json.dumps(leaves)`).

    Args:
        expr (dict): Expression canonique.

    Returns:
        tuple:
            str: Signature compilée.
            dict: `match_caches` — conditions AND par champ.
            bool: `supported` — True si AND pur.
            list[str]: `notes` — avertissements/causes de non-support.
            dict | None: `aggregate_spec` — spécification d’agrégat.
    """
    leaves = _flatten_and_nodes(expr)
    if leaves is None:
        return ("unsupported:or-not", {}, False, ["or/not unsupported in MVP"], None)

    agg_spec, cache_leaves = _extract_aggregate_spec(leaves)
    parts: list[tuple[str, Any]] = []
    for lf in cache_leaves:
        parts.extend(_compile_leaf_to_cache_pairs(lf))

    # fusion (AND): grouper par champ; si plusieurs conds pour un même champ -> liste ET-ée
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
