# backend/app/services/user_challenge_tasks/task_expression_validator.py
# Expression validation — exact preservation of the logic.

from __future__ import annotations

import re
from typing import Any, Callable

from app.domain.models.challenge_ast import TaskAnd, TaskExpression
from app.services.referentials_cache import exists_attribute_id, exists_id

from .task_expression_compiler import TaskExpressionCompiler


class TaskExpressionValidator:
    """AST expression validator.

    Description:
        Exact preservation of the existing validate_task_expression
        and _validate_tasks_payload logic. No behavioral changes.
    """

    def __init__(self):
        """Initialize the validator."""
        self.compiler = TaskExpressionCompiler()

    def validate_task_expression(self, expr: TaskExpression) -> list[str]:
        """Extended validation of a task expression.

        FUNCTION IDENTICAL TO THE ORIGINAL validate_task_expression.

        Description:
            - Referentials (types, sizes, countries/states, attributes).
            - Numeric bounds (min/max).
            - Aggregates: **AND-only**, at most one per task.

        Args:
            expr: Already Pydantic-validated expression.

        Returns:
            list[str]: List of errors (empty if OK).
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
                # min_total presence & type checked by Pydantic already; nothing else here
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
                    # a sibling country_is is required
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
        normalize_func: Callable[..., Any],
        preprocess_func: Callable[..., Any],
        TypeAdapter: Any,
    ) -> None:
        """Validate the task payload (raises on the first error).

        FUNCTION IDENTICAL TO THE ORIGINAL _validate_tasks_payload.

        Description:
            - Uniqueness/consistency of `order` values.
            - Pydantic parse + code→id normalization.
            - Extended validation (`validate_task_expression`).
            - Sanity check of `constraints` (min_count >= 0).

        Args:
            user_id: User identifier.
            uc_id: UserChallenge identifier.
            tasks_payload: List of task items.
            normalize_func: Normalization function.
            preprocess_func: Preprocessing function.
            TypeAdapter: Pydantic type adapter.

        Returns:
            None

        Raises:
            ValueError: On structural or business invalidity.
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
                # 1) apply short form -> canonical (AND by default)
                expr_pre = preprocess_func(expr_raw)

                # 2) validate/parse Pydantic (Union of nodes)
                expr_model: TaskExpression = TypeAdapter(TaskExpression).validate_python(expr_pre)

                # 3) existing normalizations (e.g. attributes.code -> ids, type_in.codes -> type_ids)
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
        normalize_func: Callable[..., Any],
        preprocess_func: Callable[..., Any],
        TypeAdapter: Any,
    ) -> dict[str, Any]:
        """Validate a task payload **without persisting** and format the response.

        FUNCTION IDENTICAL TO THE ORIGINAL validate_only.

        Args:
            user_id: User identifier.
            uc_id: UserChallenge identifier.
            tasks_payload: List of task items.
            normalize_func: Normalization function.
            preprocess_func: Preprocessing function.
            TypeAdapter: Pydantic type adapter.

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
