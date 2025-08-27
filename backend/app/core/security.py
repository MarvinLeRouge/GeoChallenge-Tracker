# backend/app/core/security.py
# Hash de mot de passe (bcrypt), génération/validation JWT, dépendance FastAPI `get_current_user`.

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
    expire = now() + (expires_delta or dt.timedelta(minutes=60))
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

def get_current_user(token: str = Depends(oauth2_scheme)):
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
    """Valide la complexité du mot de passe.

    Description:
        Exige au minimum : 8 caractères, 1 majuscule, 1 minuscule, 1 chiffre et 1 caractère spécial.
        Lève une `HTTPException(400)` si la politique n’est pas respectée.

    Args:
        password (str): Mot de passe à contrôler.

    Returns:
        None: Lève exception en cas d’échec.

    Raises:
        HTTPException: 400 si la politique de complexité n’est pas respectée.
    """
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
    """Génère un code de vérification.

    Description:
        Produit un identifiant aléatoire (UUID4) à usage temporaire pour les workflows de confirmation.

    Returns:
        str: Code de vérification.
    """
    result = str(uuid4())

    return result