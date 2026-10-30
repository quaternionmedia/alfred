from typing import Optional

from beanie import PydanticObjectId
from bson import ObjectId
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi_crudrouter import MotorCRUDRouter
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from alfred.config import DB_NAME, DB_URL

from ..errors import Code, Refusal
from ..models import UserRead as User
from ..models.render import (
    Render,
    RenderStatus,
    RenderUpdate,
    display_name_for,
    output_filename,
    render_state,
    safe_name,
)
from ..responses import PartialFileResponse
from ..utils.bucket import (
    INVALID_ID,
    NOT_FOUND,
    fresh,
    parse_reference,
    signed_url,
)
from ..utils.captions import (
    TooManyCaptions,
    checked_captions,
    timeline_end,
    with_captions,
)
from ..utils.db import get_client
from ..utils.destinations import (
    BucketDestination,
    Delivery,
    DeliveryError,
    LocalDestination,
    UnknownDestination,
    get_destination,
)
from ..utils.encoding import QUALITIES, UnknownQuality, preset_for
from ..utils.logger import failure_reason
from ..utils.media import RefusedEdl, check_edl, output_path
from ..utils.ownership import may_access, owner_filter, owner_key
from ..utils.signing import media_url
from ..utils.storage import remove_render_files
from ..utils.tasks import renderRemote
from .media import MediaAccess, media_access
from .templates import TEMPLATE_NAMES
from .users import current_active_user


class RenderStore:
    """The render collection, as the routes use it: their only way to MongoDB,
    so tests swap in a store of their own (tests/unit/render_harness.py)."""

    async def get(self, render_id) -> Optional[Render]:
        return await Render.get(PydanticObjectId(render_id))

    async def list(self, query: dict, skip: int, limit: int) -> list:
        """Newest first; the renders matching `query`, an `owner_filter`."""
        return await Render.find(query).sort('-_id').skip(skip).to_list(limit)

    async def insert(self, render: Render) -> None:
        await render.insert()

    async def update(self, render_id, fields: dict) -> None:
        await Render.find_one({'_id': PydanticObjectId(render_id)}).update(
            {'$set': fields}
        )

    async def delete(self, render: Render) -> None:
        await render.delete()


def get_render_store() -> RenderStore:
    return RenderStore()


def get_render_queue():
    """How a render reaches the worker: Celery's `delay`, or a test's stand-in."""
    return renderRemote.delay


async def load_render(store: RenderStore, item_id: str) -> Render:
    """The render with this id: 422 if the id is malformed, 404 if absent."""
    if not ObjectId.is_valid(item_id):
        raise fresh(INVALID_ID)
    render = await store.get(item_id)
    if render is None:
        raise fresh(NOT_FOUND)
    return render


def can_access(render: Render, user) -> bool:
    """Whether `user` may see and act on `render` (contract C6): its owner or
    a superuser; an ownerless render is a superuser's (docs/ownership.md)."""
    return may_access(render.username, user)


async def load_owned_render(store: RenderStore, item_id: str, user) -> Render:
    """As `load_render`, and 404 unless `user` may access it: never 403,
    which would confirm the id exists."""
    render = await load_render(store, item_id)
    if not can_access(render, user):
        raise fresh(NOT_FOUND)
    return render


def task_payload(render: Render) -> dict:
    """The worker's arguments for `render`, as plain JSON data (contract C7).

    Encoding goes as a preset's name (C5). Captions become textBox clips after
    the timeline's own, on top (K2), made again on every queueing.
    """
    moviesize = [render.width or 1920, render.height or 1080]
    edl = render.edl.model_dump()
    if render.captions:
        edl = with_captions(
            edl,
            render.captions,
            render.caption_style,
            moviesize,
            until=timeline_end(render.edl),
        )
    return dict(
        edl=edl,
        renderId=str(render.id),
        filename=render.filename,
        moviesize=moviesize,
        fps=render.fps or 30.0,
        quality=render.quality,
    )


def refuse_bad_captions(render: Render) -> None:
    """422 for more captions than a render may carry; otherwise put in order."""
    try:
        render.captions = checked_captions(render.captions) if render.captions else None
    except TooManyCaptions as exc:
        raise Refusal(Code.TOO_MANY_CAPTIONS, str(exc)) from exc


# Fields only the server writes; a client's values are discarded.
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

# 8K, either way: the engine allocates the frame first thing.
MAX_DIMENSION = 7680

# Every frame is the worker's time and disk.
MAX_FPS = 120


