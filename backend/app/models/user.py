from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
import datetime as dt
from app.core.bson_utils import *

class Preferences(BaseModel):
    language: Optional[str] = "fr"
    dark_mode: Optional[bool] = False

class UserBase(BaseModel):
    username: str
    email: EmailStr
    role: str = "user"
    is_active: bool = True
    is_verified: bool = False
    preferences: Optional[Preferences] = Preferences()
    model_config = {
        "populate_by_name": True
    }

class UserCreate(UserBase):
    password: str  # plain password received from client

class UserUpdate(BaseModel):
    email: Optional[EmailStr]
    password: Optional[str]
    preferences: Optional[Preferences]

class User(UserBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    updated_at: Optional[dt.datetime] = None
    challenges: Optional[List[PyObjectId]] = []

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}

