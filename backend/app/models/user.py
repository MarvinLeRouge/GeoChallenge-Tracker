from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime
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

class UserCreate(UserBase):
    password: str  # plain password received from client

class UserUpdate(BaseModel):
    email: Optional[EmailStr]
    password: Optional[str]
    preferences: Optional[Preferences]

class User(UserBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    challenges: Optional[List[PyObjectId]] = []

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {PyObjectId: str}

