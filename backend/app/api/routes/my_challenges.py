# backend/app/api/routes/my_challenges.py
# "My challenges" routes: sync, listing, batch patch, detail, and individual patch of a UserChallenge.

from __future__ import annotations

from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Body, HTTPException, Path, Query, status

from app.api.deps import CurrentUserId
from app.api.dto.calendar_verification import (
    CalendarFilters,
    CalendarResult,
    MatrixFilters,
    MatrixResult,
)
from app.api.dto.user_challenge import (
    DetailResponse,
    PatchResponse,
    PatchUCIn,
    UserChallengeListResponse,
)
from app.api.dto.user_challenge_batch import (
    BatchPatchItem,
    BatchPatchResponse,
    BatchPatchResultItem,
)
from app.core.bson_utils import PyObjectId
from app.db.mongodb import get_db
from app.services.calendar_verification import CalendarVerificationService
from app.services.matrix_verification import MatrixVerificationService
from app.services.user_challenges_service import (
    get_user_challenge_detail,
    list_user_challenges,
    patch_user_challenge,
    sync_user_challenges,
)

router = APIRouter(
    prefix="/my/challenges",
    tags=["My challenges"],
)


# TODO: [BACKLOG] Route /my/challenges/sync (POST) to verify
@router.post(
    "/sync",
    status_code=200,
    summary="Synchronize missing UserChallenges",
    description=(
        "Creates **missing** UserChallenges for the current user (status `pending`).\n\n"
        "- Does not alter existing ones\n"
        "- Returns synchronization statistics"
    ),
)
async def sync(user_id: CurrentUserId):
    """Synchronizes UserChallenges.

    Description:
        Creates missing UserChallenges (initial status `pending`) based on available challenges.

    Args:

    Returns:
        dict: Statistics (created, skipped, etc.).
    """
    stats = await sync_user_challenges(user_id)
    return stats


# TODO: [BACKLOG] Route /my/challenges (GET) to verify
@router.get(
    "",
    response_model=UserChallengeListResponse,
    summary="List my UserChallenges",
    description=(
        "Returns the paginated list of UserChallenges for the current user.\n\n"
        "- Optional `status` filter (pending|accepted|dismissed|completed)\n"
        "- Pagination via `page` and `page_size` (max 200)"
    ),
)
async def list_uc(
    user_id: CurrentUserId,
    status: str | None = Query(
        default=None,
        enum=["pending", "accepted", "dismissed", "completed"],
        description="Filter by UserChallenge status.",
    ),
    page: int = Query(1, ge=1, description="Page number (≥1)."),
    page_size: int = Query(50, ge=1, le=200, description="Page size (1–200)."),
):
    """List my UserChallenges (paginated).

    Description:
        Allows filtering by status and paginating the list of UserChallenges.

    Args:
        status (str | None): Status to filter by.
        page (int): Page number (≥1).
        page_size (int): Page size (1–200).

    Returns:
        UserChallengeListResponse: Items and pagination information.
    """
    return await list_user_challenges(user_id, status, page, page_size)


# TODO: [BACKLOG] Route /my/challenges (PATCH) to verify
@router.patch(
    "",
    response_model=BatchPatchResponse,
    summary="Batch patch multiple UserChallenges",
    description=(
        "Updates the status/notes/override_reason of multiple UserChallenges in **batch**.\n\n"
        "- Non-transactional (best-effort)\n"
        "- Max 200 items"
    ),
)
async def patch_uc_batch(
    items: Annotated[
        list[BatchPatchItem],
        Body(
            ...,
            description="Array of patch instructions (uc_id, status?, notes?, override_reason?).",
        ),
    ],
    user_id: CurrentUserId,
):
    """Batch patch UserChallenges.

    Description:
        Applies itemized updates to multiple UserChallenges. Each item is validated and produces a distinct
        result (success/error) without failing the entire batch if a single item fails.

    Args:
        items (list[BatchPatchItem]): List of patch instructions.

    Returns:
        BatchPatchResponse: Detailed results per item and update count.
    """
    if not items:
        return BatchPatchResponse(updated_count=0, total=0, results=[])

    # safety guard
    if len(items) > 200:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Batch trop volumineux (max 200 items)",
        )

    results: list[BatchPatchResultItem] = []
    updated = 0

    for it in items:
        try:
            success, error, doc = await patch_user_challenge(
                user_id=user_id,
                uc_id=ObjectId(str(it.uc_id)),
                patch_data={
                    "status": it.status,
                    "notes": it.notes,
                    "override_reason": it.override_reason,
                },
            )
            if not success or not doc:
                results.append(
                    BatchPatchResultItem(
                        uc_id=it.uc_id, ok=False, error=error or "UserChallenge not found"
                    )
                )
                continue
            updated += 1
            results.append(BatchPatchResultItem(uc_id=it.uc_id, ok=True))
        except HTTPException as e:
            # propagate 404s from the service as itemized results rather than a global failure
            results.append(BatchPatchResultItem(uc_id=it.uc_id, ok=False, error=str(e.detail)))
        except Exception as e:
            results.append(BatchPatchResultItem(uc_id=it.uc_id, ok=False, error=str(e)))

    return BatchPatchResponse(updated_count=updated, total=len(items), results=results)


