# backend/app/models/state.py
# Référentiel d’états/régions, relié à un pays. En France, une "région" ; aux USA, un "état"

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.core.bson_utils import MongoBaseModel, PyObjectId
from app.core.utils import now


class StateBase(BaseModel):
    """Champs de base d’un État/région.

    Attributes:
        name (str): Nom de l’État/région.
        code (str | None): Code court (ex. INSEE / abréviation).
        country_id (PyObjectId): Référence vers `Country`.
    """

    name: str
    code: str | None = None  # ex: code INSEE / abbr
    country_id: PyObjectId  # ref -> Country


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

    name: str | None = None
    code: str | None = None
    country_id: PyObjectId | None = None


class State(MongoBaseModel, StateBase):
    """Document Mongo d’un État/région.

    Description:
        Étend `StateBase` avec les champs de traçabilité (`_id`, `created_at`, `updated_at`).
    """

    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: dt.datetime | None = None
