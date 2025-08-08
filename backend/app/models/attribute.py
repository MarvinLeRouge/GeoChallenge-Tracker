# backend/app/api/models/attribute.py

from pydantic import BaseModel, Field
from typing import Optional
import datetime as dt
from app.core.utils import *
from app.core.bson_utils import *

class AttributeBase(BaseModel):
    name: str                        # libellé principal ("Dogs allowed")
    name_reverse: Optional[str] = None  # libellé inverse ("No dogs allowed")
    attr_id: int                     # identifiant global, ex. 14
    is_reverse: bool = False         # forme inversée ?

class AttributeCreate(AttributeBase):
    pass

class AttributeUpdate(BaseModel):
    name: Optional[str]
    name_reverse: Optional[str]
    attr_id: Optional[int]
    is_reverse: Optional[bool]

class Attribute(AttributeBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}
