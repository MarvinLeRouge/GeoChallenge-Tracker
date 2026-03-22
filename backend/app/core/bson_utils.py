# backend/app/core/bson_utils.py
# Pydantic v2 helpers for ObjectId and a Mongo base model, with a clean JSON Schema for OpenAPI.
from __future__ import annotations

from typing import Any

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, GetCoreSchemaHandler
from pydantic.json_schema import GetJsonSchemaHandler, JsonSchemaValue
from pydantic_core import core_schema


class PyObjectId(ObjectId):
    """ObjectId compatible with Pydantic v2 and OpenAPI.

    Description:
        Extends `bson.ObjectId` with Pydantic v2 hooks to:
        - accept a 24-character hex string **or** an existing `ObjectId`
        - serialize as a string in responses
        - expose a clean OpenAPI schema (`type: string`, `format: objectid`)

    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        """Pydantic v2 hook: core-side validation/serialization schema.

        Description:
            Defines JSON acceptance (str) and Python validation, with serialization to str.

        Args:
            source_type (Any): Source type as seen by Pydantic.
            handler (GetCoreSchemaHandler): Core schema handler.

        Returns:
            core_schema.CoreSchema: Validation/serialization schema.
        """
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.with_info_plain_validator_function(cls._validate),
            serialization=core_schema.plain_serializer_function_ser_schema(str),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema_obj: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """Pydantic v2 hook: JSON schema for OpenAPI.

        Description:
            Generates a clean JSON schema (string + ObjectId pattern) to avoid warnings
            and improve the Swagger UI experience.

        Args:
            core_schema_obj (core_schema.CoreSchema): Core schema.
            handler (GetJsonSchemaHandler): JSON schema handler.

        Returns:
            JsonSchemaValue: OpenAPI-compatible JSON schema.
        """
        json_schema = handler(core_schema_obj)
        # Keep it simple and explicit for Swagger UI
        json_schema.update(
            {
                "type": "string",
                "format": "objectid",
                "pattern": "^[a-fA-F0-9]{24}$",
                "examples": ["507f1f77bcf86cd799439011"],
            }
        )
        return json_schema

    @classmethod
    def _validate(cls, v: Any, info: core_schema.ValidationInfo) -> ObjectId:
        """Validates and converts a value to ObjectId.

        Description:
            Accepts an already-typed `ObjectId` or a valid 24-hex string. Raises `TypeError` otherwise.

        Args:
            v (Any): Value to convert.
            info (core_schema.ValidationInfo): Pydantic validation context.

        Returns:
            ObjectId: Validated instance.

        Raises:
            TypeError: If the value is not a valid ObjectId.
        """
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise TypeError(f"Invalid ObjectId: {v!r}")


class MongoBaseModel(BaseModel):
    """Pydantic BaseModel for Mongo documents.

    Description:
        - The `_id` field is exposed via the `id` alias (type `PyObjectId`)
        - Encoders/config adapted for Mongo (aliases, `arbitrary_types_allowed`, ObjectId->str encoding)
    """

    id: PyObjectId | None = Field(default=None, alias="_id")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )


# Convenience helpers
def dump_mongo(model: BaseModel, *, exclude_none: bool = True) -> dict:
    """Dumps a model for Mongo (dict).

    Description:
        Serializes to a dict ready for Mongo, respecting aliases (`_id`) and
        excluding `None` fields by default.

    Args:
        model (BaseModel): Pydantic model to serialize.
        exclude_none (bool): Exclude None fields.

    Returns:
        dict: Serialized document ready to insert or update.
    """
    return model.model_dump(by_alias=True, exclude_none=exclude_none)


def dump_mongo_json(model: BaseModel, *, exclude_none: bool = True) -> str:
    """Dumps a model for Mongo (JSON string).

    Description:
        JSON equivalent of `dump_mongo`, useful for logging/debugging.

    Args:
        model (BaseModel): Pydantic model to serialize.
        exclude_none (bool): Exclude None fields.

    Returns:
        str: JSON string of the serialized document.
    """
    return model.model_dump_json(by_alias=True, exclude_none=exclude_none)
