from typing import List, Optional

from fastapi import FastAPI, Query
from models import Template, TemplateUpdate
from fastapi_crudrouter import MotorCRUDRouter
from db import client

app = FastAPI()

templates = MotorCRUDRouter(
    schema=Template,
    client=client,
    create_schema=Template,
    update_schema=TemplateUpdate
    )

app.include_router(templates)#, tags=['template'])
