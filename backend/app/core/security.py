# backend/app/core/security.py
# Password hashing (bcrypt), JWT generation/validation, and FastAPI `get_current_user` dependency.

import datetime as dt
import re
from typing import Annotated

from bson import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.bson_utils import PyObjectId
from app.core.settings import get_settings
from app.core.utils import now
from app.db.mongodb import get_collection
from app.domain.models.user import User

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", scopes={})


def hash_password(password: str) -> str:
    """Hashes a password using bcrypt via Passlib.

    Description:
        Computes a secure hash of the password using the configured Passlib context.

    Args:
        password (str): Plain-text password.

    Returns:
        str: Hash suitable for storage in the database.
    """
    result = pwd_context.hash(password)

    return result


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a password against its hash.

    Description:
        Uses Passlib to compare `plain_password` against `hashed_password`.

    Args:
        plain_password (str): Plain-text password.
        hashed_password (str): Hash stored in the database.

    Returns:
        bool: True if they match, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: dt.timedelta | None = None):
    """Creates a JWT access token.

    Description:
        Encodes a signed JWT containing `data` (e.g. `sub`) and an expiration date.
        The default expiration is 60 minutes if not specified.

    Args:
        data (dict): Claims to include (e.g. `{"sub": "<user_id>"}`).
        expires_delta (datetime.timedelta | None): Token validity duration.

    Returns:
        str: Signed JWT token.
    """
    to_encode = data.copy()
    expire = now() + (expires_delta or dt.timedelta(minutes=15))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: dt.timedelta | None = None) -> str:
    """Creates a JWT refresh token.

    Description:
        Encodes a longer-lived JWT (7 days by default) used to obtain new access tokens.

    Args:
        data (dict): Claims to include (e.g. `{"sub": "<user_id>"}`).
        expires_delta (datetime.timedelta | None): Token validity duration.

    Returns:
        str: Signed JWT refresh token.
    """
    to_encode = data.copy()
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
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
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

    raw_user = await coll_users.find_one({"_id": ObjectId(user_id)})
    if raw_user is None:
        raise credentials_exception

    result = User(**raw_user)
    return result


def get_current_user_id(current_user: Annotated[User, Depends(get_current_user)]) -> PyObjectId:
    user_id = current_user.id
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user without id",
        )
    return user_id


def validate_password_strength(password: str) -> tuple[bool, str]:
    """Validates password strength.

    Args:
        password (str): Password to check.

    Returns:
        tuple[bool, str]: (is_valid, error_message if not valid)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not re.search(r"[A-Z]", password):
        return False, "Password must include at least one uppercase letter"

    if not re.search(r"[a-z]", password):
        return False, "Password must include at least one lowercase letter"

    if not re.search(r"[0-9]", password):
        return False, "Password must include at least one number"

    if not re.search(r"[\W_]", password):  # special character
        return False, "Password must include at least one special character"

    return True, ""
