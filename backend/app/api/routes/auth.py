# backend/app/api/routes/auth.py
# Routes d'authentification et gestion des utilisateurs :
# - Inscription, login, refresh token
# - Vérification d'email et renvoi de code
# - Utilise JWT et envoie d'email de confirmation

from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Body, Query, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt, JWTError
from pydantic import BaseModel, Field
from pymongo.collection import Collection
from pymongo.collation import Collation

from app.core.settings import settings
from app.core.security import (
    verify_password,
    hash_password,
    validate_password_strength,
    create_access_token,
    create_refresh_token,
)
from app.core.email import send_verification_email
from app.core.utils import now
from app.core.bson_utils import PyObjectId
from app.db.mongodb import get_collection
from app.models.user import (
    UserOut,
    UserInRegister,
    RefreshTokenRequest,
    ResendVerificationRequest,
    TokenPair,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Case-insensitive collation (case-insensitive, accent-sensitive)
COLLATION_CI = Collation(locale="en", strength=2)

def users_coll() -> Collection:
    """Retourne la collection MongoDB `users`."""
    return get_collection("users")


class MessageOut(BaseModel):
    message: str = Field(..., examples=["OK"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Inscription d’un nouvel utilisateur",
    description=(
        "Crée un compte utilisateur avec email et username uniques.\n\n"
        "- Vérifie la force du mot de passe\n"
        "- Hash le mot de passe\n"
        "- Envoie un email avec un code de vérification (24h)\n"
        "- Retourne les informations publiques du compte créé"
    ),
)
def register(
    payload: UserInRegister = Body(..., description="Données d'inscription : username, email et mot de passe."),
    users: Collection = Depends(users_coll),
):
    """Inscription d’un utilisateur.

    Description:
        Enregistre un nouvel utilisateur après validation de la force du mot de passe et unicité (email/username).
        Génère un code de vérification et envoie un email. Le compte est créé non vérifié.

    Args:
        payload (UserInRegister): Données d'inscription (username, email, password).
        users (Collection): Collection MongoDB des utilisateurs.

    Returns:
        UserOut: Données publiques de l’utilisateur (id, username, email, role).
    """

    username = (payload.username or "").strip()
    email = (payload.email or "").strip()

    if not validate_password_strength(payload.password):
        raise HTTPException(status_code=400, detail="Password too weak")

    # Unicité insensible à la casse (sans champs *_lower)
    existing = users.find_one(
        {"$or": [{"username": username}, {"email": email}]},
        collation=COLLATION_CI,
        projection={"_id": 1},
    )
    if existing:
        raise HTTPException(status_code=409, detail="Username or email already used")

    verification_code = create_verification_code()
    doc = {
        "username": username,
        "email": email,
        "role": "user",
        "is_active": True,
        "is_verified": False,
        "preferences": {"language": "fr", "dark_mode": False},
        "password_hash": hash_password(payload.password),
        "verification_code": verification_code,
        "verification_expires_at": now() + dt.timedelta(hours=24),
        "created_at": now(),
        "updated_at": None,
    }
    res = users.insert_one(doc)

    try:
        send_verification_email(email=email, code=verification_code)
    except Exception:
        pass

    created = users.find_one({"_id": res.inserted_id}, {"_id": 1, "email": 1, "username": 1, "role": 1})
    return {
        "_id": created["_id"],
        "email": created["email"],
        "username": created["username"],
        "role": created.get("role", "user"),
    }


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Connexion d’un utilisateur",
    description=(
        "Authentifie via formulaire OAuth2 **ou** JSON (username/email + password).\n\n"
        "- Retourne un couple de jetons (access + refresh)\n"
        "- Le compte doit être vérifié\n"
        "- 401 si identifiants invalides ou compte non vérifié"
    ),
)
async def login(
    request: Request,
    users: Collection = Depends(users_coll),
):
    """Connexion utilisateur.

    Description:
        Authentifie l’utilisateur avec identifiant (username/email) et mot de passe, puis génère un access token
        et un refresh token JWT. Accepte `application/x-www-form-urlencoded`, `multipart/form-data` et JSON.

    Args:
        request (Request): Requête HTTP (support JSON ou formulaire).
        users (Collection): Collection MongoDB des utilisateurs.

    Returns:
        TokenPair: Contenant access_token, refresh_token et token_type.
    """
    # Accepte form-data OAuth2 (Swagger) OU JSON {identifier|username|email, password}
    ctype = request.headers.get("content-type", "")
    ident = ""
    password = ""

    if "application/x-www-form-urlencoded" in ctype or "multipart/form-data" in ctype:
        form = await request.form()
        ident = (form.get("username") or form.get("identifier") or "").strip()
        password = form.get("password") or ""
    else:
        try:
            body = await request.json()
        except Exception:
            body = {}
        ident = (body.get("identifier") or body.get("username") or body.get("email") or "").strip()
        password = body.get("password") or ""

    if not ident or not password:
        raise HTTPException(status_code=422, detail="Missing credentials")

    user = users.find_one(
        {"$or": [{"email": ident}, {"username": ident}]},
        collation=COLLATION_CI,
    )
    if user is None or not verify_password(password, user.get("password_hash", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.get("is_verified", False):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unverified user")

    sub = str(user["_id"])
    access_token = create_access_token(data={"sub": sub})
    refresh_token = create_refresh_token(data={"sub": sub})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renouvellement du token d’accès",
    description=(
        "Génère un nouveau token d’accès à partir d’un refresh token valide.\n\n"
        "- Vérifie la validité du refresh token\n"
        "- Vérifie que l’utilisateur est actif\n"
        "- Retourne un nouvel access token"
    ),
)
def refresh_token(
    payload: RefreshTokenRequest = Body(..., description="Refresh token JWT valide."),
    users: Collection = Depends(users_coll),
):
    """Rafraîchissement du token d’accès.

    Description:
        Décode un refresh token JWT valide, contrôle l’existence et l’état de l’utilisateur,
        puis génère un nouvel access token.

    Args:
        payload (RefreshTokenRequest): Refresh token à valider.
        users (Collection): Collection MongoDB des utilisateurs.

    Returns:
        TokenResponse: Nouveau jeton d’accès.
    """
    try:
        data = jwt.decode(payload.refresh_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        sub = data.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = users.find_one({"_id": PyObjectId(sub)}, {"_id": 1, "is_active": 1})
    if not user or not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    access_token = create_access_token(data={"sub": str(user["_id"])})
    return {"access_token": access_token, "token_type": "bearer"}


class VerifyEmailBody(BaseModel):
    code: str


def create_verification_code() -> str:
    """Crée un code de vérification aléatoire et unique."""
    import secrets
    return secrets.token_urlsafe(24)


@router.get(
    "/verify-email",
    response_model=MessageOut,
    summary="Vérification d’email par code",
    description=(
        "Vérifie un code de confirmation reçu par email.\n\n"
        "- Active l’utilisateur si code valide et non expiré\n"
        "- Supprime le code et son expiration\n"
        "- Retourne un message de confirmation"
    ),
)
def verify_email(
    code: str = Query(..., description="Code de vérification reçu par email, valide 24h."),
    users: Collection = Depends(users_coll),
):
    """Vérification email.

    Description:
        Vérifie que le code fourni correspond à un compte en attente de vérification et non expiré,
        puis active définitivement l’utilisateur.

    Args:
        code (str): Code de vérification envoyé par email.
        users (Collection): Collection MongoDB des utilisateurs.

    Returns:
        MessageOut: Message confirmant la vérification.
    """
    now_ts = now()
    user = users.find_one(
        {"verification_code": code, "verification_expires_at": {"$gte": now_ts}},
        projection={"_id": 1},
    )
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    users.update_one(
        {"_id": user["_id"]},
        {"$set": {"is_verified": True, "updated_at": now()}, "$unset": {"verification_code": "", "verification_expires_at": ""}}
    )
    return {"message": "Email verified"}


@router.post(
    "/verify-email",
    response_model=MessageOut,
    summary="Vérification d’email via POST",
    description="Alternative POST pour transmettre le code de vérification dans le corps JSON.",
)
def verify_email_post(
    body: VerifyEmailBody = Body(..., description="Objet contenant le code de vérification."),
    users: Collection = Depends(users_coll),
):
    """Vérification email (POST).

    Description:
        Identique à la version GET mais reçoit le code dans un body JSON.

    Args:
        body (VerifyEmailBody): Objet contenant le code de vérification.
        users (Collection): Collection MongoDB des utilisateurs.

    Returns:
        MessageOut: Message confirmant la vérification.
    """
    return verify_email(code=body.code, users=users)


@router.post(
    "/resend-verification",
    response_model=MessageOut,
    summary="Renvoi du code de vérification",
    description=(
        "Régénère et renvoie un email de vérification si le compte existe et n’est pas encore activé.\n\n"
        "- Ne révèle pas si le compte existe réellement\n"
        "- Met à jour l’expiration du code (24h)"
    ),
)
def resend_verification(
    body: ResendVerificationRequest = Body(..., description="Identifiant (username ou email) de l’utilisateur."),
    users: Collection = Depends(users_coll),
):
    """Renvoi d’email de vérification.

    Description:
        Génère et envoie un nouveau code de vérification pour l’utilisateur identifié (username/email),
        si son compte n’est pas encore vérifié.

    Args:
        body (ResendVerificationRequest): Identifiant (username ou email).
        users (Collection): Collection MongoDB des utilisateurs.

    Returns:
        MessageOut: Message de confirmation (sans divulguer l’existence du compte).
    """
    ident = (body.identifier or "").strip()
    user = users.find_one(
        {"$or": [{"email": ident}, {"username": ident}]},
        collation=COLLATION_CI,
        projection={"_id": 1, "email": 1, "is_verified": 1},
    )
    if user and not user.get("is_verified", False):
        code = create_verification_code()
        users.update_one(
            {"_id": user["_id"]},
            {"$set": {"verification_code": code, "verification_expires_at": now() + dt.timedelta(hours=24), "updated_at": now()}}
        )
        try:
            send_verification_email(email=user["email"], code=code)
        except Exception:
            pass
    return {"message": "If the account exists and is not verified, a new email was sent."}
