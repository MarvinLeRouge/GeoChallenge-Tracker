# backend/app/services/user_challenge_tasks.py

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime
from bson import ObjectId
import re
from threading import RLock

from pydantic import BaseModel, Field, ValidationError, TypeAdapter
from app.core.bson_utils import PyObjectId
from app.db.mongodb import get_collection

# ==== AST imports (must match your models) ====
from app.models.challenge_ast import (
    TaskExpression,
    TaskAnd, TaskOr, TaskNot,
    RuleTypeIn, RuleSizeIn, RulePlacedYear, RulePlacedBefore, RulePlacedAfter,
    RuleStateIn, RuleCountryIs, RuleDifficultyBetween, RuleTerrainBetween,
    RuleAttributes,
    # Aggregate leaves
    RuleAggSumDifficultyAtLeast, RuleAggSumTerrainAtLeast,
    RuleAggSumDiffPlusTerrAtLeast, RuleAggSumAltitudeAtLeast,
)
from app.models.challenge_ast import preprocess_expression_default_and  # <-- import

collections_mapping: Dict[str, Dict[str, Any]] = {}
_collections_lock = RLock()
_mapping_ready = False

def _as_oid(x) -> ObjectId:
    return x if isinstance(x, ObjectId) else ObjectId(str(x))

def _map_collection(collection_name: str, *, code_field: Optional[str] = None,
                    name_field: Optional[str] = None,
                    extra_numeric_id_field: Optional[str] = None) -> None:
    """
    Construit collections_mapping[collection_name] avec :
      - ids: set(ObjectId)
      - code: {lower -> ObjectId}         (si code_field)
      - name: {lower -> ObjectId}         (si name_field)
      - numeric_ids: set(int)             (si extra_numeric_id_field)
      - doc_by_id: {ObjectId -> doc partiel}
    """
    coll = get_collection(collection_name)

    # Construire la projection dynamiquement pour éviter les clés None
    projection: Dict[str, int] = {"_id": 1}
    if code_field:
        projection[code_field] = 1
    if name_field:
        projection[name_field] = 1
    if extra_numeric_id_field:
        projection[extra_numeric_id_field] = 1

    docs = list(coll.find({}, projection))

    ids: set[ObjectId] = set()
    code_map: Dict[str, ObjectId] = {}
    name_map: Dict[str, ObjectId] = {}
    numeric_ids: set[int] = set()
    doc_by_id: Dict[ObjectId, Dict[str, Any]] = {}

    for d in docs:
        oid = d["_id"]
        ids.add(oid)
        doc_by_id[oid] = d
        if code_field and d.get(code_field):
            code_map[str(d[code_field]).lower()] = oid
        if name_field and d.get(name_field):
            name_map[str(d[name_field]).lower()] = oid
        if extra_numeric_id_field and d.get(extra_numeric_id_field) is not None:
            try:
                numeric_ids.add(int(d[extra_numeric_id_field]))
            except Exception:
                pass

    out: Dict[str, Any] = {"ids": ids, "doc_by_id": doc_by_id}
    if code_field:
        out["code"] = code_map
    if name_field:
        out["name"] = name_map
    if extra_numeric_id_field:
        out["numeric_ids"] = numeric_ids

    collections_mapping[collection_name] = out


def _map_collection_states() -> None:
    """
    states :
      collections_mapping["states"] = {
        "ids": set(ObjectId),
        "by_country": { str(country_id): { lower(state_name): ObjectId } }
      }
    """
    coll = get_collection("states")
    docs = list(coll.find({}, {"_id": 1, "country_id": 1, "name": 1}))

    ids: set[ObjectId] = set()
    by_country: Dict[str, Dict[str, ObjectId]] = {}

    for d in docs:
        sid = d["_id"]
        cid = d.get("country_id")
        nm = d.get("name")
        ids.add(sid)
        if cid and nm:
            key = str(cid)
            by_country.setdefault(key, {})
            by_country[key][nm.lower()] = sid

    collections_mapping["states"] = {"ids": ids, "by_country": by_country}


def _populate_mapping() -> None:
    collections_mapping.clear()
    _map_collection("cache_attributes", code_field="code", name_field="txt",
                    extra_numeric_id_field="cache_attribute_id")
    _map_collection("cache_types",    code_field="code")
    _map_collection("cache_sizes",    code_field="code", name_field="name")  # si "name" existe
    _map_collection("countries",      name_field="name")
    _map_collection_states()


