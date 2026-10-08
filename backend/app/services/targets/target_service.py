# backend/app/services/targets/target_service.py
# Main target management service with dependency injection.

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.utils import utcnow

from . import target_service_evaluation as evaluation_helpers
from . import target_service_listing as listing_helpers
from .geo_utils import get_user_location
from .target_evaluator import TargetEvaluator
from .target_scorer import TargetScorer

log = logging.getLogger(__name__)


class TargetService:
    """Main cache target management service.

    Description:
        Orchestrates the evaluation, scoring, persistence,
        and retrieval of cache targets for UserChallenges.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize the service.

        Args:
            db: MongoDB database instance.
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
        """Evaluate and persist targets for a UserChallenge.

        Args:
            user_id: Owning user identifier.
            uc_id: Target UserChallenge identifier.
            limit_per_task: Per-task result cap.
            hard_limit_total: Global aggregation cap.
            geo_ctx: Geographic context {lat, lon, radius_km}.
            evaluated_at: Evaluation timestamp.
            force: Force recalculation even if targets already exist.

        Returns:
            dict: {ok, inserted, updated, total, skipped?}.

        Raises:
            PermissionError: If the UC does not exist or is not owned by the user.
        """
        # Validate ownership
        await self._validate_user_challenge_ownership(user_id, uc_id)

        log.info("[targets] evaluate UC=%s user=%s force=%s", uc_id, user_id, force)

        # Short-circuit if not forcing and enough targets already exist
        if not force:
            existing_count = await self._count_existing_targets(user_id, uc_id)
            threshold = min(hard_limit_total, limit_per_task * 5)
            if existing_count >= threshold:
                log.info("[targets] skipped UC=%s — %d existing targets", uc_id, existing_count)
                return {
                    "ok": True,
                    "inserted": 0,
                    "updated": 0,
                    "total": existing_count,
                    "skipped": True,
                }

        # When forcing, wipe existing targets so stale entries don't survive
        if force:
            await self.db.targets.delete_many({"user_id": user_id, "user_challenge_id": uc_id})
            log.info("[targets] force — existing targets deleted for UC=%s", uc_id)

        # Retrieve required data
        username = await self.evaluator.get_username(user_id)
        tasks = await self.evaluator.get_user_challenge_tasks(uc_id)
        progress_map = await self.evaluator.get_latest_progress_task_map(uc_id)

        # Evaluate candidate caches
        candidates = await self.evaluator.evaluate_cache_candidates(
            tasks=tasks,
            progress_map=progress_map,
            username=username,
            user_id=user_id,
            geo_ctx=geo_ctx,
            limit_per_task=limit_per_task,
            hard_limit_total=hard_limit_total,
        )

        log.info("[targets] UC=%s — %d candidate(s) found", uc_id, len(candidates))

        # Score and persist
        result = await self._score_and_persist_targets(
            candidates=candidates,
            user_id=user_id,
            uc_id=uc_id,
            tasks=tasks,
            progress_map=progress_map,
            geo_ctx=geo_ctx,
            evaluated_at=evaluated_at or utcnow(),
        )

        log.info(
            "[targets] UC=%s — inserted=%d updated=%d total=%d",
            uc_id,
            result["inserted"],
            result["updated"],
            result["total"],
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
        """List targets for a UserChallenge (paginated).

        Args:
            user_id: User identifier.
            uc_id: UserChallenge identifier.
            page: Page number.
            page_size: Page size.
            sort: Sort key.

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
        """List nearby targets for a UserChallenge.

        Args:
            user_id: User identifier.
            uc_id: UserChallenge identifier.
            lat: Latitude.
            lon: Longitude.
            radius_km: Radius in km.
            page: Page number.
            page_size: Page size.
            sort: Sort key.

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
        """List all targets for a user.

        Args:
            user_id: User identifier.
            status_filter: UC status filter.
            page: Page number.
            page_size: Page size.
            sort: Sort key.

        Returns:
            dict: {items, nb_items, page, page_size, nb_pages}.
        """
        # Build filters with join on user_challenges
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
        """List nearby targets for all challenges of a user.

        Args:
            user_id: User identifier.
            lat: Latitude (or None to use the user's saved location).
            lon: Longitude (or None to use the user's saved location).
            radius_km: Radius in km.
            status_filter: UC status filter.
            page: Page number.
            page_size: Page size.
            sort: Sort key.

        Returns:
            dict: {items, nb_items, page, page_size, nb_pages}.
        """
        # Resolve location if needed
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

    async def evaluate_all_for_user(
        self,
        user_id: ObjectId,
        force: bool = False,
    ) -> dict[str, Any]:
        """Evaluate targets for all accepted UserChallenges of a user.

        Args:
            user_id: User identifier.
            force: Force recalculation even if targets already exist.

        Returns:
            dict: {ok, evaluated, total_inserted, total_updated, last_targets_evaluated_at}.
        """
        coll_uc = self.db.user_challenges
        uc_docs = await coll_uc.find(
            {"user_id": user_id, "status": "accepted"}, {"_id": 1}
        ).to_list(length=None)

        log.info("[targets] evaluate_all user=%s — %d accepted UC(s)", user_id, len(uc_docs))

        total_inserted = 0
        total_updated = 0
        evaluated = 0

        for doc in uc_docs:
            uc_id = doc["_id"]
            try:
                result = await self.evaluate_targets_for_user_challenge(
                    user_id=user_id,
                    uc_id=uc_id,
                    force=force,
                )
                if not result.get("skipped"):
                    total_inserted += result.get("inserted", 0)
                    total_updated += result.get("updated", 0)
                evaluated += 1
            except Exception:
                log.exception("[targets] evaluate_all — UC %s failed", uc_id)

        now = utcnow()
        await self.db.users.update_one(
            {"_id": user_id},
            {"$set": {"last_targets_evaluated_at": now}},
        )

        log.info(
            "[targets] evaluate_all done — %d UC(s) evaluated, inserted=%d updated=%d",
            evaluated,
            total_inserted,
            total_updated,
        )

        return {
            "ok": True,
            "evaluated": evaluated,
            "total_inserted": total_inserted,
            "total_updated": total_updated,
            "last_targets_evaluated_at": now,
        }

    async def get_targets_refresh_status(self, user_id: ObjectId) -> dict[str, Any]:
        """Return whether targets need to be refreshed for a user.

        Compares ``last_not_found_import_at`` and ``last_targets_evaluated_at``
        on the user document to determine staleness.

        Args:
            user_id: User identifier.

        Returns:
            dict: {needs_refresh, last_not_found_import_at, last_targets_evaluated_at}.
        """
        user = await self.db.users.find_one(
            {"_id": user_id},
            {"last_not_found_import_at": 1, "last_targets_evaluated_at": 1},
        )

        last_import = user.get("last_not_found_import_at") if user else None
        last_eval = user.get("last_targets_evaluated_at") if user else None

        needs_refresh = bool(
            last_import is not None and (last_eval is None or last_import > last_eval)
        )

        return {
            "needs_refresh": needs_refresh,
            "last_not_found_import_at": last_import,
            "last_targets_evaluated_at": last_eval,
        }

    async def delete_targets_for_user_challenge(
        self, user_id: ObjectId, uc_id: ObjectId
    ) -> dict[str, Any]:
        """Delete all targets for a UserChallenge.

        Args:
            user_id: User identifier.
            uc_id: UserChallenge identifier.

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

    # --- Private methods (thin delegations to target_service_{evaluation,listing}) ---

    async def _validate_user_challenge_ownership(self, user_id: ObjectId, uc_id: ObjectId):
        """Validate that the UC belongs to the user."""
        return await evaluation_helpers.validate_user_challenge_ownership(self.db, user_id, uc_id)

    async def _count_existing_targets(self, user_id: ObjectId, uc_id: ObjectId) -> int:
        """Count existing targets."""
        return await evaluation_helpers.count_existing_targets(self.db, user_id, uc_id)

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
        """Score and persist targets."""
        return await evaluation_helpers.score_and_persist_targets(
            self.db,
            self.scorer,
            candidates=candidates,
            user_id=user_id,
            uc_id=uc_id,
            tasks=tasks,
            progress_map=progress_map,
            geo_ctx=geo_ctx,
            evaluated_at=evaluated_at,
        )

    async def _list_targets_with_pagination(
        self,
        filters: dict[str, Any],
        page: int,
        page_size: int,
        sort: str,
    ) -> dict[str, Any]:
        """Generic pagination utility for targets."""
        return await listing_helpers.list_targets_with_pagination(
            self.db, filters=filters, page=page, page_size=page_size, sort=sort
        )

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
        """List targets within a geographic radius using $geoNear."""
        return await listing_helpers.list_targets_nearby(
            self.db,
            base_filters=base_filters,
            lat=lat,
            lon=lon,
            radius_km=radius_km,
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
        """List targets with an optional UC status filter."""
        return await listing_helpers.list_targets_for_user_with_status_filter(
            self.db,
            user_id=user_id,
            status_filter=status_filter,
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
        """List nearby targets with an optional UC status filter."""
        return await listing_helpers.list_targets_nearby_for_user_with_status_filter(
            self.db,
            user_id=user_id,
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
            sort=sort,
        )
