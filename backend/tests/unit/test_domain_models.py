"""Tests for Domain Models (unit tests - no DB required)."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.core.bson_utils import PyObjectId
from app.domain.models.cache import Cache, CacheAttributeRef, CacheBase, CacheCreate, CacheUpdate
from app.domain.models.challenge import (
    Challenge,
    ChallengeBase,
    ChallengeCreate,
    ChallengeMeta,
    ChallengeUpdate,
)
from app.domain.models.user import (
    Preferences,
    User,
    UserBase,
    UserCreate,
    UserLocation,
    UserUpdate,
)


class TestCacheAttributeRef:
    """Test CacheAttributeRef model."""

    def test_cache_attribute_ref_creation(self):
        """Test CacheAttributeRef creation with valid data."""
        attr_id = PyObjectId()
        attr = CacheAttributeRef(attribute_doc_id=attr_id, is_positive=True)

        assert attr.attribute_doc_id == attr_id
        assert attr.is_positive is True

    def test_cache_attribute_ref_negative(self):
        """Test CacheAttributeRef with negative attribute."""
        attr_id = PyObjectId()
        attr = CacheAttributeRef(attribute_doc_id=attr_id, is_positive=False)

        assert attr.is_positive is False


class TestCacheBase:
    """Test CacheBase model."""

    def test_cache_base_minimal(self):
        """Test CacheBase with minimal required fields."""
        cache = CacheBase(GC="GC12345", title="Test Cache")

        assert cache.GC == "GC12345"
        assert cache.title == "Test Cache"
        assert cache.description_html is None
        assert cache.attributes == []

    def test_cache_base_with_location(self):
        """Test CacheBase with location data."""
        cache = CacheBase(GC="GC12345", title="Test Cache", lat=48.8566, lon=2.3522)

        assert cache.lat == 48.8566
        assert cache.lon == 2.3522

    def test_cache_base_with_geojson_loc(self):
        """Test CacheBase with GeoJSON loc field."""
        cache = CacheBase(
            GC="GC12345",
            title="Test Cache",
            loc={"type": "Point", "coordinates": [2.3522, 48.8566]},
        )

        assert cache.loc is not None
        assert cache.loc["type"] == "Point"

    def test_cache_base_with_attributes(self):
        """Test CacheBase with attributes list."""
        attr_id = PyObjectId()
        cache = CacheBase(
            GC="GC12345",
            title="Test Cache",
            attributes=[CacheAttributeRef(attribute_doc_id=attr_id, is_positive=True)],
        )

        assert len(cache.attributes) == 1
        assert cache.attributes[0].is_positive is True

    def test_cache_base_with_difficulty_terrain(self):
        """Test CacheBase with difficulty and terrain."""
        cache = CacheBase(GC="GC12345", title="Test Cache", difficulty=2.5, terrain=3.0)

        assert cache.difficulty == 2.5
        assert cache.terrain == 3.0

    def test_cache_base_with_status(self):
        """Test CacheBase with valid status values."""
        for status in ["active", "disabled", "archived"]:
            cache = CacheBase(GC="GC12345", title="Test Cache", status=status)
            assert cache.status == status

    def test_cache_base_invalid_status(self):
        """Test CacheBase rejects invalid status."""
        with pytest.raises(ValidationError):
            CacheBase(GC="GC12345", title="Test Cache", status="invalid_status")


class TestCacheCreate:
    """Test CacheCreate model."""

    def test_cache_create(self):
        """Test CacheCreate is identical to CacheBase."""
        cache = CacheCreate(GC="GC12345", title="Test Cache")

        assert cache.GC == "GC12345"
        assert cache.title == "Test Cache"


class TestCacheUpdate:
    """Test CacheUpdate model."""

    def test_cache_update_partial(self):
        """Test CacheUpdate with partial data."""
        update = CacheUpdate(title="New Title")

        assert update.title == "New Title"
        assert update.description_html is None

    def test_cache_update_with_attributes(self):
        """Test CacheUpdate with new attributes."""
        attr_id = PyObjectId()
        update = CacheUpdate(
            attributes=[CacheAttributeRef(attribute_doc_id=attr_id, is_positive=True)]
        )

        assert len(update.attributes) == 1  # type: ignore


class TestCache:
    """Test Cache model (MongoDB document)."""

    def test_cache_creation(self):
        """Test Cache creation with timestamps."""
        cache = Cache(GC="GC12345", title="Test Cache")

        assert cache.GC == "GC12345"
        assert cache.title == "Test Cache"
        assert cache.created_at is not None
        assert isinstance(cache.created_at, datetime)

    def test_cache_with_id(self):
        """Test Cache with _id field."""
        cache_id = PyObjectId()
        cache = Cache(_id=cache_id, GC="GC12345", title="Test Cache")

        assert cache.id == cache_id


class TestUserLocation:
    """Test UserLocation model."""

    def test_user_location_creation(self):
        """Test UserLocation with valid coordinates."""
        location = UserLocation(lon=2.3522, lat=48.8566)

        assert location.lon == 2.3522
        assert location.lat == 48.8566
        assert location.updated_at is not None
        assert isinstance(location.updated_at, datetime)

    def test_user_location_with_custom_timestamp(self):
        """Test UserLocation with custom updated_at."""
        custom_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        location = UserLocation(lon=2.3522, lat=48.8566, updated_at=custom_time)

        assert location.updated_at == custom_time


class TestPreferences:
    """Test Preferences model."""

    def test_preferences_default(self):
        """Test Preferences with default values."""
        prefs = Preferences()

        assert prefs.language == "fr"
        assert prefs.dark_mode is False

    def test_preferences_custom(self):
        """Test Preferences with custom values."""
        prefs = Preferences(language="en", dark_mode=True)

        assert prefs.language == "en"
        assert prefs.dark_mode is True


class TestUserBase:
    """Test UserBase model."""

    def test_user_base_minimal(self):
        """Test UserBase with minimal required fields."""
        user = UserBase(username="testuser", email="test@example.com")

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == "user"
        assert user.is_active is True
        assert user.is_verified is False

    def test_user_base_with_preferences(self):
        """Test UserBase with custom preferences."""
        prefs = Preferences(language="en", dark_mode=True)
        user = UserBase(username="testuser", email="test@example.com", preferences=prefs)

        assert user.preferences is not None
        assert user.preferences.language == "en"


class TestUserCreate:
    """Test UserCreate model."""

    def test_user_create(self):
        """Test UserCreate with password."""
        user = UserCreate(username="testuser", email="test@example.com", password="Secure123!")

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.password == "Secure123!"


class TestUserUpdate:
    """Test UserUpdate model."""

    def test_user_update_email(self):
        """Test UserUpdate with new email."""
        update = UserUpdate(email="newemail@example.com")

        assert update.email == "newemail@example.com"

    def test_user_update_password(self):
        """Test UserUpdate with new password."""
        update = UserUpdate(password="NewSecure456!")

        assert update.password == "NewSecure456!"

    def test_user_update_preferences(self):
        """Test UserUpdate with new preferences."""
        prefs = Preferences(language="es")
        update = UserUpdate(preferences=prefs)

        assert update.preferences is not None
        assert update.preferences.language == "es"


class TestUser:
    """Test User model (MongoDB document)."""

    def test_user_creation(self):
        """Test User creation with timestamps."""
        user = User(username="testuser", email="test@example.com")

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == "user"
        assert user.is_active is True
        assert user.challenges == []
        assert user.created_at is not None

    def test_user_with_verification_code(self):
        """Test User with verification code."""
        user = User(
            username="testuser",
            email="test@example.com",
            verification_code="ABC123",
            is_verified=False,
        )

        assert user.verification_code == "ABC123"
        assert user.is_verified is False

    def test_user_with_location(self):
        """Test User with location."""
        location = UserLocation(lon=2.3522, lat=48.8566)
        user = User(username="testuser", email="test@example.com", location=location)

        assert user.location is not None
        assert user.location.lon == 2.3522


class TestChallengeMeta:
    """Test ChallengeMeta model."""

    def test_challenge_meta_empty(self):
        """Test ChallengeMeta with no data."""
        meta = ChallengeMeta()

        assert meta.avg_days_to_complete is None
        assert meta.avg_caches_involved is None
        assert meta.completions is None
        assert meta.acceptance_rate is None

    def test_challenge_meta_with_data(self):
        """Test ChallengeMeta with statistics."""
        meta = ChallengeMeta(
            avg_days_to_complete=15.5,
            avg_caches_involved=10.0,
            completions=42,
            acceptance_rate=0.75,
        )

        assert meta.avg_days_to_complete == 15.5
        assert meta.completions == 42
        assert meta.acceptance_rate == 0.75


class TestChallengeBase:
    """Test ChallengeBase model."""

    def test_challenge_base_minimal(self):
        """Test ChallengeBase with minimal required fields."""
        cache_id = PyObjectId()
        challenge = ChallengeBase(cache_id=cache_id, name="Test Challenge")

        assert challenge.cache_id == cache_id
        assert challenge.name == "Test Challenge"
        assert challenge.description is None
        assert challenge.meta is None

    def test_challenge_base_with_meta(self):
        """Test ChallengeBase with meta statistics."""
        cache_id = PyObjectId()
        meta = ChallengeMeta(completions=10)
        challenge = ChallengeBase(cache_id=cache_id, name="Test Challenge", meta=meta)

        assert challenge.meta is not None
        assert challenge.meta.completions == 10


class TestChallengeCreate:
    """Test ChallengeCreate model."""

    def test_challenge_create(self):
        """Test ChallengeCreate is identical to ChallengeBase."""
        cache_id = PyObjectId()
        challenge = ChallengeCreate(cache_id=cache_id, name="New Challenge")

        assert challenge.cache_id == cache_id
        assert challenge.name == "New Challenge"


class TestChallengeUpdate:
    """Test ChallengeUpdate model."""

    def test_challenge_update_partial(self):
        """Test ChallengeUpdate with partial data."""
        update = ChallengeUpdate(name="Updated Name")

        assert update.name == "Updated Name"
        assert update.cache_id is None

    def test_challenge_update_with_meta(self):
        """Test ChallengeUpdate with new meta."""
        meta = ChallengeMeta(completions=50)
        update = ChallengeUpdate(meta=meta)

        assert update.meta is not None
        assert update.meta.completions == 50


class TestChallenge:
    """Test Challenge model (MongoDB document)."""

    def test_challenge_creation(self):
        """Test Challenge creation with timestamps."""
        cache_id = PyObjectId()
        challenge = Challenge(cache_id=cache_id, name="Test Challenge")

        assert challenge.cache_id == cache_id
        assert challenge.name == "Test Challenge"
        assert challenge.created_at is not None
        assert isinstance(challenge.created_at, datetime)

    def test_challenge_with_id(self):
        """Test Challenge with _id field."""
        challenge_id = PyObjectId()
        cache_id = PyObjectId()
        challenge = Challenge(_id=challenge_id, cache_id=cache_id, name="Test")

        assert challenge.id == challenge_id