def refresh_referentials_cache():
    """À appeler après un seed pour recharger les mappings en mémoire."""
    _populate_mapping()


# Populate au chargement du module
if not _mapping_ready:
    _populate_mapping()

# --------------------------------------------------------------------------------------
# Existence checks via cache
# --------------------------------------------------------------------------------------

def _exists_id(coll_name: str, oid: ObjectId) -> bool:
    try:
        oid = oid if isinstance(oid, ObjectId) else ObjectId(str(oid))
    except Exception:
        return False
    entry = collections_mapping.get(coll_name) or {}
    return oid in entry.get("ids", set())

def _exists_attribute_id(attr_id: int) -> bool:
    entry = collections_mapping.get("cache_attributes") or {}
    try:
        return int(attr_id) in entry.get("numeric_ids", set())
    except Exception:
        return False

# --------------------------------------------------------------------------------------
# Resolve code/name → document id (via cache)
# --------------------------------------------------------------------------------------

def _resolve_code_to_id(collection: str, field: str, value: str) -> Optional[ObjectId]:
    entry = collections_mapping.get(collection) or {}
    m = entry.get(field) or {}
    return m.get(str(value).lower())

def _resolve_attribute_code(code: str) -> Optional[Tuple[ObjectId, Optional[int]]]:
    entry = collections_mapping.get("cache_attributes") or {}
    # on tente par code, puis par 'txt' (rangé dans name_map)
    oid = (entry.get("code", {}) or {}).get(code.lower())
    if oid is None:
        oid = (entry.get("name", {}) or {}).get(code.lower())
    if oid is None:
        return None
    doc = (entry.get("doc_by_id") or {}).get(oid) or {}
    num = int(doc["cache_attribute_id"]) if doc.get("cache_attribute_id") is not None else None
    return oid, num

def _resolve_type_code(code: str) -> Optional[ObjectId]:
    return _resolve_code_to_id("cache_types", "code", code)

def _resolve_size_code(code: str) -> Optional[ObjectId]:
    return _resolve_code_to_id("cache_sizes", "code", code)

def _resolve_size_name(name: str) -> Optional[ObjectId]:
    return _resolve_code_to_id("cache_sizes", "name", name)

def _resolve_country_name(name: str) -> Optional[ObjectId]:
    return _resolve_code_to_id("countries", "name", name)

def _resolve_state_name(state_name: str, *, country_id: Optional[ObjectId] = None) -> Tuple[Optional[ObjectId], Optional[str]]:
    entry = collections_mapping.get("states") or {}
    by_country = entry.get("by_country", {})
    target = (state_name or "").lower()

    if country_id:
        key = str(country_id if isinstance(country_id, ObjectId) else ObjectId(str(country_id)))
        sid = (by_country.get(key) or {}).get(target)
        return (sid, None) if sid else (None, f"state not found '{state_name}' in country '{key}'")

    # pas de pays fourni → ambiguïtés possibles
    hits = []
    for cid, states in by_country.items():
        if target in states:
            hits.append(states[target])
    if not hits:
        return None, f"state name not found '{state_name}'"
    if len(hits) > 1:
        return None, f"state name ambiguous without country '{state_name}'"
    return hits[0], None


# ==== DTO-like models used by services ====
class PatchTaskItem(BaseModel):
    _id: Optional[PyObjectId] = None
    user_challenge_id: PyObjectId
    order: int = 0
    expression: TaskExpression
    constraints: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None

