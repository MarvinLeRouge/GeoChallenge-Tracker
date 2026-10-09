# app/api/routes/maintenance/targets_stats.py
# Per-user admin routes: force target re-evaluation, found-caches sync, and stats.

from __future__ import annotations

from typing import Annotated

from bson import ObjectId
from fastapi import File, HTTPException, UploadFile, status
from fastapi import Path as ApiPath

from app.api.dto.user_stats import UserStatsOut
from app.core.middleware import read_upload_file_with_limit
from app.core.settings import get_settings
from app.db.mongodb import get_db
from app.services.found_caches_sync import extract_gc_codes, sync_found_caches
from app.services.targets_service import evaluate_all_for_user
from app.services.user_stats import get_user_stats

from ._router import router


@router.post(
    "/users/{user_id}/targets/evaluate-all",
    status_code=status.HTTP_200_OK,
    summary="Force re-evaluate targets for a given user (admin)",
    description=(
        "Wipes and recomputes targets for **all** accepted UserChallenges of the given user.\n\n"
        "Use this when a user reports stale or missing targets."
    ),
)
async def maintenance_evaluate_all_targets(
    user_id: str = ApiPath(..., description="User identifier."),
):
    """Force re-evaluate targets for a given user.

    Args:
        user_id (str): Target user identifier.

    Returns:
        dict: {ok, evaluated, total_inserted, total_updated, last_targets_evaluated_at}.
    """
    try:
        uid = ObjectId(user_id)
    except Exception as err:
        raise HTTPException(status_code=422, detail="Invalid user_id.") from err

    return await evaluate_all_for_user(user_id=uid, force=True)


@router.post(
    "/users/{user_id}/found-caches/sync",
    status_code=status.HTTP_200_OK,
    summary="Sync found caches from a text file (admin)",
    description=(
        "Uploads a plain-text file and extracts every GC code it contains.\n\n"
        "The extracted list is treated as the **complete and authoritative** found-cache list "
        "for the given user:\n"
        "- Found caches **not in the list** are deleted.\n"
        "- GC codes **not yet in found caches** are inserted.\n"
        "- GC codes not matched to any known cache are reported as `unknown_gc_codes`."
    ),
)
async def maintenance_sync_found_caches(
    user_id: Annotated[str, ApiPath(..., description="Target user identifier.")],
    file: Annotated[UploadFile, File(..., description="Plain-text file containing GC codes.")],
):
    """Sync found caches for a given user from a canonical text file.

    Args:
        user_id (str): Target user identifier.
        file (UploadFile): Text file whose content will be scanned for GC codes.

    Returns:
        dict: {nb_provided, nb_deleted, nb_added, nb_unknown_gc, unknown_gc_codes}.
    """
    try:
        uid = ObjectId(user_id)
    except Exception as err:
        raise HTTPException(status_code=422, detail="Invalid user_id.") from err

    settings = get_settings()
    content = await read_upload_file_with_limit(file, settings.max_upload_bytes)

    try:
        text = content.decode("utf-8", errors="replace")
    except Exception as err:
        raise HTTPException(status_code=400, detail="Unable to decode file content.") from err

    gc_codes = extract_gc_codes(text)
    db = get_db()
    return await sync_found_caches(db=db, user_id=uid, gc_codes=gc_codes)


@router.get(
    "/users/{user_id}/stats",
    response_model=UserStatsOut,
    summary="Get statistics for a given user (admin)",
    description="Returns summary statistics for the specified user.",
)
async def maintenance_get_user_stats(
    user_id: str = ApiPath(..., description="Target user identifier."),
) -> UserStatsOut:
    """Get statistics for a given user.

    Args:
        user_id (str): Target user identifier.

    Returns:
        UserStatsOut: Computed statistics.
    """
    try:
        uid = ObjectId(user_id)
    except Exception as err:
        raise HTTPException(status_code=422, detail="Invalid user_id.") from err

    try:
        return await get_user_stats(user_id=uid, target_user_id=uid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
