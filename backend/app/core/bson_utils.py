# backend/app/api/core/bson_utils.py

from pydantic import BaseModel, Field, EmailStr, GetCoreSchemaHandler
from pydantic_core import core_schema
from typing import Optional, List, Any
from bson import ObjectId

class PyObjectId(ObjectId):
    """Custom class for using MongoDB ObjectIds with Pydantic V2."""

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        return core_schema.json_or_python_schema(
            python_schema=core_schema.with_info_plain_validator_function(cls.validate),
            json_schema=core_schema.with_info_plain_validator_function(cls.validate),
            serialization=core_schema.plain_serializer_function_ser_schema(str),
        )

    @classmethod
    def validate(cls, v: Any, info: core_schema.ValidationInfo) -> ObjectId:
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise TypeError(f"Invalid ObjectId: {v}")

# Base générique à hériter pour tous les modèles liés à MongoDB
class MongoBaseModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id")
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}