def _normalize_code_to_id(expr: TaskExpression, *, index_for_errors: int) -> TaskExpression:
    from app.models.challenge_ast import TaskExpression as TE
    def _norm(node: Any) -> Any:
        if isinstance(node, dict):
            k = node.get("kind")

            # --- attributes: code -> cache_attribute_doc_id (+ cache_attribute_id si connu)
            if k == "attributes" and isinstance(node.get("attributes"), list):
                new_attrs = []
                for a in node["attributes"]:
                    a = dict(a)
                    code = a.get("code")
                    # NOTE: le modèle AST attend 'cache_attribute_doc_id'
                    if code and not a.get("cache_attribute_doc_id"):
                        res = _resolve_attribute_code(code)  # doit renvoyer (oid, numeric_id)
                        if not res:
                            raise ValueError(f"index {index_for_errors}: attribute code not found '{code}'")
                        doc_id, num_id = res
                        a["cache_attribute_doc_id"] = doc_id
                        # ne pas écraser si déjà présent
                        a.setdefault("cache_attribute_id", num_id)
                    new_attrs.append(a)
                node = {**node, "attributes": new_attrs}

            # --- type_in: cache_type_code -> cache_type_doc_id
            elif k == "type_in" and isinstance(node.get("types"), list):
                new_types = []
                for t in node["types"]:
                    t = dict(t)
                    if t.get("cache_type_code") and not t.get("cache_type_doc_id"):
                        found = _resolve_type_code(t["cache_type_code"])  # retourne l'OID du doc type
                        if not found:
                            raise ValueError(f"index {index_for_errors}: type code not found '{t['cache_type_code']}'")
                        t["cache_type_doc_id"] = found
                    new_types.append(t)
                node = {**node, "types": new_types}

            # --- size_in: code/name -> cache_size_doc_id
            elif k == "size_in" and isinstance(node.get("sizes"), list):
                new_sizes = []
                for s in node["sizes"]:
                    s = dict(s)
                    if not s.get("cache_size_doc_id"):
                        found = None
                        if s.get("code"):
                            found = _resolve_size_code(s["code"])
                        elif s.get("name"):
                            found = _resolve_size_name(s["name"])
                        if not found:
                            label = s.get("code") or s.get("name") or "<?>"
                            raise ValueError(f"index {index_for_errors}: size not found '{label}'")
                        s["cache_size_doc_id"] = found
                    new_sizes.append(s)
                node = {**node, "sizes": new_sizes}

            # --- country_is, state_in: laisse comme tu as déjà (tes versions hautes sont OK)
            # (country.name -> country_id si nécessaire, states via _resolve_state_name(...))

            # recurse
            for key, val in list(node.items()):
                node[key] = _norm(val)
            return node

        if isinstance(node, list):
            return [_norm(x) for x in node]
        return node

    expr_dict = expr.model_dump(by_alias=True)
    normalized = _norm(expr_dict)
    return TypeAdapter(TE).validate_python(normalized)

def _has_country_is(nodes) -> bool:
    for n in nodes:
        if isinstance(n, RuleCountryIs):
            return True
        # Si sous-AND imbriqué, on check récursivement
        if isinstance(n, TaskAnd) and _has_country_is(n.nodes):
            return True
    return False

def _walk_expr(expr: TaskExpression):
    """Yield (kind, node, parent_kind) for structure validation."""
    if isinstance(expr, (TaskAnd, TaskOr)):
        parent = expr.kind
        for child in expr.nodes:
            for k, n, pk in _walk_expr(child):
                yield (k, n, pk if pk is not None else parent)
        return
    if isinstance(expr, TaskNot):
        for k, n, pk in _walk_expr(expr.node):
            yield (k, n, "not")
        return
    return [(expr.kind, expr, None)]

def _is_aggregate_kind(kind: str) -> bool:
    return kind in (
        "aggregate_sum_difficulty_at_least",
        "aggregate_sum_terrain_at_least",
        "aggregate_sum_diff_plus_terr_at_least",
        "aggregate_sum_altitude_at_least",
    )

def validate_task_expression(expr: TaskExpression) -> List[str]:
    """
    Extended validation:
    - referentials (types, sizes, states, country, attributes)
    - numeric ranges
    - aggregates: AND-only (not under OR/NOT), at most 1 aggregate per task
    """
    errors: List[str] = []
    aggregate_count = 0

    for kind, node, parent in _walk_expr(expr):
        if _is_aggregate_kind(kind):
            aggregate_count += 1
            if parent in ("or", "not"):
                errors.append(f"{kind}: aggregate rules are only supported under AND (not under {parent})")
            # check min_total presence & type via Pydantic already; nothing else here
            continue

        if kind == "type_in":
            for oid in node.type_ids:
                if not _exists_id("cache_types", oid):
                    errors.append(f"type_in: unknown cache_type id '{oid}'")
        elif kind == "size_in":
            for oid in node.size_ids:
                if not _exists_id("cache_sizes", oid):
                    errors.append(f"size_in: unknown cache_size id '{oid}'")
        elif kind == "state_in":
            for oid in node.state_ids:
                if not _exists_id("states", oid):
                    errors.append(f"state_in: unknown state id '{oid}'")
                # obligation d’un country_is sibling
                if isinstance(expr, TaskAnd):
                    if not _has_country_is(expr.nodes):
                        errors.append("state_in requires a sibling country_is in the same AND group")
        elif kind == "country_is":
            if not _exists_id("countries", node.country_id):
                errors.append(f"country_is: unknown country id '{node.country_id}'")
        elif kind == "attributes":
            for i, a in enumerate(node.attributes):
                if not _exists_attribute_id(a.cache_attribute_id):
                    errors.append(f"attributes[{i}].cache_attribute_id unknown '{a.cache_attribute_id}'")
        elif kind in ("difficulty_between", "terrain_between"):
            if node.min > node.max:
                errors.append(f"{kind}: min must be <= max")
        # placed_year/before/after validated by pydantic types

    if aggregate_count > 1:
        errors.append("Only a single aggregate rule is supported per task (MVP)")

    return errors

