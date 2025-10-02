# backend/app/api/routes/my_challenges.py
# Routes "mes challenges" : synchronisation, listing, patch en lot, détail et patch unitaire d’un UserChallenge.

from __future__ import annotations

from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from app.core.bson_utils import PyObjectId
from app.core.security import CurrentUserId, get_current_user
from app.models.user_challenge_dto import (
    DetailResponse,
    UserChallengeListResponse,
    PatchResponse,
    PatchUCIn,
)
from app.services.user_challenges import (
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
def sync(user_id: CurrentUserId):
    """Synchroniser les UserChallenges.

    Description:
        Crée les UserChallenges manquants (status initial `pending`) en fonction des challenges disponibles.

    Args:

    Returns:
        dict: Statistiques (créations, ignorés, etc.).
    """
    stats = sync_user_challenges(user_id)
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
def list_uc(
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
    return list_user_challenges(user_id, status, page, page_size)


# --- modèles locaux pour le batch ---
class BatchPatchItem(BaseModel):
    uc_id: PyObjectId = Field(..., description="UserChallenge id")
    status: str | None = Field(
        default=None,
        description="Nouveau statut (pending|accepted|dismissed|completed)",
    )
    notes: str | None = None
    override_reason: str | None = None


class BatchPatchResultItem(BaseModel):
    uc_id: PyObjectId
    ok: bool
    error: str | None = None


class BatchPatchResponse(BaseModel):
    updated_count: int
    total: int
    results: list[BatchPatchResultItem]


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
def patch_uc_batch(
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
            doc = patch_user_challenge(
                user_id=user_id,
                uc_id=ObjectId(str(it.uc_id)),
                status=it.status,
                notes=it.notes,
                override_reason=it.override_reason,
            )
            if not doc:
                results.append(
                    BatchPatchResultItem(uc_id=it.uc_id, ok=False, error="UserChallenge not found")
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
def get_uc(
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
    doc = get_user_challenge_detail(user_id, ObjectId(str(uc_id)))
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
def patch_uc(
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
    doc = patch_user_challenge(
        user_id=user_id,
        uc_id=ObjectId(str(uc_id)),
        status=payload.status,
        notes=payload.notes,
        override_reason=payload.override_reason,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UserChallenge not found")
    return doc
