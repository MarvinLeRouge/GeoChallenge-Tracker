# app/core/bson_utils.py
# Pydantic v2–ready helpers for MongoDB
from __future__ import annotations

from typing import Any, Optional
from bson import ObjectId
from pydantic import BaseModel, Field, ConfigDict, GetCoreSchemaHandler
from pydantic_core import core_schema
from pydantic.json_schema import JsonSchemaValue, GetJsonSchemaHandler


class PyObjectId(ObjectId):
    """Pydantic v2-compatible ObjectId with JSON schema support for OpenAPI."""

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        # Accept either a valid 24-hex string or an ObjectId instance; serialize as string
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.with_info_plain_validator_function(cls._validate),
            serialization=core_schema.plain_serializer_function_ser_schema(str),
        )

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema_obj: core_schema.CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        # Render as a string in OpenAPI to avoid "PlainValidatorFunctionSchema" errors
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
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise TypeError(f"Invalid ObjectId: {v!r}")


class MongoBaseModel(BaseModel):
    """Base class for MongoDB documents with Pydantic v2 config/encoders."""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={PyObjectId: str},
    )

# Convenience helpers
def dump_mongo(model: BaseModel, *, exclude_none: bool = True) -> dict:
    """Dump a model using Mongo-friendly options (aliases, no nulls)."""
    return model.model_dump(by_alias=True, exclude_none=exclude_none)

def dump_mongo_json(model: BaseModel, *, exclude_none: bool = True) -> str:
    """JSON string version of `dump_mongo`."""
    return model.model_dump_json(by_alias=True, exclude_none=exclude_none)
