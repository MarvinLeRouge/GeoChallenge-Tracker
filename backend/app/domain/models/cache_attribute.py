# backend/app/models/cache_attribute.py
# Référentiel décrivant les attributs possibles d’une cache (code, libellés, alias).

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.core.bson_utils import MongoBaseModel
from app.core.utils import now


class CacheAttributeBase(BaseModel):
    """Attribut de cache (référentiel).

    Description:
        Définit l’ID global d’attribut, son identifiant texte, les libellés et alias.

    Attributes:
        cache_attribute_id (int): Identifiant numérique global (ex. 14).
        txt (str): Identifiant texte (ex. "dogs_allowed").
        name (str): Libellé principal (ex. "Dogs allowed").
        name_reverse (str | None): Libellé inverse (ex. "No dogs allowed").
        aliases (list[str]): Synonymes/variantes.
    """

    cache_attribute_id: int  # identifiant global, ex. 14
    txt: str  # identifiant txt (ex.: dogs_allowed)
    name: str  # libellé principal ("Dogs allowed")
    name_reverse: str | None = None  # libellé inverse ("No dogs allowed")
    aliases: list[str] = Field(default_factory=list)


class CacheAttributeCreate(CacheAttributeBase):
    """Payload de création d’un attribut de cache.

    Description:
        Identique à `CacheAttributeBase` pour insertion dans le référentiel.
    """

    pass


class CacheAttributeUpdate(BaseModel):
    """Payload de mise à jour d’un attribut.

    Description:
        Mise à jour partielle des champs du référentiel.

    Attributes:
        cache_attribute_id (int | None): Nouvel ID global.
        name (str | None): Nouveau libellé.
        name_reverse (str | None): Nouveau libellé inverse.
        aliases (list[str] | None): Nouveaux alias.
    """

    cache_attribute_id: int | None = None
    name: str | None = None
    name_reverse: str | None = None
    aliases: list[str] | None = None


class CacheAttribute(MongoBaseModel, CacheAttributeBase):
    """Document Mongo d’un attribut de cache (référentiel).

    Description:
        Étend `CacheAttributeBase` avec les champs _id, created_at, updated_at.
    """

    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: dt.datetime | None = None
