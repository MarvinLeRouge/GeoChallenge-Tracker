# backend/app/models/country.py
# Minimal country reference data (name + ISO code).

import datetime as dt

from pydantic import BaseModel, Field

from app.core.bson_utils import MongoBaseModel
from app.core.utils import now


class CountryBase(BaseModel):
    """Country (reference data).

    Attributes:
        name (str): Name (e.g. "France").
        code (str | None): ISO 3166-1 alpha-2 code (e.g. "FR").
    """

    name: str  # e.g. "France"
    code: str | None = None  # e.g. "FR", "DE", ISO 3166-1 alpha-2


class CountryCreate(CountryBase):
    """Country creation payload (reference data)."""

    pass


class CountryUpdate(BaseModel):
    """Country update payload.

    Attributes:
        name (str | None): New name.
        code (str | None): New code.
    """

    name: str | None
    code: str | None


class Country(MongoBaseModel, CountryBase):
    """Country Mongo document (reference data).

    Description:
        Extends `CountryBase` with _id, created_at, updated_at.
    """

    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: dt.datetime | None = None
