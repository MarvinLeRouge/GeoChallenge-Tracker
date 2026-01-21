# backend/app/services/user_challenge_tasks.py
# Compile/valide les expressions de tâches, applique les normalisations code→id et opère le CRUD logique.

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any, cast

from bson import ObjectId
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from app.core.bson_utils import PyObjectId
from app.core.utils import utcnow
from app.db.mongodb import get_collection

# ==== AST imports (must match your models) ====
from app.domain.models.challenge_ast import (
    RuleCountryIs,
    TaskAnd,
    TaskExpression,
    TaskNot,
    TaskOr,
    preprocess_expression_default_and,
)
from app.domain.models.challenge_ast import (
    TaskExpression as TE,
)
from app.services.referentials_cache import (
    exists_attribute_id,
    exists_id,
    resolve_attribute_code,
    resolve_country_name,
    resolve_size_code,
    resolve_size_name,
    resolve_state_name,
    resolve_type_code,
)

# ======================================================================================
#                                   Public helpers
# ======================================================================================


def compile_expression_to_cache_match(expr: TaskExpression) -> dict[str, Any]:
    """Compiler une expression AST vers un filtre Mongo `caches`.

    Description:
        Gère AND/OR/NOT pour les feuilles supportées ; ignore les feuilles d’agrégat (traitées ailleurs).

    Args:
        expr: Expression Pydantic déjà validée.

    Returns:
        dict: Filtre Mongo (peut contenir `$and/$or/$nor`).
    """

    def _leaf_to_match(leaf: Any) -> dict[str, Any]:
        k = getattr(leaf, "kind", None)

        if k == "type_in":
            # canonique: node.type_ids (liste d'OIDs)
            ids = [oid for oid in (getattr(leaf, "type_ids", None) or [])]
            return {"type_id": {"$in": ids}} if ids else {}

        if k == "size_in":
            ids = [oid for oid in (getattr(leaf, "size_ids", None) or [])]
            return {"size_id": {"$in": ids}} if ids else {}

        if k == "placed_year":
            y = int(leaf.year)
            return {"placed_year": y}

        if k == "placed_before":
            d = leaf.date
            return {"placed_at": {"$lt": d}}

        if k == "placed_after":
            d = leaf.date
            return {"placed_at": {"$gt": d}}

        if k == "difficulty_between":
            return {"difficulty": {"$gte": leaf.min, "$lte": leaf.max}}

        if k == "terrain_between":
            return {"terrain": {"$gte": leaf.min, "$lte": leaf.max}}

        if k == "country_is":
            return {"country_id": leaf.country_id}

        if k == "state_in":
            ids = [oid for oid in (getattr(leaf, "state_ids", None) or [])]
            return {"state_id": {"$in": ids}} if ids else {}

        if k == "attributes":
            # Liste d'attributs ET-és (tous doivent matcher)
            clauses: list[dict[str, Any]] = []
            for a in leaf.attributes:
                # on privilégie cache_attribute_doc_id si présent, sinon id numérique
                attr_doc_id = getattr(a, "cache_attribute_doc_id", None) or getattr(
                    a, "attribute_doc_id", None
                )
                num_id = getattr(a, "cache_attribute_id", None)
                is_pos = bool(getattr(a, "is_positive", True))
                sub: dict[str, Any] = {"attributes": {"$elemMatch": {"is_positive": is_pos}}}
                if attr_doc_id:
                    sub["attributes"]["$elemMatch"]["attribute_doc_id"] = attr_doc_id
                elif num_id is not None:
                    sub["attributes"]["$elemMatch"]["cache_attribute_id"] = int(num_id)
                # sinon: si seulement "code" => interdit ici (doit avoir été normalisé avant)
                clauses.append(sub)
            return {"$and": clauses} if clauses else {}

        # Agrégats: ne participent pas au filtre "cache" (calculés côté progress/metrics)
        if k in {
            "aggregate_sum_difficulty_at_least",
            "aggregate_sum_terrain_at_least",
            "aggregate_sum_diff_plus_terr_at_least",
            "aggregate_sum_altitude_at_least",
        }:
            return {}

        # Par défaut: rien
        return {}

    def _node(expr_node: Any) -> dict[str, Any]:
        if isinstance(expr_node, TaskAnd):
            parts = [_node(n) for n in expr_node.nodes]
            parts = [p for p in parts if p]  # strip empties
            return {"$and": parts} if parts else {}

        if isinstance(expr_node, TaskOr):
            parts = [_node(n) for n in expr_node.nodes]
            parts = [p for p in parts if p]
            return {"$or": parts} if parts else {}

        if isinstance(expr_node, TaskNot):
            inner = _node(expr_node.node)
            return {"$nor": [inner]} if inner else {}

        # Feuille
        return _leaf_to_match(expr_node)

    return _node(expr)


