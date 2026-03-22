# backend/app/models/cache_type.py
# Reference list of cache types (Traditional, Mystery, Event, …) and their aliases.

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.core.bson_utils import MongoBaseModel
from app.core.utils import now


class CacheTypeBase(BaseModel):
    """Cache type (reference data).

    Description:
        Name, code and aliases associated with a geocache type.

    Attributes:
        name (str): Label (e.g. "Traditional").
        code (str | None): Abbreviation (e.g. "TR").
        aliases (list[str]): Recognized aliases for this type.
    """

    name: str  # e.g. "Traditional", "Mystery", etc.
    code: str | None = None  # abbreviation, e.g. "TR", "MY", "EV"
    aliases: list[str] = Field(default_factory=list)


class CacheTypeCreate(CacheTypeBase):
    """Cache type creation payload.

    Description:
        Identical to `CacheTypeBase` for insertion into the reference data.
    """

    pass


class CacheTypeUpdate(BaseModel):
    """Cache type update payload.

    Description:
        Partial field update.

    Attributes:
        name (str | None): New label.
        code (str | None): New abbreviation.
        aliases (list[str] | None): New aliases.
    """

    name: str | None = None
    code: str | None = None
    aliases: list[str] | None = None


class CacheType(MongoBaseModel, CacheTypeBase):
    """Cache type Mongo document (reference data).

    Description:
        Extends `CacheTypeBase` with _id, created_at, updated_at.
    """

    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: dt.datetime | None = None
