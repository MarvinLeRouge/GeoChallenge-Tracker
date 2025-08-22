# backend/app/models/user.py

from __future__ import annotations
from typing import Optional, List
import datetime as dt
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from app.core.utils import *
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
    preferences: Optional[Preferences] = Field(default_factory=Preferences)

class UserCreate(UserBase):
    password: str  # plain password received from client

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    preferences: Optional[Preferences] = None

class User(MongoBaseModel, UserBase):
    # Document persisted in MongoDB
    challenges: List[PyObjectId] = Field(default_factory=list)
    verification_code: Optional[str] = None
    verification_expires_at: Optional[dt.datetime] = None

    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None

# Input/Output DTOs

class UserInRegister(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(min_length=8)

class UserInLogin(BaseModel):
    identifier: str  # email ou username
    password: str

class UserOut(BaseModel):
    id: PyObjectId = Field(alias="_id")
    email: EmailStr
    username: str
    role: Optional[str] = "user"

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class ResendVerificationRequest(BaseModel):
    identifier: str  # email ou username