# ==== DTO-like models used by services ====
class PatchTaskItem(BaseModel):
    """Payload interne pour patch/put de tâche.

    Attributes:
        _id (PyObjectId | None): Id existant (si update).
        user_challenge_id (PyObjectId): UC parent.
        order (int): Ordre d’affichage.
        expression (TaskExpression): AST canonique.
        constraints (dict): Contraintes.
        metrics (dict): Métriques.
        notes (str | None): Notes.
    """

    _id: PyObjectId | None = None
    user_challenge_id: PyObjectId
    order: int = 0
    expression: TaskExpression
    constraints: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None


def _normalize_code_to_id(expr: TaskExpression, *, index_for_errors: int) -> TaskExpression:
    """Normaliser les codes/labels en ObjectId dans l’AST.

    Description:
        - Attributs: `code` → `cache_attribute_doc_id` (+ `cache_attribute_id`).
        - Type: `cache_type_code` → `cache_type_doc_id`.
        - Taille: `code`/`name` → `cache_size_doc_id`.
        - Pays/État: résolution par nom/code avec erreurs explicites.

    Args:
        expr: Expression validée.
        index_for_errors: Index de la tâche (pour messages d’erreur).

    Returns:
        TaskExpression: Expression enrichie d’identifiants.
    """

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
                        res = resolve_attribute_code(code)  # doit renvoyer (oid, numeric_id)
                        if not res:
                            raise ValueError(
                                f"index {index_for_errors}: attribute code not found '{code}'"
                            )
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
                        found = resolve_type_code(
                            t["cache_type_code"]
                        )  # retourne l'OID du doc type
                        if not found:
                            raise ValueError(
                                f"index {index_for_errors}: type code not found '{t['cache_type_code']}'"
                            )
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
                            found = resolve_size_code(s["code"])
                        elif s.get("name"):
                            found = resolve_size_name(s["name"])
                        if not found:
                            label = s.get("code") or s.get("name") or "<?>"
                            raise ValueError(f"index {index_for_errors}: size not found '{label}'")
                        s["cache_size_doc_id"] = found
                    new_sizes.append(s)
                node = {**node, "sizes": new_sizes}

            # --- country_is: accepter {"country": {"code" | "name"}} et conserver les champs lisibles
            elif k == "country_is":
                c = dict(node.get("country") or {})
                if not node.get("country_id"):
                    cid = None
                    if (not cid) and c.get("name"):
                        cid = resolve_country_name(c["name"])
                    if not cid:
                        label = c.get("code") or c.get("name") or "<?>"
                        raise ValueError(
                            f"country_is: country not found '{label}' (index {index_for_errors})"
                        )
                    node["country_id"] = cid
                # conserver le bloc 'country' tel que fourni (lisibilité GET)
                node["country"] = c or node.get("country") or {}

            # --- state_in: accepter {"states":[{"name": ...}]} (et/ou "state_names": [...])
            #               nécessite le country du même AND (tu as déjà une validation côté validate_task_expression)
            elif k == "state_in":
                # on collecte des ids à partir de plusieurs formes acceptées
                state_ids = list(node.get("state_ids") or [])
                # compat courte: state_names: ["X","Y"]
                for nm in node.get("state_names") or []:
                    sid = resolve_state_name(
                        nm,
                        country_id=node.get("country_id")
                        or (node.get("country") or {}).get("country_id"),
                    )
                    if not sid:
                        raise ValueError(
                            f"state_in: state not found '{nm}' (index {index_for_errors})"
                        )
                    state_ids.append(sid)
                # forme riche: states: [{"name": ...}]
                for s in node.get("states") or []:
                    s = dict(s)
                    sid = s.get("state_id")
                    if not sid and s.get("name"):
                        sid = resolve_state_name(
                            s["name"],
                            context_country_id=node.get("country_id")
                            or (node.get("country") or {}).get("country_id"),
                        )
                    if not sid:
                        label = s.get("name") or "<?>"
                        raise ValueError(
                            f"state_in: state not found '{label}' (index {index_for_errors})"
                        )
                    state_ids.append(sid)
                if state_ids:
                    node["state_ids"] = list(dict.fromkeys(state_ids))  # dedup
                # conserver 'states' et/ou 'state_names' (lisibilité GET)

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


