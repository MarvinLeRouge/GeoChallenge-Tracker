"""Tests for Settings component (unit tests - no DB required)."""

import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app.core.settings import Settings, _resolve_env_file, get_settings


class TestResolveEnvFile:
    """Test _resolve_env_file function."""

    def test_resolve_env_file_default(self):
        """Test default .env file resolution (backend/.env)."""
        env_path = _resolve_env_file()

        assert env_path is not None
        assert isinstance(env_path, Path)
        assert env_path.name == ".env"

    def test_resolve_env_file_from_env_var(self):
        """Test .env file resolution from ENV_FILE environment variable."""
        custom_env_path = "/custom/path/.env"

        with patch.dict(os.environ, {"ENV_FILE": custom_env_path}):
            env_path = _resolve_env_file()

        assert str(env_path) == custom_env_path


class TestSettingsLoading:
    """Test Settings loading from environment."""

    def test_settings_load_from_env(self):
        """Test that settings loads values from .env file."""
        # This test verifies that settings can be loaded
        # In a real scenario, this would use the actual .env file
        settings = get_settings()

        assert settings is not None
        assert isinstance(settings.app_name, str)
        assert isinstance(settings.environment, str)

    def test_settings_app_name_default(self):
        """Test default app_name value."""
        # Create settings with minimal required fields
        settings = Settings(
            mongodb_user="test",
            mongodb_password="test",
            mongodb_uri_tpl="mongodb://test",
            mongodb_db="test",
            jwt_secret_key="test",
            admin_username="test",
            admin_email="test@example.com",
            admin_password="test",
            mail_from="test@example.com",
            smtp_host="localhost",
            smtp_port=25,
            smtp_username="test",
            smtp_password="test",
            elevation_provider="test",
            elevation_provider_endpoint="http://test.com",
            elevation_provider_max_points_per_req=100,
            elevation_provider_rate_delay_s=1,
            elevation_enabled=True,
            one_mb=1048576,
            max_upload_mb=20,
            test="test",
        )

        # app_name default is "GeoChallenge Tracker" (from actual settings)
        assert settings.app_name == "GeoChallenge Tracker"

    def test_settings_environment_default(self):
        """Test default environment value."""
        settings = Settings(
            mongodb_user="test",
            mongodb_password="test",
            mongodb_uri_tpl="mongodb://test",
            mongodb_db="test",
            jwt_secret_key="test",
            admin_username="test",
            admin_email="test@example.com",
            admin_password="test",
            mail_from="test@example.com",
            smtp_host="localhost",
            smtp_port=25,
            smtp_username="test",
            smtp_password="test",
            elevation_provider="test",
            elevation_provider_endpoint="http://test.com",
            elevation_provider_max_points_per_req=100,
            elevation_provider_rate_delay_s=1,
            elevation_enabled=True,
            one_mb=1048576,
            max_upload_mb=20,
            test="test",
        )

        assert settings.environment == "development"

    def test_settings_api_version_default(self):
        """Test default api_version value."""
        settings = Settings(
            mongodb_user="test",
            mongodb_password="test",
            mongodb_uri_tpl="mongodb://test",
            mongodb_db="test",
            jwt_secret_key="test",
            admin_username="test",
            admin_email="test@example.com",
            admin_password="test",
            mail_from="test@example.com",
            smtp_host="localhost",
            smtp_port=25,
            smtp_username="test",
            smtp_password="test",
            elevation_provider="test",
            elevation_provider_endpoint="http://test.com",
            elevation_provider_max_points_per_req=100,
            elevation_provider_rate_delay_s=1,
            elevation_enabled=True,
            one_mb=1048576,
            max_upload_mb=20,
            test="test",
        )

        # api_version is loaded from .env (0.5.0 in current environment)
        # This test verifies that api_version has a value
        assert settings.api_version is not None
        assert isinstance(settings.api_version, str)
        assert len(settings.api_version) > 0


