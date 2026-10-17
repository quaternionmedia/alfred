from os.path import join
from typing import Optional

from beanie import PydanticObjectId
from bson import ObjectId
from fastapi import Depends, HTTPException
from fastapi_crudrouter import MotorCRUDRouter

from alfred.config import DB_NAME, DB_URL, VIDEO_DIR

from ..models import UserRead as User
from ..models.render import (
    Render,
    RenderStatus,
    RenderUpdate,
    display_name_for,
    output_filename,
)
from ..utils.bucket import INVALID_ID, NOT_FOUND, generate_signed_url
from ..utils.db import get_client
from ..utils.destinations import DeliveryError, get_destination
from ..utils.encoding import QUALITIES, UnknownQuality, preset_for
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


def can_access(render: Render, user) -> bool:
    """Whether `user` may see and act on `render` (contract C6).

    Its owner -- `render.username`, the creating user's email -- or a
    superuser. A render stored without an owner is a superuser's alone:
    there is nobody else it can be attributed to.
    """
    if getattr(user, 'is_superuser', False):
        return True
    return render.username is not None and render.username == user.email


async def load_owned_render(store: RenderStore, item_id: str, user) -> Render:
    """As `load_render`, and 404 unless `user` may access it.

    404 rather than 403, so a caller cannot learn which ids exist.
    """
    render = await load_render(store, item_id)
    if not can_access(render, user):
        raise NOT_FOUND
    return render


def task_payload(render: Render) -> dict:
    """The worker's arguments for `render`, as plain JSON data (contract C7).

    These went over the broker as pickle: a beanie document's `Edl`, an
    `ObjectId`, a tuple. The serializer is JSON-only now, and anything it
    cannot encode would fail at `delay()`. So the EDL goes as a dict, which
    the worker parses back into an `Edl`, and the id as a string.

    Encoding travels as the name of a preset (C5), never as encoder options.
    """
    return dict(
        edl=render.edl.dict(),
        renderId=str(render.id),
        filename=render.filename,
        moviesize=[render.width or 1920, render.height or 1080],
        fps=render.fps or 30.0,
        quality=render.quality,
    )


# Fields the server writes. Whatever a client sends for them on POST /render
# is discarded: a request could otherwise arrive already "RENDERED", already
# delivered, or attributed to somebody else.
SERVER_OWNED = (
    'username',
    'filename',
    'display_name',
    'status',
    'progress',
    'error',
    'link',
    'destination',
)

# The largest frame a render may ask for, either way: 8K. Without a bound one
# request could ask the worker for a frame of any size, and the first thing
# the engine does is allocate it.
MAX_DIMENSION = 7680


def refuse_bad_request(render: Render) -> str:
    """422 for encoder options or a size out of range; else the preset name.

    `ffmpeg_params` and `bitrate` went onto ffmpeg's command line as sent
    (C5). They are refused rather than ignored, so a client relying on them
    finds out at once instead of getting a render encoded some other way.
    """
    supplied = [name for name in ('ffmpeg_params', 'bitrate') if getattr(render, name)]
    if supplied:
        raise HTTPException(
            status_code=422,
            detail=(
                f'{" and ".join(supplied)} cannot be set by a client; '
                f'choose a quality instead: {", ".join(QUALITIES)}'
            ),
        )
    for name, default in (('width', 1920), ('height', 1080)):
        value = getattr(render, name)
        if value is None:
            setattr(render, name, default)
        elif not 16 <= value <= MAX_DIMENSION:
            raise HTTPException(
                status_code=422,
                detail=f'{name} must be between 16 and {MAX_DIMENSION} pixels',
            )
    try:
        return preset_for(render.quality).name
    except UnknownQuality as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
            quality = refuse_bad_request(render)
            refuse_unrenderable(render.edl)
            for name in SERVER_OWNED:
                setattr(render, name, None)
            # The id is chosen here rather than by the insert, so the filename
            # that depends on it is written with the document instead of by a
            # second update a moment later.
            render.id = PydanticObjectId()
            render.username = user.email
            render.quality = quality
            # The id alone names the file. It was project, description, size,
            # quality, duration and a timestamp -- every part but the id taken
            # from the request, so a project called `../../x` became a write to
            # /x_...mp4 from the worker. (The id went in at all because two
            # renders of one project in the same second shared a file.) The
            # readable name is kept separately, sanitised, for downloads.
            render.filename = output_filename(render.id)
            render.display_name = display_name_for(render)
            await store.insert(render)
            queue(**task_payload(render))
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
            # A render stored before this change keeps its old composite
            # filename, which may carry anything its request did. It is
            # re-rendered under its id instead, and an old quality name (the
            # form flow saved `web` and `TV`) falls back to the default.
            changes = dict(
                filename=output_filename(render.id),
                display_name=render.display_name or display_name_for(render),
                quality=preset_for(render.quality, strict=False).name,
                status=None,
                progress=None,
                error=None,
            )
            await store.update(render.id, changes)
            for name, value in changes.items():
                setattr(render, name, value)
            queue(**task_payload(render))
            return str(render.id)

        @self.get('/{item_id}/status', response_model=RenderStatus)
        async def renderStatus(
            item_id: str,
            user: User = Depends(current_active_user),
            store: RenderStore = Depends(get_render_store),
        ):
            """# Render status

            Where a render has got to: `state` is one of `queued`,
            `rendering`, `rendered` or `failed`, and `error` says why when it
            is `failed`. `status` is the raw stored value, unchanged for
            clients that already read it.

            Anything waiting on a render had to fetch every render the caller
            could see and look for its own, and could not tell why one failed.
            """
            render = await load_owned_render(store, item_id, user)
            return RenderStatus.of(render)

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
