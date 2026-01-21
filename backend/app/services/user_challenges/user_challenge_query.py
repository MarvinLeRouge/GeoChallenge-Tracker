# backend/app/services/user_challenges/user_challenge_query.py
# Service de requêtes optimisées pour les UserChallenges.

from __future__ import annotations

from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from .status_calculator import StatusCalculator


class UserChallengeQuery:
    """Service de requêtes pour UserChallenges.

    Description:
        Responsable des requêtes complexes avec jointures,
        pagination et filtrage pour les UserChallenges.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialiser le service de requêtes.

        Args:
            db: Instance de base de données MongoDB.
        """
        self.db = db
        self.status_calculator = StatusCalculator()

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
            status_filter: Filtre de statut effectif.
            page: Numéro de page (1-based).
            page_size: Taille de page.

        Returns:
            dict: Résultats paginés avec metadata.
        """
        # Construire le pipeline de base
        pipeline = self._build_list_pipeline(user_id, status_filter)

        # Compter le total
        total_count = await self._count_filtered_user_challenges(user_id, status_filter)

        # Pagination
        skip = (page - 1) * page_size
        pipeline.extend(
            [
                {"$skip": skip},
                {"$limit": page_size},
            ]
        )

        # Exécuter la requête
        coll_ucs = self.db.user_challenges
        cursor = coll_ucs.aggregate(pipeline)
        items = []

        async for doc in cursor:
            # Calculer le statut effectif
            doc["effective_status"] = self.status_calculator.calculate_effective_status(
                doc.get("status"), doc.get("computed_status")
            )
            # Convertir _id en string
            doc["id"] = str(doc.pop("_id"))
            items.append(doc)

        # Calculer la pagination
        nb_pages = (total_count + page_size - 1) // page_size

        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "nb_pages": nb_pages,
            "total": total_count,
        }

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
        pipeline: list[dict[str, Any]] = [
            # Matcher l'UC spécifique
            {"$match": {"_id": uc_id, "user_id": user_id}},
            # Joindre avec le challenge
            {
                "$lookup": {
                    "from": "challenges",
                    "localField": "challenge_id",
                    "foreignField": "_id",
                    "as": "challenge",
                }
            },
            {"$unwind": "$challenge"},
            # Joindre avec la cache
            {
                "$lookup": {
                    "from": "caches",
                    "localField": "challenge.cache_id",
                    "foreignField": "_id",
                    "as": "cache",
                }
            },
            {"$unwind": {"path": "$cache", "preserveNullAndEmptyArrays": True}},
            # Projection complète
            {
                "$project": {
                    "_id": 1,
                    "status": 1,
                    "computed_status": 1,
                    "manual_override": 1,
                    "override_reason": 1,
                    "overridden_at": 1,
                    "notes": 1,
                    "progress": 1,
                    "created_at": 1,
                    "updated_at": 1,
                    "challenge": {
                        "id": "$challenge._id",
                        "name": "$challenge.name",
                        "description": "$challenge.description",
                    },
                    "cache": {
                        "$cond": {
                            "if": {"$eq": ["$cache", None]},
                            "then": None,
                            "else": {
                                "id": "$cache._id",
                                "GC": "$cache.GC",
                                "difficulty": "$cache.difficulty",
                                "terrain": "$cache.terrain",
                            },
                        }
                    },
                }
            },
        ]

        coll_ucs = self.db.user_challenges
        cursor = coll_ucs.aggregate(pipeline)

        try:
            doc = await cursor.next()
            # Calculer le statut effectif
            doc["effective_status"] = self.status_calculator.calculate_effective_status(
                doc.get("status"), doc.get("computed_status")
            )
            # Convertir _id en string
            doc["id"] = str(doc.pop("_id"))
            return doc
        except StopAsyncIteration:
            return None

    def _build_list_pipeline(
        self, user_id: ObjectId, status_filter: str | None
    ) -> list[dict[str, Any]]:
        """Construire le pipeline de base pour la liste.

        Args:
            user_id: Identifiant de l'utilisateur.
            status_filter: Filtre de statut.

        Returns:
            list: Pipeline MongoDB.
        """
        pipeline: list[dict[str, Any]] = [
            {"$match": {"user_id": user_id}},
        ]

        # Ajouter le filtre de statut si spécifié
        if status_filter:
            status_stages = self.status_calculator.build_status_filter_pipeline(status_filter)
            pipeline.extend(status_stages)

        # Jointures avec challenge et cache
        pipeline.extend(
            [
                # Joindre avec challenge
                {
                    "$lookup": {
                        "from": "challenges",
                        "localField": "challenge_id",
                        "foreignField": "_id",
                        "as": "challenge",
                    }
                },
                {"$unwind": "$challenge"},
                # Joindre avec cache
                {
                    "$lookup": {
                        "from": "caches",
                        "localField": "challenge.cache_id",
                        "foreignField": "_id",
                        "as": "cache",
                    }
                },
                {"$unwind": {"path": "$cache", "preserveNullAndEmptyArrays": True}},
                # Projection pour la liste
                {
                    "$project": {
                        "_id": 1,
                        "status": 1,
                        "computed_status": 1,
                        "progress": 1,
                        "updated_at": 1,
                        "challenge": {
                            "id": "$challenge._id",
                            "name": "$challenge.name",
                        },
                        "cache": {
                            "$cond": {
                                "if": {"$eq": ["$cache", None]},
                                "then": None,
                                "else": {
                                    "id": "$cache._id",
                                    "GC": "$cache.GC",
                                    "difficulty": "$cache.difficulty",
                                    "terrain": "$cache.terrain",
                                },
                            }
                        },
                    }
                },
                # Tri par updated_at desc par défaut
                {"$sort": {"updated_at": -1}},
            ]
        )

        return pipeline

    async def _count_filtered_user_challenges(
        self, user_id: ObjectId, status_filter: str | None
    ) -> int:
        """Compter les UserChallenges avec filtrage.

        Args:
            user_id: Identifiant de l'utilisateur.
            status_filter: Filtre de statut.

        Returns:
            int: Nombre de résultats.
        """
        pipeline: list[dict[str, Any]] = [
            {"$match": {"user_id": user_id}},
        ]

        # Ajouter le filtre de statut si spécifié
        if status_filter:
            status_stages = self.status_calculator.build_status_filter_pipeline(status_filter)
            pipeline.extend(status_stages)

        # Compter
        pipeline.append({"$count": "total"})

        coll_ucs = self.db.user_challenges
        cursor = coll_ucs.aggregate(pipeline)

        try:
            result = await cursor.next()
            return result["total"]
        except StopAsyncIteration:
            return 0
