# backend/app/models/country.py
# Référentiel minimal des pays (nom + code ISO).

from pydantic import BaseModel, Field
from typing import Optional
import datetime as dt
from app.core.utils import *
from app.core.bson_utils import *

class CountryBase(BaseModel):
    """Pays (référentiel).

    Attributes:
        name (str): Nom (ex. "France").
        code (str | None): Code ISO 3166-1 alpha-2 (ex. "FR").
    """
    name: str                      # ex: "France"
    code: Optional[str] = None     # ex: "FR", "DE", ISO 3166-1 alpha-2

class CountryCreate(CountryBase):
    """Payload de création d’un pays (référentiel)."""
    pass

class CountryUpdate(BaseModel):
    """Payload de mise à jour d’un pays.

    Attributes:
        name (str | None): Nouveau nom.
        code (str | None): Nouveau code.
    """
    name: Optional[str]
    code: Optional[str]

class Country(MongoBaseModel, CountryBase):
    """Document Mongo d’un pays (référentiel).

    Description:
        Étend `CountryBase` avec _id, created_at, updated_at.
    """
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None
