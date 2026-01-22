# backend/app/core/security.py
# Hash de mot de passe (bcrypt), génération/validation JWT, dépendance FastAPI `get_current_user`.

import datetime as dt
import re
from typing import Annotated
from uuid import uuid4

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
    """Hash de mot de passe (bcrypt via Passlib).

    Description:
        Calcule un hash sécurisé du mot de passe en utilisant le contexte Passlib configuré.

    Args:
        password (str): Mot de passe en clair.

    Returns:
        str: Hash stockable en base.
    """
    result = pwd_context.hash(password)

    return result


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe contre son hash.

    Description:
        Utilise Passlib pour comparer `plain_password` au `hashed_password`.

    Args:
        plain_password (str): Mot de passe en clair.
        hashed_password (str): Hash stocké en base.

    Returns:
        bool: True si correspondance, sinon False.
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: dt.timedelta | None = None):
    """Crée un access token JWT.

    Description:
        Encode un JWT signé contenant `data` (ex. `sub`) et une date d’expiration.
        L’expiration par défaut est de 60 minutes si non précisée.

    Args:
        data (dict): Claims à inclure (ex. `{"sub": "<user_id>"}`).
        expires_delta (datetime.timedelta | None): Durée de validité.

    Returns:
        str: Jeton JWT signé.
    """
    to_encode = data.copy()
    expire = now() + (expires_delta or dt.timedelta(minutes=15))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: dt.timedelta | None = None) -> str:
    """Crée un refresh token JWT.

    Description:
        Encode un JWT de plus longue durée (par défaut 7 jours) pour obtenir de nouveaux access tokens.

    Args:
        data (dict): Claims à inclure (ex. `{"sub": "<user_id>"}`).
        expires_delta (datetime.timedelta | None): Durée de validité.

    Returns:
        str: Jeton JWT signé (refresh).
    """
    to_encode = data.copy()
    expire = now() + (expires_delta or dt.timedelta(days=7))  # refresh token plus long
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm="HS256")

    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Dépendance FastAPI: charge l’utilisateur courant depuis le JWT.

    Description:
        - Décode le JWT reçu via le schéma OAuth2 Bearer
        - Extrait `sub` (id utilisateur) puis charge l’utilisateur en base
        - Lève 401 si le token est invalide ou si l’utilisateur n’existe pas

    Args:
        token (str): Jeton d’authentification Bearer (injection via `oauth2_scheme`).

    Returns:
        dict: Document utilisateur (tel que stocké en base).

    Raises:
        HTTPException: 401 si jeton invalide/inexistant ou utilisateur introuvable.
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


def require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user


def validate_password_strength(password: str) -> tuple[bool, str]:
    """Valide la complexité du mot de passe.

    Args:
        password (str): Mot de passe à contrôler.

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

    if not re.search(r"[\W_]", password):  # caractère spécial
        return False, "Password must include at least one special character"

    return True, ""


def generate_verification_code() -> str:
    """Génère un code de vérification.

    Description:
        Produit un identifiant aléatoire (UUID4) à usage temporaire pour les workflows de confirmation.

    Returns:
        str: Code de vérification.
    """
    result = str(uuid4())

    return result


# Type aliases pour faciliter l'usage
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserId = Annotated[PyObjectId, Depends(get_current_user_id)]
