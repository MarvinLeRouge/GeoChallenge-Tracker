# backend/app/models/cache_attribute.py
# Reference data describing possible cache attributes (code, labels, aliases).

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.core.bson_utils import MongoBaseModel
from app.core.utils import now


class CacheAttributeBase(BaseModel):
    """Cache attribute (reference data).

    Description:
        Defines the global attribute ID, its text identifier, labels and aliases.

    Attributes:
        cache_attribute_id (int): Global numeric identifier (e.g. 14).
        txt (str): Text identifier (e.g. "dogs_allowed").
        name (str): Main label (e.g. "Dogs allowed").
        name_reverse (str | None): Reverse label (e.g. "No dogs allowed").
        aliases (list[str]): Synonyms/variants.
    """

    cache_attribute_id: int  # global identifier, e.g. 14
    txt: str  # text identifier (e.g. dogs_allowed)
    name: str  # main label ("Dogs allowed")
    name_reverse: str | None = None  # reverse label ("No dogs allowed")
    aliases: list[str] = Field(default_factory=list)


class CacheAttributeCreate(CacheAttributeBase):
    """Cache attribute creation payload.

    Description:
        Identical to `CacheAttributeBase` for insertion into the reference data.
    """

    pass


class CacheAttributeUpdate(BaseModel):
    """Cache attribute update payload.

    Description:
        Partial update of reference data fields.

    Attributes:
        cache_attribute_id (int | None): New global ID.
        name (str | None): New label.
        name_reverse (str | None): New reverse label.
        aliases (list[str] | None): New aliases.
    """

    cache_attribute_id: int | None = None
    name: str | None = None
    name_reverse: str | None = None
    aliases: list[str] | None = None


class CacheAttribute(MongoBaseModel, CacheAttributeBase):
    """Cache attribute Mongo document (reference data).

    Description:
        Extends `CacheAttributeBase` with _id, created_at, updated_at.
    """

    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: dt.datetime | None = None
