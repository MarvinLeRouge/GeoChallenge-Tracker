# backend/auth – app/api/routes/auth.py

from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
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
    # dependency callable that returns the users collection
    return get_collection("users")


class MessageOut(BaseModel):
    message: str = Field(..., examples=["OK"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserInRegister, users: Collection = Depends(users_coll)):
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


@router.post("/login", response_model=TokenPair)
def login(form_data: OAuth2PasswordRequestForm = Depends(), users: Collection = Depends(users_coll)):
    ident = (form_data.username or "").strip()
    user = users.find_one(
        {"$or": [{"email": ident}, {"username": ident}]},
        collation=COLLATION_CI,
    )
    if user is None or not verify_password(form_data.password, user.get("password_hash", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.get("is_verified", False):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unverified user")

    sub = str(user["_id"])
    access_token = create_access_token(data={"sub": sub})
    refresh_token = create_refresh_token(data={"sub": sub})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@router.post("/token", response_model=TokenResponse)
def refresh_token(payload: RefreshTokenRequest, users: Collection = Depends(users_coll)):
    try:
        data = jwt.decode(payload.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
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
    import secrets
    return secrets.token_urlsafe(24)


@router.get("/verify-email", response_model=MessageOut)
def verify_email(code: str, users: Collection = Depends(users_coll)):
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


@router.post("/verify-email", response_model=MessageOut)
def verify_email_post(body: VerifyEmailBody, users: Collection = Depends(users_coll)):
    return verify_email(code=body.code, users=users)


@router.post("/resend-verification", response_model=MessageOut)
def resend_verification(body: ResendVerificationRequest, users: Collection = Depends(users_coll)):
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