def _has_country_is(nodes: Iterable[Any]) -> bool:
    """Tester la présence d’un nœud `country_is` dans un AND.

    Args:
        nodes: Nœuds frères.

    Returns:
        bool: True si `country_is` trouvé.
    """
    for n in nodes:
        if isinstance(n, RuleCountryIs):
            return True
        # Si sous-AND imbriqué, on check récursivement
        if isinstance(n, TaskAnd) and _has_country_is(n.nodes):
            return True
    return False


def _walk_expr(expr: TaskExpression):
    """Itérer (kind, node, parent_kind) à des fins de validation structurelle.

    Args:
        expr: Expression à parcourir.

    Returns:
        Iterable[tuple[str, Any, str|None]]: Triplets (kind, node, parent).
    """
    if isinstance(expr, (TaskAnd, TaskOr)):
        parent = expr.kind
        for child in expr.nodes:
            for k, n, pk in _walk_expr(child):
                yield (k, n, pk if pk is not None else parent)
        return
    if isinstance(expr, TaskNot):
        for k, n, _pk in _walk_expr(expr.node):
            yield (k, n, "not")
        return
    return [(expr.kind, expr, None)]


def _is_aggregate_kind(kind: str) -> bool:
    """Indiquer si `kind` correspond à une feuille d’agrégat.

    Args:
        kind: Nom de la règle.

    Returns:
        bool: True si agrégat.
    """
    return kind in (
        "aggregate_sum_difficulty_at_least",
        "aggregate_sum_terrain_at_least",
        "aggregate_sum_diff_plus_terr_at_least",
        "aggregate_sum_altitude_at_least",
    )


def validate_task_expression(expr: TaskExpression) -> list[str]:
    """Validation étendue d’une expression de tâche.

    Description:
        - Référentiels (types, tailles, pays/états, attributs)
        - Bornes numériques (min/max)
        - Agrégats: **AND-only**, au plus un par tâche

    Args:
        expr: Expression déjà Pydantic-validée.

    Returns:
        list[str]: Liste d’erreurs (vide si OK).
    """
    errors: list[str] = []
    aggregate_count = 0

    for kind, node, parent in _walk_expr(expr):
        if _is_aggregate_kind(kind):
            aggregate_count += 1
            if parent in ("or", "not"):
                errors.append(
                    f"{kind}: aggregate rules are only supported under AND (not under {parent})"
                )
            # check min_total presence & type via Pydantic already; nothing else here
            continue

        if kind == "type_in":
            for oid in node.type_ids:
                if not exists_id("cache_types", oid):
                    errors.append(f"type_in: unknown cache_type id '{oid}'")
        elif kind == "size_in":
            for oid in node.size_ids:
                if not exists_id("cache_sizes", oid):
                    errors.append(f"size_in: unknown cache_size id '{oid}'")
        elif kind == "state_in":
            for oid in node.state_ids:
                if not exists_id("states", oid):
                    errors.append(f"state_in: unknown state id '{oid}'")
                # obligation d’un country_is sibling
                if isinstance(expr, TaskAnd):
                    if not _has_country_is(expr.nodes):
                        errors.append(
                            "state_in requires a sibling country_is in the same AND group"
                        )
        elif kind == "country_is":
            if not exists_id("countries", node.country_id):
                errors.append(f"country_is: unknown country id '{node.country_id}'")
        elif kind == "attributes":
            for i, a in enumerate(node.attributes):
                if not exists_attribute_id(a.cache_attribute_id):
                    errors.append(
                        f"attributes[{i}].cache_attribute_id unknown '{a.cache_attribute_id}'"
                    )
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
    """Adapter d’anciennes formes courtes vers la forme canonique.

    Description:
        Ex.: `type_in.codes -> type_in.types[{cache_type_code}]`,
        `size_in.codes -> size_in.sizes[{code}]`.

    Args:
        exp: Expression brute.

    Returns:
        Any: Expression transformée non destructivement.
    """

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


