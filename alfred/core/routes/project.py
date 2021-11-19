from fastapi_crudrouter import MotorCRUDRouter
from ..models import Project, ProjectUpdate
from ..utils.db import get_client

class ProjectAPI(MotorCRUDRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, 
            schema = Project,
            client = get_client(),
            create_schema = Project,
            update_schema = ProjectUpdate,
        )
