# backend/app/services/user_challenge_tasks/task_expression_validator.py
# Validation des expressions - PRESERVATION EXACTE DE LA LOGIQUE

from __future__ import annotations

import re
from typing import Any, Callable

from app.domain.models.challenge_ast import TaskAnd, TaskExpression
from app.services.referentials_cache import exists_attribute_id, exists_id

from .task_expression_compiler import TaskExpressionCompiler


class TaskExpressionValidator:
    """Validateur d'expressions AST.

    Description:
        Préservation EXACTE de la logique existante de validate_task_expression
        et _validate_tasks_payload. Aucune modification comportementale.
    """

    def __init__(self):
        """Initialiser le validateur."""
        self.compiler = TaskExpressionCompiler()

    def validate_task_expression(self, expr: TaskExpression) -> list[str]:
        """Validation étendue d'une expression de tâche.

        FONCTION IDENTIQUE À L'ORIGINALE validate_task_expression.

        Description:
            - Référentiels (types, tailles, pays/états, attributs)
            - Bornes numériques (min/max)
            - Agrégats: **AND-only**, au plus un par tâche

        Args:
            expr: Expression déjà Pydantic-validée.

        Returns:
            list[str]: Liste d'erreurs (vide si OK).
        """
        errors: list[str] = []
        aggregate_count = 0

        for kind, node, parent in self.compiler.walk_expression_tree(expr):
            if self.compiler.is_aggregate_kind(kind):
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
                    # obligation d'un country_is sibling
                    if isinstance(expr, TaskAnd):
                        if not self.compiler.has_country_is_in_and(expr.nodes):
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

    def validate_tasks_payload(
        self,
        user_id: Any,
        uc_id: Any,
        tasks_payload: list[dict[str, Any]],
        normalize_func: callable,
        preprocess_func: callable,
        TypeAdapter: Any,
    ) -> None:
        """Valider le payload de tâches (lève à la première erreur).

        FONCTION IDENTIQUE À L'ORIGINALE _validate_tasks_payload.

        Description:
            - Unicité/cohérence des `order`
            - Pydantic parse + normalisation code→id
            - Validation étendue (`validate_task_expression`)
            - Sanity check des `constraints` (min_count ≥ 0)

        Args:
            user_id: Utilisateur.
            uc_id: UserChallenge.
            tasks_payload: Liste d'items.
            normalize_func: Fonction de normalisation.
            preprocess_func: Fonction de préprocessing.
            TypeAdapter: Adaptateur de type Pydantic.

        Returns:
            None

        Raises:
            ValueError: En cas d'invalidité structurelle ou métier.
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
                expr_pre = preprocess_func(expr_raw)

                # 2) valider/parse Pydantic (Union des nœuds)
                expr_model: TaskExpression = TypeAdapter(TaskExpression).validate_python(expr_pre)

                # 3) tes normalisations existantes (ex: attributes.code -> ids, type_in.codes -> type_ids)
                expr_model = normalize_func(expr_model, index_for_errors=i)

            except Exception as err:
                raise ValueError(f"invalid expression at index {i}: {err}") from err

            # NEW: extended validation (aggregates + referentials)
            errs = self.validate_task_expression(expr_model)
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

    def validate_only_format_response(
        self,
        user_id: Any,
        uc_id: Any,
        tasks_payload: list[dict[str, Any]],
        normalize_func: callable,
        preprocess_func: callable,
        TypeAdapter: Any,
    ) -> dict[str, Any]:
        """Valider un payload de tâches **sans persister** et formater la réponse.

        FONCTION IDENTIQUE À L'ORIGINALE validate_only.

        Args:
            user_id: Utilisateur.
            uc_id: UserChallenge.
            tasks_payload: Liste d'items de tâches.
            normalize_func: Fonction de normalisation.
            preprocess_func: Fonction de préprocessing.
            TypeAdapter: Adaptateur de type Pydantic.

        Returns:
            dict: `{ok: bool, errors: list[...]}`
        """

        def _mk_err(index: int, field: str, code: str, message: str) -> dict[str, Any]:
            return {"index": index, "field": field, "code": code, "message": message}

        try:
            self.validate_tasks_payload(
                user_id, uc_id, tasks_payload, normalize_func, preprocess_func, TypeAdapter
            )

            return {"ok": True, "errors": []}
        except Exception as e:
            # Check if it's a Pydantic ValidationError
            if hasattr(e, "errors") and callable(getattr(e, "errors", None)):
                # Pydantic validation of the AST structure / types
                try:
                    pydantic_errors = e.errors()
                except Exception:
                    pydantic_errors = [{"msg": str(e)}]

                msg = "; ".join(
                    [err.get("msg", "validation error") for err in pydantic_errors] or [str(e)]
                )

                return {
                    "ok": False,
                    "errors": [_mk_err(0, "expression", "pydantic_validation_error", msg)],
                }
            else:
                # Our validate_tasks_payload raises ValueError with messages like "invalid expression at index i: ...",
                # or "constraints.min_count ... (index i)". Extract the index if present.
                s = str(e)
                m = re.search(r"index\s+(\d+)", s)
                idx = int(m.group(1)) if m else 0
                # Try to infer the field mentioned in the message, default to expression
                field = "constraints" if "constraints" in s else "expression"
                code = "invalid_expression" if "expression" in s else "invalid_payload"

                return {"ok": False, "errors": [_mk_err(idx, field, code, s)]}
