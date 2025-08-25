# app/models/target_dto.py
from __future__ import annotations

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


# ---- Types communs ----

class LocOut(BaseModel):
    """Latitude/Longitude en décimal (format d’API)."""
    lat: float
    lng: float


# ---- Sorties "list" pour les routes GET /targets ----

class TargetListItemOut(BaseModel):
    """
    Élément d’une liste de targets :
    - une cache candidate qui satisfait ≥1 task du UserChallenge
    - distance_km n’apparaît que pour les endpoints 'nearby'
    """
    id: str                                        # id du document target
    user_challenge_id: str
    cache_id: str

    # Résumé cache (optionnel selon la jointure effectuée côté service)
    GC: Optional[str] = None
    name: Optional[str] = None
    loc: Optional[LocOut] = None

    matched_task_ids: List[str] = Field(default_factory=list)
    primary_task_id: Optional[str] = None

    score: float
    reasons: List[str] = Field(default_factory=list)
    pinned: bool = False

    distance_km: Optional[float] = None           # si recherche 'nearby'


class TargetListResponse(BaseModel):
    items: List[TargetListItemOut]
    total: int
    page: int
    limit: int


# ---- (Optionnel) DTO de preview "par tâche" ----

class MatchRef(BaseModel):
    """Référence (UC, Task) qu’une cache permet de couvrir."""
    uc_id: str
    task_id: str


class TargetOut(BaseModel):
    """
    Sortie enrichie pour des modes "preview" (si utilisés plus tard).
    À n’utiliser que si le service alimente ces champs via des jointures.
    """
    cache_id: str
    name: str
    loc: LocOut
    type_id: Optional[str] = None
    difficulty: Optional[float] = None
    terrain: Optional[float] = None
    matched: List[MatchRef] = Field(default_factory=list)
    score: float
    reasons: List[str] = Field(default_factory=list)
    distance_km: Optional[float] = None
    already_found: bool = False
    pinned: bool = False


class PerTaskBucket(BaseModel):
    uc_id: str
    task_id: str
    needed: int
    candidates: List[TargetOut]


class TargetsPreviewPerTaskResponse(BaseModel):
    mode: Literal["per_task"] = "per_task"
    buckets: List[PerTaskBucket]
    meta: Dict[str, Any] = Field(default_factory=dict)


# ---- (Optionnel) DTO de preview "global" ----

class CoverageGap(BaseModel):
    uc_id: str
    task_id: str
    remaining: int


class TargetsPreviewGlobalResponse(BaseModel):
    mode: Literal["global"] = "global"
    selection: List[TargetOut]
    covered_pairs: int
    remaining: List[CoverageGap]
    meta: Dict[str, Any] = Field(default_factory=dict)
