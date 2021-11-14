from fastapi_users import models
from typing import Optional
from datetime import date
from odmantic import Model

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

class Template(Model):
    logic: dict
    fields: Optional[List]
    class Config:
        title = 'Template Project'

class TemplateUpdate(Template):
    logic: Optional[dict]
    fields: Optional[List]
