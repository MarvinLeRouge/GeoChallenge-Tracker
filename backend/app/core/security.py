# backend/app/api/core/security.py

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from jose import jwt, JWTError
import datetime as dt
from bson import ObjectId
import re
from uuid import uuid4
from app.core.utils import *
from app.core.settings import settings
from app.db.mongodb import get_collection

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login", 
    scopes={}
)

# Hash password
def hash_password(password: str) -> str:
    result = pwd_context.hash(password)

    return result

# Vérification
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# Access token
def create_access_token(data: dict, expires_delta: dt.timedelta | None = None):
    to_encode = data.copy()
    expire = now() + (expires_delta or dt.timedelta(minutes=60))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    
    return encoded_jwt

# Refresh token
def create_refresh_token(data: dict, expires_delta: dt.timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = now() + (expires_delta or dt.timedelta(days=7))  # refresh token plus long
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm="HS256")
    
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme)):
    users_collection = get_collection("users")
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if user is None:
        raise credentials_exception

    return user

def validate_password_strength(password: str) -> None:
    """Vérifie la complexité du mot de passe (min 8, maj, min, chiffre, spécial)."""
    if len(password) < 8 \
        or not re.search(r"[A-Z]", password) \
        or not re.search(r"[a-z]", password) \
        or not re.search(r"[0-9]", password) \
        or not re.search(r"[\W_]", password):  # caractère spécial

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters and include uppercase, lowercase, number, and special character."
        )

def generate_verification_code():
    result = str(uuid4())

    return result