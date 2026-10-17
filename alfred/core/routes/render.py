from os.path import join
from typing import Optional

from beanie import PydanticObjectId
from bson import ObjectId
from fastapi import Depends, HTTPException
from fastapi_crudrouter import MotorCRUDRouter
from otto.getdata import timestr

from alfred.config import DB_NAME, DB_URL, VIDEO_DIR

from ..models import UserRead as User
from ..models.render import Render, RenderUpdate
from ..utils.bucket import INVALID_ID, NOT_FOUND, generate_signed_url
from ..utils.db import get_client
from ..utils.destinations import DeliveryError, get_destination
from ..utils.media import RefusedEdl, check_edl
from ..utils.tasks import renderRemote
from .templates import TEMPLATE_NAMES
from .users import current_active_superuser, current_active_user


class RenderStore:
    """The render collection, as the routes use it.

    The routes reach MongoDB only through this, for two reasons: they can be
    exercised without a database (a dependency override swaps in an in-memory
    store; see tests/unit/render_harness.py), and the queries deciding what a
    caller can reach live in one place.
    """

    async def get(self, render_id) -> Optional[Render]:
        return await Render.get(PydanticObjectId(render_id))

    async def insert(self, render: Render) -> None:
        await render.insert()

    async def update(self, render_id, fields: dict) -> None:
        await Render.find_one({'_id': PydanticObjectId(render_id)}).update(
            {'$set': fields}
        )


def get_render_store() -> RenderStore:
    return RenderStore()


def get_render_queue():
    """How a render reaches the worker: Celery's `delay`.

    A dependency so that a test can record what would be sent instead.
    """
    return renderRemote.delay


async def load_render(store: RenderStore, item_id: str) -> Render:
    """The render with this id: 422 if the id is malformed, 404 if absent."""
    if not ObjectId.is_valid(item_id):
        raise INVALID_ID
    render = await store.get(item_id)
    if render is None:
        raise NOT_FOUND
    return render


def task_payload(render: Render, filename: str) -> dict:
    """The worker's arguments for `render`, as plain JSON data (contract C7).

    These went over the broker as pickle: a beanie document's `Edl`, an
    `ObjectId`, a tuple. The serializer is JSON-only now, and anything it
    cannot encode would fail at `delay()`. So the EDL goes as a dict, which
    the worker parses back into an `Edl`, and the id as a string.
    """
    return dict(
        edl=render.edl.dict(),
        renderId=str(render.id),
        filename=filename,
        moviesize=[render.width, render.height],
        fps=render.fps,
        bitrate=render.bitrate,
        ffmpeg_params=render.ffmpeg_params,
    )


def refuse_unrenderable(edl):
    """422 for an EDL the engine should not be handed; nothing otherwise.

    Before anything is stored or queued, so a refused request leaves no trace:
    no render document, no job, no failed render to explain later. The
    detail names the clip and the reason (see `utils.media`).

    Covers the media contract (C4) -- library paths and allowed URLs only --
    and the template allowlist, which until now only the single-template
    preview checked. Everything else reached `getattr(otto.templates, name)`
    with a name from the request, and otto's template namespace holds helpers
    such as `rgbToDec` beside the templates.
    """
    try:
        check_edl(edl, TEMPLATE_NAMES)
    except RefusedEdl as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class RenderAPI(MotorCRUDRouter):
    def __init__(
        self,
        schema=Render,
        create_schema=Render,
        update_schema=RenderUpdate,
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

        @self.post('', *args, **kwargs)
        async def queueRender(
            render: Render,
            user: User = Depends(current_active_user),
            store: RenderStore = Depends(get_render_store),
            queue=Depends(get_render_queue),
        ):
            refuse_unrenderable(render.edl)
            render.username = user.email
            # The id is chosen here rather than by the insert, so the filename
            # that depends on it is written with the document instead of by a
            # second update a moment later.
            render.id = PydanticObjectId()

            # The render's own id goes in the filename, because everything else
            # in it can repeat. It was project, description, size, quality,
            # duration and a second-resolution timestamp -- so two renders of
            # the same project in the same second produced the same filename
            # and the second silently overwrote the first's output. Three
            # concurrent renders in the e2e suite collided on exactly that and
            # ended up sharing one file, each reporting success.
            ts = timestr()
            filename = f'{render.project}{"_" + render.description if render.description else ""}_{render.width}x{render.height}{"_" + render.quality if render.quality else ""}_{render.edl.duration}s_{ts}_{render.id}.mp4'  # noqa: E501
            render.filename = filename
            await store.insert(render)
            queue(**task_payload(render, filename))
            return str(render.id)

        @self.post('/rerender/{id}', *args, **kwargs)
        async def reQueueRender(
            id: str,
            user: User = Depends(current_active_superuser),
            store: RenderStore = Depends(get_render_store),
            queue=Depends(get_render_queue),
        ):
            # A malformed id was a 500 from `ObjectId(id)`, and a missing one
            # a 500 from reading `.edl` off None.
            render = await load_render(store, id)
            # A stored EDL is checked like a new one: it may predate the media
            # contract, and re-queueing it must not reopen what that closed.
            refuse_unrenderable(render.edl)
            queue(**task_payload(render, render.filename))
            return str(render.id)

        @self.post('/{item_id}/deliver', *args, **kwargs)
        async def deliverRender(
            item_id: str,
            destination: Optional[str] = None,
            user: User = Depends(current_active_user),
        ):
            """# Deliver a render

            Sends a finished render to a destination and records where it went.

            The destination defaults to the project's saved one, then to
            `local` -- so a server with no cloud account still has somewhere to
            put a render, which the previous single path to a Google bucket did
            not allow.
            """
            if not ObjectId.is_valid(item_id):
                raise INVALID_ID
            render = await self.schema.find_one({'_id': ObjectId(item_id)})
            if render is None:
                raise NOT_FOUND
            if not render.filename:
                raise HTTPException(
                    status_code=409,
                    detail='That render has no output file yet',
                )

            chosen = destination or render.destination
            try:
                # VIDEO_DIR, not DATA_DIR. The Celery task writes finished
                # renders to videos/; this looked in data/ and would have
                # reported every render missing.
                delivery = get_destination(chosen).deliver(
                    join(VIDEO_DIR, render.filename)
                )
            except DeliveryError as exc:
                # 502, not 500: the render is fine and the request was valid.
                # Something downstream would not take it, and that is worth
                # retrying, which a 500 does not suggest.
                raise HTTPException(status_code=502, detail=str(exc)) from exc

            render.destination = delivery.destination
            render.link = delivery.location
            await render.save()
            return delivery

        @self.get('/{item_id}', *args, **kwargs)
        async def getSignedRenderLink(
            item_id: str, user: User = Depends(current_active_user)
        ):
            return generate_signed_url(item_id)

        @self.get('', *args, **kwargs)
        async def get_all_renders(skip: Optional[int] = 0, limit: Optional[int] = 100):
            return await self.schema.find_all().skip(skip).sort('-_id').to_list(limit)
