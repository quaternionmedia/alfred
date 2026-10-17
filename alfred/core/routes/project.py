from typing import Optional

from beanie.odm.operators.update.general import Set
from bson import ObjectId
from fastapi import Depends
from fastapi_crudrouter import MotorCRUDRouter
from otto.models import Edl
from pydantic import BaseModel

from alfred.config import DB_NAME, DB_URL

from ..models import Project, ProjectUpdate, RenderSettings
from ..utils.bucket import INVALID_ID, NOT_FOUND
from ..utils.db import User, get_client
from .users import current_active_user


def visible_to(user):
    """The query that restricts projects to the ones `user` may touch.

    Superusers see everything, including projects stored before ownership
    existed. Everybody else sees the projects they own, and a project without
    an owner matches no email, so it is superuser-only by construction rather
    than by a separate rule someone could forget.

    One function for listing and for every single-project route, so "can I
    see it in the list" and "can I open it" cannot disagree.
    """
    if user.is_superuser:
        return {}
    return {'owner': user.email}


class ProjectSettings(BaseModel):
    """The subset of a project the flow stages may write.

    Deliberately not `ProjectUpdate`: this route must not be a way to replace
    a project's clips or logic. Naming the writable fields keeps "remember my
    render size" from becoming an arbitrary write to the document.
    """

    render_settings: Optional[RenderSettings]
    destination: Optional[str]


class ProjectAPI(MotorCRUDRouter):
    """Projects, each visible only to its owner and to superusers.

    The crud router's generated routes knew nothing about who was asking: any
    authenticated account could list, read, overwrite or delete any project,
    and `DELETE /project` emptied the collection for everybody. Each generated
    route is replaced here with one that scopes its query to the caller, and
    the bulk delete is not mounted at all.

    A project the caller may not see answers 404, exactly as one that does not
    exist. 403 would confirm that the id is real, which is information about
    somebody else's work.
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
            # No `DELETE /project`. One request from any account deleted every
            # project in the database; there is no ownership-scoped version of
            # that worth having, and a superuser who means it has the shell.
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

            A separate route rather than a PUT to the project, because the
            crud router's update replaces the whole document -- a partial body
            arrives with `logic` unset, and `logic` is required, so saving one
            preference meant sending the entire project back and racing anyone
            else editing it. This writes only the fields it is given.
            """
            project = await self._owned(item_id, user)

            patch = settings.dict(exclude_none=True)
            for field, value in patch.items():
                setattr(project, field, value)
            await project.save()
            return project

        @self.put('/{item_id}/timeline', *args, **kwargs)
        async def saveProjectTimeline(
            item_id: str,
            edl: Edl,
            user: User = Depends(current_active_user),
        ):
            """# Save a project's timeline

            The clips, and nothing else.

            The editor had a save button that posted to `/edl`, which is not a
            route on this server and never has been -- so the timeline could
            not be persisted at all, and every edit was lost on reload. The
            obvious alternative, `PUT /project/{id}`, replaces the whole
            document: a partial body arrives with `logic` unset, `logic` is
            required, and the project is left unreadable. That is not
            hypothetical; it happened, and every subsequent GET answered 500.

            So this writes one field, for the same reason `/settings` does.
            """
            project = await self._owned(item_id, user)

            project.edl = edl
            await project.save()
            return project

    async def _owned(self, item_id, user):
        """The project `item_id`, if `user` may touch it; otherwise 404.

        Every single-project route goes through here. The id is checked
        before the query so a malformed one answers 422 -- "that is not an
        id" -- rather than the 404 reserved for "no project of yours".
        """
        if not ObjectId.is_valid(item_id):
            raise INVALID_ID
        project = await self.schema.find_one(
            {'_id': ObjectId(item_id), **visible_to(user)}
        )
        if project is None:
            raise NOT_FOUND
        return project

    # The generated routes, scoped to the caller. The crud router builds each
    # route from these factories, so overriding them replaces the routes at
    # their original paths and methods -- no second registration that the
    # first would shadow.

    def _get_all(self, *args, **kwargs):
        async def route(
            pagination: dict = self.pagination,
            user: User = Depends(current_active_user),
        ):
            skip, limit = pagination.get('skip'), pagination.get('limit')
            query = self.schema.find(visible_to(user)).skip(skip or 0)
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
            # Both assigned by the server. A client-chosen id could collide
            # with a project the caller cannot see, and the duplicate-key
            # error would confirm that it exists.
            model.id = None
            model.owner = user.email
            return await model.create()

        return route

    def _update(self, *args, **kwargs):
        async def route(
            item_id: str,
            model: self.update_schema,  # type: ignore
            user: User = Depends(current_active_user),
        ):
            project = await self._owned(item_id, user)
            # This route writes every field of the body, present or not. Left
            # as sent, `owner` would be whatever the caller claimed -- or null,
            # for any body that simply omitted it, which would orphan the
            # project out of its own owner's reach.
            model.owner = project.owner
            del model.id
            return await project.update(Set(model))

        return route

    def _delete_one(self, *args, **kwargs):
        async def route(item_id: str, user: User = Depends(current_active_user)):
            project = await self._owned(item_id, user)
            await project.delete()
            # The deleted project, as the route documents. The generated
            # version returned the driver's DeleteResult, which is not a
            # Project, so every successful delete answered 500.
            return project

        return route
