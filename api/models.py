from fastapi_users import models
from pydantic import BaseModel
from odmantic import Model
from typing import Optional, List
from datetime import datetime
from beanie import Document

class User(models.BaseUser):
    first_name: str
    birthdate: Optional[datetime]


class UserCreate(models.BaseUserCreate):
    first_name: str
    birthdate: Optional[datetime]
    pass

class UserUpdate(models.BaseUserUpdate):
    first_name: Optional[str]
    birthdate: Optional[datetime]
    pass


class UserDB(User, models.BaseUserDB):
    pass

class Template(Document):
    logic: dict
    fields: Optional[List]
    class Config:
        title = 'Template Project'

class TemplateUpdate(Template):
    logic: Optional[dict]
    fields: Optional[List]
