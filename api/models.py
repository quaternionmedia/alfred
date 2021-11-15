from fastapi_users import models
from typing import Optional
from datetime import date

class User(models.BaseUser):
    first_name: str
    birthdate: Optional[date]


class UserCreate(models.BaseUserCreate):
    first_name: str
    birthdate: Optional[date]


class UserUpdate(models.BaseUserUpdate):
    first_name: str
    birthdate: Optional[date]


class UserDB(User, models.BaseUserDB):
    pass