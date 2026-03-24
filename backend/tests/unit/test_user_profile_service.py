"""Tests for UserProfileService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from app.api.dto.user_profile import UserLocationIn
from app.services.user_profile_service import UserProfileService


def _make_db():
    """Return a MockDB with a .users AsyncMock collection."""

    class MockDB:
        def __init__(self):
            self.users = AsyncMock()

    return MockDB()


class TestGetUser:
    @pytest.mark.asyncio
    async def test_returns_user_doc_when_found(self):
        db = _make_db()
        user_id = ObjectId()
        doc = {"_id": user_id, "username": "alice"}
        db.users.find_one = AsyncMock(return_value=doc)

        service = UserProfileService(db)
        result = await service.get_user(user_id)

        assert result == doc
        db.users.find_one.assert_called_once_with({"_id": user_id})

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        db = _make_db()
        db.users.find_one = AsyncMock(return_value=None)

        service = UserProfileService(db)
        result = await service.get_user(ObjectId())

        assert result is None


class TestGetUserLocation:
    @pytest.mark.asyncio
    async def test_returns_location_when_present(self):
        db = _make_db()
        user_id = ObjectId()
        geo = {"type": "Point", "coordinates": [2.3, 48.8]}
        db.users.find_one = AsyncMock(return_value={"_id": user_id, "location": geo})

        service = UserProfileService(db)
        result = await service.get_user_location(user_id)

        assert result == geo

    @pytest.mark.asyncio
    async def test_returns_none_when_user_not_found(self):
        db = _make_db()
        db.users.find_one = AsyncMock(return_value=None)

        service = UserProfileService(db)
        result = await service.get_user_location(ObjectId())

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_location_field(self):
        db = _make_db()
        db.users.find_one = AsyncMock(return_value={"_id": ObjectId()})

        service = UserProfileService(db)
        result = await service.get_user_location(ObjectId())

        assert result is None


class TestSetUserLocation:
    @pytest.mark.asyncio
    async def test_set_via_lat_lon(self):
        db = _make_db()
        update_result = MagicMock()
        db.users.update_one = AsyncMock(return_value=update_result)

        service = UserProfileService(db)
        location_in = UserLocationIn(lat=48.8, lon=2.3)
        result = await service.set_user_location(ObjectId(), location_in)

        assert result is update_result
        call_args = db.users.update_one.call_args
        geojson = call_args[0][1]["$set"]["location"]
        assert geojson["type"] == "Point"
        assert geojson["coordinates"] == [2.3, 48.8]

    @pytest.mark.asyncio
    async def test_set_via_position_string(self):
        db = _make_db()
        update_result = MagicMock()
        db.users.update_one = AsyncMock(return_value=update_result)

        service = UserProfileService(db)
        location_in = UserLocationIn(position="N 48° 51.000 E 002° 18.000")

        with patch(
            "app.services.user_profile_service.parse_location_to_lon_lat",
            return_value=(2.3, 48.85),
        ):
            result = await service.set_user_location(ObjectId(), location_in)

        assert result is update_result

    @pytest.mark.asyncio
    async def test_raises_value_error_when_no_coords_provided(self):
        db = _make_db()
        service = UserProfileService(db)
        location_in = UserLocationIn()  # no lat/lon/position

        with pytest.raises(ValueError, match="lat/lon"):
            await service.set_user_location(ObjectId(), location_in)

    @pytest.mark.asyncio
    async def test_raises_value_error_when_coords_out_of_range(self):
        db = _make_db()
        service = UserProfileService(db)
        location_in = UserLocationIn(position="N 99° 00.000 E 000° 00.000")

        with patch(
            "app.services.user_profile_service.parse_location_to_lon_lat",
            return_value=(0.0, 99.0),  # lat=99 > 90 → out of range
        ):
            with pytest.raises(ValueError, match="range"):
                await service.set_user_location(ObjectId(), location_in)


class TestGetUserLocationFormatted:
    @pytest.mark.asyncio
    async def test_returns_formatted_output_for_valid_point(self):
        db = _make_db()
        user_id = ObjectId()
        geo = {"type": "Point", "coordinates": [2.3, 48.8]}
        db.users.find_one = AsyncMock(return_value={"_id": user_id, "location": geo})

        service = UserProfileService(db)
        result = await service.get_user_location_formatted(user_id)

        assert result is not None
        assert result.lat == 48.8
        assert result.lon == 2.3

    @pytest.mark.asyncio
    async def test_returns_none_when_no_location(self):
        db = _make_db()
        db.users.find_one = AsyncMock(return_value=None)

        service = UserProfileService(db)
        result = await service.get_user_location_formatted(ObjectId())

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_wrong_type(self):
        db = _make_db()
        db.users.find_one = AsyncMock(
            return_value={"_id": ObjectId(), "location": {"type": "Polygon"}}
        )

        service = UserProfileService(db)
        result = await service.get_user_location_formatted(ObjectId())

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_wrong_coordinates_count(self):
        db = _make_db()
        db.users.find_one = AsyncMock(
            return_value={
                "_id": ObjectId(),
                "location": {"type": "Point", "coordinates": [2.3]},
            }
        )

        service = UserProfileService(db)
        result = await service.get_user_location_formatted(ObjectId())

        assert result is None


class TestDeleteUserLocation:
    @pytest.mark.asyncio
    async def test_calls_update_one_with_unset(self):
        db = _make_db()
        update_result = MagicMock()
        db.users.update_one = AsyncMock(return_value=update_result)

        service = UserProfileService(db)
        result = await service.delete_user_location(ObjectId())

        assert result is update_result
        call_args = db.users.update_one.call_args[0][1]
        assert "$unset" in call_args
        assert "location" in call_args["$unset"]


class TestUserExists:
    @pytest.mark.asyncio
    async def test_returns_true_when_found(self):
        db = _make_db()
        db.users.count_documents = AsyncMock(return_value=1)

        service = UserProfileService(db)
        assert await service.user_exists(ObjectId()) is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_found(self):
        db = _make_db()
        db.users.count_documents = AsyncMock(return_value=0)

        service = UserProfileService(db)
        assert await service.user_exists(ObjectId()) is False
