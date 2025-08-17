# backend/app/api/routes/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pymongo.collection import Collection
from bson import ObjectId
from jose import jwt, JWTError
import datetime as dt
from app.core.utils import *
from app.core.settings import settings
from app.core.security import verify_password, create_access_token, create_refresh_token, get_current_user, validate_password_strength, hash_password, generate_verification_code
from app.core.email import send_verification_email
from app.models.user import *
from app.db.mongodb import get_collection

router = APIRouter(prefix="/auth", tags=["auth"])

# Login
@router.post("/login", response_model=TokenPair)
def login(user_in: UserInLogin):
    
    users_collection = get_collection("users")
    user = users_collection.find_one({
        "$or": [
            {"email": user_in.identifier},
            {"username": user_in.identifier}
        ]
    })
    print("user", user)
    if user is None or not verify_password(user_in.password, user.get("password_hash", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.get("is_verified", False):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unverified user")
    
    token_data = {"sub": str(user["_id"])}    
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

# Accès au compte
@router.get("/me", response_model=UserOut)
def read_users_me(current_user: dict = Depends(get_current_user)) -> UserOut:
    return UserOut(**current_user)

# Refresh access token
@router.post("/refresh", response_model=TokenResponse)
def refresh_token(body: RefreshTokenRequest):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(body.refresh_token, settings.jwt_secret_key, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    new_token = create_access_token(data={"sub": user_id})
    return {
        "access_token": new_token,
        "token_type": "bearer"
    }

@router.get("/register-debug")
def debug_register():
    return {"status": "reachable"}


# Register
@router.post("/register")
async def register(user_in: UserInRegister):
    print("coucoucoucoucoucoucoucoucoucoucoucoucoucoucoucoucoucoucoucoucoucoucoucoucoucoucoucoucoucoucoucoucoucoucoucou")
    users_collection = get_collection("users")

    # Vérifier unicité
    if users_collection.find_one({"$or": [{"email": user_in.email}, {"username": user_in.username}]}):
        raise HTTPException(status_code=409, detail="Email or username already registered.")

    # Valider complexité du mot de passe
    validate_password_strength(user_in.password)

    # Hasher le mot de passe
    hashed_password = hash_password(user_in.password)

    # Générer code de vérification + expiration (ex: 1h)
    verification_code = generate_verification_code()
    verification_expires_at = now() + dt.timedelta(hours=1)

    # Créer le user
    new_user = {
        "username": user_in.username,
        "email": user_in.email,
        "password_hash": hashed_password,
        "is_verified": False,
        "verification_code": verification_code,
        "verification_expires_at": verification_expires_at,
        "created_at": now(),
        "updated_at": None,
        "challenges": []
    }

    users_collection.insert_one(new_user)
    # L'envoi de mail viendra plus tard
    await send_verification_email(
        to_email=user_in.email,
        username=user_in.username,
        code=verification_code
    )
    return {"message": "User created. Please check your email to verify your account."}

# Send verification email
@router.get("/verify-email")
def verify_email(code: str):
    users_collection = get_collection("users")
    
    user = users_collection.find_one({"verification_code": code})
    if not user:
        raise HTTPException(status_code=404, detail="Invalid verification code")

    if user.get("verification_expires_at") is None or user["verification_expires_at"] < now():
        raise HTTPException(status_code=400, detail="Verification code expired")

    users_collection.update_one(
        {"_id": user["_id"]},
        {
            "$set": {"is_verified": True},
            "$unset": {"verification_code": "", "verification_expires_at": ""}
        }
    )

    return {"message": "Email verified successfully"}

@router.post("/resend-verification")
async def resend_verification(data: ResendVerificationRequest):
    users_collection = get_collection("users")

    user = users_collection.find_one({
        "$or": [
            {"email": data.identifier},
            {"username": data.identifier}
        ]
    })

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.get("is_verified"):
        raise HTTPException(status_code=400, detail="User is already verified")

    # Nouveau code
    code = generate_verification_code()
    expires_at = now() + dt.timedelta(hours=1)

    users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "verification_code": code,
            "verification_expires_at": expires_at
        }}
    )

    await send_verification_email(
        to_email=user["email"],
        username=user["username"],
        code=code
    )

    return {"message": "Verification email resent"}


@router.post("/token", response_model=TokenPair)
def issue_token(form_data: OAuth2PasswordRequestForm = Depends()):
    users_collection = get_collection("users")
    # On accepte username OU email dans le champ "username" du formulaire
    user = users_collection.find_one({
        "$or": [
            {"email": form_data.username},
            {"username": form_data.username}
        ]
    })
    if user is None or not verify_password(form_data.password, user.get("password_hash", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.get("is_verified", False):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unverified user")

    token_data = {"sub": str(user["_id"])}
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,   # Swagger ne l’utilisera pas, mais c’est OK
        "token_type": "bearer"
    }
