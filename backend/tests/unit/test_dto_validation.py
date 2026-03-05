"""Tests for DTO validation (Pydantic models)."""

import pytest
from pydantic import ValidationError

from app.domain.models.user import UserInLogin, UserInRegister


class TestUserInRegister:
    """Test UserInRegister DTO validation."""

    def test_user_in_register_valid(self):
        """Test valid UserInRegister DTO."""
        user_data = {"username": "testuser", "email": "test@example.com", "password": "Secure123!"}

        user = UserInRegister(**user_data)

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.password == "Secure123!"

    def test_user_in_register_weak_password(self):
        """Test that weak password is rejected."""
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "weak",  # < 8 characters
        }

        with pytest.raises(ValidationError) as exc_info:
            UserInRegister(**user_data)

        assert "password" in str(exc_info.value)

    def test_user_in_register_invalid_email(self):
        """Test that invalid email is rejected."""
        user_data = {
            "username": "testuser",
            "email": "invalid-email",  # Invalid email format
            "password": "Secure123!",
        }

        with pytest.raises(ValidationError) as exc_info:
            UserInRegister(**user_data)

        assert "email" in str(exc_info.value)

    def test_user_in_register_duplicate(self):
        """Test that duplicate username/email validation is NOT done at DTO level."""
        # Note: Duplicate checking is done at service/DB level, not DTO level
        # DTO only validates format, not uniqueness
        user_data = {
            "username": "existinguser",
            "email": "existing@example.com",
            "password": "Secure123!",
        }

        # This should NOT raise at DTO level (uniqueness is checked later)
        user = UserInRegister(**user_data)
        assert user.username == "existinguser"
        assert user.email == "existing@example.com"

    def test_user_in_register_username_too_short(self):
        """Test that username < 3 characters is rejected."""
        user_data = {
            "username": "ab",  # < 3 characters
            "email": "test@example.com",
            "password": "Secure123!",
        }

        with pytest.raises(ValidationError) as exc_info:
            UserInRegister(**user_data)

        assert "username" in str(exc_info.value)

    def test_user_in_register_username_too_long(self):
        """Test that username > 30 characters is rejected."""
        user_data = {
            "username": "a" * 31,  # > 30 characters
            "email": "test@example.com",
            "password": "Secure123!",
        }

        with pytest.raises(ValidationError) as exc_info:
            UserInRegister(**user_data)

        assert "username" in str(exc_info.value)

    def test_user_in_register_missing_fields(self):
        """Test that missing required fields are rejected."""
        # Missing password
        user_data = {"username": "testuser", "email": "test@example.com"}

        with pytest.raises(ValidationError) as exc_info:
            UserInRegister(**user_data)

        assert "password" in str(exc_info.value)

    def test_user_in_register_extra_fields_ignored(self):
        """Test that extra fields are ignored (Pydantic behavior)."""
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "Secure123!",
            "extra_field": "should be ignored",
        }

        user = UserInRegister(**user_data)

        assert user.username == "testuser"
        assert not hasattr(user, "extra_field")


class TestUserInLogin:
    """Test UserInLogin DTO validation."""

    def test_user_in_login_valid_with_email(self):
        """Test valid UserInLogin with email."""
        login_data = {"identifier": "test@example.com", "password": "Secure123!"}

        login = UserInLogin(**login_data)

        assert login.identifier == "test@example.com"
        assert login.password == "Secure123!"

    def test_user_in_login_valid_with_username(self):
        """Test valid UserInLogin with username."""
        login_data = {"identifier": "testuser", "password": "Secure123!"}

        login = UserInLogin(**login_data)

        assert login.identifier == "testuser"
        assert login.password == "Secure123!"

    def test_user_in_login_missing_password(self):
        """Test that missing password is rejected."""
        login_data = {"identifier": "test@example.com"}

        with pytest.raises(ValidationError) as exc_info:
            UserInLogin(**login_data)

        assert "password" in str(exc_info.value)

    def test_user_in_login_missing_identifier(self):
        """Test that missing identifier is rejected."""
        login_data = {"password": "Secure123!"}

        with pytest.raises(ValidationError) as exc_info:
            UserInLogin(**login_data)

        assert "identifier" in str(exc_info.value)
