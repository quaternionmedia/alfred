from typing import Optional

from beanie.odm.operators.update.general import Set
from bson import ObjectId
from fastapi import Depends, HTTPException
from fastapi_crudrouter import MotorCRUDRouter
from otto.models import Edl
from pydantic import BaseModel

from alfred.config import DB_NAME, DB_URL

from ..models import Project, ProjectUpdate, RenderSettings
from ..utils.bucket import INVALID_ID, NOT_FOUND, fresh
from ..utils.captions import TooManyCaptions, checked_captions
from ..utils.db import User, get_client
from ..utils.ownership import owner_filter, owner_key
from .users import current_active_user

# Where a project keeps its owner key. Every query below scopes itself with
# `owner_filter(user, OWNER)`, the same rule the renders use, so "can I see it
# in the list" and "can I open it" cannot disagree -- here or across the two.
OWNER = 'owner'


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

            Only those, at the database too. It loaded the project, changed
            the fields and saved the whole document back, so a timeline saved
            in between was overwritten with the one this request had loaded.
            """
            project = await self._owned(item_id, user)

            patch = settings.dict(exclude_none=True)
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

            The clips, and nothing else.

            The editor had a save button that posted to `/edl`, which is not a
            route on this server and never has been -- so the timeline could
            not be persisted at all, and every edit was lost on reload. The
            obvious alternative, `PUT /project/{id}`, replaces the whole
            document: a partial body arrives with `logic` unset, `logic` is
            required, and the project is left unreadable. That is not
            hypothetical; it happened, and every subsequent GET answered 500.

            So this writes one field, for the same reason `/settings` does.

            Each clip is validated against otto's `Clip` and stored as sent
            (contract M4): the fields the editor set and no others, so a
            saved timeline renders exactly as the editor renders it. It used
            to come back with otto's defaults written in -- `fadeIn: 1` and
            `fadeOut: 1` on every clip -- which rendered as fades nobody
            chose. The answer is the project as stored.
            """
            project = await self._owned(item_id, user)

            await project.set({'edl': edl})
            return await self._as_stored(project)

    async def _as_stored(self, project):
        """`project` read back after a write: what the next GET will answer.

        Not the object just written. beanie merges the stored document into
        it field by field after an update, which marks the EDL's `duration`
        as sent even where it was not, and the answer would say `null` for
        something the project does not hold.
        """
        return await self.schema.get(project.id)

    async def _owned(self, item_id, user):
        """The project `item_id`, if `user` may touch it; otherwise 404.

        Every single-project route goes through here. The id is checked
        before the query so a malformed one answers 422 -- "that is not an
        id" -- rather than the 404 reserved for "no project of yours".
        """
        if not ObjectId.is_valid(item_id):
            # A copy per raise: re-raising the shared instance grows its
            # traceback with every request (see `bucket.fresh`).
            raise fresh(INVALID_ID)
        project = await self.schema.find_one(
            {'_id': ObjectId(item_id), **owner_filter(user, OWNER)}
        )
        if project is None:
            raise fresh(NOT_FOUND)
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
            # All assigned by the server. A client-chosen id could collide
            # with a project the caller cannot see, and the duplicate-key
            # error would confirm that it exists. Only the demo generator marks
            # a project as the account's demo; a second mark would collide
            # with the real one on its unique index.
            model.id = None
            model.owner = owner_key(user)
            model.demo = None
            # A transcription is the server's record; captions sent with a new
            # project are held to the rules their own route applies.
            model.captions_job = None
            try:
                model.captions = (
                    checked_captions(model.captions) if model.captions else None
                )
            except TooManyCaptions as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
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
            # project out of its own owner's reach. `demo` likewise: a body
            # could otherwise mark any project as the account's demo, or unmark
            # the real one.
            model.owner = project.owner
            model.demo = project.demo
            # Likewise the captions: they have a route of their own, which
            # checks them as a list, and the job is the server's record of a
            # transcription. Written here, a body that left them out -- every
            # client that saves a project it read before captions existed --
            # would wipe them.
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
            # The deleted project, as the route documents. The generated
            # version returned the driver's DeleteResult, which is not a
            # Project, so every successful delete answered 500.
            return project

        return route
