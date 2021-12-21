from typing import List, Optional

from fastapi import FastAPI, Query
from alfred.core.models import Project, ProjectUpdate
from fastapi_crudrouter import MotorCRUDRouter
from alfred.core.utils import get_client
from alfred.config import DB_NAME
app = FastAPI()

projects = MotorCRUDRouter(
    schema=Project,
    client=get_client(),
    database=DB_NAME,
    create_schema=Project,
    update_schema=ProjectUpdate
    )

app.include_router(projects)#, tags=['template'])

print('testing api', DB_NAME)