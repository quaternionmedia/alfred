from fastapi_crudrouter import MotorCRUDRouter
from ..models import Project, ProjectUpdate
from ..utils.db import get_client, deOid
from alfred.config import DB_URL, DB_NAME
from typing import Optional

class ProjectAPI(MotorCRUDRouter):
    def __init__(self, *args, **kwargs):
        self.client = get_client()
        super().__init__(*args, **kwargs, 
            schema = Project,
            client = self.client,
            create_schema = Project,
            update_schema = ProjectUpdate,
            database = DB_NAME,
        )

        @self.get('')
        async def get_all_projects(skip: Optional[int] = 0, limit: Optional[int] = 100):
            return deOid(await self.client[DB_NAME].Project.find({}, projection=['_id', 'name']).skip(skip).to_list(limit))
