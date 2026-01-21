# backend/app/services/user_challenges/user_challenge_sync.py
# Service de synchronisation des UserChallenges manquants.

from __future__ import annotations

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import UpdateOne

from app.core.utils import utcnow

from .status_calculator import StatusCalculator


class UserChallengeSync:
    """Service de synchronisation des UserChallenges.

    Description:
        Responsable de la création des UserChallenges manquants
        et de l'auto-completion basée sur les caches trouvées.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialiser le service de synchronisation.

        Args:
            db: Instance de base de données MongoDB.
        """
        self.db = db
        self.status_calculator = StatusCalculator()

    async def sync_user_challenges(self, user_id: ObjectId) -> dict[str, int]:
        """Créer les UserChallenges manquants pour un utilisateur.

        Args:
            user_id: Identifiant de l'utilisateur.

        Returns:
            dict: Statistiques de synchronisation.
        """
        # Étape 1: Créer les UC manquants
        creation_stats = await self._create_missing_user_challenges(user_id)

        # Étape 2: Auto-compléter ceux dont la cache est trouvée
        completion_stats = await self._auto_complete_found_challenges(user_id)

        # Compter le total final
        total_count = await self._count_user_challenges(user_id)

        return {
            "created": creation_stats["created"],
            "existing": creation_stats["existing"],
            "auto_completed": completion_stats["updated"],
            "total_user_challenges": total_count,
        }

    async def _create_missing_user_challenges(self, user_id: ObjectId) -> dict[str, int]:
        """Créer les UserChallenges manquants avec status=pending.

        Args:
            user_id: Identifiant de l'utilisateur.

        Returns:
            dict: Statistiques de création.
        """
        coll_challenges = self.db.challenges
        coll_ucs = self.db.user_challenges

        # Récupérer tous les challenge IDs
        challenge_ids = await coll_challenges.distinct("_id")
        if not challenge_ids:
            return {"created": 0, "existing": 0}

        # Identifier les challenges manquants
        existing_challenge_ids = set(await coll_ucs.distinct("challenge_id", {"user_id": user_id}))
        missing_challenge_ids = [cid for cid in challenge_ids if cid not in existing_challenge_ids]

        if not missing_challenge_ids:
            return {"created": 0, "existing": len(existing_challenge_ids)}

        # Préparer les opérations d'insertion
        operations = []
        now = utcnow()

        for challenge_id in missing_challenge_ids:
            operations.append(
                UpdateOne(
                    {"user_id": user_id, "challenge_id": challenge_id},
                    {
                        "$setOnInsert": {
                            "user_id": user_id,
                            "challenge_id": challenge_id,
                            "status": "pending",
                            "created_at": now,
                        },
                        "$set": {"updated_at": now},
                    },
                    upsert=True,
                )
            )

        # Exécuter les opérations
        if operations:
            result = await coll_ucs.bulk_write(operations, ordered=False)
            created_count = result.upserted_count
        else:
            created_count = 0

        return {
            "created": created_count,
            "existing": len(existing_challenge_ids),
        }

    async def _auto_complete_found_challenges(self, user_id: ObjectId) -> dict[str, int]:
        """Auto-compléter les UC dont la cache est trouvée.

        Args:
            user_id: Identifiant de l'utilisateur.

        Returns:
            dict: Statistiques d'auto-completion.
        """
        # Pipeline pour identifier les UC à auto-compléter
        pipeline: list[dict[str, Any]] = [
            # Matcher les UC de l'utilisateur
            {"$match": {"user_id": user_id}},
            # Joindre avec les challenges
            {
                "$lookup": {
                    "from": "challenges",
                    "localField": "challenge_id",
                    "foreignField": "_id",
                    "as": "challenge",
                }
            },
            {"$unwind": "$challenge"},
            # Joindre avec les found_caches
            {
                "$lookup": {
                    "from": "found_caches",
                    "let": {"cache_id": "$challenge.cache_id", "user_id": "$user_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$cache_id", "$$cache_id"]},
                                        {"$eq": ["$user_id", "$$user_id"]},
                                    ]
                                }
                            }
                        }
                    ],
                    "as": "found",
                }
            },
            # Filtrer ceux qui ont la cache trouvée mais pas completed
            {
                "$match": {
                    "$and": [
                        {"found": {"$ne": []}},  # Cache trouvée
                        {"status": {"$ne": "completed"}},  # Pas encore completed manuellement
                        {
                            "computed_status": {"$ne": "completed"}
                        },  # Pas encore completed automatiquement
                    ]
                }
            },
            # Projeter seulement l'ID
            {"$project": {"_id": 1}},
        ]

        coll_ucs = self.db.user_challenges
        cursor = coll_ucs.aggregate(pipeline)
        ucs_to_complete = [doc["_id"] async for doc in cursor]

        if not ucs_to_complete:
            return {"updated": 0}

        # Mettre à jour les UC identifiés
        now = utcnow()
        progress_snapshot = self.status_calculator.create_progress_snapshot(100.0)

        result = await coll_ucs.update_many(
            {"_id": {"$in": ucs_to_complete}},
            {
                "$set": {
                    "computed_status": "completed",
                    "progress": progress_snapshot,
                    "updated_at": now,
                }
            },
        )

        return {"updated": result.modified_count}

    async def _count_user_challenges(self, user_id: ObjectId) -> int:
        """Compter le total des UserChallenges pour un utilisateur.

        Args:
            user_id: Identifiant de l'utilisateur.

        Returns:
            int: Nombre total de UserChallenges.
        """
        coll_ucs = self.db.user_challenges
        return await coll_ucs.count_documents({"user_id": user_id})

    async def reset_user_challenge_status(self, user_id: ObjectId, uc_id: ObjectId) -> bool:
        """Remettre un UserChallenge à son état par défaut.

        Args:
            user_id: Identifiant de l'utilisateur.
            uc_id: Identifiant du UserChallenge.

        Returns:
            bool: True si la remise à zéro a réussi.
        """
        coll_ucs = self.db.user_challenges
        now = utcnow()

        result = await coll_ucs.update_one(
            {"_id": uc_id, "user_id": user_id},
            {
                "$set": {
                    "status": "pending",
                    "updated_at": now,
                },
                "$unset": {
                    "computed_status": "",
                    "progress": "",
                    "manual_override": "",
                    "override_reason": "",
                    "overridden_at": "",
                    "notes": "",
                },
            },
        )

        return result.modified_count > 0