async def list_tasks(user_id: ObjectId, uc_id: ObjectId) -> list[dict[str, Any]]:
    """Lister les tâches d’un UC (déjà canoniques pour l’API).

    Description:
        Lit, tente une validation telle quelle, sinon applique un « legacy fixup »
        puis renvoie l’expression **canonisée** (AND par défaut).

    Args:
        user_id: Utilisateur.
        uc_id: UserChallenge.

    Returns:
        list[dict]: Tâches prêtes pour `TaskOut`.
    """
    coll = await get_collection("user_challenge_tasks")
    cur = coll.find({"user_challenge_id": uc_id}, sort=[("order", 1), ("_id", 1)])

    tasks: list[dict[str, Any]] = []
    async for d in cur:
        # title est requis côté TaskOut -> fallback si absent
        title = d.get("title") or "Untitled task"
        exp = d.get("expression")

        # Try to validate as-is
        try:
            exp_pre = preprocess_expression_default_and(exp)
            exp_model = cast(TaskExpression, TypeAdapter(TaskExpression).validate_python(exp_pre))
            exp_out = exp_model.model_dump(by_alias=True)
        except Exception:
            # Legacy repair, then validate
            fixed = _legacy_fixup_expression(exp)
            exp_pre = preprocess_expression_default_and(fixed)
            exp_model = cast(TaskExpression, TypeAdapter(TaskExpression).validate_python(exp_pre))
            exp_out = exp_model.model_dump(by_alias=True)
        tasks.append(
            {
                "id": d["_id"],  # TaskOut.id (PyObjectId géré par tes encoders)
                "order": d.get("order", 0),
                "title": title,
                "expression": exp_out,
                "constraints": d.get("constraints", {}),
                "status": d.get("status"),  # optionnel dans TaskOut
                "metrics": d.get("metrics"),
                "progress": d.get("progress"),
                "last_evaluated_at": d.get("last_evaluated_at"),
                "updated_at": d.get("updated_at"),
                "created_at": d.get("created_at"),
            }
        )

    return tasks


def validate_only(
    user_id: ObjectId, uc_id: ObjectId, tasks_payload: list[dict[str, Any]]
) -> dict[str, Any]:
    """Valider un payload de tâches **sans persister**.

    Args:
        user_id: Utilisateur.
        uc_id: UserChallenge.
        tasks_payload: Liste d’items de tâches.

    Returns:
        dict: `{ok: bool, errors: list[...]}`
    """

    def _mk_err(index: int, field: str, code: str, message: str) -> dict[str, Any]:
        return {"index": index, "field": field, "code": code, "message": message}

    try:
        _validate_tasks_payload(user_id, uc_id, tasks_payload)

        return {"ok": True, "errors": []}
    except ValidationError as e:
        # Pydantic validation of the AST structure / types
        msg = "; ".join(
            [err.get("msg", "validation error") for err in getattr(e, "errors", lambda: [])()]
            or [str(e)]
        )

        return {
            "ok": False,
            "errors": [_mk_err(0, "expression", "pydantic_validation_error", msg)],
        }
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


