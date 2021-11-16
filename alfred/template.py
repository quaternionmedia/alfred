from fastapi import Depends
from fastapi_crudrouter import MotorCRUDRouter
from fastapi_crudrouter.core import NOT_FOUND
from models import Template, TemplateUpdate
from typing import Optional

from users import fastapi_users, current_active_user
from db import client
from config import DB_URL, DB_NAME
from users import fastapi_users, current_active_user


templateAPI = MotorCRUDRouter(
    schema = Template,
    client = client,
    # db_url = DB_URL,
    # database = DB_NAME,
    create_schema = Template,
    update_schema = TemplateUpdate
)