# --------------------------------------------------------------------------------------
# Public API kept from BEFORE: list_tasks / put_tasks / validate_only
# --------------------------------------------------------------------------------------

def _legacy_fixup_expression(exp: Any) -> Any:
    """Convert legacy short forms to canonical-compatible shapes (non-destructive)."""
    def _fix(node: Any) -> Any:
        if isinstance(node, dict):
            k = node.get("kind")

            # type_in: { codes: [...] } -> { types: [{cache_type_code: ...}, ...] }
            if k == "type_in" and "codes" in node and "types" not in node:
                node = {**node}
                node["types"] = [{"cache_type_code": c} for c in node.pop("codes")]

            # size_in: { codes: [...] } -> { sizes: [{code: ...}, ...] }
            if k == "size_in" and "codes" in node and "sizes" not in node:
                node = {**node}
                node["sizes"] = [{"code": c} for c in node.pop("codes")]

            # recurse into children
            for kk, vv in list(node.items()):
                node[kk] = _fix(vv)
            return node

        if isinstance(node, list):
            return [_fix(x) for x in node]
        return node

    return _fix(exp)

def list_tasks(user_id: ObjectId, uc_id: ObjectId) -> Dict[str, Any]:
    coll = get_collection("user_challenge_tasks")
    cur = coll.find(
        {"user_challenge_id": uc_id},
        sort=[("order", 1), ("_id", 1)]
    )

    tasks: List[Dict[str, Any]] = []
    for d in cur:
        # title est requis côté TaskOut -> fallback si absent
        title = d.get("title") or "Untitled task"
        exp = d.get("expression")

        # Try to validate as-is
        try:
            exp_pre = preprocess_expression_default_and(exp)
            exp_model = TypeAdapter(TaskExpression).validate_python(exp_pre)
            exp_out = exp_model.model_dump(by_alias=True)
        except Exception:
            # Legacy repair, then validate
            fixed = _legacy_fixup_expression(exp)
            exp_pre = preprocess_expression_default_and(fixed)
            exp_model = TypeAdapter(TaskExpression).validate_python(exp_pre)
            exp_out = exp_model.model_dump(by_alias=True)
        tasks.append({
            "id": d["_id"],  # TaskOut.id (PyObjectId géré par tes encoders)
            "order": d.get("order", 0),
            "title": title,
            "expression": exp_out,
            "constraints": d.get("constraints", {}),
            "status": d.get("status"),                  # optionnel dans TaskOut
            "metrics": d.get("metrics"),
            "progress": d.get("progress"),
            "last_evaluated_at": d.get("last_evaluated_at"),
            "updated_at": d.get("updated_at"),
            "created_at": d.get("created_at"),
        })

    return tasks

