# backend/app/api/routes/auth.py
# Authentication and user management routes:
# - Registration, login, token refresh
# - Email verification and code resend
# - Uses JWT and sends confirmation emails

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Cookie,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorCollection
from pydantic import BaseModel, Field
from pymongo.collation import Collation

from app.api.dto.user_profile import VerifyEmailBody
from app.core.bson_utils import PyObjectId
from app.core.email import send_verification_email
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.core.settings import get_settings
from app.core.utils import now
from app.db.mongodb import get_collection
from app.domain.models.user import (
    ResendVerificationRequest,
    TokenResponse,
    UserInRegister,
    UserOut,
)

settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Auth"])

# Case-insensitive collation (case-insensitive, accent-sensitive)
COLLATION_CI = Collation(locale="en", strength=2)


def create_verification_code() -> str:
    """Creates a random, unique verification code."""
    import secrets

    return secrets.token_urlsafe(24)


async def users_coll() -> AsyncIOMotorCollection:
    """Returns the MongoDB `users` collection."""
    return await get_collection("users")


class MessageOut(BaseModel):
    message: str = Field(..., examples=["OK"])


# DONE: [BACKLOG] Route /auth/register (POST) verified
@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description=(
        "Creates a user account with a unique email and username.\n\n"
        "- Validates password strength\n"
        "- Hashes the password\n"
        "- Sends a verification email with a code (valid 24h)\n"
        "- Returns the public information of the created account"
    ),
)
async def register(
    payload: Annotated[
        UserInRegister,
        Body(..., description="Registration data: username, email, and password."),
    ],
    users: Annotated[AsyncIOMotorCollection, Depends(users_coll)],
    background_tasks: BackgroundTasks,
):
    """Registers a user.

    Description:
        Creates a new user after validating password strength and uniqueness (email/username).
        Generates a verification code and sends an email. The account is created unverified.

    Args:
        payload (UserInRegister): Registration data (username, email, password).
        users (AsyncIOMotorCollection): MongoDB users collection.

    Returns:
        UserOut: Public user data (id, username, email, role).
    """

    username = (payload.username or "").strip()
    email = (payload.email or "").strip()

    is_valid, error_msg = validate_password_strength(payload.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # Case-insensitive uniqueness check (without *_lower fields)
    existing = await users.find_one(
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
    res = await users.insert_one(doc)

    if background_tasks:
        background_tasks.add_task(
            send_verification_email,
            to_email=email,
            username=username,
            code=verification_code,
        )

    created = await users.find_one(
        {"_id": res.inserted_id}, {"_id": 1, "email": 1, "username": 1, "role": 1}
    )

    if created is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve created user")

    return {
        "_id": created["_id"],
        "email": created["email"],
        "username": created["username"],
        "role": created.get("role", "user"),
    }


# DONE: [BACKLOG] Route /auth/login (POST) verified
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in a user",
    description=(
        "Authenticates via OAuth2 form **or** JSON (username/email + password).\n\n"
        "- Returns an access token in the JSON response\n"
        "- Sets the refresh token in an HttpOnly cookie (7 days)\n"
        "- The account must be verified\n"
        "- 401 if credentials are invalid or account is unverified"
    ),
)
async def login(
    request: Request,
    response: Response,
    users: Annotated[AsyncIOMotorCollection, Depends(users_coll)],
):
    """Logs in a user.

    Description:
        Authenticates the user with an identifier (username/email) and password, then generates an access token
        and a JWT refresh token. Accepts `application/x-www-form-urlencoded`, `multipart/form-data`, and JSON.

    Args:
        request (Request): HTTP request (JSON or form support).
        users (AsyncIOMotorCollection): MongoDB users collection.

    Returns:
        TokenPair: Contains access_token, refresh_token, and token_type.
    """
    # Accept form-data OAuth2 (Swagger) OR JSON {identifier|username|email, password}
    ctype = request.headers.get("content-type", "")
    ident = ""
    password = ""

    if "application/x-www-form-urlencoded" in ctype or "multipart/form-data" in ctype:
        form = await request.form()
        # Safe extraction with type checking
        raw_ident = form.get("username") or form.get("identifier") or ""
        raw_password = form.get("password") or ""

        # Ensure we have strings, not UploadFile objects
        ident = raw_ident.strip() if isinstance(raw_ident, str) else ""
        password = raw_password if isinstance(raw_password, str) else ""
    else:
        try:
            body = await request.json()
        except Exception:
            body = {}
        ident = (body.get("identifier") or body.get("username") or body.get("email") or "").strip()
        password = body.get("password") or ""

    if not ident or not password:
        raise HTTPException(status_code=422, detail="Missing credentials")

    user = await users.find_one(
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
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        max_age=7 * 24 * 3600,
        path="/auth/refresh",
    )
    return {"access_token": access_token, "token_type": "bearer"}


# DONE: [BACKLOG] Route /auth/refresh (POST) verified
@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renew the access token",
    description=(
        "Generates a new access token from the refresh token (HttpOnly cookie).\n\n"
        "- Validates the refresh token\n"
        "- Checks that the user is active\n"
        "- Returns a new access token"
    ),
)
async def refresh_token(
    users: Annotated[AsyncIOMotorCollection, Depends(users_coll)],
    refresh_token: Annotated[str | None, Cookie()] = None,
):
    """Refreshes the access token.

    Description:
        Reads the refresh token from the HttpOnly cookie, checks the user’s existence and status,
        then generates a new access token.

    Args:
        users (AsyncIOMotorCollection): MongoDB users collection.
        refresh_token (str | None): Refresh token read from the HttpOnly cookie.

    Returns:
        TokenResponse: New access token.
    """
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        data = jwt.decode(
            refresh_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        sub = data.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from e

    user = await users.find_one({"_id": PyObjectId(sub)}, {"_id": 1, "is_active": 1})
    if not user or not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    access_token = create_access_token(data={"sub": str(user["_id"])})
    return {"access_token": access_token, "token_type": "bearer"}


# DONE: [BACKLOG] Route /auth/verify-email (GET) verified
@router.get(
    "/verify-email",
    response_model=MessageOut,
    summary="Verify email by code",
    description=(
        "Verifies a confirmation code received by email.\n\n"
        "- Activates the user if the code is valid and not expired\n"
        "- Removes the code and its expiration\n"
        "- Returns a confirmation message"
    ),
)
async def verify_email(
    code: Annotated[
        str, Query(..., description="Verification code received by email, valid for 24h.")
    ],
    users: Annotated[AsyncIOMotorCollection, Depends(users_coll)],
):
    """Verifies email.

    Description:
        Checks that the provided code matches a pending, non-expired verification,
        then permanently activates the user.

    Args:
        code (str): Verification code sent by email.
        users (AsyncIOMotorCollection): MongoDB users collection.

    Returns:
        MessageOut: Message confirming verification.
    """
    now_ts = now()
    user = await users.find_one(
        {"verification_code": code, "verification_expires_at": {"$gte": now_ts}},
        projection={"_id": 1},
    )
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    await users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {"is_verified": True, "updated_at": now_ts},
            "$unset": {"verification_code": "", "verification_expires_at": ""},
        },
    )
    return {"message": "Email verified"}


