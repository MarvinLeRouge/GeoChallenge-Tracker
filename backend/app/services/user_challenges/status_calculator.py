# backend/app/services/user_challenges/status_calculator.py
# Effective status calculation logic for UserChallenges.

from __future__ import annotations

from typing import Any


class StatusCalculator:
    """Effective status calculation service for UserChallenges.

    Description:
        Responsible for computing statuses by taking into account
        manual statuses, computed statuses, and overrides.
    """

    @staticmethod
    def calculate_effective_status(user_status: str | None, computed_status: str | None) -> str:
        """Calculate the effective status of a UserChallenge.

        Args:
            user_status: Manual status set by the user.
            computed_status: Automatically computed status.

        Returns:
            str: Effective status.
        """
        # Rule: completed if either manual or computed status is completed
        if user_status == "completed" or computed_status == "completed":
            return "completed"

        # Otherwise return the user status or 'pending' as default
        return user_status or "pending"

    @staticmethod
    def build_status_filter_pipeline(status_filter: str) -> list[dict[str, Any]]:
        """Build a MongoDB pipeline to filter by effective status.

        Args:
            status_filter: Status to filter on ('pending', 'accepted', 'dismissed', 'completed').

        Returns:
            list: MongoDB pipeline stages.
        """
        if status_filter == "completed":
            # Effective completed: manual OR computed status is completed
            return [
                {
                    "$match": {
                        "$or": [
                            {"status": "completed"},
                            {"computed_status": "completed"},
                        ]
                    }
                }
            ]

        elif status_filter == "dismissed":
            # Effective dismissed = user status (excluding completed)
            return [
                {
                    "$match": {
                        "$and": [
                            {"status": "dismissed"},
                            {"computed_status": {"$ne": "completed"}},
                        ]
                    }
                }
            ]

        elif status_filter == "accepted":
            # Effective accepted = user status (excluding completed)
            return [
                {
                    "$match": {
                        "$and": [
                            {"status": "accepted"},
                            {"computed_status": {"$ne": "completed"}},
                        ]
                    }
                }
            ]

        elif status_filter == "pending":
            # Effective pending = no user status (excluding completed)
            return [
                {
                    "$match": {
                        "$and": [
                            {"status": {"$in": [None, "pending"]}},
                            {"computed_status": {"$ne": "completed"}},
                        ]
                    }
                }
            ]

        # No filter
        return []

    @staticmethod
    def should_auto_complete(challenge_cache_found: bool) -> str | None:
        """Determine whether a UserChallenge should be auto-completed.

        Args:
            challenge_cache_found: True if the challenge's cache has been found.

        Returns:
            str | None: 'completed' if auto-completion applies, None otherwise.
        """
        return "completed" if challenge_cache_found else None

    @staticmethod
    def create_progress_snapshot(completion_percent: float = 100.0) -> dict[str, Any]:
        """Create a progress snapshot.

        Args:
            completion_percent: Completion percentage.

        Returns:
            dict: Progress snapshot.
        """
        from app.core.utils import utcnow

        return {
            "percent": completion_percent,
            "tasks_done": 1 if completion_percent >= 100.0 else 0,
            "tasks_total": 1,
            "checked_at": utcnow(),
        }

    @staticmethod
    def validate_status_transition(
        current_status: str | None,
        new_status: str | None,
        computed_status: str | None,
    ) -> tuple[bool, str | None]:
        """Validate a status transition.

        Args:
            current_status: Current status.
            new_status: Requested new status.
            computed_status: Computed status.

        Returns:
            tuple: (is_valid, error_message).
        """
        valid_statuses = ["pending", "accepted", "dismissed", "completed"]

        # Verify that the new status is valid
        if new_status and new_status not in valid_statuses:
            return False, f"Invalid status: {new_status}"

        # If computed_status is completed, downgrading is not allowed
        if computed_status == "completed" and new_status in ["pending", "dismissed"]:
            return False, "Cannot change status of auto-completed challenge"

        return True, None

    @staticmethod
    def determine_override_logic(
        new_status: str | None,
        computed_status: str | None,
    ) -> tuple[bool, str | None]:
        """Determine manual override logic.

        Args:
            new_status: Requested new status.
            computed_status: Computed status.

        Returns:
            tuple: (is_manual_override, override_type).
        """
        # Override if forcing completed while not yet auto-completed
        if new_status == "completed" and computed_status != "completed":
            return True, "manual_completion"

        # Override if forcing a status different from the computed one
        if computed_status and new_status and new_status != computed_status:
            return True, "status_override"

        return False, None
