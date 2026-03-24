"""Tests for security functions (password hashing, JWT tokens)."""

import datetime as dt
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId
from fastapi import HTTPException
from jose import jwt

from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_current_user_id,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.core.settings import get_settings

settings = get_settings()


class TestPasswordHashing:
    """Test password hashing functionality."""

    def test_hash_password(self):
        """Test that hash_password returns a hash string."""
        password = "Secure123!"
        hashed = hash_password(password)

        assert hashed is not None
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert hashed != password  # Hash != original

    def test_verify_password_valid(self):
        """Test verify_password with correct password."""
        password = "Secure123!"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_invalid(self):
        """Test verify_password with wrong password."""
        password = "Secure123!"
        hashed = hash_password(password)

        assert verify_password("WrongPassword", hashed) is False


class TestJWTTokenCreation:
    """Test JWT token creation functionality."""

    def test_create_access_token(self):
        """Test creation of JWT access token."""
        data = {"sub": "test_user_id"}
        expires_delta = dt.timedelta(minutes=30)

        token = create_access_token(data=data, expires_delta=expires_delta)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
        assert token.count(".") == 2  # JWT has 3 parts separated by dots

    def test_create_access_token_default_expiration(self):
        """Test access token creation with default expiration (15 min)."""
        data = {"sub": "test_user_id"}

        token = create_access_token(data=data)

        assert token is not None
        # Decode to verify expiration
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert "exp" in payload

    def test_create_refresh_token(self):
        """Test creation of JWT refresh token."""
        data = {"sub": "test_user_id"}
        expires_delta = dt.timedelta(days=7)

        token = create_refresh_token(data=data, expires_delta=expires_delta)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
        assert token.count(".") == 2  # JWT has 3 parts separated by dots

    def test_create_refresh_token_default_expiration(self):
        """Test refresh token creation with default expiration (7 days)."""
        data = {"sub": "test_user_id"}

        token = create_refresh_token(data=data)

        assert token is not None
        # Decode to verify expiration
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert "exp" in payload

    def test_create_access_token_contains_subject(self):
        """Test that access token contains the subject (sub) claim."""
        user_id = "test_user_123"
        data = {"sub": user_id}

        token = create_access_token(data=data)

        # Decode to verify subject
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == user_id