def refuse_bad_request(render: Render) -> str:
    """422 for encoder options, or a size or rate out of range; else the preset.

    `ffmpeg_params` and `bitrate` are refused, not ignored (C5), so a client
    relying on them finds out at once.
    """
    supplied = [name for name in ('ffmpeg_params', 'bitrate') if getattr(render, name)]
    if supplied:
        raise Refusal(
            Code.ENCODER_OPTIONS_REFUSED,
            f'{" and ".join(supplied)} cannot be set by a client; '
            f'choose a quality instead: {", ".join(QUALITIES)}',
        )
    for name, default in (('width', 1920), ('height', 1080)):
        value = getattr(render, name)
        if value is None:
            setattr(render, name, default)
        elif not 16 <= value <= MAX_DIMENSION:
            raise Refusal(
                Code.FRAME_SIZE_OUT_OF_RANGE,
                f'{name} must be between 16 and {MAX_DIMENSION} pixels',
            )
    # Null is the default rate (`task_payload`); anything else must be one.
    if render.fps is not None and not 1 <= render.fps <= MAX_FPS:
        raise Refusal(
            Code.FPS_OUT_OF_RANGE,
            f'fps must be between 1 and {MAX_FPS} frames per second',
        )
    try:
        return preset_for(render.quality).name
    except UnknownQuality as exc:
        raise Refusal(Code.UNKNOWN_QUALITY, str(exc)) from exc


NO_OUTPUT = Refusal(Code.RENDER_NOT_FINISHED, 'That render has no output file yet')


def finished_output(render: Render) -> str:
    """The path of a finished render's file; 409 if there is none yet.

    Finished as the worker says: mid-render, the file on disk is not yet a video.
    """
    if render_state(render.status, render.progress) != 'rendered':
        raise fresh(NO_OUTPUT)
    path = output_path(render.filename)
    if path is None:
        raise fresh(NO_OUTPUT)
    return path


def download_path(render: Render) -> str:
    """The route a render's owner downloads it from."""
    return f'/render/{render.id}/download'


def download_name(render: Render) -> str:
    """What a downloaded render is saved as: its display name, `.mp4`."""
    return f'{safe_name(render.display_name or display_name_for(render))}.mp4'


def download_url(render: Render) -> Optional[str]:
    """A signed URL for a finished render's file; None while there is none.

    Contract M1. Only for a caller who passed the ownership check: whoever
    holds it can fetch the file until it expires.
    """
    if render_state(render.status, render.progress) != 'rendered':
        return None
    if output_path(render.filename) is None:
        return None
    return media_url(download_path(render))


def bucket_link(reference) -> Optional[str]:
    """A freshly signed URL for a `(bucket, object)` reference; None if none.

    Blocking: the storage client may go to the network for credentials.
    """
    bucket, blob = reference
    try:
        return signed_url(blob, bucket=bucket)
    except Exception as exc:  # noqa: BLE001 - vendor SDK raises broadly
        print(f'could not sign a link to {blob} ({bucket or "default bucket"})', exc)
        return None


def public_link(render: Render) -> Optional[str]:
    """`render.link` as a caller can follow it now.

    A bucket delivery's `gs://<bucket>/<object>`, or a stored signed URL, is
    signed afresh; a local delivery's, or an old `data/` path, is the download
    route. Blocking, as signing is.
    """
    link = render.link
    if render.destination == LocalDestination.name or (
        isinstance(link, str) and link.lstrip('/').startswith('data/')
    ):
        return download_path(render)
    reference = parse_reference(link)
    if reference is not None:
        return bucket_link(reference)
    return link


def render_view(render: Render) -> dict:
    """A render as the API answers with it: the document as FastAPI encodes
    one, `download_url`, and a `link` that can be followed now. Blocking."""
    view = jsonable_encoder(render)
    view['download_url'] = download_url(render)
    view['link'] = public_link(render)
    return view


def refuse_unrenderable(edl):
    """422 for an EDL the engine should not be handed, naming the clip.

    Before anything is stored or queued, so a refusal leaves no trace. Media
    must be the library's or an allowed host's (C4), and templates offered
    ones: otto's template namespace also holds helpers such as `rgbToDec`.
    """
    try:
        check_edl(edl, TEMPLATE_NAMES)
    except RefusedEdl as exc:
        raise Refusal(Code.EDL_REFUSED, str(exc)) from exc


