# backend/app/models/user.py
# User schemas: Mongo document, registration/login payloads, public outputs and tokens.

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.core.bson_utils import MongoBaseModel, PyObjectId
from app.core.utils import now, utcnow


class UserLocation(BaseModel):
    """User location.

    Attributes:
        lon (float): Longitude.
        lat (float): Latitude.
        updated_at (datetime): Update timestamp (UTC).
    """

    lon: float
    lat: float
    updated_at: dt.datetime = Field(default_factory=lambda: utcnow())


class Preferences(BaseModel):
    """User preferences.

    Attributes:
        language (str | None): Language (e.g. 'fr').
        dark_mode (bool | None): Dark theme.
    """

    language: str | None = "fr"
    dark_mode: bool | None = False


class UserBase(BaseModel):
    """Common user fields.

    Attributes:
        username (str): Unique username.
        email (EmailStr): Unique email.
        role (str): Role ('user' by default).
        is_active (bool): Account active.
        is_verified (bool): Email verified.
        preferences (Preferences | None): UI preferences.
    """

    username: str
    email: EmailStr
    role: str = "user"
    is_active: bool = True
    is_verified: bool = False
    preferences: Preferences | None = Field(default_factory=Preferences)


class UserCreate(UserBase):
    """Registration payload.

    Attributes:
        password (str): Plain-text password received from the client.
    """

    password: str  # plain password received from client


class UserUpdate(BaseModel):
    """User update payload.

    Attributes:
        email (EmailStr | None): New email.
        password (str | None): New password (plain text).
        preferences (Preferences | None): New preferences.
    """

    email: EmailStr | None = None
    password: str | None = None
    preferences: Preferences | None = None


class User(MongoBaseModel, UserBase):
    """User Mongo document.

    Attributes:
        challenges (list[PyObjectId]): Associated UserChallenges.
        verification_code (str | None): Email verification code.
        verification_expires_at (datetime | None): Code expiration.
        location (UserLocation | None): Last known location.
        created_at (datetime): Creation time (local).
        updated_at (datetime | None): Last update.
    """

    challenges: list[PyObjectId] = Field(default_factory=list)
    verification_code: str | None = None
    verification_expires_at: dt.datetime | None = None
    location: UserLocation | None = None

    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: dt.datetime | None = None

    # --- Input normalization ---
    # If the DB provides location as a GeoJSON Point, convert it to the expected UserLocation.
    @model_validator(mode="before")
    @classmethod
    def _normalize_geojson_location(cls, data: dict):
        if not isinstance(data, dict):
            return data
        loc = data.get("location")
        if isinstance(loc, dict) and loc.get("type") == "Point":
            coords = loc.get("coordinates") or []
            if len(coords) >= 2:
                lon, lat = coords[0], coords[1]
                # Preserve any updated_at field present in the DB object
                ua = loc.get("updated_at")
                data["location"] = {
                    "lon": float(lon),
                    "lat": float(lat),
                    **({"updated_at": ua} if ua else {}),
                }
        return data


# Input/Output DTOs


class UserInRegister(BaseModel):
    """Registration input.

    Attributes:
        username (str): 3–30 characters.
        email (EmailStr): Valid email.
        password (str): ≥ 8 characters.
    """

    username: str = Field(min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(min_length=8)


class UserInLogin(BaseModel):
    """Login input.

    Attributes:
        identifier (str): Email or username.
        password (str): Password.
    """

    identifier: str  # email or username
    password: str


class UserOut(BaseModel):
    """Public user output.

    Attributes:
        id (PyObjectId): Alias for `_id`.
        email (EmailStr): Email.
        username (str): Username.
        role (str | None): Role.
    """

    id: PyObjectId = Field(alias="_id")
    email: EmailStr
    username: str
    role: str | None = "user"

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )


class TokenPair(BaseModel):
    """JWT token pair.

    Attributes:
        access_token (str): Access token.
        refresh_token (str): Refresh token.
        token_type (str): ‘bearer’.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenResponse(BaseModel):
    """Access token response.

    Attributes:
        access_token (str): Access token.
        token_type (str): ‘bearer’.
    """

    access_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Refresh token input.

    Attributes:
        refresh_token (str): JWT refresh token.
    """

    refresh_token: str


class ResendVerificationRequest(BaseModel):
    """Email verification resend input.

    Attributes:
        identifier (str): Email or username.
    """

    identifier: str  # email or username
