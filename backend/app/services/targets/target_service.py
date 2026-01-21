# backend/app/services/targets/target_service.py
# Service principal de gestion des targets avec injection de dépendances.

from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.utils import utcnow

from .geo_utils import get_user_location
from .target_evaluator import TargetEvaluator
from .target_scorer import TargetScorer


class TargetService:
    """Service principal de gestion des targets de caches.

    Description:
        Service principal qui orchestre l'évaluation, le scoring,
        la persistance et la récupération des targets de caches
        pour les UserChallenges.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialiser le service.

        Args:
            db: Instance de base de données MongoDB.
        """
        self.db = db
        self.evaluator = TargetEvaluator(db)
        self.scorer = TargetScorer()

    async def evaluate_targets_for_user_challenge(
        self,
        user_id: ObjectId,
        uc_id: ObjectId,
        limit_per_task: int = 200,
        hard_limit_total: int = 2000,
        geo_ctx: dict[str, Any] | None = None,
        evaluated_at: datetime | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Évaluer et persister les targets d'un UserChallenge.

        Args:
            user_id: Utilisateur propriétaire.
            uc_id: UserChallenge ciblé.
            limit_per_task: Cap par tâche.
            hard_limit_total: Cap global d'agrégation.
            geo_ctx: Contexte géo {lat, lon, radius_km}.
            evaluated_at: Timestamp d'évaluation.
            force: Forcer le recalcul même si targets existent.

        Returns:
            dict: {ok, inserted, updated, total, skipped?}.

        Raises:
            PermissionError: Si l'UC n'existe pas ou n'appartient pas au user.
        """
        # Validation de l'ownership
        await self._validate_user_challenge_ownership(user_id, uc_id)

        # Court-circuit si pas de force et assez de targets
        if not force:
            existing_count = await self._count_existing_targets(user_id, uc_id)
            threshold = min(hard_limit_total, limit_per_task * 5)
            if existing_count >= threshold:
                return {
                    "ok": True,
                    "inserted": 0,
                    "updated": 0,
                    "total": existing_count,
                    "skipped": True,
                }

        # Récupération des données nécessaires
        username = await self.evaluator.get_username(user_id)
        tasks = await self.evaluator.get_user_challenge_tasks(uc_id)
        progress_map = await self.evaluator.get_latest_progress_task_map(uc_id)

        # Évaluation des caches candidates
        candidates = await self.evaluator.evaluate_cache_candidates(
            tasks=tasks,
            progress_map=progress_map,
            username=username,
            user_id=user_id,
            geo_ctx=geo_ctx,
            limit_per_task=limit_per_task,
            hard_limit_total=hard_limit_total,
        )

        # Scoring et persistance
        result = await self._score_and_persist_targets(
            candidates=candidates,
            user_id=user_id,
            uc_id=uc_id,
            tasks=tasks,
            progress_map=progress_map,
            geo_ctx=geo_ctx,
            evaluated_at=evaluated_at or utcnow(),
        )

        return result

    async def list_targets_for_user_challenge(
        self,
        user_id: ObjectId,
        uc_id: ObjectId,
        page: int = 1,
        page_size: int = 50,
        sort: str = "-score",
    ) -> dict[str, Any]:
        """Lister les targets d'un UserChallenge (paginé).

        Args:
            user_id: Utilisateur.
            uc_id: UserChallenge.
            page: Numéro de page.
            page_size: Taille de page.
            sort: Clé de tri.

        Returns:
            dict: {items, nb_items, page, page_size, nb_pages}.
        """
        return await self._list_targets_with_pagination(
            filters={"user_id": user_id, "user_challenge_id": uc_id},
            page=page,
            page_size=page_size,
            sort=sort,
        )

    async def list_targets_nearby_for_user_challenge(
        self,
        user_id: ObjectId,
        uc_id: ObjectId,
        lat: float,
        lon: float,
        radius_km: float,
        page: int = 1,
        page_size: int = 50,
        sort: str = "distance",
    ) -> dict[str, Any]:
        """Lister les targets proches pour un UserChallenge.

        Args:
            user_id: Utilisateur.
            uc_id: UserChallenge.
            lat: Latitude.
            lon: Longitude.
            radius_km: Rayon en km.
            page: Numéro de page.
            page_size: Taille de page.
            sort: Clé de tri.

        Returns:
            dict: {items, nb_items, page, page_size, nb_pages}.
        """
        return await self._list_targets_nearby(
            base_filters={"user_id": user_id, "user_challenge_id": uc_id},
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            page=page,
            page_size=page_size,
            sort=sort,
        )

    async def list_targets_for_user(
        self,
        user_id: ObjectId,
        status_filter: str | None = None,
        page: int = 1,
        page_size: int = 50,
        sort: str = "-score",
    ) -> dict[str, Any]:
        """Lister toutes les targets d'un utilisateur.

        Args:
            user_id: Utilisateur.
            status_filter: Filtre de statut UC.
            page: Numéro de page.
            page_size: Taille de page.
            sort: Clé de tri.

        Returns:
            dict: {items, nb_items, page, page_size, nb_pages}.
        """
        # Construire les filtres avec jointure sur user_challenges
        return await self._list_targets_for_user_with_status_filter(
            user_id=user_id,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
            sort=sort,
        )

    async def list_targets_nearby_for_user(
        self,
        user_id: ObjectId,
        lat: float | None = None,
        lon: float | None = None,
        radius_km: float = 50.0,
        status_filter: str | None = None,
        page: int = 1,
        page_size: int = 50,
        sort: str = "distance",
    ) -> dict[str, Any]:
        """Lister les targets proches pour tous les challenges d'un utilisateur.

        Args:
            user_id: Utilisateur.
            lat: Latitude (ou None pour utiliser la localisation user).
            lon: Longitude (ou None pour utiliser la localisation user).
            radius_km: Rayon en km.
            status_filter: Filtre de statut UC.
            page: Numéro de page.
            page_size: Taille de page.
            sort: Clé de tri.

        Returns:
            dict: {items, nb_items, page, page_size, nb_pages}.
        """
        # Résoudre la localisation si nécessaire
        if lat is None or lon is None:
            user_location = await get_user_location(user_id)
            if not user_location:
                raise ValueError(
                    "No user location found; provide lat/lon or save your location first."
                )
            lat, lon = user_location

        return await self._list_targets_nearby_for_user_with_status_filter(
            user_id=user_id,
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
            sort=sort,
        )

    async def delete_targets_for_user_challenge(
        self, user_id: ObjectId, uc_id: ObjectId
    ) -> dict[str, Any]:
        """Supprimer toutes les targets d'un UserChallenge.

        Args:
            user_id: Utilisateur.
            uc_id: UserChallenge.

        Returns:
            dict: {ok, deleted}.
        """
        coll_targets = self.db.targets
        result = await coll_targets.delete_many(
            {
                "user_id": user_id,
                "user_challenge_id": uc_id,
            }
        )

        return {
            "ok": True,
            "deleted": result.deleted_count,
        }

    # --- Méthodes privées ---

    async def _validate_user_challenge_ownership(self, user_id: ObjectId, uc_id: ObjectId):
        """Valider que l'UC appartient bien à l'utilisateur."""
        coll_uc = self.db.user_challenges
        uc = await coll_uc.find_one({"_id": uc_id, "user_id": user_id}, {"_id": 1})
        if not uc:
            raise PermissionError("UserChallenge not found or not owned by user")

    async def _count_existing_targets(self, user_id: ObjectId, uc_id: ObjectId) -> int:
        """Compter les targets existantes."""
        coll_targets = self.db.targets
        return await coll_targets.count_documents(
            {
                "user_id": user_id,
                "user_challenge_id": uc_id,
            }
        )

    async def _score_and_persist_targets(
        self,
        candidates: dict[ObjectId, dict[str, Any]],
        user_id: ObjectId,
        uc_id: ObjectId,
        tasks: list[dict[str, Any]],
        progress_map: dict[ObjectId, dict[str, Any]],
        geo_ctx: dict[str, Any] | None,
        evaluated_at: datetime,
    ) -> dict[str, Any]:
        """Scorer et persister les targets."""
        coll_targets = self.db.targets
        now = utcnow()
        inserted = 0
        updated = 0

        # Calculer le nombre total de tâches non terminées
        total_incomplete_tasks = sum(
            1 for task in tasks if progress_map.get(task["_id"], {}).get("percent", 0) < 100
        )

        for cache_id, candidate in candidates.items():
            cache_data = candidate["cache"]
            matched_tasks = candidate["matched_tasks"]

            # Calculer les scores
            distance_m = cache_data.get("distance_m")
            radius_km = geo_ctx.get("radius_km") if geo_ctx else None

            scores = self.scorer.calculate_composite_score(
                matched_tasks=matched_tasks,
                total_incomplete_tasks=total_incomplete_tasks,
                distance_m=distance_m,
                radius_km=radius_km,
            )

            # Choisir la tâche principale
            primary_task_id = self.scorer.choose_primary_task_by_ratio(matched_tasks)

            # Document à insérer/mettre à jour
            doc = {
                "cache_id": cache_id,
                "cache_GC": cache_data.get("GC"),
                "cache_title": cache_data.get("title"),
                "cache_owner": cache_data.get("owner"),
                "cache_difficulty": cache_data.get("difficulty"),
                "cache_terrain": cache_data.get("terrain"),
                "cache_loc": cache_data.get("loc"),
                "primary_task_id": primary_task_id,
                "matched_tasks_count": len(matched_tasks),
                "score": scores["composite"],
                "score_details": {
                    "urgency": scores["urgency"],
                    "coverage": scores["coverage"],
                    "geographic": scores["geographic"],
                },
                "evaluated_at": evaluated_at,
                "updated_at": now,
            }

            # Ajouter les infos géo si disponibles
            if distance_m is not None:
                doc["distance_m"] = distance_m

            # Upsert
            result = await coll_targets.update_one(
                {"user_id": user_id, "user_challenge_id": uc_id, "cache_id": cache_id},
                {"$set": doc, "$setOnInsert": {"created_at": now}},
                upsert=True,
            )

            if result.upserted_id:
                inserted += 1
            elif result.modified_count > 0:
                updated += 1

        # Compter le total final
        total = await self._count_existing_targets(user_id, uc_id)

        return {
            "ok": True,
            "inserted": inserted,
            "updated": updated,
            "total": total,
        }

    async def _list_targets_with_pagination(
        self,
        filters: dict[str, Any],
        page: int,
        page_size: int,
        sort: str,
    ) -> dict[str, Any]:
        """Utilitaire de pagination générique pour les targets."""
        coll_targets = self.db.targets

        # Compter le total
        total_count = await coll_targets.count_documents(filters)

        # Pagination
        skip = (page - 1) * page_size
        nb_pages = (total_count + page_size - 1) // page_size

        # Construire le sort
        sort_spec = []
        for sort_key in sort.split(","):
            sort_key = sort_key.strip()
            if sort_key.startswith("-"):
                sort_spec.append((sort_key[1:], -1))
            else:
                sort_spec.append((sort_key, 1))

        # Récupérer les items
        cursor = coll_targets.find(filters).sort(sort_spec).skip(skip).limit(page_size)
        items = await cursor.to_list(length=None)

        return {
            "items": items,
            "nb_items": total_count,
            "page": page,
            "page_size": page_size,
            "nb_pages": nb_pages,
        }

    async def _list_targets_nearby(
        self,
        base_filters: dict[str, Any],
        lat: float,
        lon: float,
        radius_km: float,
        page: int,
        page_size: int,
        sort: str,
    ) -> dict[str, Any]:
        """Lister les targets avec filtre géographique."""
        # Pour l'instant, implémentation simple sans $geoNear
        # TODO: Optimiser avec aggregation pipeline géographique
        return await self._list_targets_with_pagination(
            filters=base_filters,
            page=page,
            page_size=page_size,
            sort=sort,
        )

    async def _list_targets_for_user_with_status_filter(
        self,
        user_id: ObjectId,
        status_filter: str | None,
        page: int,
        page_size: int,
        sort: str,
    ) -> dict[str, Any]:
        """Lister les targets avec filtre de statut UC."""
        base_filters = {"user_id": user_id}

        if status_filter:
            # Jointure avec user_challenges pour filtrer par statut
            # Pour l'instant, implémentation simple
            # TODO: Optimiser avec aggregation pipeline
            pass

        return await self._list_targets_with_pagination(
            filters=base_filters,
            page=page,
            page_size=page_size,
            sort=sort,
        )

    async def _list_targets_nearby_for_user_with_status_filter(
        self,
        user_id: ObjectId,
        lat: float,
        lon: float,
        radius_km: float,
        status_filter: str | None,
        page: int,
        page_size: int,
        sort: str,
    ) -> dict[str, Any]:
        """Lister les targets proches avec filtre de statut UC."""
        # Combinaison des filtres géo + statut
        # Pour l'instant, implémentation simple
        base_filters = {"user_id": user_id}

        return await self._list_targets_nearby(
            base_filters=base_filters,
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            page=page,
            page_size=page_size,
            sort=sort,
        )
