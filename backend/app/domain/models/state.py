# backend/app/models/state.py
# Reference data for states/regions, linked to a country. A "région" in France; a "state" in the USA.

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.core.bson_utils import MongoBaseModel, PyObjectId
from app.core.utils import now


class StateBase(BaseModel):
    """Base state/region fields.

    Attributes:
        name (str): State/region name.
        code (str | None): Short code (e.g. INSEE code / abbreviation).
        country_id (PyObjectId): Reference to `Country`.
    """

    name: str
    code: str | None = None  # e.g. INSEE code / abbreviation
    country_id: PyObjectId  # ref -> Country


class StateCreate(StateBase):
    """State/region creation payload."""

    pass


class StateUpdate(BaseModel):
    """State/region update payload.

    Attributes:
        name (str | None): New name.
        code (str | None): New code.
        country_id (PyObjectId | None): New referenced country.
    """

    name: str | None = None
    code: str | None = None
    country_id: PyObjectId | None = None


class State(MongoBaseModel, StateBase):
    """State/region Mongo document.

    Description:
        Extends `StateBase` with audit fields (`_id`, `created_at`, `updated_at`).
    """

    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: dt.datetime | None = None