class TestJWTTokenDecoding:
    """Test JWT token decoding/validation functionality."""

    def test_decode_token_valid(self):
        """Test decoding of valid JWT token."""
        # Create a valid token
        data = {"sub": "test_user_id", "custom_claim": "test_value"}
        token = create_access_token(data=data)

        # Decode and verify
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

        assert payload is not None
        assert payload["sub"] == "test_user_id"
        assert payload["custom_claim"] == "test_value"
        assert "exp" in payload

    def test_decode_token_expired(self):
        """Test that token contains expired timestamp."""
        # Create a token that expired 1 hour ago
        data = {"sub": "test_user_id"}
        expires_delta = dt.timedelta(hours=-1)  # Expired 1 hour ago

        token = create_access_token(data=data, expires_delta=expires_delta)

        # Decode without verification to check expiration is in the past
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False},
        )

        # Verify the expiration is indeed in the past
        import time

        assert payload["exp"] < time.time(), "Token should be expired"
        assert "exp" in payload, "Token should contain expiration claim"

    def test_decode_token_invalid_signature(self):
        """Test that invalid signature raises JWTError."""
        # Create a valid token
        data = {"sub": "test_user_id"}
        token = create_access_token(data=data)

        # Try to decode with wrong secret key
        with pytest.raises(jwt.JWTError):
            jwt.decode(token, "wrong_secret_key", algorithms=[settings.jwt_algorithm])

    def test_decode_token_invalid_algorithm(self):
        """Test that invalid algorithm raises JWTError."""
        # Create a valid token
        data = {"sub": "test_user_id"}
        token = create_access_token(data=data)

        # Try to decode with wrong algorithm
        with pytest.raises(jwt.JWTError):
            jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=["HS512"],  # Wrong algorithm
            )

    def test_decode_token_tampered(self):
        """Test that tampered token raises JWTError."""
        # Create a valid token
        data = {"sub": "test_user_id"}
        token = create_access_token(data=data)

        # Tamper with the payload (second part of JWT)
        parts = token.split(".")
        tampered_payload = parts[1][:-1] + ("0" if parts[1][-1] != "0" else "1")
        tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"

        # Attempting to decode should raise JWTError
        with pytest.raises(jwt.JWTError):
            jwt.decode(tampered_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


# ---------------------------------------------------------------------------
# validate_password_strength
# ---------------------------------------------------------------------------


class TestValidatePasswordStrength:
    """Test validate_password_strength from app.core.security."""

    def test_valid_strong_password(self):
        valid, msg = validate_password_strength("Str0ng!Pass")
        assert valid is True
        assert msg == ""

    def test_too_short(self):
        valid, msg = validate_password_strength("Ab1!xyz")
        assert valid is False
        assert "8 characters" in msg

    def test_no_uppercase(self):
        valid, msg = validate_password_strength("str0ng!pass")
        assert valid is False
        assert "uppercase" in msg

    def test_no_lowercase(self):
        valid, msg = validate_password_strength("STR0NG!PASS")
        assert valid is False
        assert "lowercase" in msg

    def test_no_digit(self):
        valid, msg = validate_password_strength("Strong!Pass")
        assert valid is False
        assert "number" in msg

    def test_no_special_char(self):
        valid, msg = validate_password_strength("Str0ngPass")
        assert valid is False
        assert "special character" in msg

    def test_underscore_counts_as_special(self):
        """Underscore is matched by [\\W_] and counts as a special character."""
        valid, msg = validate_password_strength("Str0ng_Pass")
        assert valid is True
        assert msg == ""

    def test_exactly_8_chars_valid(self):
        valid, msg = validate_password_strength("Ab1!wxyz")
        assert valid is True

    def test_7_chars_too_short(self):
        valid, msg = validate_password_strength("Ab1!xyz")
        assert valid is False
        assert "8 characters" in msg


# ---------------------------------------------------------------------------
# get_current_user (lines 119-140)
# ---------------------------------------------------------------------------


_RAW_USER = {
    "_id": None,  # filled per test
    "username": "testuser",
    "email": "test@example.com",
    "role": "user",
    "is_active": True,
    "is_verified": False,
}


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_valid_token_user_found(self):
        user_id = ObjectId()
        raw = {**_RAW_USER, "_id": user_id}
        token = create_access_token(data={"sub": str(user_id)})

        coll = AsyncMock()
        coll.find_one = AsyncMock(return_value=raw)

        with patch("app.core.security.get_collection", return_value=coll):
            user = await get_current_user(token)

        assert str(user.id) == str(user_id)
        assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_valid_token_user_not_found_raises_401(self):
        user_id = ObjectId()
        token = create_access_token(data={"sub": str(user_id)})

        coll = AsyncMock()
        coll.find_one = AsyncMock(return_value=None)

        with patch("app.core.security.get_collection", return_value=coll):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        coll = AsyncMock()
        with patch("app.core.security.get_collection", return_value=coll):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user("not.a.valid.jwt")

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_token_missing_sub_raises_401(self):
        token = create_access_token(data={"other_claim": "value"})

        coll = AsyncMock()
        with patch("app.core.security.get_collection", return_value=coll):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token)

        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# get_current_user_id (lines 144-150)
# ---------------------------------------------------------------------------


class TestGetCurrentUserId:
    def test_user_with_id_returns_id(self):
        from app.domain.models.user import User

        oid = ObjectId()
        user = User(_id=oid, username="test", email="test@example.com")
        result = get_current_user_id(user)
        assert result == oid

    def test_user_with_none_id_raises_401(self):
        from app.domain.models.user import User

        user = User(username="test", email="test@example.com")  # id=None by default
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id(user)

        assert exc_info.value.status_code == 401
