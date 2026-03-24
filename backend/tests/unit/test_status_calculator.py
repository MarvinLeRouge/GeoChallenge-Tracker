"""Tests for StatusCalculator (unit tests - no DB required)."""

from __future__ import annotations

from app.services.user_challenges.status_calculator import StatusCalculator


class TestCalculateEffectiveStatus:
    def test_both_none_returns_pending(self):
        assert StatusCalculator.calculate_effective_status(None, None) == "pending"

    def test_user_status_completed_wins(self):
        assert StatusCalculator.calculate_effective_status("completed", None) == "completed"

    def test_computed_status_completed_wins(self):
        assert StatusCalculator.calculate_effective_status("accepted", "completed") == "completed"

    def test_both_completed_returns_completed(self):
        assert StatusCalculator.calculate_effective_status("completed", "completed") == "completed"

    def test_user_status_accepted_returned(self):
        assert StatusCalculator.calculate_effective_status("accepted", None) == "accepted"

    def test_user_status_dismissed_returned(self):
        assert StatusCalculator.calculate_effective_status("dismissed", None) == "dismissed"

    def test_none_user_status_returns_pending(self):
        assert StatusCalculator.calculate_effective_status(None, "accepted") == "pending"


class TestBuildStatusFilterPipeline:
    def test_completed_filter(self):
        pipeline = StatusCalculator.build_status_filter_pipeline("completed")
        assert len(pipeline) == 1
        match = pipeline[0]["$match"]
        assert "$or" in match

    def test_dismissed_filter(self):
        pipeline = StatusCalculator.build_status_filter_pipeline("dismissed")
        assert len(pipeline) == 1
        match = pipeline[0]["$match"]
        assert "$and" in match
        conditions = match["$and"]
        statuses = [c.get("status") for c in conditions]
        assert "dismissed" in statuses

    def test_accepted_filter(self):
        pipeline = StatusCalculator.build_status_filter_pipeline("accepted")
        assert len(pipeline) == 1
        match = pipeline[0]["$match"]
        assert "$and" in match

    def test_pending_filter(self):
        pipeline = StatusCalculator.build_status_filter_pipeline("pending")
        assert len(pipeline) == 1
        match = pipeline[0]["$match"]
        assert "$and" in match

    def test_unknown_filter_returns_empty(self):
        pipeline = StatusCalculator.build_status_filter_pipeline("unknown_status")
        assert pipeline == []


class TestShouldAutoComplete:
    def test_cache_found_returns_completed(self):
        assert StatusCalculator.should_auto_complete(True) == "completed"

    def test_cache_not_found_returns_none(self):
        assert StatusCalculator.should_auto_complete(False) is None


class TestCreateProgressSnapshot:
    def test_100_percent_tasks_done_is_1(self):
        snap = StatusCalculator.create_progress_snapshot(100.0)
        assert snap["percent"] == 100.0
        assert snap["tasks_done"] == 1
        assert snap["tasks_total"] == 1

    def test_50_percent_tasks_done_is_0(self):
        snap = StatusCalculator.create_progress_snapshot(50.0)
        assert snap["tasks_done"] == 0

    def test_snapshot_has_checked_at(self):
        snap = StatusCalculator.create_progress_snapshot()
        assert "checked_at" in snap


class TestValidateStatusTransition:
    def test_valid_accepted(self):
        ok, err = StatusCalculator.validate_status_transition(None, "accepted", None)
        assert ok is True
        assert err is None

    def test_invalid_status_string(self):
        ok, err = StatusCalculator.validate_status_transition(None, "invalid", None)
        assert ok is False
        assert "Invalid status" in err

    def test_downgrade_from_computed_completed_rejected(self):
        ok, err = StatusCalculator.validate_status_transition("completed", "pending", "completed")
        assert ok is False
        assert "auto-completed" in err

    def test_downgrade_to_dismissed_rejected_when_computed_completed(self):
        ok, err = StatusCalculator.validate_status_transition("completed", "dismissed", "completed")
        assert ok is False

    def test_none_new_status_is_valid(self):
        ok, err = StatusCalculator.validate_status_transition("accepted", None, None)
        assert ok is True


class TestDetermineOverrideLogic:
    def test_manual_completion_when_not_yet_computed(self):
        override, kind = StatusCalculator.determine_override_logic("completed", "pending")
        assert override is True
        assert kind == "manual_completion"

    def test_status_override_when_different_from_computed(self):
        override, kind = StatusCalculator.determine_override_logic("dismissed", "accepted")
        assert override is True
        assert kind == "status_override"

    def test_no_override_when_same_as_computed(self):
        override, kind = StatusCalculator.determine_override_logic("accepted", "accepted")
        assert override is False
        assert kind is None

    def test_no_override_when_both_none(self):
        override, kind = StatusCalculator.determine_override_logic(None, None)
        assert override is False
