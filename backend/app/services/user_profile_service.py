# backend/app/services/user_profile_service.py
# Service de gestion des profils utilisateur avec injection de dépendances.

from __future__ import annotations

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.results import UpdateResult

from app.api.dto.user_profile import UserLocationIn, UserLocationOut
from app.core.bson_utils import PyObjectId
from app.core.utils import utcnow
from app.services.location_parser import parse_location_to_lon_lat


class UserProfileService:
    """Service de gestion des profils utilisateur.

    Description:
        Encapsule toute la logique métier liée aux profils utilisateur :
        - Gestion de la localisation (lecture/écriture)
        - Validation et parsing des coordonnées
        - Formatage des données de sortie
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialiser le service.

        Args:
            db: Instance de base de données MongoDB.
        """
        self.db = db

    async def get_user(self, user_id: ObjectId) -> dict | None:
        """Récupérer les informations d'un utilisateur.

        Args:
            user_id: Identifiant de l'utilisateur.

        Returns:
            dict | None: Profil utilisateur ou None si non trouvé.
        """
        collection = self.db.users
        user_doc = await collection.find_one({"_id": user_id})
        return user_doc

    async def get_user_location(self, user_id: ObjectId) -> dict | None:
        """Récupérer la localisation d'un utilisateur.

        Args:
            user_id: Identifiant de l'utilisateur.

        Returns:
            dict | None: Champ `location` (GeoJSON Point) ou None.
        """
        collection = self.db.users
        user_doc = await collection.find_one({"_id": user_id}, {"_id": 1, "location": 1})
        return (user_doc or {}).get("location")

    async def set_user_location(
        self, user_id: ObjectId, location_input: UserLocationIn
    ) -> UpdateResult:
        """Définir la localisation d'un utilisateur.

        Args:
            user_id: Identifiant de l'utilisateur.
            location_input: Données de localisation à enregistrer.

        Returns:
            UpdateResult: Résultat de la mise à jour MongoDB.

        Raises:
            ValueError: Si les coordonnées ne peuvent pas être parsées.
        """
        # Parser et valider les coordonnées
        if location_input.position:
            lon, lat = parse_location_to_lon_lat(location_input.position)
        elif location_input.lat is not None and location_input.lon is not None:
            lat, lon = location_input.lat, location_input.lon
        else:
            raise ValueError("Either position or lat/lon must be provided")

        # Valider les bornes
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Coordinates out of valid range")

        # Créer l'objet GeoJSON Point
        geojson_location = {
            "type": "Point",
            "coordinates": [lon, lat],
        }

        # Mettre à jour en base
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
        """Récupérer la localisation formatée d'un utilisateur.

        Args:
            user_id: Identifiant de l'utilisateur.

        Returns:
            UserLocationOut | None: Localisation formatée ou None si pas de localisation.
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
        """Supprimer la localisation d'un utilisateur.

        Args:
            user_id: Identifiant de l'utilisateur.

        Returns:
            UpdateResult: Résultat de la mise à jour MongoDB.
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
        """Vérifier si un utilisateur existe.

        Args:
            user_id: Identifiant de l'utilisateur.

        Returns:
            bool: True si l'utilisateur existe, False sinon.
        """
        collection = self.db.users
        count = await collection.count_documents({"_id": user_id}, limit=1)
        return count > 0
