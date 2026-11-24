from typing import Optional

from beanie.odm.operators.update.general import Set
from bson import ObjectId
from fastapi import Depends
from fastapi_crudrouter import MotorCRUDRouter
from otto.models import Edl
from pydantic import BaseModel

from alfred.config import DB_NAME, DB_URL

from ..errors import Code, Refusal
from ..models import Project, ProjectUpdate, RenderSettings
from ..utils.bucket import INVALID_ID, NOT_FOUND, fresh
from ..utils.captions import (
    TooManyCaptions,
    checked_captions,
    project_style,
    style_to_store,
)
from ..utils.db import User, get_client
from ..utils.ownership import owner_filter, owner_key
from .users import current_active_user

# Where a project keeps its owner key; every query scopes with
# `owner_filter(user, OWNER)`, as the renders' do.
OWNER = 'owner'


class ProjectSettings(BaseModel):
    """The subset of a project the flow stages may write; not `ProjectUpdate`,
    so this route cannot replace a project's clips or logic."""

    render_settings: Optional[RenderSettings] = None
    destination: Optional[str] = None


class ProjectAPI(MotorCRUDRouter):
    """Projects, each visible only to its owner and to superusers.

    Each route the crud router generates is replaced by one scoped to the
    caller, and the bulk delete is not mounted. A project the caller may not
    see is a 404, never a 403, which would confirm the id.
    """

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
        super().__init__(
            *args,
            **kwargs,
            schema=schema,
            client=self.client,
            create_schema=create_schema,
            update_schema=update_schema,
            db_url=DB_URL,
            database=DB_NAME,
            # No `DELETE /project`: the bulk delete takes everybody's.
            delete_all_route=False,
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

            Writes only the fields given, at the database too, so it races no
            other save. `PUT /project/{id}` replaces the whole document.
            """
            project = await self._owned(item_id, user)

            patch = settings.model_dump(exclude_none=True)
            if patch:
                await project.set(patch)
            return await self._as_stored(project)

        @self.put('/{item_id}/timeline', *args, **kwargs)
        async def saveProjectTimeline(
            item_id: str,
            edl: Edl,
            user: User = Depends(current_active_user),
        ):
            """# Save a project's timeline

            The clips, and nothing else: one field, as `/settings` writes.

            Each clip is validated against otto's `Clip` and stored as sent
            (contract M4), with no defaults written in, so it renders as the
            editor shows it. The answer is the project as stored.
            """
            project = await self._owned(item_id, user)

            await project.set({'edl': edl})
            return await self._as_stored(project)

    async def _as_stored(self, project):
        """`project` read back after a write: what the next GET will answer.
        Not the written object, which beanie's merge leaves claiming fields
        the EDL was never sent."""
        return await self.schema.get(project.id)

    async def _owned(self, item_id, user):
        """The project `item_id`, if `user` may touch it; otherwise 404. A
        malformed id is a 422, not the 404 of "no project of yours"."""
        if not ObjectId.is_valid(item_id):
            # A copy per raise (`bucket.fresh`).
            raise fresh(INVALID_ID)
        project = await self.schema.find_one(
            {'_id': ObjectId(item_id), **owner_filter(user, OWNER)}
        )
        if project is None:
            raise fresh(NOT_FOUND)
        return project

    # The generated routes, scoped to the caller: overriding the factories
    # replaces each route in place, with nothing to shadow.

    def _get_all(self, *args, **kwargs):
        async def route(
            pagination: dict = self.pagination,
            user: User = Depends(current_active_user),
        ):
            skip, limit = pagination.get('skip'), pagination.get('limit')
            query = self.schema.find(owner_filter(user, OWNER)).skip(skip or 0)
            return await query.to_list(limit or 100)

        return route

    def _get_one(self, *args, **kwargs):
        async def route(item_id: str, user: User = Depends(current_active_user)):
            return await self._owned(item_id, user)

        return route

    def _create(self, *args, **kwargs):
        async def route(
            model: self.create_schema,  # type: ignore
            user: User = Depends(current_active_user),
        ):
            # Server-assigned: a client's id could confirm another's project
            # by colliding, and only the demo generator marks a demo.
            model.id = None
            model.owner = owner_key(user)
            model.demo = None
            # Captions held to their own route's rules; drawn only if the
            # style sent says so.
            model.captions_job = None
            try:
                model.captions = (
                    checked_captions(model.captions) if model.captions else None
                )
            except TooManyCaptions as exc:
                raise Refusal(Code.TOO_MANY_CAPTIONS, str(exc)) from exc
            if model.captions or model.caption_style is not None:
                model.caption_style = project_style(
                    style_to_store(model.caption_style, None)
                )
            return await model.create()

        return route

    def _update(self, *args, **kwargs):
        async def route(
            item_id: str,
            model: self.update_schema,  # type: ignore
            user: User = Depends(current_active_user),
        ):
            project = await self._owned(item_id, user)
            # Every field of the body is written, sent or not: keep the
            # server's own as stored.
            model.owner = project.owner
            model.demo = project.demo
            # Captions have their own route; a body without them must not wipe them.
            model.captions = project.captions
            model.caption_style = project.caption_style
            model.captions_job = project.captions_job
            del model.id
            await project.update(Set(model))
            return await self._as_stored(project)

        return route

    def _delete_one(self, *args, **kwargs):
        async def route(item_id: str, user: User = Depends(current_active_user)):
            project = await self._owned(item_id, user)
            await project.delete()
            # The deleted project, as documented; not the driver's DeleteResult.
            return project

        return route
