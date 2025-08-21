# target_dto.py
from __future__ import annotations
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


# --- Types communs ---

class LocOut(BaseModel):
    """Latitude/Longitude en décimal."""
    lat: float
    lng: float


class MatchRef(BaseModel):
    """Référence (UC, Task) qu'une cache permet de couvrir."""
    uc_id: str
    task_id: str


# --- Sorties principales ---

class TargetOut(BaseModel):
    """Cache candidate ('cible') pour faire progresser des tâches/UC."""
    cache_id: str
    name: str
    loc: LocOut
    type_id: str
    difficulty: float
    terrain: float
    matched: List[MatchRef] = Field(default_factory=list)   # tâches couvertes
    score: float
    reasons: List[str] = Field(default_factory=list)        # explications compactes
    distance_km: Optional[float] = None                     # si filtrage centre/rayon
    already_found: bool = False                             # toujours False au MVP (filtré en amont)
    pinned: bool = False                                    # réservé pour persistance future


class PerTaskBucket(BaseModel):
    """Groupe de candidats pour une tâche donnée."""
    uc_id: str
    task_id: str
    needed: int                                             # min_count - current_count (>= 0)
    candidates: List[TargetOut]


class TargetsPreviewPerTaskResponse(BaseModel):
    """Réponse en mode per_task : top-K par tâche."""
    mode: Literal["per_task"] = "per_task"
    buckets: List[PerTaskBucket]
    meta: Dict[str, Any] = Field(default_factory=dict)      # ex: {"k": 5, "scope_size": 3}


class CoverageGap(BaseModel):
    """Slots restants par tâche après sélection (mode global)."""
    uc_id: str
    task_id: str
    remaining: int                                          # >= 0


class TargetsPreviewGlobalResponse(BaseModel):
    """Réponse en mode global : sélection gloutonne multi-couverture."""
    mode: Literal["global"] = "global"
    selection: List[TargetOut]                              # jusqu'à K éléments
    covered_pairs: int                                      # nb total de slots couverts
    remaining: List[CoverageGap]
    meta: Dict[str, Any] = Field(default_factory=dict)      # ex: {"k": 5, "pool": 120, "scope_size": 8}