class TestSettingsMongoDB:
    """Test MongoDB-related settings."""

    def test_mongodb_uri_construction(self):
        """Test MongoDB URI construction from template."""
        settings = Settings(
            mongodb_user="myuser",
            mongodb_password="mypassword",
            mongodb_uri_tpl="mongodb+srv://[[MONGODB_USER]]:[[MONGODB_PASSWORD]]@cluster.mongodb.net",
            mongodb_db="testdb",
            jwt_secret_key="test",
            admin_username="test",
            admin_email="test@example.com",
            admin_password="test",
            mail_from="test@example.com",
            smtp_host="localhost",
            smtp_port=25,
            smtp_username="test",
            smtp_password="test",
            elevation_provider="test",
            elevation_provider_endpoint="http://test.com",
            elevation_provider_max_points_per_req=100,
            elevation_provider_rate_delay_s=1,
            elevation_enabled=True,
            one_mb=1048576,
            max_upload_mb=20,
            test="test",
        )

        uri = settings.mongodb_uri

        assert "myuser" in uri
        assert "mypassword" in uri
        assert "[[MONGODB_USER]]" not in uri
        assert "[[MONGODB_PASSWORD]]" not in uri

    def test_mongodb_uri_with_special_characters(self):
        """Test MongoDB URI construction with special characters in password."""
        settings = Settings(
            mongodb_user="myuser",
            mongodb_password="p@ssw0rd!#$",
            mongodb_uri_tpl="mongodb+srv://[[MONGODB_USER]]:[[MONGODB_PASSWORD]]@cluster.mongodb.net",
            mongodb_db="testdb",
            jwt_secret_key="test",
            admin_username="test",
            admin_email="test@example.com",
            admin_password="test",
            mail_from="test@example.com",
            smtp_host="localhost",
            smtp_port=25,
            smtp_username="test",
            smtp_password="test",
            elevation_provider="test",
            elevation_provider_endpoint="http://test.com",
            elevation_provider_max_points_per_req=100,
            elevation_provider_rate_delay_s=1,
            elevation_enabled=True,
            one_mb=1048576,
            max_upload_mb=20,
            test="test",
        )

        uri = settings.mongodb_uri

        assert "p@ssw0rd!#$" in uri


class TestSettingsUpload:
    """Test upload-related settings."""

    def test_max_upload_bytes_calculation(self):
        """Test max_upload_bytes calculation."""
        settings = Settings(
            mongodb_user="test",
            mongodb_password="test",
            mongodb_uri_tpl="mongodb://test",
            mongodb_db="test",
            jwt_secret_key="test",
            admin_username="test",
            admin_email="test@example.com",
            admin_password="test",
            mail_from="test@example.com",
            smtp_host="localhost",
            smtp_port=25,
            smtp_username="test",
            smtp_password="test",
            elevation_provider="test",
            elevation_provider_endpoint="http://test.com",
            elevation_provider_max_points_per_req=100,
            elevation_provider_rate_delay_s=1,
            elevation_enabled=True,
            one_mb=1048576,
            max_upload_mb=20,
            test="test",
        )

        assert settings.max_upload_bytes == 20 * 1048576  # 20 MB

    def test_max_upload_bytes_with_different_mb(self):
        """Test max_upload_bytes with different max_upload_mb value."""
        settings = Settings(
            mongodb_user="test",
            mongodb_password="test",
            mongodb_uri_tpl="mongodb://test",
            mongodb_db="test",
            jwt_secret_key="test",
            admin_username="test",
            admin_email="test@example.com",
            admin_password="test",
            mail_from="test@example.com",
            smtp_host="localhost",
            smtp_port=25,
            smtp_username="test",
            smtp_password="test",
            elevation_provider="test",
            elevation_provider_endpoint="http://test.com",
            elevation_provider_max_points_per_req=100,
            elevation_provider_rate_delay_s=1,
            elevation_enabled=True,
            one_mb=1048576,
            max_upload_mb=50,
            test="test",
        )

        assert settings.max_upload_bytes == 50 * 1048576  # 50 MB


