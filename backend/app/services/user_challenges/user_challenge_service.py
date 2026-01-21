# backend/app/services/user_challenges/user_challenge_service.py
# Service principal de gestion des UserChallenges avec injection de dépendances.

from __future__ import annotations

from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.utils import utcnow

from .status_calculator import StatusCalculator
from .user_challenge_query import UserChallengeQuery
from .user_challenge_sync import UserChallengeSync
from .user_challenge_validator import UserChallengeValidator


class UserChallengeService:
    """Service principal de gestion des UserChallenges.

    Description:
        Service principal qui orchestre la synchronisation,
        les requêtes, la validation et les mises à jour
        des UserChallenges.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialiser le service.

        Args:
            db: Instance de base de données MongoDB.
        """
        self.db = db

        # Initialiser les composants
        self.status_calculator = StatusCalculator()
        self.sync_service = UserChallengeSync(db)
        self.query_service = UserChallengeQuery(db)
        self.validator = UserChallengeValidator(db)

    async def sync_user_challenges(self, user_id: ObjectId) -> dict[str, int]:
        """Créer et synchroniser les UserChallenges pour un utilisateur.

        Args:
            user_id: Identifiant de l'utilisateur.

        Returns:
            dict: Statistiques de synchronisation.
        """
        return await self.sync_service.sync_user_challenges(user_id)

    async def list_user_challenges(
        self,
        user_id: ObjectId,
        status_filter: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """Lister les UserChallenges avec pagination et filtrage.

        Args:
            user_id: Identifiant de l'utilisateur.
            status_filter: Filtre de statut ('pending', 'accepted', 'dismissed', 'completed').
            page: Numéro de page (1-based).
            page_size: Taille de page.

        Returns:
            dict: Résultats paginés avec metadata.
        """
        return await self.query_service.list_user_challenges(
            user_id=user_id,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
        )

    async def get_user_challenge_detail(
        self, user_id: ObjectId, uc_id: ObjectId
    ) -> dict[str, Any] | None:
        """Récupérer le détail complet d'un UserChallenge.

        Args:
            user_id: Identifiant de l'utilisateur.
            uc_id: Identifiant du UserChallenge.

        Returns:
            dict | None: Détail enrichi ou None si non trouvé.
        """
        return await self.query_service.get_user_challenge_detail(user_id, uc_id)

    async def patch_user_challenge(
        self,
        user_id: ObjectId,
        uc_id: ObjectId,
        patch_data: dict[str, Any],
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        """Mettre à jour un UserChallenge avec validation.

        Args:
            user_id: Identifiant de l'utilisateur.
            uc_id: Identifiant du UserChallenge.
            patch_data: Données de patch.

        Returns:
            tuple: (success, error_message, updated_uc).
        """
        # Validation
        is_valid, error_msg, validated_data = await self.validator.validate_patch_operation(
            user_id, uc_id, patch_data
        )
        if not is_valid:
            return False, error_msg, None

        # Récupérer les dépendances
        dependencies = await self.validator.get_patch_dependencies(user_id, uc_id)
        current_uc = dependencies.get("current_uc", {})

        # Préparer les données de mise à jour
        update_data = self._prepare_patch_update(validated_data, current_uc, dependencies)

        # Appliquer la mise à jour
        success = await self._apply_patch_update(user_id, uc_id, update_data)
        if not success:
            return False, "Failed to update UserChallenge", None

        # Récupérer l'UC mis à jour
        updated_uc = await self.get_user_challenge_detail(user_id, uc_id)

        return True, None, updated_uc

    async def bulk_update_status(
        self,
        user_id: ObjectId,
        uc_ids: list[ObjectId],
        new_status: str,
    ) -> dict[str, Any]:
        """Mettre à jour le statut de plusieurs UserChallenges.

        Args:
            user_id: Identifiant de l'utilisateur.
            uc_ids: Liste des identifiants UserChallenges.
            new_status: Nouveau statut à appliquer.

        Returns:
            dict: Résultat de l'opération en lot.
        """
        # Validation
        is_valid, error_msg, valid_ids = await self.validator.validate_bulk_operation(
            user_id, uc_ids, new_status
        )
        if not is_valid:
            return {"success": False, "error": error_msg, "updated": 0}

        # Préparer la mise à jour
        now = utcnow()
        update_doc = {
            "status": new_status,
            "updated_at": now,
        }

        # Ajouter des champs spécifiques selon le statut
        if new_status == "completed":
            update_doc["manual_override"] = True
            update_doc["override_reason"] = "Manual completion"
            update_doc["overridden_at"] = now
            # Créer un snapshot de progression
            update_doc["progress"] = self.status_calculator.create_progress_snapshot(100.0)

        # Appliquer la mise à jour en lot
        coll_ucs = self.db.user_challenges
        result = await coll_ucs.update_many(
            {"_id": {"$in": valid_ids}, "user_id": user_id}, {"$set": update_doc}
        )

        return {
            "success": True,
            "updated": result.modified_count,
            "requested": len(valid_ids),
        }

    async def reset_user_challenge(
        self, user_id: ObjectId, uc_id: ObjectId
    ) -> tuple[bool, str | None]:
        """Remettre un UserChallenge à son état par défaut.

        Args:
            user_id: Identifiant de l'utilisateur.
            uc_id: Identifiant du UserChallenge.

        Returns:
            tuple: (success, error_message).
        """
        # Valider la propriété
        if not await self.validator.validate_ownership(user_id, uc_id):
            return False, "UserChallenge not found or not owned"

        # Appliquer la remise à zéro
        success = await self.sync_service.reset_user_challenge_status(user_id, uc_id)

        return success, None if success else "Failed to reset UserChallenge"

    def _prepare_patch_update(
        self,
        validated_data: dict[str, Any],
        current_uc: dict[str, Any],
        dependencies: dict[str, Any],
    ) -> dict[str, Any]:
        """Préparer les données de mise à jour pour un patch.

        Args:
            validated_data: Données validées du patch.
            current_uc: UserChallenge actuel.
            dependencies: Dépendances contextuelles.

        Returns:
            dict: Données de mise à jour MongoDB.
        """
        now = utcnow()
        update_data = {
            "updated_at": now,
        }

        # Copier les champs validés
        for field in ["status", "notes", "manual_override", "override_reason"]:
            if field in validated_data:
                if validated_data[field] is None:
                    update_data.setdefault("$unset", {})[field] = ""
                else:
                    update_data[field] = validated_data[field]

        # Gérer la logique d'override
        new_status = validated_data.get("status")
        computed_status = dependencies.get("computed_status")

        if new_status:
            is_override, override_type = self.status_calculator.determine_override_logic(
                new_status, computed_status
            )

            if is_override:
                update_data["manual_override"] = True
                update_data["overridden_at"] = now
                if override_type == "manual_completion":
                    update_data["override_reason"] = "Manual completion"
                    # Créer un snapshot de progression
                    update_data["progress"] = self.status_calculator.create_progress_snapshot(100.0)

        # Auto-compléter si applicable
        if dependencies.get("can_auto_complete") and not current_uc.get("computed_status"):
            update_data["computed_status"] = "completed"
            update_data["progress"] = self.status_calculator.create_progress_snapshot(100.0)

        return update_data

    async def _apply_patch_update(
        self,
        user_id: ObjectId,
        uc_id: ObjectId,
        update_data: dict[str, Any],
    ) -> bool:
        """Appliquer une mise à jour MongoDB.

        Args:
            user_id: Identifiant de l'utilisateur.
            uc_id: Identifiant du UserChallenge.
            update_data: Données de mise à jour.

        Returns:
            bool: True si la mise à jour a réussi.
        """
        coll_ucs = self.db.user_challenges

        # Séparer $set et $unset
        set_data = {k: v for k, v in update_data.items() if k != "$unset"}
        unset_data = update_data.get("$unset", {})

        # Construire la requête de mise à jour
        update_query = {}
        if set_data:
            update_query["$set"] = set_data
        if unset_data:
            update_query["$unset"] = unset_data

        result = await coll_ucs.update_one({"_id": uc_id, "user_id": user_id}, update_query)

        return result.modified_count > 0
