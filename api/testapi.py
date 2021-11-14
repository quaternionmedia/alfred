from typing import List, Optional

from fastapi import FastAPI, Query
from models import Template, TemplateUpdate
from fastapi_crudrouter import MotorCRUDRouter

app = FastAPI()

templates = MotorCRUDRouter(
    schema=Template,
    db_url='mongodb://localhost',
    database='alfred',
    create_schema=Template,
    update_schema=TemplateUpdate
    )

app.include_router(templates)#, tags=['template'])

