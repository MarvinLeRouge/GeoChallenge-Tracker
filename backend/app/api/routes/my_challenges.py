# backend/app/api/routes/my_challenges.py
# Routes "mes challenges" : synchronisation, listing, patch en lot, détail et patch unitaire d’un UserChallenge.

from __future__ import annotations

from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status

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
from app.core.security import CurrentUserId, get_current_user
from app.db.mongodb import db
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
    tags=["my-challenges"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/sync",
    status_code=200,
    summary="Synchroniser les UserChallenges manquants",
    description=(
        "Crée les UserChallenges **manquants** pour l’utilisateur courant (statut `pending`).\n\n"
        "- N’altère pas ceux déjà existants\n"
        "- Retourne des statistiques de synchronisation"
    ),
)
async def sync(user_id: CurrentUserId):
    """Synchroniser les UserChallenges.

    Description:
        Crée les UserChallenges manquants (status initial `pending`) en fonction des challenges disponibles.

    Args:

    Returns:
        dict: Statistiques (créations, ignorés, etc.).
    """
    stats = await sync_user_challenges(user_id)
    return stats


@router.get(
    "",
    response_model=UserChallengeListResponse,
    summary="Lister mes UserChallenges",
    description=(
        "Retourne la liste paginée des UserChallenges de l’utilisateur.\n\n"
        "- Filtre optionnel `status` (pending|accepted|dismissed|completed)\n"
        "- Pagination via `page` et `page_size` (max 200)"
    ),
)
async def list_uc(
    user_id: CurrentUserId,
    status: str | None = Query(
        default=None,
        enum=["pending", "accepted", "dismissed", "completed"],
        description="Filtrer par statut du UserChallenge.",
    ),
    page: int = Query(1, ge=1, description="Numéro de page (≥1)."),
    page_size: int = Query(50, ge=1, le=200, description="Taille de page (1–200)."),
):
    """Lister mes UserChallenges (paginé).

    Description:
        Permet de filtrer par statut et de paginer la liste des UserChallenges.

    Args:
        status (str | None): Statut à filtrer.
        page (int): Numéro de page (≥1).
        page_size (int): Taille de page (1–200).

    Returns:
        UserChallengeListResponse: Items et informations de pagination.
    """
    return await list_user_challenges(user_id, status, page, page_size)


@router.patch(
    "",
    response_model=BatchPatchResponse,
    summary="Patch en lot de plusieurs UserChallenges",
    description=(
        "Modifie en **lot** le statut/notes/override_reason de plusieurs UserChallenges.\n\n"
        "- Non transactionnel (best-effort)\n"
        "- Max 200 items"
    ),
)
async def patch_uc_batch(
    items: Annotated[
        list[BatchPatchItem],
        Body(
            ...,
            description="Tableau d’ordres de patch (uc_id, status?, notes?, override_reason?).",
        ),
    ],
    user_id: CurrentUserId,
):
    """Patch en lot de UserChallenges.

    Description:
        Applique des mises à jour itemisées sur plusieurs UserChallenges. Chaque item est validé et produit un résultat
        distinct (succès/erreur), sans échec global si un item échoue.

    Args:
        items (list[BatchPatchItem]): Liste d’ordres de patch.

    Returns:
        BatchPatchResponse: Résultats détaillés par item et nombre de mises à jour.
    """
    if not items:
        return BatchPatchResponse(updated_count=0, total=0, results=[])

    # garde-fou
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
            # propage les 404 du service en résultat itemisé plutôt qu’en échec global
            results.append(BatchPatchResultItem(uc_id=it.uc_id, ok=False, error=str(e.detail)))
        except Exception as e:
            results.append(BatchPatchResultItem(uc_id=it.uc_id, ok=False, error=str(e)))

    return BatchPatchResponse(updated_count=updated, total=len(items), results=results)


@router.get(
    "/{uc_id}",
    response_model=DetailResponse,
    summary="Détail d’un UserChallenge",
    description="Retourne le détail d’un UserChallenge appartenant à l’utilisateur.",
)
async def get_uc(
    uc_id: Annotated[PyObjectId, Path(..., description="Identifiant du UserChallenge.")],
    user_id: CurrentUserId,
):
    """Détail d’un UserChallenge.

    Description:
        Récupère le UserChallenge s’il appartient à l’utilisateur courant, sinon renvoie 404.

    Args:
        uc_id (PyObjectId): Identifiant du UserChallenge.

    Returns:
        DetailResponse: Détail du UserChallenge.
    """
    doc = await get_user_challenge_detail(user_id, ObjectId(str(uc_id)))
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UserChallenge not found")
    return doc


@router.patch(
    "/{uc_id}",
    response_model=PatchResponse,
    summary="Modifier statut/notes d’un UserChallenge",
    description=(
        "Met à jour un UserChallenge : statut (`pending|accepted|dismissed|completed`), notes et `override_reason`."
    ),
)
async def patch_uc(
    uc_id: Annotated[PyObjectId, Path(..., description="Identifiant du UserChallenge.")],
    payload: Annotated[
        PatchUCIn,
        Body(..., description="Champs modifiables : `status`, `notes`, `override_reason`."),
    ],
    user_id: CurrentUserId,
):
    """Patch d’un UserChallenge.

    Description:
        Met à jour le statut et/ou les notes (et le `override_reason`) d’un UserChallenge appartenant à l’utilisateur.

    Args:
        uc_id (PyObjectId): Identifiant du UserChallenge.
        payload (PatchUCIn): Données de mise à jour.

    Returns:
        PatchResponse: UserChallenge après mise à jour.
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

    service = CalendarVerificationService(db)
    return await service.verify_user_calendar(str(user_id), filters)


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

    service = MatrixVerificationService(db)
    return await service.verify_user_matrix(str(user_id), filters)
