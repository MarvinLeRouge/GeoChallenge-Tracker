# backend/app/models/target_dto.py
# Schémas de sortie pour les endpoints de targets (listes, per-task, global).

from __future__ import annotations

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


# ---- Types communs ----

class LocOut(BaseModel):
    """Coordonnées décimales.

    Attributes:
        lat (float): Latitude.
        lng (float): Longitude.
    """
    lat: float
    lng: float


# ---- Sorties "list" pour les routes GET /targets ----

class TargetListItemOut(BaseModel):
    """Élément de liste « target ».

    Description:
        Représente une cache candidate qui satisfait ≥1 tâche. `distance_km` n’est présent
        que pour les endpoints « nearby ».

    Attributes:
        id (str): Id du document target.
        user_challenge_id (str): UC concerné.
        cache_id (str): Cache ciblée.
        GC (str | None): Code GC (si jointure).
        name (str | None): Nom de la cache (si jointure).
        loc (LocOut | None): Coordonnées (si jointure).
        matched_task_ids (list[str]): Tâches satisfaites.
        primary_task_id (str | None): Tâche principale.
        score (float): Score de tri.
        reasons (list[str]): Raisons textuelles.
        pinned (bool): Épinglée.
        distance_km (float | None): Distance (si mode nearby).
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
    """Réponse liste paginée de targets.

    Attributes:
        items (list[TargetListItemOut]): Résultats.
        total (int): Total trouvé.
        page (int): Page courante.
        limit (int): Taille de page.
    """
    items: List[TargetListItemOut]
    total: int
    page: int
    limit: int


# ---- (Optionnel) DTO de preview "par tâche" ----

class MatchRef(BaseModel):
    """Référence (UC, Task) couverte.

    Attributes:
        uc_id (str): UC visé.
        task_id (str): Tâche couverte.
    """
    uc_id: str
    task_id: str


class TargetOut(BaseModel):
    """Target enrichie (preview).

    Description:
        Vue détaillée optionnelle si les services réalisent des jointures/agrégations.

    Attributes:
        cache_id (str): Id cache.
        name (str): Nom cache.
        loc (LocOut): Coordonnées.
        type_id (str | None): Type.
        difficulty (float | None): D.
        terrain (float | None): T.
        matched (list[MatchRef]): Couvertures.
        score (float): Score.
        reasons (list[str]): Raisons.
        distance_km (float | None): Distance (nearby).
        already_found (bool): Déjà trouvée.
        pinned (bool): Épinglée.
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
    """Grappe de candidats par tâche.

    Attributes:
        uc_id (str): UC.
        task_id (str): Tâche.
        needed (int): Restant à couvrir.
        candidates (list[TargetOut]): Sélection proposée.
    """
    uc_id: str
    task_id: str
    needed: int
    candidates: List[TargetOut]


class TargetsPreviewPerTaskResponse(BaseModel):
    """Réponse de preview « par tâche ».

    Attributes:
        mode (Literal['per_task']): Indicateur de mode.
        buckets (list[PerTaskBucket]): Groupes par tâche.
        meta (dict): Métadonnées libres.
    """
    mode: Literal["per_task"] = "per_task"
    buckets: List[PerTaskBucket]
    meta: Dict[str, Any] = Field(default_factory=dict)


# ---- (Optionnel) DTO de preview "global" ----

class CoverageGap(BaseModel):
    """Manque de couverture.

    Attributes:
        uc_id (str): UC.
        task_id (str): Tâche.
        remaining (int): Reste à couvrir.
    """
    uc_id: str
    task_id: str
    remaining: int


class TargetsPreviewGlobalResponse(BaseModel):
    """Réponse de preview « global ».

    Attributes:
        mode (Literal['global']): Indicateur de mode.
        selection (list[TargetOut]): Sélection globale.
        covered_pairs (int): Couples (UC,Task) couverts.
        remaining (list[CoverageGap]): Manques restants.
        meta (dict): Métadonnées libres.
    """
    mode: Literal["global"] = "global"
    selection: List[TargetOut]
    covered_pairs: int
    remaining: List[CoverageGap]
    meta: Dict[str, Any] = Field(default_factory=dict)
