# backend/app/api/models/user.py

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
import datetime as dt
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
    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: Optional[dt.datetime] = None
    challenges: Optional[List[PyObjectId]] = []
    verification_code: Optional[str] = None
    verification_expires_at: Optional[dt.datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}


class UserInRegister(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(min_length=8)

class UserInLogin(BaseModel):
    identifier: str  # Peut être un email OU un username
    password: str

class UserOut(BaseModel):
    id: str = Field(alias="_id")
    email: EmailStr
    username: str
    role: Optional[str] = "user"

    model_config = {
        "populate_by_name": True,  # pour autoriser _id → id
        "json_encoders": {
            ObjectId: str
        }
    }

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