from datetime import datetime
from typing import Optional

from beanie import PydanticObjectId
from fastapi_users import schemas
from pydantic import field_validator


class UserRead(schemas.BaseUser[PydanticObjectId]):
    # A 24-hex string on the wire, under real auth and the bypass alike
    # (tests/unit/test_user_serialisation.py).
    id: str
    first_name: str
    birthdate: Optional[datetime] = None
    address: Optional[str] = None

    @field_validator('id', mode='before')
    @classmethod
    def _identifier_as_string(cls, value):
        """The stored ObjectId, or the dev route's string, as a string."""
        return str(value) if value is not None else value


class UserCreate(schemas.BaseUserCreate):
    first_name: str
    birthdate: Optional[datetime] = None
    address: Optional[str] = None


class UserUpdate(schemas.BaseUserUpdate):
    first_name: Optional[str] = None
    birthdate: Optional[datetime] = None
    address: Optional[str] = None
