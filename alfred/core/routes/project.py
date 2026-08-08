from typing import Optional

from bson import ObjectId
from fastapi import Depends
from fastapi_crudrouter import MotorCRUDRouter
from pydantic import BaseModel

from ..models import Project, ProjectUpdate, RenderSettings
from ..models import UserRead as User
from ..utils.bucket import INVALID_ID, NOT_FOUND
from ..utils.db import get_client
from .users import current_active_user
from alfred.config import DB_URL, DB_NAME


class ProjectSettings(BaseModel):
    """The subset of a project the flow stages may write.

    Deliberately not `ProjectUpdate`: this route must not be a way to replace
    a project's clips or logic. Naming the writable fields keeps "remember my
    render size" from becoming an arbitrary write to the document.
    """

    render_settings: Optional[RenderSettings]
    destination: Optional[str]


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

        @self.put('/{item_id}/settings', *args, **kwargs)
        async def saveProjectSettings(
            item_id: str,
            settings: ProjectSettings,
            user: User = Depends(current_active_user),
        ):
            """# Save a project's flow settings

            The render size and destination a project should default to, so
            reopening it brings the flow back rather than asking again.

            A separate route rather than a PUT to the project, because the
            crud router's update replaces the whole document -- a partial body
            arrives with `logic` unset, and `logic` is required, so saving one
            preference meant sending the entire project back and racing anyone
            else editing it. This writes only the fields it is given.
            """
            if not ObjectId.is_valid(item_id):
                raise INVALID_ID
            project = await self.schema.find_one({'_id': ObjectId(item_id)})
            if project is None:
                raise NOT_FOUND

            patch = settings.dict(exclude_none=True)
            for field, value in patch.items():
                setattr(project, field, value)
            await project.save()
            return project