async def send_to_worker(queue, store: RenderStore, render: Render) -> None:
    """Hand a stored render to the worker; 503 if the broker would not take it.

    Off the loop: an unanswering broker takes thirty seconds to fail. A render
    not queued is recorded `failed` with the reason, never left `queued`.
    """
    payload = task_payload(render)
    try:
        await run_in_threadpool(queue, **payload)
    except Exception as exc:  # noqa: BLE001 - the broker is down, or worse
        reason = failure_reason(exc)
        await store.update(
            render.id, {'status': 'failed', 'error': f'could not be queued: {reason}'}
        )
        raise Refusal(
            Code.RENDER_NOT_QUEUED, f'The render could not be queued: {reason}'
        ) from exc


class RenderLabels(BaseModel):
    """What `PUT /render/{id}` may change: the labels, and nothing else.

    The rest is the server's record; `filename`, above all, decides which file
    a download serves.
    """

    name: Optional[str] = None
    project: Optional[str] = None
    project_id: Optional[PydanticObjectId] = None
    description: Optional[str] = None

    model_config = ConfigDict(extra='forbid')


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
        super().__init__(
            *args,
            **kwargs,
            schema=schema,
            client=self.client,
            create_schema=create_schema,
            update_schema=update_schema,
            db_url=DB_URL,
            database=DB_NAME,
            # No `DELETE /render`: the bulk delete takes everybody's (C6).
            delete_all_route=False,
        )

        @self.get('', *args, **kwargs)
        async def get_all_renders(
            skip: Optional[int] = 0,
            limit: Optional[int] = 100,
            user: User = Depends(current_active_user),
            store: RenderStore = Depends(get_render_store),
        ):
            """# Renders

            The caller's renders, newest first; every render for a superuser.

            Each carries `download_url`: a signed URL for the finished file
            that a browser can use directly, or null until there is one.
            """
            visible = owner_filter(user, 'username')
            renders = await store.list(visible, skip or 0, limit or 100)
            # Off the event loop: each finished render's file is looked for.
            return await run_in_threadpool(lambda: [render_view(r) for r in renders])

        @self.post('', *args, **kwargs)
        async def queueRender(
            render: Render,
            user: User = Depends(current_active_user),
            store: RenderStore = Depends(get_render_store),
            queue=Depends(get_render_queue),
        ):
            quality = refuse_bad_request(render)
            refuse_unrenderable(render.edl)
            refuse_bad_captions(render)
            for name in SERVER_OWNED:
                setattr(render, name, None)
            # Chosen here, so the filename that depends on it goes in the insert.
            render.id = PydanticObjectId()
            render.username = owner_key(user)
            render.quality = quality
            # The id alone names the file: nothing from the request reaches a
            # path. The readable name is kept apart, sanitised, for downloads.
            render.filename = output_filename(render.id)
            render.display_name = display_name_for(render)
            await store.insert(render)
            await send_to_worker(queue, store, render)
            return str(render.id)

        @self.post('/rerender/{id}', *args, **kwargs)
        async def reQueueRender(
            id: str,
            user: User = Depends(current_active_user),
            store: RenderStore = Depends(get_render_store),
            queue=Depends(get_render_queue),
        ):
            """# Render again

            Re-queues a stored render: its owner's or, for a superuser, any.
            """
            render = await load_owned_render(store, id, user)
            # Checked like a new one: a stored EDL may predate the checks.
            refuse_unrenderable(render.edl)
            # Renamed by its id, and an old quality name (`web`, `TV`) becomes
            # the default.
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
            await send_to_worker(queue, store, render)
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
            clients that already read it. `download_url` is a signed URL for
            the finished file, or null until there is one.
            """
            render = await load_owned_render(store, item_id, user)
            url = await run_in_threadpool(download_url, render)
            return RenderStatus.of(render, download_url=url)

        @self.post('/{item_id}/deliver', *args, **kwargs)
        async def deliverRender(
            item_id: str,
            destination: Optional[str] = None,
            user: User = Depends(current_active_user),
            store: RenderStore = Depends(get_render_store),
        ):
            """# Deliver a render

            Sends a finished render to a destination and records where it went.

            The destination defaults to the one this render was last sent to,
            then to `local`, which every server has.

            409 until the render has finished: the encoder writes its output
            as it goes, and a copy taken mid-render is not a video.
            """
            render = await load_owned_render(store, item_id, user)
            source = finished_output(render)

            chosen = destination or render.destination
            try:
                # Off the loop: a delivery copies or uploads the whole file.
                delivery = await run_in_threadpool(
                    get_destination(chosen).deliver, source
                )
            except DeliveryError as exc:
                # 502, not 500: the request was valid and downstream refused;
                # worth retrying, unless no destination has the name.
                unknown = isinstance(exc, UnknownDestination)
                code = Code.DESTINATION_UNKNOWN if unknown else Code.DELIVERY_FAILED
                raise Refusal(code, str(exc)) from exc

            # A local delivery's link is the download route, not a server path.
            if delivery.destination == LocalDestination.name:
                delivery = Delivery(
                    destination=delivery.destination, location=download_path(render)
                )
            # Recorded as delivered before the link is signed: the object is
            # in the bucket whether or not a link can be made to it now.
            await store.update(
                render.id,
                {'destination': delivery.destination, 'link': delivery.location},
            )
            if delivery.destination != BucketDestination.name:
                return delivery
            # The stored location lasts; each caller gets a link signed now.
            reference = parse_reference(delivery.location)
            link = (
                await run_in_threadpool(bucket_link, reference) if reference else None
            )
            if link is None:
                raise Refusal(
                    Code.DELIVERED_WITHOUT_LINK,
                    'The render was uploaded, but no link to it could be signed',
                )
            return Delivery(destination=delivery.destination, location=link)

        @self.get('/{item_id}', *args, **kwargs)
        async def getSignedRenderLink(
            item_id: str,
            user: User = Depends(current_active_user),
            store: RenderStore = Depends(get_render_store),
        ):
            """# A cloud link to a render

            A signed, time-limited URL for the render's copy in the cloud
            bucket, for its owner or a superuser. 502 when the bucket cannot
            sign one: always, on a server with no cloud account, where the
            download route is the way to get a render back.
            """
            render = await load_owned_render(store, item_id, user)
            # A bucket delivery's own object (its bucket may not be today's
            # BUCKET_NAME); else the worker's upload, named after the file.
            reference = parse_reference(render.link) or (None, render.filename)
            # Off the loop: the storage client may fetch credentials.
            link = await run_in_threadpool(bucket_link, reference)
            if link is None:
                raise Refusal(
                    Code.CLOUD_LINK_UNAVAILABLE,
                    'No cloud link is available for this render',
                )
            return link

        @self.put('/{item_id}', *args, **kwargs)
        async def relabelRender(
            item_id: str,
            labels: RenderLabels,
            user: User = Depends(current_active_user),
            store: RenderStore = Depends(get_render_store),
        ):
            """# Relabel a render

            Changes a render's name, project or description: its owner's, or
            any for a superuser. Fields not sent are left as they were; any
            other field is a 422 (see `RenderLabels`).
            """
            render = await load_owned_render(store, item_id, user)
            changes = labels.model_dump(exclude_unset=True)
            for name, value in changes.items():
                setattr(render, name, value)
            changes['display_name'] = display_name_for(render)
            render.display_name = changes['display_name']
            await store.update(render.id, changes)
            return await run_in_threadpool(render_view, render)

        @self.delete('/{item_id}', *args, **kwargs)
        async def deleteRender(
            item_id: str,
            user: User = Depends(current_active_user),
            store: RenderStore = Depends(get_render_store),
        ):
            """# Delete a render

            Its owner's, or any for a superuser. Its video goes with it, and
            any copy a local delivery made; a copy in a cloud bucket stays.
            """
            render = await load_owned_render(store, item_id, user)
            await store.delete(render)
            # After the record, so no render points at nothing; best effort.
            await run_in_threadpool(remove_render_files, render.id, render.filename)
            return render


# Not behind the session: a browser fetching by itself has a signed URL
# instead (contract M1, `media_access`).
renderFileAPI = APIRouter()


@renderFileAPI.get(
    '/render/{item_id}/download',
    response_class=PartialFileResponse,
    responses={
        200: {'content': {'video/mp4': {}}, 'description': 'the video'},
        206: {'content': {'video/mp4': {}}, 'description': 'a range of it'},
        401: {'description': 'no session, and no valid signature for this path'},
        404: {'description': 'no such render, or not yours'},
        409: {'description': 'not rendered yet'},
    },
)
async def downloadRender(
    item_id: str,
    access: MediaAccess = Depends(media_access),
    store: RenderStore = Depends(get_render_store),
):
    """# Download a render

    The finished video, as an attachment named for its project
    (`Content-Disposition: attachment; filename="<name>.mp4"`), with HTTP
    Range support so a player can seek in it. 409 until the render has
    finished.

    With a session, for the render's owner or a superuser. Or with none,
    through the signed `download_url` that `GET /render/{id}/status` and
    `GET /render` hand out, so a browser can stream it into a `<video>` or
    save it from a link.
    """
    if access.signed:
        # Issued after the ownership check, for this render alone.
        render = await load_render(store, item_id)
    else:
        render = await load_owned_render(store, item_id, access.user)
    return PartialFileResponse(
        finished_output(render),
        media_type='video/mp4',
        filename=download_name(render),
    )
