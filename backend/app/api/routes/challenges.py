# backend/app/api/routes/challenges.py
# Routes admin pour (re)créer les challenges automatiquement depuis les caches "challenge".

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field
from bson import ObjectId

from app.core.bson_utils import PyObjectId
from app.core.security import get_current_user

from app.services.challenge_autocreate import create_challenges_from_caches

router = APIRouter(
    prefix="/challenges", 
    tags=["challenges"],
    dependencies=[Depends(get_current_user)]
)


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Vérifie que l’utilisateur a un rôle admin, sinon 403."""
    role = current_user.get("role")
    if role != "admin":
        # Ajuste le message si tu préfères
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user


class RefreshIn(BaseModel):
    cache_ids: Optional[List[PyObjectId]] = Field(
        default=None,
        description="Liste optionnelle de cache_ids (_id Mongo) à considérer; si absent, balaye toute la collection."
    )


@router.post(
    "/refresh-from-caches",
    summary="(Re)crée les challenges depuis les caches 'challenge'",
    description=(
        "Analyse les caches marquées 'challenge' et crée/met à jour les documents de challenge.\n\n"
        "- Option: restreindre à une liste de `cache_ids`\n"
        "- Réservé aux administrateurs (dépendance `require_admin`)"
    ),
    dependencies=[Depends(require_admin)],
)
def refresh_from_caches(
    payload: RefreshIn = Body(
        default_factory=RefreshIn,
        description="Paramètres d’exécution : optionnellement une liste de `cache_ids` (_id Mongo) à considérer.",
    ),
):
    """(Re)création de challenges à partir des caches.

    Description:
        Lance la génération/rafraîchissement des challenges depuis les caches marquées comme 'challenge'
        (p. ex. via un attribut spécifique). Peut être restreint à certaines caches.

    Args:
        payload (RefreshIn): Liste optionnelle de `cache_ids` MongoDB à traiter.

    Returns:
        dict: Indicateur de succès et statistiques de traitement.
    """
    cache_ids = None
    if payload.cache_ids:
        cache_ids = [ObjectId(str(x)) for x in payload.cache_ids]
    stats = create_challenges_from_caches(cache_ids=cache_ids)

    return {"ok": True, "stats": stats}