def validate_only(user_id: ObjectId, uc_id: ObjectId, tasks_payload: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate without writing. Returns { ok: bool, errors: [...] }.
    """
    def _mk_err(index: int, field: str, code: str, message: str) -> Dict[str, Any]:
        return {"index": index, "field": field, "code": code, "message": message}

    try:
        _validate_tasks_payload(user_id, uc_id, tasks_payload)

        return {"ok": True, "errors": []}
    except ValidationError as e:
        # Pydantic validation of the AST structure / types
        msg = "; ".join([err.get("msg", "validation error") for err in getattr(e, "errors", lambda: [])()] or [str(e)])

        return {"ok": False, "errors": [_mk_err(0, "expression", "pydantic_validation_error", msg)]}
    except Exception as e:
        # Our _validate_tasks_payload raises ValueError with messages like "invalid expression at index i: ...",
        # or "constraints.min_count ... (index i)". Extract the index if present.
        s = str(e)
        m = re.search(r"index\s+(\d+)", s)
        idx = int(m.group(1)) if m else 0
        # Try to infer the field mentioned in the message, default to expression
        field = "constraints" if "constraints" in s else "expression"
        code = "invalid_expression" if "expression" in s else "invalid_payload"

        return {"ok": False, "errors": [_mk_err(idx, field, code, s)]}

def put_tasks(user_id: ObjectId, uc_id: ObjectId, tasks_payload: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Validate first (raises on error)
    _validate_tasks_payload(user_id, uc_id, tasks_payload)

    coll = get_collection("user_challenge_tasks")
    coll.delete_many({"user_challenge_id": uc_id})

    to_insert = []
    now = datetime.utcnow()
    for i, item in enumerate(tasks_payload):
        _maybe_id = item.get("id") or item.get("_id")
        doc_id = ObjectId(str(_maybe_id)) if _maybe_id else ObjectId()
        title = item.get("title") or f"Task #{i+1}"

        # NEW: canonicalize expression for storage
        expr_pre = preprocess_expression_default_and(item["expression"])
        expr_model = TypeAdapter(TaskExpression).validate_python(expr_pre)
        expr_model = _normalize_code_to_id(expr_model, index_for_errors=i)
        expr_canonical = expr_model.model_dump(by_alias=True)

        doc = {
            "_id": doc_id,
            "user_challenge_id": uc_id,
            "order": int(item.get("order", i)),
            "title": title,
            "expression": expr_canonical,     # <--- store canonical
            "constraints": item.get("constraints", {}),
            "status": item.get("status") or "todo",
            "metrics": item.get("metrics", {}),
            "notes": item.get("notes"),
            "last_evaluated_at": None,
            "created_at": now,
            "updated_at": now,
        }
        to_insert.append(doc)

    if to_insert:
        coll.insert_many(to_insert, ordered=True)

    # read-back (already canonical)
    cur = coll.find({"user_challenge_id": uc_id}).sort([("order", 1), ("_id", 1)])
    items: List[Dict[str, Any]] = []
    for d in cur:
        items.append({
            "id": d["_id"],
            "order": d.get("order", 0),
            "title": d.get("title"),
            "expression": d.get("expression"),    # already canonical
            "constraints": d.get("constraints", {}),
            "status": d.get("status"),
            "metrics": d.get("metrics"),
            "progress": d.get("progress"),
            "last_evaluated_at": d.get("last_evaluated_at"),
            "updated_at": d.get("updated_at"),
            "created_at": d.get("created_at"),
        })

    return items

# --------------------------------------------------------------------------------------
# Internal validation utils (payload-level)
# --------------------------------------------------------------------------------------

def _validate_tasks_payload(user_id: ObjectId, uc_id: ObjectId, tasks_payload: List[Dict[str, Any]]) -> None:
    """
    Raises Exception on first error; used by both validate_only & put_tasks.
    """
    if not isinstance(tasks_payload, list) or len(tasks_payload) == 0:
        raise ValueError("tasks_payload must be a non-empty list")

    # Validate & collect expressions
    seen_orders = set()
    for i, item in enumerate(tasks_payload):
        # order uniqueness / monotonicity (basic check)
        order_val = int(item.get("order", i))
        if order_val in seen_orders:
            raise ValueError(f"duplicate order '{order_val}' in tasks payload")
        seen_orders.add(order_val)

        # pydantic-parse expression first (will ensure structure & types)
        expr_raw = item.get("expression")
        if expr_raw is None:
            raise ValueError("each task must have an 'expression'")
        try:
            # 1) appliquer la forme courte -> canonique (AND par défaut)
            expr_pre = preprocess_expression_default_and(expr_raw)

            # 2) valider/parse Pydantic (Union des nœuds)
            expr_model = TypeAdapter(TaskExpression).validate_python(expr_pre)

            # 3) tes normalisations existantes (ex: attributes.code -> ids, type_in.codes -> type_ids)
            expr_model = _normalize_code_to_id(expr_model, index_for_errors=i)

        except ValidationError as e:
            raise ValueError(f"invalid expression at index {i}: {e}")

        # NEW: extended validation (aggregates + referentials)
        errs = validate_task_expression(expr_model)
        if errs:
            raise ValueError(f"expression at index {i} invalid: {errs}")

        # constraints basic sanity (min_count >= 0 if provided)
        constraints = item.get("constraints") or {}
        if "min_count" in constraints:
            try:
                mc = int(constraints["min_count"])
                if mc < 0:
                    raise ValueError
            except Exception:
                raise ValueError(f"constraints.min_count must be a non-negative integer (index {i})")

    # Optional: verify uc_id belongs to user? (depends on your security model)
    # get_collection("user_challenges").find_one({"_id": uc_id, "user_id": user_id}) ...

