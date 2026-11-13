# backend/app/core/security.py
# Password hashing (argon2id, with bcrypt verification for legacy hashes), JWT
# generation/validation, and FastAPI `get_current_user` dependency.

import datetime as dt
import os
import re
import secrets
from collections.abc import Callable
from typing import Annotated

import bcrypt
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWTError as JWTError

from app.core.bson_utils import PyObjectId
from app.core.errors import AppError, ErrorCode
from app.core.settings import get_settings
from app.core.utils import now
from app.db.mongodb import get_collection
from app.domain.models.user import User

settings = get_settings()

# argon2id (argon2-cffi defaults, identical to passlib's) for every new hash. bcrypt is
# kept for verification only, so accounts hashed before the argon2id migration still log
# in and get upgraded by `needs_rehash()`.
_argon2_hasher = PasswordHasher()
# passlib silently hashed only the first 72 bytes; bcrypt >= 5 raises instead.
_BCRYPT_MAX_BYTES = 72
# Same variable uvicorn reads for --root-path: Swagger posts to the public, prefixed URL
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{os.getenv('UVICORN_ROOT_PATH', '').rstrip('/')}/auth/login", scopes={}
)


def hash_password(password: str) -> str:
    """Hashes a password using argon2id.

    Args:
        password (str): Plain-text password.

    Returns:
        str: Hash suitable for storage in the database.
    """
    return _argon2_hasher.hash(password)


def _is_argon2_hash(hashed_password: str) -> bool:
    return hashed_password.startswith("$argon2")


def _is_bcrypt_hash(hashed_password: str) -> bool:
    return hashed_password.startswith(("$2a$", "$2b$", "$2y$"))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a password against its hash.

    Description:
        Works for both current (argon2id) and legacy (bcrypt) hashes. For bcrypt,
        the password is truncated to 72 bytes, as it was when the hash was created.

    Args:
        plain_password (str): Plain-text password.
        hashed_password (str): Hash stored in the database.

    Returns:
        bool: True if they match, False otherwise.

    Raises:
        ValueError: If the hash is neither argon2 nor bcrypt, or is malformed bcrypt.
    """
    if _is_argon2_hash(hashed_password):
        try:
            return _argon2_hasher.verify(hashed_password, plain_password)
        except VerificationError, InvalidHashError:
            return False
    if _is_bcrypt_hash(hashed_password):
        password_bytes = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
    raise ValueError("Password hash could not be identified")


def needs_rehash(hashed_password: str) -> bool:
    """Checks whether a stored hash should be upgraded to the current scheme.

    Description:
        True for non-argon2 hashes (e.g. legacy bcrypt) or argon2 hashes whose
        parameters differ from the current ones. Callers that just verified a
        password successfully should re-hash it with `hash_password()` and persist
        the result when this returns True, so accounts migrate to argon2id
        gradually as their users log in, without forcing a password reset.

    Args:
        hashed_password (str): Hash stored in the database.

    Returns:
        bool: True if the hash should be replaced with a fresh one.
    """
    if not _is_argon2_hash(hashed_password):
        return True
    return _argon2_hasher.check_needs_rehash(hashed_password)


def create_access_token(data: dict, expires_delta: dt.timedelta | None = None):
    """Creates a JWT access token.

    Description:
        Encodes a signed JWT containing `data` (e.g. `sub`) and an expiration date.
        Defaults to `settings.jwt_expiration_minutes` if not specified.

    Args:
        data (dict): Claims to include (e.g. `{"sub": "<user_id>"}`).
        expires_delta (datetime.timedelta | None): Token validity duration.

    Returns:
        str: Signed JWT token.
    """
    to_encode = data.copy()
    expire = now() + (expires_delta or dt.timedelta(minutes=settings.jwt_expiration_minutes))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: dt.timedelta | None = None) -> str:
    """Creates a JWT refresh token.

    Description:
        Encodes a longer-lived JWT (7 days by default) used to obtain new access tokens.
        Includes a unique `jti` claim (unless already provided in `data`) so the token can
        be individually revoked server-side (see `app.core.token_revocation`).

    Args:
        data (dict): Claims to include (e.g. `{"sub": "<user_id>"}`).
        expires_delta (datetime.timedelta | None): Token validity duration.

    Returns:
        str: Signed JWT refresh token.
    """
    to_encode = data.copy()
    to_encode.setdefault("jti", secrets.token_urlsafe(16))
    expire = now() + (expires_delta or dt.timedelta(days=7))  # refresh token has a longer TTL
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """FastAPI dependency: loads the current user from the JWT.

    Description:
        - Decodes the JWT received via the OAuth2 Bearer scheme
        - Extracts `sub` (user id) then loads the user from the database
        - Raises 401 if the token is invalid or the user does not exist

    Args:
        token (str): Bearer authentication token (injected via `oauth2_scheme`).

    Returns:
        dict: User document as stored in the database.

    Raises:
        HTTPException: 401 if the token is invalid/missing or the user is not found.
    """
    coll_users = await get_collection("users")
    credentials_exception = AppError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code=ErrorCode.INVALID_TOKEN,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id_raw = payload.get("sub")
        if user_id_raw is None or not isinstance(user_id_raw, str):
            raise credentials_exception
        user_id: str = user_id_raw
    except JWTError as e:
        raise credentials_exception from e

    try:
        object_id = ObjectId(user_id)
    except (InvalidId, TypeError) as e:
        raise credentials_exception from e

    raw_user = await coll_users.find_one({"_id": object_id})
    if raw_user is None:
        raise credentials_exception

    result = User(**raw_user)
    return result


def get_current_user_id(current_user: Annotated[User, Depends(get_current_user)]) -> PyObjectId:
    user_id = current_user.id
    if user_id is None:
        raise AppError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=ErrorCode.INVALID_TOKEN,
            detail="Invalid user without id",
        )
    return user_id


# (check, code, message), evaluated in order; the first failing rule is reported
_PASSWORD_RULES: list[tuple[Callable[[str], bool], ErrorCode, str]] = [
    (
        lambda p: len(p) >= 8,
        ErrorCode.PASSWORD_TOO_SHORT,
        "Password must be at least 8 characters long",
    ),
    (
        lambda p: bool(re.search(r"[A-Z]", p)),
        ErrorCode.PASSWORD_NO_UPPERCASE,
        "Password must include at least one uppercase letter",
    ),
    (
        lambda p: bool(re.search(r"[a-z]", p)),
        ErrorCode.PASSWORD_NO_LOWERCASE,
        "Password must include at least one lowercase letter",
    ),
    (
        lambda p: bool(re.search(r"[0-9]", p)),
        ErrorCode.PASSWORD_NO_DIGIT,
        "Password must include at least one number",
    ),
    (
        lambda p: bool(re.search(r"[\W_]", p)),
        ErrorCode.PASSWORD_NO_SPECIAL,
        "Password must include at least one special character",
    ),
]
PASSWORD_ERROR_CODES: dict[str, ErrorCode] = {message: code for _, code, message in _PASSWORD_RULES}


def validate_password_strength(password: str) -> tuple[bool, str]:
    """Validates password strength.

    Args:
        password (str): Password to check.

    Returns:
        tuple[bool, str]: (is_valid, error_message if not valid). The message maps to
        its error code through `PASSWORD_ERROR_CODES`.
    """
    for check, _, message in _PASSWORD_RULES:
        if not check(password):
            return False, message
    return True, ""
