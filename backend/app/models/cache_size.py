# backend/app/models/cache_size.py
# Référentiel listant les tailles (Small, Micro, Regular, …) avec ordre d’affichage.

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.core.bson_utils import MongoBaseModel
from app.core.utils import now


class CacheSizeBase(BaseModel):
    """Taille de cache (référentiel).

    Description:
        Nom/Code de taille et ordre pour le tri.

    Attributes:
        name (str): Nom (ex. "Small", "Micro").
        code (str | None): Code court (ex. "S", "M").
        aliases (list[str]): Alias reconnus pour cette taille.
        order (int | None): Ordre d’affichage.
    """

    name: str  # ex: "Small", "Micro", "Regular"
    code: str | None = None  # code interne ou abbr (ex: "S", "M")
    aliases: list[str] = Field(default_factory=list)  # alias reconnus pour cette taille
    order: int | None = None  # ordonnancement des cache sizes


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
        aliases (list[str] | None): Nouveaux alias.
        order (int | None): Nouvel ordre.
    """

    name: str | None = None
    code: str | None = None
    aliases: list[str] | None = None
    order: int | None = None


class CacheSize(MongoBaseModel, CacheSizeBase):
    """Document Mongo d’une taille de cache (référentiel).

    Description:
        Étend `CacheSizeBase` avec _id, created_at, updated_at.
    """

    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: dt.datetime | None = None
