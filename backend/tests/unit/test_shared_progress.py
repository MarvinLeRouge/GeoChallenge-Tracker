"""Tests for ProgressSnapshot (unit — pure Pydantic model)."""

from __future__ import annotations

import datetime as dt

from app.shared.progress import ProgressSnapshot


class TestProgressSnapshot:
    def test_default_values(self):
        snap = ProgressSnapshot()
        assert snap.percent == 0.0
        assert snap.tasks_done == 0
        assert snap.tasks_total == 0
        assert isinstance(snap.checked_at, dt.datetime)

    def test_custom_values(self):
        snap = ProgressSnapshot(percent=75.0, tasks_done=3, tasks_total=4)
        assert snap.percent == 75.0
        assert snap.tasks_done == 3
        assert snap.tasks_total == 4

    def test_percent_100(self):
        snap = ProgressSnapshot(percent=100.0, tasks_done=5, tasks_total=5)
        assert snap.percent == 100.0

    def test_checked_at_auto_set(self):
        before = dt.datetime.now()
        snap = ProgressSnapshot()
        after = dt.datetime.now()
        assert before <= snap.checked_at.replace(tzinfo=None) <= after

    def test_explicit_checked_at(self):
        ts = dt.datetime(2024, 6, 1, 12, 0, 0)
        snap = ProgressSnapshot(checked_at=ts)
        assert snap.checked_at == ts

    def test_serializes_to_dict(self):
        snap = ProgressSnapshot(percent=50.0, tasks_done=1, tasks_total=2)
        d = snap.model_dump()
        assert d["percent"] == 50.0
        assert d["tasks_done"] == 1
        assert d["tasks_total"] == 2
        assert "checked_at" in d
