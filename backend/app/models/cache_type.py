# backend/app/models/cache_type.py
# Référentiel listant les types (Traditional, Mystery, Event, …) et leurs alias.

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.core.bson_utils import MongoBaseModel
from app.core.utils import now


class CacheTypeBase(BaseModel):
    """Type de cache (référentiel).

    Description:
        Nom, code et alias associés à un type de géocache.

    Attributes:
        name (str): Libellé (ex. "Traditional").
        code (str | None): Abréviation (ex. "TR").
        aliases (list[str]): Alias reconnus pour ce type.
    """

    name: str  # ex: "Traditional", "Mystery", etc.
    code: str | None = None  # abréviation, ex: "TR", "MY", "EV"
    aliases: list[str] = Field(default_factory=list)


class CacheTypeCreate(CacheTypeBase):
    """Payload de création d’un type de cache.

    Description:
        Identique à `CacheTypeBase` pour insertion dans le référentiel.
    """

    pass


class CacheTypeUpdate(BaseModel):
    """Payload de mise à jour d’un type de cache.

    Description:
        Mise à jour partielle des champs.

    Attributes:
        name (str | None): Nouveau libellé.
        code (str | None): Nouvelle abréviation.
        aliases (list[str] | None): Nouveaux alias.
    """

    name: str | None = None
    code: str | None = None
    aliases: list[str] | None = None


class CacheType(MongoBaseModel, CacheTypeBase):
    """Document Mongo d’un type de cache (référentiel).

    Description:
        Étend `CacheTypeBase` avec _id, created_at, updated_at.
    """

    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: dt.datetime | None = None