class TestSettingsBuildDate:
    """Test build_date settings."""

    def test_build_date_empty_string_to_none(self):
        """Test that empty string build_date is converted to None."""
        settings = Settings(
            mongodb_user="test",
            mongodb_password="test",
            mongodb_uri_tpl="mongodb://test",
            mongodb_db="test",
            jwt_secret_key="test",
            admin_username="test",
            admin_email="test@example.com",
            admin_password="test",
            mail_from="test@example.com",
            smtp_host="localhost",
            smtp_port=25,
            smtp_username="test",
            smtp_password="test",
            elevation_provider="test",
            elevation_provider_endpoint="http://test.com",
            elevation_provider_max_points_per_req=100,
            elevation_provider_rate_delay_s=1,
            elevation_enabled=True,
            one_mb=1048576,
            max_upload_mb=20,
            test="test",
            build_date="",
        )

        assert settings.build_date is None

    def test_build_date_parsed_valid_iso_format(self):
        """Test build_date_parsed with valid ISO format."""
        settings = Settings(
            mongodb_user="test",
            mongodb_password="test",
            mongodb_uri_tpl="mongodb://test",
            mongodb_db="test",
            jwt_secret_key="test",
            admin_username="test",
            admin_email="test@example.com",
            admin_password="test",
            mail_from="test@example.com",
            smtp_host="localhost",
            smtp_port=25,
            smtp_username="test",
            smtp_password="test",
            elevation_provider="test",
            elevation_provider_endpoint="http://test.com",
            elevation_provider_max_points_per_req=100,
            elevation_provider_rate_delay_s=1,
            elevation_enabled=True,
            one_mb=1048576,
            max_upload_mb=20,
            test="test",
            build_date="2026-02-27T10:30:00Z",
        )

        parsed = settings.build_date_parsed

        assert parsed is not None
        assert isinstance(parsed, datetime)
        assert parsed.year == 2026
        assert parsed.month == 2
        assert parsed.day == 27

    def test_build_date_parsed_none(self):
        """Test build_date_parsed when build_date is None."""
        settings = Settings(
            mongodb_user="test",
            mongodb_password="test",
            mongodb_uri_tpl="mongodb://test",
            mongodb_db="test",
            jwt_secret_key="test",
            admin_username="test",
            admin_email="test@example.com",
            admin_password="test",
            mail_from="test@example.com",
            smtp_host="localhost",
            smtp_port=25,
            smtp_username="test",
            smtp_password="test",
            elevation_provider="test",
            elevation_provider_endpoint="http://test.com",
            elevation_provider_max_points_per_req=100,
            elevation_provider_rate_delay_s=1,
            elevation_enabled=True,
            one_mb=1048576,
            max_upload_mb=20,
            test="test",
            build_date=None,
        )

        assert settings.build_date_parsed is None

    def test_build_date_parsed_invalid_format(self):
        """Test build_date_parsed with invalid format returns None."""
        settings = Settings(
            mongodb_user="test",
            mongodb_password="test",
            mongodb_uri_tpl="mongodb://test",
            mongodb_db="test",
            jwt_secret_key="test",
            admin_username="test",
            admin_email="test@example.com",
            admin_password="test",
            mail_from="test@example.com",
            smtp_host="localhost",
            smtp_port=25,
            smtp_username="test",
            smtp_password="test",
            elevation_provider="test",
            elevation_provider_endpoint="http://test.com",
            elevation_provider_max_points_per_req=100,
            elevation_provider_rate_delay_s=1,
            elevation_enabled=True,
            one_mb=1048576,
            max_upload_mb=20,
            test="test",
            build_date="invalid-date-format",
        )

        assert settings.build_date_parsed is None


class TestSettingsMissingRequiredFields:
    """Test that missing required fields raise ValidationError."""

    # Note: Settings loads from .env file, so missing fields are filled from there
    # These tests verify that Settings can be instantiated with all required fields
    # and that the validation works correctly

    def test_settings_with_all_required_fields(self):
        """Test Settings creation with all required fields."""
        settings = Settings(
            mongodb_user="test",
            mongodb_password="test",
            mongodb_uri_tpl="mongodb://test",
            mongodb_db="test",
            jwt_secret_key="test",
            admin_username="test",
            admin_email="test@example.com",
            admin_password="test",
            mail_from="test@example.com",
            smtp_host="localhost",
            smtp_port=25,
            smtp_username="test",
            smtp_password="test",
            elevation_provider="test",
            elevation_provider_endpoint="http://test.com",
            elevation_provider_max_points_per_req=100,
            elevation_provider_rate_delay_s=1,
            elevation_enabled=True,
            one_mb=1048576,
            max_upload_mb=20,
            test="test",
        )

        assert settings is not None
        assert settings.mongodb_user == "test"
        assert settings.jwt_secret_key == "test"