# TODO: [BACKLOG] Route /my/challenges/{uc_id} (GET) to verify
@router.get(
    "/{uc_id}",
    response_model=DetailResponse,
    summary="UserChallenge detail",
    description="Returns the detail of a UserChallenge belonging to the current user.",
)
async def get_uc(
    uc_id: Annotated[PyObjectId, Path(..., description="UserChallenge identifier.")],
    user_id: CurrentUserId,
):
    """UserChallenge detail.

    Description:
        Retrieves the UserChallenge if it belongs to the current user, otherwise returns 404.

    Args:
        uc_id (PyObjectId): UserChallenge identifier.

    Returns:
        DetailResponse: UserChallenge detail.
    """
    doc = await get_user_challenge_detail(user_id, ObjectId(str(uc_id)))
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UserChallenge not found")
    return doc


# TODO: [BACKLOG] Route /my/challenges/{uc_id} (PATCH) to verify
@router.patch(
    "/{uc_id}",
    response_model=PatchResponse,
    summary="Update status/notes of a UserChallenge",
    description=(
        "Updates a UserChallenge: status (`pending|accepted|dismissed|completed`), notes, and `override_reason`."
    ),
)
async def patch_uc(
    uc_id: Annotated[PyObjectId, Path(..., description="UserChallenge identifier.")],
    payload: Annotated[
        PatchUCIn,
        Body(..., description="Editable fields: `status`, `notes`, `override_reason`."),
    ],
    user_id: CurrentUserId,
):
    """Patch a UserChallenge.

    Description:
        Updates the status and/or notes (and `override_reason`) of a UserChallenge belonging to the current user.

    Args:
        uc_id (PyObjectId): UserChallenge identifier.
        payload (PatchUCIn): Update data.

    Returns:
        PatchResponse: UserChallenge after update.
    """
    success, error, updated_uc = await patch_user_challenge(
        user_id=user_id,
        uc_id=ObjectId(str(uc_id)),
        patch_data={
            "status": payload.status,
            "notes": payload.notes,
            "override_reason": payload.override_reason,
        },
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "Failed to update UserChallenge",
        )
    if not updated_uc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UserChallenge not found")
    return updated_uc


# DONE: [BACKLOG] Route /my/challenges/basics/calendar (GET) verified
@router.get(
    "/basics/calendar",
    response_model=CalendarResult,
    summary="Verify user's calendar completion",
)
async def verify_calendar(
    user_id: CurrentUserId,
    cache_type: str | None = Query(None, description="Optional cache type name filter"),
    cache_size: str | None = Query(None, description="Optional cache size name filter"),
) -> CalendarResult:
    """
    Verify if the current user has completed the calendar challenge.

    Returns completion status for both 365-day and 366-day scenarios.
    Optional filtering by cache type and/or cache size.

    Args:
        user_id: Current user ID (from JWT token).
        cache_type: Optional cache type name for filtering.
        cache_size: Optional cache size name for filtering.

    Returns:
        CalendarResult: Calendar completion status and details.
    """
    filters = CalendarFilters(cache_type_name=cache_type, cache_size_name=cache_size)

    db = get_db()
    service = CalendarVerificationService(db)
    return await service.verify_user_calendar(str(user_id), filters)


# DONE: [BACKLOG] Route /my/challenges/basics/matrix (GET) verified
@router.get(
    "/basics/matrix",
    response_model=MatrixResult,
    summary="Verify user's D/T matrix completion",
)
async def verify_matrix(
    user_id: CurrentUserId,
    cache_type: str | None = Query(None, description="Optional cache type name filter"),
    cache_size: str | None = Query(None, description="Optional cache size name filter"),
) -> MatrixResult:
    """
    Verify if the current user has completed the D/T matrix challenge.

    Returns completion status for 9x9 matrix (difficulty 1.0-5.0 × terrain 1.0-5.0 by 0.5).
    Optional filtering by cache type and/or cache size.

    Args:
        user_id: Current user ID (from JWT token).
        cache_type: Optional cache type name for filtering.
        cache_size: Optional cache size name for filtering.

    Returns:
        MatrixResult: D/T matrix completion status and details.
    """
    filters = MatrixFilters(cache_type_name=cache_type, cache_size_name=cache_size)

    db = get_db()
    service = MatrixVerificationService(db)
    return await service.verify_user_matrix(str(user_id), filters)
