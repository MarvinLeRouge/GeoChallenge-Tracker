# backend/app/services/user_challenge_tasks/user_challenge_task_service.py
# Main service — exact preservation of public APIs.

from __future__ import annotations

from typing import Any, cast

from bson import ObjectId
from pydantic import TypeAdapter

from app.core.utils import utcnow
from app.db.mongodb import get_collection
from app.domain.models.challenge_ast import (
    TaskExpression,
    preprocess_expression_default_and,
)

from .task_expression_compiler import TaskExpressionCompiler
from .task_expression_normalizer import TaskExpressionNormalizer
from .task_expression_validator import TaskExpressionValidator


class UserChallengeTaskService:
    """Main UserChallenge task management service.

    Description:
        Exact preservation of the 3 public APIs: list_tasks, put_tasks, validate_only.
        No behavioral changes — purely modular reorganization.
    """

    def __init__(self):
        """Initialize the service."""
        self.compiler = TaskExpressionCompiler()
        self.normalizer = TaskExpressionNormalizer()
        self.validator = TaskExpressionValidator()

    async def list_tasks(self, user_id: ObjectId, uc_id: ObjectId) -> list[dict[str, Any]]:
        """List the tasks of a UC (already canonical for the API).

        FUNCTION IDENTICAL TO THE ORIGINAL list_tasks.

        Description:
            Reads tasks, attempts validation as-is, otherwise applies a legacy fixup,
            then returns the **canonicalized** expression (AND by default).

        Args:
            user_id: User identifier.
            uc_id: UserChallenge identifier.

        Returns:
            list[dict]: Tasks ready for `TaskOut`.
        """
        coll = await get_collection("user_challenge_tasks")
        cur = coll.find({"user_challenge_id": uc_id}, sort=[("order", 1), ("_id", 1)])

        tasks: list[dict[str, Any]] = []
        async for d in cur:
            # title is required by TaskOut -> fallback if absent
            title = d.get("title") or "Untitled task"
            exp = d.get("expression")

            # Try to validate as-is
            try:
                exp_pre = preprocess_expression_default_and(exp)
                exp_model = cast(
                    TaskExpression, TypeAdapter(TaskExpression).validate_python(exp_pre)
                )
                exp_out = exp_model.model_dump(by_alias=True)
            except Exception:
                # Legacy repair, then validate
                fixed = self.normalizer.legacy_fixup_expression(exp)
                exp_pre = preprocess_expression_default_and(fixed)
                exp_model = cast(
                    TaskExpression, TypeAdapter(TaskExpression).validate_python(exp_pre)
                )
                exp_out = exp_model.model_dump(by_alias=True)
            tasks.append(
                {
                    "id": d["_id"],  # TaskOut.id (PyObjectId handled by encoders)
                    "order": d.get("order", 0),
                    "title": title,
                    "expression": exp_out,
                    "constraints": d.get("constraints", {}),
                    "status": d.get("status"),  # optional in TaskOut
                    "metrics": d.get("metrics"),
                    "progress": d.get("progress"),
                    "last_evaluated_at": d.get("last_evaluated_at"),
                    "updated_at": d.get("updated_at"),
                    "created_at": d.get("created_at"),
                }
            )

        return tasks

    def validate_only(
        self, user_id: ObjectId, uc_id: ObjectId, tasks_payload: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Validate a task payload **without persisting**.

        FUNCTION IDENTICAL TO THE ORIGINAL validate_only.

        Args:
            user_id: User identifier.
            uc_id: UserChallenge identifier.
            tasks_payload: List of task items.

        Returns:
            dict: `{ok: bool, errors: list[...]}`
        """
        return self.validator.validate_only_format_response(
            user_id=user_id,
            uc_id=uc_id,
            tasks_payload=tasks_payload,
            normalize_func=self.normalizer.normalize_code_to_id,
            preprocess_func=preprocess_expression_default_and,
            TypeAdapter=TypeAdapter,
        )

    async def put_tasks(
        self, user_id: ObjectId, uc_id: ObjectId, tasks_payload: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Replace all tasks of a UC (canonicalization + insert).

        FUNCTION IDENTICAL TO THE ORIGINAL put_tasks.

        Description:
            Validates, deletes existing tasks, inserts **canonicalized** tasks (code→id),
            then re-reads for a stable return value.

        Args:
            user_id: User identifier.
            uc_id: UserChallenge identifier.
            tasks_payload: List of tasks.

        Returns:
            list[dict]: Stored tasks (canonicalized).
        """
        # Validate first (raises on error)
        self.validator.validate_tasks_payload(
            user_id=user_id,
            uc_id=uc_id,
            tasks_payload=tasks_payload,
            normalize_func=self.normalizer.normalize_code_to_id,
            preprocess_func=preprocess_expression_default_and,
            TypeAdapter=TypeAdapter,
        )

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
            expr_model = self.normalizer.normalize_code_to_id(expr_model, index_for_errors=i)
            expr_canonical = expr_model.model_dump(by_alias=True)

            doc = {
                "_id": doc_id,
                "user_challenge_id": uc_id,
                "order": int(item.get("order", i)),
                "title": title,
                "expression": expr_canonical,  # store canonical form
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

    # === Utility functions exposed for compatibility ===

    def compile_expression_to_cache_match(self, expr: TaskExpression) -> dict[str, Any]:
        """Utility function exposed for external compatibility.

        Args:
            expr: Validated AST expression.

        Returns:
            dict: MongoDB filter for the caches collection.
        """
        return self.compiler.compile_expression_to_cache_match(expr)

    def validate_task_expression(self, expr: TaskExpression) -> list[str]:
        """Utility function exposed for external compatibility.

        Args:
            expr: Validated AST expression.

        Returns:
            list[str]: List of errors (empty if OK).
        """
        return self.validator.validate_task_expression(expr)