async def put_tasks(
    user_id: ObjectId, uc_id: ObjectId, tasks_payload: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Remplacer toutes les tâches d’un UC (canonisation + insert).

    Description:
        Valide, efface l’existant, insère des tâches **canonisées** (code→id),
        puis relit pour retour stable.

    Args:
        user_id: Utilisateur.
        uc_id: UserChallenge.
        tasks_payload: Liste de tâches.

    Returns:
        list[dict]: Tâches stockées (canonisées).
    """
    # Validate first (raises on error)
    _validate_tasks_payload(user_id, uc_id, tasks_payload)

    coll = await get_collection("user_challenge_tasks")
    await coll.delete_many({"user_challenge_id": uc_id})

    to_insert = []
    now = utcnow()
    for i, item in enumerate(tasks_payload):
        _maybe_id = item.get("id") or item.get("_id")
        doc_id = ObjectId(str(_maybe_id)) if _maybe_id else ObjectId()
        title = item.get("title") or f"Task #{i + 1}"

        # NEW: canonicalize expression for storage
        expr_pre = preprocess_expression_default_and(item["expression"])
        expr_model: TaskExpression = TypeAdapter(TaskExpression).validate_python(expr_pre)
        expr_model = _normalize_code_to_id(expr_model, index_for_errors=i)
        expr_canonical = expr_model.model_dump(by_alias=True)

        doc = {
            "_id": doc_id,
            "user_challenge_id": uc_id,
            "order": int(item.get("order", i)),
            "title": title,
            "expression": expr_canonical,  # <--- store canonical
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
        await coll.insert_many(to_insert, ordered=True)

    # read-back (already canonical)
    cur = coll.find({"user_challenge_id": uc_id}).sort([("order", 1), ("_id", 1)])
    items: list[dict[str, Any]] = []
    async for d in cur:
        items.append(
            {
                "id": d["_id"],
                "order": d.get("order", 0),
                "title": d.get("title"),
                "expression": d.get("expression"),  # already canonical
                "constraints": d.get("constraints", {}),
                "status": d.get("status"),
                "metrics": d.get("metrics"),
                "progress": d.get("progress"),
                "last_evaluated_at": d.get("last_evaluated_at"),
                "updated_at": d.get("updated_at"),
                "created_at": d.get("created_at"),
            }
        )

    return items


# --------------------------------------------------------------------------------------
# Internal validation utils (payload-level)
# --------------------------------------------------------------------------------------


def _validate_tasks_payload(
    user_id: ObjectId, uc_id: ObjectId, tasks_payload: list[dict[str, Any]]
) -> None:
    """Valider le payload de tâches (lève à la première erreur).

    Description:
        - Unicité/cohérence des `order`
        - Pydantic parse + normalisation code→id
        - Validation étendue (`validate_task_expression`)
        - Sanity check des `constraints` (min_count ≥ 0)

    Args:
        user_id: Utilisateur.
        uc_id: UserChallenge.
        tasks_payload: Liste d’items.

    Returns:
        None

    Raises:
        ValueError: En cas d’invalidité structurelle ou métier.
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
            expr_model: TaskExpression = TypeAdapter(TaskExpression).validate_python(expr_pre)

            # 3) tes normalisations existantes (ex: attributes.code -> ids, type_in.codes -> type_ids)
            expr_model = _normalize_code_to_id(expr_model, index_for_errors=i)

        except ValidationError as err:
            raise ValueError(f"invalid expression at index {i}: {err}") from err

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
            except Exception as err:
                raise ValueError(
                    f"constraints.min_count must be a non-negative integer (index {i})"
                ) from err

    # Optional: verify uc_id belongs to user? (depends on your security model)
    # get_collection("user_challenges").find_one({"_id": uc_id, "user_id": user_id}) ...
