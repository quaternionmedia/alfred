from fastapi_crudrouter import MotorCRUDRouter
from ..models import Project, ProjectUpdate
from ..utils import client

projectAPI = MotorCRUDRouter(
    schema = Project,
    client = client,
    create_schema = Project,
    update_schema = ProjectUpdate
)