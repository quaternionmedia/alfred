from fastapi_crudrouter import MotorCRUDRouter
from ..models import Project, ProjectUpdate
from ..utils.db import get_client
from alfred.config import DB_URL, DB_NAME


class ProjectAPI(MotorCRUDRouter):
    def __init__(
        self,
        schema=Project,
        create_schema=Project,
        update_schema=ProjectUpdate,
        db_name=DB_NAME,
        *args,
        **kwargs,
    ):
        self.schema = schema
        self.create_schema = (create_schema,)
        self.update_schema = (update_schema,)
        self.db_name = db_name
        self.client = get_client()
        # self.db = self.client[DB_NAME]
        super().__init__(
            *args,
            **kwargs,
            schema=schema,
            client=self.client,
            create_schema=create_schema,
            update_schema=update_schema,
            db_url=DB_URL,
            database=DB_NAME,
        )
