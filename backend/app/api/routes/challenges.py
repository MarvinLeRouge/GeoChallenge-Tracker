
# backend/app/api/routes/challenges.py

"""
Routes `challenges` — création automatique depuis les caches portant l'attribut challenge (cache_attribute_id=71).
Protégé admin. Utilise PyObjectId pour la validation côté Swagger/OpenAPI.
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field
from bson import ObjectId

from app.core.bson_utils import PyObjectId
from app.core.security import get_current_user

from app.services.challenge_autocreate import create_challenges_from_caches

router = APIRouter(prefix="/challenges", tags=["challenges"])


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
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


@router.post("/refresh-from-caches", summary="Auto-crée les challenges depuis les caches 'challenge' (attr_id=71)",
             dependencies=[Depends(require_admin)])
def refresh_from_caches(payload: RefreshIn = Body(default_factory=RefreshIn)):
    # PyObjectId hérite d'ObjectId -> compatible, mais on convertit explicitement pour éviter les surprises
    cache_ids = None
    if payload.cache_ids:
        cache_ids = [ObjectId(str(x)) for x in payload.cache_ids]
    stats = create_challenges_from_caches(cache_ids=cache_ids)

    return {"ok": True, "stats": stats}
