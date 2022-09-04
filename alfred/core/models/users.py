from typing import Optional
from fastapi_users import schemas
from beanie import PydanticObjectId
from datetime import datetime


class UserRead(schemas.BaseUser[PydanticObjectId]):
    first_name: str
    birthdate: Optional[datetime]
    address: Optional[str]


class UserCreate(schemas.BaseUserCreate):
    first_name: str
    birthdate: Optional[datetime]
    address: Optional[str]


class UserUpdate(schemas.BaseUserUpdate):
    first_name: Optional[str]
    birthdate: Optional[datetime]
    address: Optional[str]
