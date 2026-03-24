"""Tests for PatchTaskItem (unit — pure Pydantic model)."""

from __future__ import annotations

from bson import ObjectId

from app.domain.models.challenge_ast import RulePlacedYear, TaskAnd
from app.services.user_challenge_tasks.task_data_models import PatchTaskItem


def _minimal_expr():
    return TaskAnd(nodes=[RulePlacedYear(year=2020)])


class TestPatchTaskItem:
    def test_minimal_valid(self):
        item = PatchTaskItem(
            user_challenge_id=ObjectId(),
            expression=_minimal_expr(),
        )
        assert item.order == 0
        assert item.constraints == {}
        assert item.metrics == {}
        assert item.notes is None

    def test_custom_order_and_notes(self):
        item = PatchTaskItem(
            user_challenge_id=ObjectId(),
            order=3,
            expression=_minimal_expr(),
            notes="test note",
        )
        assert item.order == 3
        assert item.notes == "test note"

    def test_constraints_and_metrics(self):
        item = PatchTaskItem(
            user_challenge_id=ObjectId(),
            expression=_minimal_expr(),
            constraints={"min_count": 5},
            metrics={"current_count": 2},
        )
        assert item.constraints["min_count"] == 5
        assert item.metrics["current_count"] == 2

    def test_notes_none_accepted(self):
        item = PatchTaskItem(
            user_challenge_id=ObjectId(),
            expression=_minimal_expr(),
            notes=None,
        )
        assert item.notes is None

    def test_serializes_to_dict(self):
        uc_id = ObjectId()
        item = PatchTaskItem(
            user_challenge_id=uc_id,
            expression=_minimal_expr(),
        )
        d = item.model_dump()
        assert "user_challenge_id" in d
        assert "expression" in d
