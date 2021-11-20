from fastapi_crudrouter import MotorCRUDRouter
from ..models import Project, ProjectUpdate
from ..utils.db import get_client
from alfred.config import DB_URL, DB_NAME
from typing import Optional

class ProjectAPI(MotorCRUDRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, 
            schema = Project,
            client = get_client(),
            create_schema = Project,
            update_schema = ProjectUpdate,
            database = DB_NAME,
        )

        @self.get('')
        async def get_all_projects(skip: Optional[int] = 0, limit: Optional[int] = 100):
            db = get_db()
            print('getting all projects', skip, limit)
            return deOid(await db.Project.find({}, projection=['_id', 'name']).skip(skip).to_list(limit))