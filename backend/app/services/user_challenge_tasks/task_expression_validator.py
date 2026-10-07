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

    def _validate_aggregate_node(self, kind: str, parent: str | None) -> list[str]:
        """Validate an aggregate-kind node's placement (AND-only).

        Args:
            kind: Aggregate node kind.
            parent: Parent node kind ("and"/"or"/"not"/None).

        Returns:
            list[str]: Validation errors (empty if placement is valid).
        """
        if parent in ("or", "not"):
            return [f"{kind}: aggregate rules are only supported under AND (not under {parent})"]
        return []

    @staticmethod
    def _validate_type_in_node(node: Any) -> list[str]:
        """Validate a `type_in` node's referenced cache type ids.

        Args:
            node: Parsed `type_in` AST node.

        Returns:
            list[str]: Validation errors.
        """
        errors: list[str] = []
        for t in node.types:
            if t.cache_type_doc_id is not None and not exists_id(
                "cache_types", t.cache_type_doc_id
            ):
                errors.append(f"type_in: unknown cache_type id '{t.cache_type_doc_id}'")
        return errors

    @staticmethod
    def _validate_size_in_node(node: Any) -> list[str]:
        """Validate a `size_in` node's referenced cache size ids.

        Args:
            node: Parsed `size_in` AST node.

        Returns:
            list[str]: Validation errors.
        """
        errors: list[str] = []
        for s in node.sizes:
            if s.cache_size_doc_id is not None and not exists_id(
                "cache_sizes", s.cache_size_doc_id
            ):
                errors.append(f"size_in: unknown cache_size id '{s.cache_size_doc_id}'")
        return errors

    def _validate_state_in_node(self, node: Any, expr: TaskExpression) -> list[str]:
        """Validate a `state_in` node's state ids and sibling `country_is` requirement.

        Args:
            node: Parsed `state_in` AST node.
            expr: The full expression, to check for a sibling `country_is`.

        Returns:
            list[str]: Validation errors.
        """
        errors: list[str] = []
        for oid in node.state_ids:
            if not exists_id("states", oid):
                errors.append(f"state_in: unknown state id '{oid}'")
            # a sibling country_is is required
            if isinstance(expr, TaskAnd):
                if not self.compiler.has_country_is_in_and(expr.nodes):
                    errors.append("state_in requires a sibling country_is in the same AND group")
        return errors

    @staticmethod
    def _validate_country_is_node(node: Any) -> list[str]:
        """Validate a `country_is` node's referenced country id.

        Args:
            node: Parsed `country_is` AST node.

        Returns:
            list[str]: Validation errors.
        """
        if not exists_id("countries", node.country.country_id):
            return [f"country_is: unknown country id '{node.country.country_id}'"]
        return []

    @staticmethod
    def _validate_attributes_node(node: Any) -> list[str]:
        """Validate an `attributes` node's referenced attribute ids.

        Args:
            node: Parsed `attributes` AST node.

        Returns:
            list[str]: Validation errors.
        """
        errors: list[str] = []
        for i, a in enumerate(node.attributes):
            if not exists_attribute_id(a.cache_attribute_id):
                errors.append(
                    f"attributes[{i}].cache_attribute_id unknown '{a.cache_attribute_id}'"
                )
        return errors

    @staticmethod
    def _validate_between_node(kind: str, node: Any) -> list[str]:
        """Validate a `difficulty_between`/`terrain_between` node's min <= max bound.

        Args:
            kind: Node kind (for the error message).
            node: Parsed `*_between` AST node.

        Returns:
            list[str]: Validation errors.
        """
        if node.min > node.max:
            return [f"{kind}: min must be <= max"]
        return []

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
                errors.extend(self._validate_aggregate_node(kind, parent))
                # min_total presence & type checked by Pydantic already; nothing else here
                continue

            if kind == "type_in":
                errors.extend(self._validate_type_in_node(node))
            elif kind == "size_in":
                errors.extend(self._validate_size_in_node(node))
            elif kind == "state_in":
                errors.extend(self._validate_state_in_node(node, expr))
            elif kind == "country_is":
                errors.extend(self._validate_country_is_node(node))
            elif kind == "attributes":
                errors.extend(self._validate_attributes_node(node))
            elif kind in ("difficulty_between", "terrain_between"):
                errors.extend(self._validate_between_node(kind, node))
            # placed_year/before/after validated by pydantic types

        if aggregate_count > 1:
            errors.append("Only a single aggregate rule is supported per task (MVP)")

        return errors

    @staticmethod
    def _register_task_order(i: int, item: dict[str, Any], seen_orders: set[int]) -> None:
        """Check `order` uniqueness and register it in `seen_orders`.

        Args:
            i: Task index (used as the default order and in error messages).
            item: Raw task payload item.
            seen_orders: Orders seen so far, mutated in place.

        Raises:
            ValueError: If `order` was already seen.
        """
        order_val = int(item.get("order", i))
        if order_val in seen_orders:
            raise ValueError(f"duplicate order '{order_val}' in tasks payload")
        seen_orders.add(order_val)

    @staticmethod
    def _parse_and_normalize_expression(
        i: int,
        expr_raw: Any,
        preprocess_func: Callable[..., Any],
        TypeAdapter: Any,
        normalize_func: Callable[..., Any],
    ) -> TaskExpression:
        """Preprocess, Pydantic-parse, then normalize a raw task expression.

        Args:
            i: Task index (for error messages).
            expr_raw: Raw expression payload.
            preprocess_func: Short-form -> canonical preprocessing function.
            TypeAdapter: Pydantic type adapter.
            normalize_func: Code -> id normalization function.

        Returns:
            TaskExpression: The parsed and normalized expression.

        Raises:
            ValueError: On any parse/validation failure.
        """
        try:
            # 1) apply short form -> canonical (AND by default)
            expr_pre = preprocess_func(expr_raw)

            # 2) validate/parse Pydantic (Union of nodes)
            expr_model: TaskExpression = TypeAdapter(TaskExpression).validate_python(expr_pre)

            # 3) existing normalizations (e.g. attributes.code -> ids, type_in.codes -> type_ids)
            return normalize_func(expr_model, index_for_errors=i)

        except Exception as err:
            raise ValueError(f"invalid expression at index {i}: {err}") from err

    @staticmethod
    def _validate_task_constraints(i: int, constraints: dict[str, Any]) -> None:
        """Sanity-check a task's `constraints` (currently just `min_count >= 0`).

        Args:
            i: Task index (for error messages).
            constraints: The task's `constraints` dict.

        Raises:
            ValueError: If `min_count` is present but not a non-negative integer.
        """
        if "min_count" not in constraints:
            return
        try:
            mc = int(constraints["min_count"])
            if mc < 0:
                raise ValueError
        except Exception as err:
            raise ValueError(
                f"constraints.min_count must be a non-negative integer (index {i})"
            ) from err

    def _validate_single_task_item(
        self,
        i: int,
        item: dict[str, Any],
        seen_orders: set[int],
        normalize_func: Callable[..., Any],
        preprocess_func: Callable[..., Any],
        TypeAdapter: Any,
    ) -> None:
        """Validate one task payload item (raises on the first error).

        Args:
            i: Task index.
            item: Raw task payload item.
            seen_orders: Orders seen so far, mutated in place.
            normalize_func: Normalization function.
            preprocess_func: Preprocessing function.
            TypeAdapter: Pydantic type adapter.

        Raises:
            ValueError: On any structural or business invalidity.
        """
        self._register_task_order(i, item, seen_orders)

        # pydantic-parse expression first (will ensure structure & types)
        expr_raw = item.get("expression")
        if expr_raw is None:
            raise ValueError("each task must have an 'expression'")
        expr_model = self._parse_and_normalize_expression(
            i, expr_raw, preprocess_func, TypeAdapter, normalize_func
        )

        # NEW: extended validation (aggregates + referentials)
        errs = self.validate_task_expression(expr_model)
        if errs:
            raise ValueError(f"expression at index {i} invalid: {errs}")

        # constraints basic sanity (min_count >= 0 if provided)
        self._validate_task_constraints(i, item.get("constraints") or {})

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
        seen_orders: set[int] = set()
        for i, item in enumerate(tasks_payload):
            self._validate_single_task_item(
                i, item, seen_orders, normalize_func, preprocess_func, TypeAdapter
            )

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
