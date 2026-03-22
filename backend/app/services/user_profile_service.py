# backend/app/services/user_profile_service.py
# User profile management service with dependency injection.

from __future__ import annotations

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.results import UpdateResult

from app.api.dto.user_profile import UserLocationIn, UserLocationOut
from app.core.bson_utils import PyObjectId
from app.core.utils import utcnow
from app.services.location_parser import parse_location_to_lon_lat


class UserProfileService:
    """User profile management service.

    Description:
        Encapsulates all business logic related to user profiles:
        - Location management (read/write)
        - Coordinate validation and parsing
        - Output data formatting
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize the service.

        Args:
            db: MongoDB database instance.
        """
        self.db = db

    async def get_user(self, user_id: ObjectId) -> dict | None:
        """Retrieve a user's information.

        Args:
            user_id: User identifier.

        Returns:
            dict | None: User profile or None if not found.
        """
        collection = self.db.users
        user_doc = await collection.find_one({"_id": user_id})
        return user_doc

    async def get_user_location(self, user_id: ObjectId) -> dict | None:
        """Retrieve a user's location.

        Args:
            user_id: User identifier.

        Returns:
            dict | None: `location` field (GeoJSON Point) or None.
        """
        collection = self.db.users
        user_doc = await collection.find_one({"_id": user_id}, {"_id": 1, "location": 1})
        return (user_doc or {}).get("location")

    async def set_user_location(
        self, user_id: ObjectId, location_input: UserLocationIn
    ) -> UpdateResult:
        """Set a user's location.

        Args:
            user_id: User identifier.
            location_input: Location data to store.

        Returns:
            UpdateResult: MongoDB update result.

        Raises:
            ValueError: If coordinates cannot be parsed.
        """
        # Parse and validate coordinates
        if location_input.position:
            lon, lat = parse_location_to_lon_lat(location_input.position)
        elif location_input.lat is not None and location_input.lon is not None:
            lat, lon = location_input.lat, location_input.lon
        else:
            raise ValueError("Either position or lat/lon must be provided")

        # Validate bounds
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Coordinates out of valid range")

        # Build the GeoJSON Point object
        geojson_location = {
            "type": "Point",
            "coordinates": [lon, lat],
        }

        # Persist to database
        collection = self.db.users
        result = await collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "location": geojson_location,
                    "updated_at": utcnow(),
                }
            },
        )

        return result

    async def get_user_location_formatted(self, user_id: ObjectId) -> UserLocationOut | None:
        """Retrieve a user's formatted location.

        Args:
            user_id: User identifier.

        Returns:
            UserLocationOut | None: Formatted location or None if no location is set.
        """
        location = await self.get_user_location(user_id)

        if not location or location.get("type") != "Point":
            return None

        coordinates = location.get("coordinates", [])
        if len(coordinates) != 2:
            return None

        lon, lat = coordinates

        return UserLocationOut(id=PyObjectId(user_id), lat=lat, lon=lon)

    async def delete_user_location(self, user_id: ObjectId) -> UpdateResult:
        """Delete a user's location.

        Args:
            user_id: User identifier.

        Returns:
            UpdateResult: MongoDB update result.
        """
        collection = self.db.users
        result = await collection.update_one(
            {"_id": user_id},
            {
                "$unset": {"location": ""},
                "$set": {"updated_at": utcnow()},
            },
        )

        return result

    async def user_exists(self, user_id: ObjectId) -> bool:
        """Check whether a user exists.

        Args:
            user_id: User identifier.

        Returns:
            bool: True if the user exists, False otherwise.
        """
        collection = self.db.users
        count = await collection.count_documents({"_id": user_id}, limit=1)
        return count > 0