# DONE: [BACKLOG] Route /auth/verify-email (POST) verified
@router.post(
    "/verify-email",
    response_model=MessageOut,
    summary="Verify email via POST",
    description="POST alternative to submit the verification code in a JSON body.",
)
async def verify_email_post(
    body: Annotated[
        VerifyEmailBody, Body(..., description="Object containing the verification code.")
    ],
    users: Annotated[AsyncIOMotorCollection, Depends(users_coll)],
):
    """Verifies email (POST).

    Description:
        Same as the GET version but receives the code in a JSON body.

    Args:
        body (VerifyEmailBody): Object containing the verification code.
        users (AsyncIOMotorCollection): MongoDB users collection.

    Returns:
        MessageOut: Message confirming verification.
    """
    return await verify_email(code=body.code, users=users)


# DONE: [BACKLOG] Route /auth/resend-verification (POST) verified
@router.post(
    "/resend-verification",
    response_model=MessageOut,
    summary="Resend the verification code",
    description=(
        "Regenerates and resends a verification email if the account exists and is not yet activated.\n\n"
        "- Does not reveal whether the account actually exists\n"
        "- Updates the code expiration (24h)"
    ),
)
async def resend_verification(
    body: Annotated[
        ResendVerificationRequest,
        Body(..., description="Identifier (username or email) of the user."),
    ],
    users: Annotated[AsyncIOMotorCollection, Depends(users_coll)],
    background_tasks: BackgroundTasks,
):
    """Resends a verification email.

    Description:
        Generates and sends a new verification code for the identified user (username/email),
        if their account is not yet verified.

    Args:
        body (ResendVerificationRequest): Identifier (username or email).
        users (AsyncIOMotorCollection): MongoDB users collection.

    Returns:
        MessageOut: Confirmation message (without revealing whether the account exists).
    """
    ident = (body.identifier or "").strip()
    user = await users.find_one(
        {"$or": [{"email": ident}, {"username": ident}]},
        collation=COLLATION_CI,
        projection={"_id": 1, "email": 1, "is_verified": 1},
    )
    if user and not user.get("is_verified", False):
        code = create_verification_code()
        await users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "verification_code": code,
                    "verification_expires_at": now() + dt.timedelta(hours=24),
                    "updated_at": now(),
                }
            },
        )
        if background_tasks:
            background_tasks.add_task(
                send_verification_email,
                to_email=user["email"],
                username=user.get("username", ""),
                code=code,
            )

    return {"message": "If the account exists and is not verified, a new email was sent."}
