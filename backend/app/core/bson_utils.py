# app/core/bson_utils.py
# Pydantic v2–ready helpers for MongoDB
from __future__ import annotations

from typing import Any, Optional
from bson import ObjectId
from pydantic import BaseModel, Field, ConfigDict
from pydantic_core import core_schema


class PyObjectId(ObjectId):
    """Custom class for using MongoDB ObjectIds with Pydantic v2."""

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler) -> core_schema.CoreSchema:
        # Accept both JSON strings and python ObjectId, and serialize to str
        return core_schema.json_or_python_schema(
            python_schema=core_schema.with_info_plain_validator_function(cls._validate),
            json_schema=core_schema.with_info_plain_validator_function(cls._validate),
            serialization=core_schema.plain_serializer_function_ser_schema(str),
        )

    @classmethod
    def _validate(cls, v: Any, info: core_schema.ValidationInfo) -> ObjectId:
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise TypeError(f"Invalid ObjectId: {v}")


class MongoBaseModel(BaseModel):
    """Base model for MongoDB documents with a standard `_id` alias."""

    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    # One place to keep all shared Pydantic v2 config
    model_config = ConfigDict(
        populate_by_name=True,           # allow dumping/feeding by aliases
        arbitrary_types_allowed=True,    # allow PyObjectId
        json_encoders={PyObjectId: str}, # serialize ObjectId -> str
    )


# Convenience helpers
def dump_mongo(model: BaseModel, *, exclude_none: bool = True) -> dict:
    """Dump a model using Mongo-friendly options (aliases, no nulls)."""
    return model.model_dump(by_alias=True, exclude_none=exclude_none)

def dump_mongo_json(model: BaseModel, *, exclude_none: bool = True) -> str:
    """JSON string version of `dump_mongo`."""
    return model.model_dump_json(by_alias=True, exclude_none=exclude_none)
