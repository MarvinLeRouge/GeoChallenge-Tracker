# backend/app/services/targets/target_service_evaluation.py
# Target evaluation/scoring/persistence helpers for TargetService.

from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.utils import utcnow

from .target_scorer import TargetScorer


async def validate_user_challenge_ownership(
    db: AsyncIOMotorDatabase, user_id: ObjectId, uc_id: ObjectId
) -> None:
    """Validate that the UC belongs to the user."""
    coll_uc = db.user_challenges
    uc = await coll_uc.find_one({"_id": uc_id, "user_id": user_id}, {"_id": 1})
    if not uc:
        raise PermissionError("UserChallenge not found or not owned by user")


async def count_existing_targets(
    db: AsyncIOMotorDatabase, user_id: ObjectId, uc_id: ObjectId
) -> int:
    """Count existing targets."""
    coll_targets = db.targets
    return await coll_targets.count_documents(
        {
            "user_id": user_id,
            "user_challenge_id": uc_id,
        }
    )


async def score_and_persist_targets(
    db: AsyncIOMotorDatabase,
    scorer: TargetScorer,
    candidates: dict[ObjectId, dict[str, Any]],
    user_id: ObjectId,
    uc_id: ObjectId,
    tasks: list[dict[str, Any]],
    progress_map: dict[ObjectId, dict[str, Any]],
    geo_ctx: dict[str, Any] | None,
    evaluated_at: datetime,
) -> dict[str, Any]:
    """Score and persist targets."""
    coll_targets = db.targets
    now = utcnow()
    inserted = 0
    updated = 0

    # Count the total number of incomplete tasks
    total_incomplete_tasks = sum(
        1 for task in tasks if progress_map.get(task["_id"], {}).get("percent", 0) < 100
    )

    for cache_id, candidate in candidates.items():
        cache_data = candidate["cache"]
        matched_tasks = candidate["matched_tasks"]

        # Calculate scores
        distance_m = cache_data.get("distance_m")
        radius_km = geo_ctx.get("radius_km") if geo_ctx else None

        scores = scorer.calculate_composite_score(
            matched_tasks=matched_tasks,
            total_incomplete_tasks=total_incomplete_tasks,
            distance_m=distance_m,
            radius_km=radius_km,
        )

        # Choose the primary task
        primary_task_id = scorer.choose_primary_task_by_ratio(matched_tasks)

        # Document to insert/update
        doc = {
            "cache_id": cache_id,
            "cache_GC": cache_data.get("GC"),
            "cache_title": cache_data.get("title"),
            "cache_owner": cache_data.get("owner"),
            "cache_difficulty": cache_data.get("difficulty"),
            "cache_terrain": cache_data.get("terrain"),
            "cache_type_code": cache_data.get("type_code"),
            "loc": cache_data.get("loc"),
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

        # Add geo info if available
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

    # Count the final total
    total = await count_existing_targets(db, user_id, uc_id)

    return {
        "ok": True,
        "inserted": inserted,
        "updated": updated,
        "total": total,
    }
