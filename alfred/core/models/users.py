from fastapi_users import models
from typing import Optional
from datetime import datetime


class User(models.BaseUser):
    first_name: str
    birthdate: Optional[datetime]
    address: Optional[str]


class UserCreate(models.BaseUserCreate):
    first_name: str
    birthdate: Optional[datetime]
    address: Optional[str]


class UserUpdate(models.BaseUserUpdate):
    first_name: Optional[str]
    birthdate: Optional[datetime]
    address: Optional[str]


class UserDB(User, models.BaseUserDB):
    pass
