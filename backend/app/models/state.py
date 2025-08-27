# backend/app/models/state.py
# Référentiel d’états/régions, relié à un pays. En France, une "région" ; aux USA, un "état"

from __future__ import annotations
from typing import Optional
import datetime as dt
from pydantic import BaseModel, Field
from app.core.utils import *
from app.core.bson_utils import *

class StateBase(BaseModel):
    """Champs de base d’un État/région.

    Attributes:
        name (str): Nom de l’État/région.
        code (str | None): Code court (ex. INSEE / abréviation).
        country_id (PyObjectId): Référence vers `Country`.
    """
    name: str
    code: Optional[str] = None        # ex: code INSEE / abbr
    country_id: PyObjectId            # ref -> Country

class StateCreate(StateBase):
    """Payload de création d’un État/région."""
    pass

class StateUpdate(BaseModel):
    """Payload de mise à jour d’un État/région.

    Attributes:
        name (str | None): Nouveau nom.
        code (str | None): Nouveau code.
        country_id (PyObjectId | None): Nouveau pays référencé.
    """
    name: Optional[str] = None
    code: Optional[str] = None
    country_id: Optional[PyObjectId] = None

class State(MongoBaseModel, StateBase):
    """Document Mongo d’un État/région.

    Description:
        Étend `StateBase` avec les champs de traçabilité (`_id`, `created_at`, `updated_at`).
    """
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None
