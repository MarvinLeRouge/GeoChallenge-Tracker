# backend/app/services/targets/target_scorer.py
# Algorithmes de scoring pour les targets de caches.

from __future__ import annotations

from typing import Any

from bson import ObjectId

from .geo_utils import calculate_geo_score


class TargetScorer:
    """Service de calcul des scores pour les targets de caches.

    Description:
        Centralise tous les algorithmes de scoring :
        - Score géographique (proximité)
        - Score d'urgence (progression des tâches)
        - Score de couverture (nombre de tâches satisfaites)
        - Score composite final
    """

    @staticmethod
    def calculate_task_urgency_score(matched_tasks: list[dict[str, Any]]) -> float:
        """Calculer le score d'urgence basé sur les ratios des tâches.

        Args:
            matched_tasks: Liste des tâches correspondantes avec leurs ratios.

        Returns:
            float: Score d'urgence (0.0 à 1.0).
        """
        if not matched_tasks:
            return 0.0

        # Prendre le ratio maximum (tâche la plus avancée)
        max_ratio = max(task.get("ratio", 0.0) for task in matched_tasks)
        return min(max_ratio, 1.0)

    @staticmethod
    def calculate_task_coverage_score(
        matched_tasks_count: int, total_incomplete_tasks: int
    ) -> float:
        """Calculer le score de couverture des tâches.

        Args:
            matched_tasks_count: Nombre de tâches couvertes par cette cache.
            total_incomplete_tasks: Nombre total de tâches non terminées.

        Returns:
            float: Score de couverture (0.0 à 1.0).
        """
        if total_incomplete_tasks <= 0:
            return 0.0

        return min(matched_tasks_count / total_incomplete_tasks, 1.0)

    @staticmethod
    def choose_primary_task_by_ratio(matched_tasks: list[dict[str, Any]]) -> ObjectId | None:
        """Choisir la tâche principale basée sur le ratio de progression.

        Args:
            matched_tasks: Liste des tâches avec leurs métriques.

        Returns:
            ObjectId | None: ID de la tâche principale ou None.
        """
        if not matched_tasks:
            return None

        # Sélectionner la tâche avec le ratio le plus élevé
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
        """Calculer le score composite final pour une target.

        Args:
            matched_tasks: Tâches correspondantes avec leurs métriques.
            total_incomplete_tasks: Nombre total de tâches incomplètes.
            distance_m: Distance en mètres (optionnel pour score géo).
            radius_km: Rayon de référence en km (optionnel pour score géo).
            weights: Poids personnalisés pour les composants de score.

        Returns:
            dict[str, float]: Scores détaillés et score composite.
        """
        # Poids par défaut
        default_weights = {
            "urgency": 0.4,  # Priorité aux tâches avancées
            "coverage": 0.3,  # Importance de couvrir plusieurs tâches
            "geographic": 0.3,  # Bonus pour la proximité
        }

        if weights:
            default_weights.update(weights)

        # Calcul des scores individuels
        urgency_score = cls.calculate_task_urgency_score(matched_tasks)
        coverage_score = cls.calculate_task_coverage_score(
            len(matched_tasks), total_incomplete_tasks
        )

        # Score géographique (optionnel)
        geo_score = 0.0
        if distance_m is not None and radius_km is not None:
            geo_score = calculate_geo_score(distance_m, radius_km)

        # Score composite pondéré
        composite_score = (
            urgency_score * default_weights["urgency"]
            + coverage_score * default_weights["coverage"]
            + geo_score * default_weights["geographic"]
        )

        return {
            "urgency": urgency_score,
            "coverage": coverage_score,
            "geographic": geo_score,
            "composite": min(composite_score, 1.0),  # Cap à 1.0
        }

    @staticmethod
    def get_task_constraints_min_count(task_doc: dict[str, Any]) -> int:
        """Extraire le min_count d'un document de tâche.

        Args:
            task_doc: Document de tâche MongoDB.

        Returns:
            int: Contrainte min_count ou 1 par défaut.
        """
        constraints = task_doc.get("constraints", {})
        return int(constraints.get("min_count", 1))
