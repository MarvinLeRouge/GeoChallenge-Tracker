# backend/app/models/cache_size.py
# Référentiel listant les tailles (Small, Micro, Regular, …) avec ordre d’affichage.

from __future__ import annotations
from typing import Optional
import datetime as dt
from pydantic import BaseModel, Field
from app.core.utils import *
from app.core.bson_utils import *

class CacheSizeBase(BaseModel):
    """Taille de cache (référentiel).

    Description:
        Nom/Code de taille et ordre pour le tri.

    Attributes:
        name (str): Nom (ex. "Small", "Micro").
        code (str | None): Code court (ex. "S", "M").
        order (int | None): Ordre d’affichage.
    """
    name: str                    # ex: "Small", "Micro", "Regular"
    code: Optional[str] = None   # code interne ou abbr (ex: "S", "M")
    order: Optional[int] = None  # ordonnancement des cache sizes

class CacheSizeCreate(CacheSizeBase):
    """Payload de création d’une taille de cache.

    Description:
        Identique à `CacheSizeBase` pour insertion dans le référentiel.
    """
    pass

class CacheSizeUpdate(BaseModel):
    """Payload de mise à jour d’une taille de cache.

    Description:
        Mise à jour partielle des champs.

    Attributes:
        name (str | None): Nouveau nom.
        code (str | None): Nouveau code.
        order (int | None): Nouvel ordre.
    """
    name: Optional[str] = None
    code: Optional[str] = None
    order: Optional[int] = None

class CacheSize(MongoBaseModel, CacheSizeBase):
    """Document Mongo d’une taille de cache (référentiel).

    Description:
        Étend `CacheSizeBase` avec _id, created_at, updated_at.
    """
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None
