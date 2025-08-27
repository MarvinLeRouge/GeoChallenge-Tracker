# backend/app/core/bson_utils.py
# Helpers Pydantic v2 pour ObjectId + base model Mongo, avec JSON Schema propre pour OpenAPI.
from __future__ import annotations

from typing import Any, Optional
from bson import ObjectId
from pydantic import BaseModel, Field, ConfigDict, GetCoreSchemaHandler
from pydantic_core import core_schema
from pydantic.json_schema import JsonSchemaValue, GetJsonSchemaHandler


class PyObjectId(ObjectId):
    """ObjectId compatible Pydantic v2 et OpenAPI.

    Description:
        Étend `bson.ObjectId` avec les hooks Pydantic v2 pour:
        - accepter une chaîne hex de 24 caractères **ou** un `ObjectId`
        - sérialiser en chaîne dans les réponses
        - exposer un schéma OpenAPI clair (`type: string`, `format: objectid`)

    """

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        """Hook Pydantic v2: schéma de validation/serialization côté core.

        Description:
            Définit l’acceptation JSON (str) et Python (validator), avec sérialisation en str.

        Args:
            source_type (Any): Type source vu par Pydantic.
            handler (GetCoreSchemaHandler): Gestionnaire de schémas core.

        Returns:
            core_schema.CoreSchema: Schéma de validation/serialization.
        """
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.with_info_plain_validator_function(cls._validate),
            serialization=core_schema.plain_serializer_function_ser_schema(str),
        )

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema_obj: core_schema.CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        """Hook Pydantic v2: schéma JSON pour OpenAPI.

        Description:
            Génère un schéma JSON propre (string + pattern ObjectId) afin d’éviter les warnings
            et d’améliorer l’UX Swagger.

        Args:
            core_schema_obj (core_schema.CoreSchema): Schéma core.
            handler (GetJsonSchemaHandler): Gestionnaire de schémas JSON.

        Returns:
            JsonSchemaValue: Schéma JSON compatible OpenAPI.
        """
        json_schema = handler(core_schema_obj)
        # Keep it simple and explicit for Swagger UI
        json_schema.update({
            "type": "string",
            "format": "objectid",
            "pattern": "^[a-fA-F0-9]{24}$",
            "examples": ["507f1f77bcf86cd799439011"]
        })
        return json_schema

    @classmethod
    def _validate(cls, v: Any, info: core_schema.ValidationInfo) -> ObjectId:
        """Valide et convertit en ObjectId.

        Description:
            Accepte un `ObjectId` déjà typé ou une chaîne valide (24 hex). Lève `TypeError` sinon.

        Args:
            v (Any): Valeur à convertir.
            info (core_schema.ValidationInfo): Contexte de validation Pydantic.

        Returns:
            ObjectId: Instance validée.

        Raises:
            TypeError: Si la valeur n’est pas un ObjectId valide.
        """
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise TypeError(f"Invalid ObjectId: {v!r}")


class MongoBaseModel(BaseModel):
    """BaseModel Pydantic pour documents Mongo.

    Description:
        - Champ `_id` exposé via l’alias `id` (type `PyObjectId`)
        - Encoders/Config adaptés à Mongo (aliases, `arbitrary_types_allowed`, encodage ObjectId->str)
    """
    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )

# Convenience helpers
def dump_mongo(model: BaseModel, *, exclude_none: bool = True) -> dict:
    """Dump d’un modèle pour Mongo (dict).

    Description:
        Sérialise en dict prêt pour Mongo, en respectant les alias (`_id`) et
        en excluant les champs `None` par défaut.

    Args:
        model (BaseModel): Modèle Pydantic à sérialiser.
        exclude_none (bool): Exclure les champs None.

    Returns:
        dict: Document sérialisé prêt à insérer/mettre à jour.
    """
    return model.model_dump(by_alias=True, exclude_none=exclude_none)

def dump_mongo_json(model: BaseModel, *, exclude_none: bool = True) -> str:
    """Dump d’un modèle pour Mongo (JSON string).

    Description:
        Équivalent JSON de `dump_mongo`, utile pour du logging/debug.

    Args:
        model (BaseModel): Modèle Pydantic à sérialiser.
        exclude_none (bool): Exclure les champs None.

    Returns:
        str: Chaîne JSON du document sérialisé.
    """
    return model.model_dump_json(by_alias=True, exclude_none=exclude_none)
