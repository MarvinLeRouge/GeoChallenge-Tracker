"""Tests for security functions (password hashing, JWT tokens)."""

import datetime as dt

import pytest
from jose import jwt

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
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
