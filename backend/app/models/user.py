# backend/app/models/user.py
# Schémas utilisateur : document Mongo, payloads d’inscription/login, sorties publiques et tokens.

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.bson_utils import MongoBaseModel, PyObjectId
from app.core.utils import now, utcnow


class UserLocation(BaseModel):
    """Localisation utilisateur.

    Attributes:
        lon (float): Longitude.
        lat (float): Latitude.
        updated_at (datetime): Horodatage de mise à jour (UTC).
    """

    lon: float
    lat: float
    updated_at: dt.datetime = Field(default_factory=lambda: utcnow())


class Preferences(BaseModel):
    """Préférences utilisateur.

    Attributes:
        language (str | None): Langue (ex. 'fr').
        dark_mode (bool | None): Thème sombre.
    """

    language: str | None = "fr"
    dark_mode: bool | None = False


class UserBase(BaseModel):
    """Champs communs utilisateur.

    Attributes:
        username (str): Pseudo unique.
        email (EmailStr): Email unique.
        role (str): Rôle ('user' par défaut).
        is_active (bool): Compte actif.
        is_verified (bool): Email vérifié.
        preferences (Preferences | None): Préférences UI.
    """

    username: str
    email: EmailStr
    role: str = "user"
    is_active: bool = True
    is_verified: bool = False
    preferences: Preferences | None = Field(default_factory=Preferences)


class UserCreate(UserBase):
    """Payload de création (inscription).

    Attributes:
        password (str): Mot de passe en clair reçu côté client.
    """

    password: str  # plain password received from client


class UserUpdate(BaseModel):
    """Payload de mise à jour utilisateur.

    Attributes:
        email (EmailStr | None): Nouvel email.
        password (str | None): Nouveau mot de passe (en clair).
        preferences (Preferences | None): Nouvelles préférences.
    """

    email: EmailStr | None = None
    password: str | None = None
    preferences: Preferences | None = None


class User(MongoBaseModel, UserBase):
    """Document Mongo utilisateur.

    Attributes:
        challenges (list[PyObjectId]): UC associés.
        verification_code (str | None): Code email.
        verification_expires_at (datetime | None): Expiration code.
        location (UserLocation | None): Dernière localisation.
        created_at (datetime): Création (local).
        updated_at (datetime | None): MAJ.
    """

    challenges: list[PyObjectId] = Field(default_factory=list)
    verification_code: str | None = None
    verification_expires_at: dt.datetime | None = None
    location: UserLocation | None = None

    created_at: dt.datetime = Field(default_factory=lambda: now())
    updated_at: dt.datetime | None = None


# Input/Output DTOs


class UserInRegister(BaseModel):
    """Entrée d’inscription.

    Attributes:
        username (str): 3–30 caractères.
        email (EmailStr): Email valide.
        password (str): ≥ 8 caractères.
    """

    username: str = Field(min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(min_length=8)


class UserInLogin(BaseModel):
    """Entrée de login.

    Attributes:
        identifier (str): Email ou username.
        password (str): Mot de passe.
    """

    identifier: str  # email ou username
    password: str


class UserOut(BaseModel):
    """Sortie publique utilisateur.

    Attributes:
        id (PyObjectId): Alias `_id`.
        email (EmailStr): Email.
        username (str): Pseudo.
        role (str | None): Rôle.
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
    """Couple de jetons JWT.

    Attributes:
        access_token (str): Jeton d’accès.
        refresh_token (str): Jeton de refresh.
        token_type (str): 'bearer'.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenResponse(BaseModel):
    """Réponse avec jeton d’accès.

    Attributes:
        access_token (str): Jeton d’accès.
        token_type (str): 'bearer'.
    """

    access_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Entrée de refresh token.

    Attributes:
        refresh_token (str): Jeton de refresh JWT.
    """

    refresh_token: str


class ResendVerificationRequest(BaseModel):
    """Entrée de renvoi de vérification email.

    Attributes:
        identifier (str): Email ou username.
    """

    identifier: str  # email ou username
