# backend/app/services/targets/target_scorer.py
# Scoring algorithms for cache targets.

from __future__ import annotations

from typing import Any

from bson import ObjectId

from .geo_utils import calculate_geo_score


class TargetScorer:
    """Score calculation service for cache targets.

    Description:
        Centralizes all scoring algorithms:
        - Geographic score (proximity)
        - Urgency score (task progression)
        - Coverage score (number of tasks satisfied)
        - Final composite score
    """

    @staticmethod
    def calculate_task_urgency_score(matched_tasks: list[dict[str, Any]]) -> float:
        """Calculate the urgency score based on task ratios.

        Args:
            matched_tasks: List of matched tasks with their ratios.

        Returns:
            float: Urgency score (0.0 to 1.0).
        """
        if not matched_tasks:
            return 0.0

        # Take the maximum ratio (most advanced task)
        max_ratio = max(task.get("ratio", 0.0) for task in matched_tasks)
        return min(max_ratio, 1.0)

    @staticmethod
    def calculate_task_coverage_score(
        matched_tasks_count: int, total_incomplete_tasks: int
    ) -> float:
        """Calculate the task coverage score.

        Args:
            matched_tasks_count: Number of tasks covered by this cache.
            total_incomplete_tasks: Total number of incomplete tasks.

        Returns:
            float: Coverage score (0.0 to 1.0).
        """
        if total_incomplete_tasks <= 0:
            return 0.0

        return min(matched_tasks_count / total_incomplete_tasks, 1.0)

    @staticmethod
    def choose_primary_task_by_ratio(matched_tasks: list[dict[str, Any]]) -> ObjectId | None:
        """Choose the primary task based on the progression ratio.

        Args:
            matched_tasks: List of tasks with their metrics.

        Returns:
            ObjectId | None: Primary task ID or None.
        """
        if not matched_tasks:
            return None

        # Select the task with the highest ratio
        primary_task = max(matched_tasks, key=lambda t: t.get("ratio", 0.0))
        return primary_task.get("_id")

    @classmethod
    def calculate_composite_score(
        cls,
        matched_tasks: list[dict[str, Any]],
        total_incomplete_tasks: int,
        distance_m: float | None = None,
        radius_km: float | None = None,
        weights: dict[str, float] | None = None,
    ) -> dict[str, float]:
        """Calculate the final composite score for a target.

        Args:
            matched_tasks: Matched tasks with their metrics.
            total_incomplete_tasks: Total number of incomplete tasks.
            distance_m: Distance in meters (optional, for the geo score).
            radius_km: Reference radius in km (optional, for the geo score).
            weights: Custom weights for score components.

        Returns:
            dict[str, float]: Detailed scores and composite score.
        """
        # Default weights
        default_weights = {
            "urgency": 0.4,  # Priority to advanced tasks
            "coverage": 0.3,  # Importance of covering multiple tasks
            "geographic": 0.3,  # Bonus for proximity
        }

        if weights:
            default_weights.update(weights)

        # Calculate individual scores
        urgency_score = cls.calculate_task_urgency_score(matched_tasks)
        coverage_score = cls.calculate_task_coverage_score(
            len(matched_tasks), total_incomplete_tasks
        )

        # Geographic score (optional)
        geo_score = 0.0
        if distance_m is not None and radius_km is not None:
            geo_score = calculate_geo_score(distance_m, radius_km)

        # Weighted composite score
        composite_score = (
            urgency_score * default_weights["urgency"]
            + coverage_score * default_weights["coverage"]
            + geo_score * default_weights["geographic"]
        )

        return {
            "urgency": urgency_score,
            "coverage": coverage_score,
            "geographic": geo_score,
            "composite": min(composite_score, 1.0),  # Cap at 1.0
        }

    @staticmethod
    def get_task_constraints_min_count(task_doc: dict[str, Any]) -> int:
        """Extract the min_count from a task document.

        Args:
            task_doc: MongoDB task document.

        Returns:
            int: min_count constraint, or 1 by default.
        """
        constraints = task_doc.get("constraints", {})
        return int(constraints.get("min_count", 1))
