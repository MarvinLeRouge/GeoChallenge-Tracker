# backend/app/models/found_cache.py
# Association (user, cache) avec date de trouvaille et notes facultatives.

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.core.bson_utils import MongoBaseModel, PyObjectId
from app.core.utils import now


class FoundCacheBase(BaseModel):
    """Trouvaille de cache par un utilisateur.

    Attributes:
        user_id (PyObjectId): Réf. `users._id`.
        cache_id (PyObjectId): Réf. `caches._id`.
        found_date (date): Date (jour) du log.
        notes (str | None): Notes facultatives.
    """

    user_id: PyObjectId  # référence à users._id
    cache_id: PyObjectId  # référence à caches._id
    found_date: dt.date  # date de log (jour précis)
    notes: str | None = None


class FoundCacheCreate(FoundCacheBase):
    """Payload de création d’une trouvaille."""

    pass


class FoundCacheUpdate(BaseModel):
    """Payload de mise à jour d’une trouvaille.

    Attributes:
        notes (str | None): Nouvelles notes.
    """

    notes: str | None = None


class FoundCache(MongoBaseModel, FoundCacheBase):
    """Document Mongo d’une trouvaille.

    Description:
        Étend `FoundCacheBase` avec _id, created_at, updated_at.
    """

    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: dt.datetime | None = None
