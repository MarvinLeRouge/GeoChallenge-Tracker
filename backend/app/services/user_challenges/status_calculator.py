# backend/app/services/user_challenges/status_calculator.py
# Logique de calcul des statuts effectifs pour les UserChallenges.

from __future__ import annotations

from typing import Any


class StatusCalculator:
    """Service de calcul des statuts effectifs pour UserChallenges.

    Description:
        Responsable de la logique de calcul des statuts en tenant compte
        des statuts manuels, calculés et des overrides.
    """

    @staticmethod
    def calculate_effective_status(user_status: str | None, computed_status: str | None) -> str:
        """Calculer le statut effectif d'un UserChallenge.

        Args:
            user_status: Statut manuel de l'utilisateur.
            computed_status: Statut calculé automatiquement.

        Returns:
            str: Statut effectif.
        """
        # Règle : completed si statut manuel OU calculé est completed
        if user_status == "completed" or computed_status == "completed":
            return "completed"

        # Sinon, retourner le statut utilisateur ou 'pending' par défaut
        return user_status or "pending"

    @staticmethod
    def build_status_filter_pipeline(status_filter: str) -> list[dict[str, Any]]:
        """Construire un pipeline MongoDB pour filtrer par statut effectif.

        Args:
            status_filter: Statut à filtrer ('pending', 'accepted', 'dismissed', 'completed').

        Returns:
            list: Étapes de pipeline MongoDB.
        """
        if status_filter == "completed":
            # Effectif: completed si statut manuel OU calculé
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
            # dismissed effectif = statut utilisateur (hors completed)
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
            # accepted effectif = statut utilisateur (hors completed)
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
            # pending effectif = pas de statut utilisateur (hors completed)
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

        # Aucun filtre
        return []

    @staticmethod
    def should_auto_complete(challenge_cache_found: bool) -> str | None:
        """Déterminer si un UserChallenge doit être auto-complété.

        Args:
            challenge_cache_found: True si la cache du challenge est trouvée.

        Returns:
            str | None: 'completed' si auto-completion, None sinon.
        """
        return "completed" if challenge_cache_found else None

    @staticmethod
    def create_progress_snapshot(completion_percent: float = 100.0) -> dict[str, Any]:
        """Créer un snapshot de progression.

        Args:
            completion_percent: Pourcentage de completion.

        Returns:
            dict: Snapshot de progression.
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
        """Valider une transition de statut.

        Args:
            current_status: Statut actuel.
            new_status: Nouveau statut demandé.
            computed_status: Statut calculé.

        Returns:
            tuple: (is_valid, error_message).
        """
        valid_statuses = ["pending", "accepted", "dismissed", "completed"]

        # Vérifier que le nouveau statut est valide
        if new_status and new_status not in valid_statuses:
            return False, f"Invalid status: {new_status}"

        # Si computed_status est completed, on ne peut pas rétrograder
        if computed_status == "completed" and new_status in ["pending", "dismissed"]:
            return False, "Cannot change status of auto-completed challenge"

        return True, None

    @staticmethod
    def determine_override_logic(
        new_status: str | None,
        computed_status: str | None,
    ) -> tuple[bool, str | None]:
        """Déterminer la logique d'override manuel.

        Args:
            new_status: Nouveau statut demandé.
            computed_status: Statut calculé.

        Returns:
            tuple: (is_manual_override, override_type).
        """
        # Override si on force completed alors que pas auto-completed
        if new_status == "completed" and computed_status != "completed":
            return True, "manual_completion"

        # Override si on force un statut différent du calculé
        if computed_status and new_status and new_status != computed_status:
            return True, "status_override"

        return False, None
