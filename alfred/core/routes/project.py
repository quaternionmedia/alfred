from fastapi_crudrouter import MotorCRUDRouter
from ..models import Project, ProjectUpdate
from ..utils.db import get_client

projectAPI = MotorCRUDRouter(
    schema = Project,
    client = client,
    create_schema = Project,
    update_schema = ProjectUpdate
)