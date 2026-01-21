# backend/app/services/targets/target_evaluator.py
# Logique d'évaluation des caches cibles pour un UserChallenge.

from __future__ import annotations

from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services.query_builder import compile_and_only

from .geo_utils import build_geo_pipeline_stage
from .target_scorer import TargetScorer


class TargetEvaluator:
    """Service d'évaluation des targets de caches pour un UserChallenge.

    Description:
        Responsable de l'identification et du scoring des caches candidates
        en fonction des tâches d'un challenge et du profil utilisateur.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialiser l'évaluateur.

        Args:
            db: Instance de base de données MongoDB.
        """
        self.db = db
        self.scorer = TargetScorer()

    async def get_username(self, user_id: ObjectId) -> str | None:
        """Récupérer le nom d'utilisateur.

        Args:
            user_id: Identifiant de l'utilisateur.

        Returns:
            str | None: Nom d'utilisateur ou None.
        """
        coll_users = self.db.users
        user_doc = await coll_users.find_one({"_id": user_id}, {"username": 1})
        return user_doc.get("username") if user_doc else None

    async def get_latest_progress_task_map(self, uc_id: ObjectId) -> dict[ObjectId, dict[str, Any]]:
        """Récupérer la carte de progression par tâche.

        Args:
            uc_id: Identifiant du UserChallenge.

        Returns:
            dict: Mapping task_id -> progress_data.
        """
        coll_progress = self.db.progress
        progress_doc = await coll_progress.find_one(
            {"user_challenge_id": uc_id}, sort=[("checked_at", -1)]
        )

        if not progress_doc:
            return {}

        task_map = {}
        for task_progress in progress_doc.get("tasks", []):
            task_id = task_progress.get("task_id")
            if task_id:
                task_map[task_id] = task_progress

        return task_map

    async def get_user_challenge_tasks(self, uc_id: ObjectId) -> list[dict[str, Any]]:
        """Récupérer les tâches d'un UserChallenge.

        Args:
            uc_id: Identifiant du UserChallenge.

        Returns:
            list: Liste des documents de tâches.
        """
        coll_tasks = self.db.user_challenge_tasks
        tasks_cursor = coll_tasks.find({"user_challenge_id": uc_id}, sort=[("order", 1)])
        return await tasks_cursor.to_list(length=None)

    async def build_cache_pipeline_for_task(
        self,
        task_doc: dict[str, Any],
        username: str | None,
        user_id: ObjectId,
        geo_ctx: dict[str, Any] | None,
        limit_per_task: int,
    ) -> list[dict[str, Any]]:
        """Construire le pipeline MongoDB pour une tâche.

        Args:
            task_doc: Document de tâche.
            username: Nom d'utilisateur (pour exclure ses caches).
            user_id: ID utilisateur (pour exclure ses trouvailles).
            geo_ctx: Contexte géographique optionnel.
            limit_per_task: Limite de résultats par tâche.

        Returns:
            list: Pipeline d'agrégation MongoDB.
        """
        pipeline = []

        # Ajouter $geoNear en premier si contexte géo
        if geo_ctx and "radius_km" in geo_ctx:
            geo_stage = build_geo_pipeline_stage(
                geo_ctx["lat"], geo_ctx["lon"], geo_ctx["radius_km"]
            )
            pipeline.append(geo_stage)

        # Filtre de base
        base_match: dict[str, Any] = {
            "status": {"$in": ["active"]},  # Seulement les caches actives
        }

        # Exclure les caches du propriétaire
        if username:
            base_match["owner"] = {"$ne": username}

        pipeline.append({"$match": base_match})

        # Anti-join avec found_caches de l'utilisateur
        pipeline.extend(
            [
                {
                    "$lookup": {
                        "from": "found_caches",
                        "let": {"cache_id": "$_id"},
                        "pipeline": [
                            {
                                "$match": {
                                    "$expr": {
                                        "$and": [
                                            {"$eq": ["$cache_id", "$$cache_id"]},
                                            {"$eq": ["$user_id", user_id]},
                                        ]
                                    }
                                }
                            }
                        ],
                        "as": "found_by_user",
                    }
                },
                {"$match": {"found_by_user": {"$size": 0}}},
            ]
        )

        # Appliquer les filtres de la tâche
        task_expression = task_doc.get("expression")
        if task_expression:
            try:
                match_filters = compile_and_only(task_expression)
                if match_filters:
                    pipeline.append({"$match": match_filters})
            except Exception:
                # En cas d'erreur de compilation, ignorer le filtre
                pass

        # Projection des champs nécessaires
        projection = {
            "_id": 1,
            "GC": 1,
            "title": 1,
            "loc": 1,
            "owner": 1,
            "difficulty": 1,
            "terrain": 1,
        }

        # Ajouter distance_m si contexte géo
        if geo_ctx and "radius_km" in geo_ctx:
            projection["distance_m"] = 1

        pipeline.append({"$project": projection})
        pipeline.append({"$limit": limit_per_task})

        return pipeline

    async def evaluate_cache_candidates(
        self,
        tasks: list[dict[str, Any]],
        progress_map: dict[ObjectId, dict[str, Any]],
        username: str | None,
        user_id: ObjectId,
        geo_ctx: dict[str, Any] | None,
        limit_per_task: int,
        hard_limit_total: int,
    ) -> dict[ObjectId, dict[str, Any]]:
        """Évaluer les caches candidates pour toutes les tâches.

        Args:
            tasks: Liste des tâches du UserChallenge.
            progress_map: Carte de progression par tâche.
            username: Nom d'utilisateur.
            user_id: ID utilisateur.
            geo_ctx: Contexte géographique.
            limit_per_task: Limite par tâche.
            hard_limit_total: Limite globale.

        Returns:
            dict: Caches uniques avec leurs tâches correspondantes.
        """
        coll_caches = self.db.caches
        unique_by_cache = {}
        total_seen = 0

        for task_doc in tasks:
            # Ignorer les tâches OR/NOT (complexes)
            if task_doc.get("expression", {}).get("type") != "and":
                continue

            # Construire et exécuter le pipeline
            pipeline = await self.build_cache_pipeline_for_task(
                task_doc, username, user_id, geo_ctx, limit_per_task
            )

            aggregate_cursor = coll_caches.aggregate(pipeline, allowDiskUse=False)
            rows = await aggregate_cursor.to_list(length=None)

            # Traiter chaque cache candidate
            for cache_row in rows:
                cache_id = cache_row["_id"]

                # Ajouter à la collection unique
                if cache_id not in unique_by_cache:
                    unique_by_cache[cache_id] = {
                        "cache": cache_row,
                        "matched_tasks": [],
                    }
                    total_seen += 1
                    if total_seen >= hard_limit_total:
                        break

                # Calculer les métriques de tâche
                min_count = self.scorer.get_task_constraints_min_count(task_doc)
                current_count = progress_map.get(task_doc["_id"], {}).get("current_count", 0)
                remaining = max(0, min_count - current_count)
                ratio = current_count / max(min_count, 1) if min_count > 0 else 0.0

                # Ajouter les infos de tâche
                unique_by_cache[cache_id]["matched_tasks"].append(
                    {
                        "_id": task_doc["_id"],
                        "min_count": min_count,
                        "current_count": current_count,
                        "remaining": remaining,
                        "ratio": ratio,
                    }
                )

            if total_seen >= hard_limit_total:
                break

        return unique_by_cache
