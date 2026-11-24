"""Whether the parts of the stack are there (contract M3).

On the thin stack (thin.yml scales the renderer to 0) a queued render sat in
`queued` for ever, and the editor polled it for ever, because nothing could
say that no renderer was running. `GET /health` says so: the database, how
many render workers answer, and how many jobs are waiting for one.

`GET /healthz` is for container health checks: no session, no database, no
broker -- if the process can answer, it is up.
"""

import asyncio
from dataclasses import dataclass
from time import monotonic
from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ..utils import audio_engine, tasks
from ..utils.concurrency import previews
from ..utils.db import get_db
from .users import current_active_user

# How long one ping waits for workers to answer, in seconds. A worker hears a
# ping the next time it polls the broker (see CeleryConfig).
PING_TIMEOUT = 1.0

# How long an answer about the renderer is reused, in seconds, so a page
# polling this does not broadcast a ping per request.
RENDERER_CACHE_SECONDS = 5.0

# The longest a request waits on the database or the broker, in seconds.
DB_TIMEOUT = 1.0
RENDERER_TIMEOUT = 5.0


class RendererHealth(BaseModel):
    ok: bool
    workers: int


class QueueHealth(BaseModel):
    # Jobs waiting for a worker; null when the broker could not be asked.
    pending: Optional[int] = None


class PreviewHealth(BaseModel):
    # Previews being drawn now, previews waiting for a slot, and how many may
    # be drawn at once (ALFRED_PREVIEW_CONCURRENCY).
    running: int
    waiting: int
    limit: int


class AudioEngineHealth(BaseModel):
    # Whether ALFRED_AUDIO_ENGINE_URL names an engine at all.
    configured: bool
    # Whether it answered, from this build: there is one to transcribe with.
    ok: bool
    # Why not, when it is not ok; null when it is.
    detail: Optional[str] = None


class Health(BaseModel):
    """`GET /health` (contracts M3 and K2)."""

    api: Literal['ok']
    db: Literal['ok', 'down']
    renderer: RendererHealth
    queue: QueueHealth
    previews: PreviewHealth
    audio_engine: AudioEngineHealth


@dataclass(frozen=True)
class RendererState:
    workers: int
    pending: Optional[int]


def check_renderer() -> RendererState:
    """Ask the broker. Blocking: a ping waits PING_TIMEOUT past the last reply."""
    try:
        workers = tasks.worker_count(timeout=PING_TIMEOUT)
    except Exception as exc:  # noqa: BLE001 - an unreachable broker is "none"
        print('could not ping the render workers:', exc, flush=True)
        workers = 0
    try:
        pending = tasks.pending_count()
    except Exception as exc:  # noqa: BLE001 - unknown, not an error
        print('could not count the render queue:', exc, flush=True)
        pending = None
    return RendererState(workers=workers, pending=pending)


class CachedRenderer:
    """The renderer's state, reused for a few seconds, one check at a time.

    Concurrent requests share the check in flight rather than each pinging.
    The task is per event loop, so a cache that outlives one loop (as in
    tests) never awaits another loop's task. A check that takes longer than
    `timeout` (by default RENDERER_TIMEOUT) answers `unanswered()` meanwhile;
    for the renderer, no workers.
    """

    def __init__(
        self,
        check=check_renderer,
        ttl=RENDERER_CACHE_SECONDS,
        timeout=None,
        unanswered=lambda: RendererState(workers=0, pending=None),
    ):
        self.check = check
        self.ttl = ttl
        self.timeout = timeout
        self.unanswered = unanswered
        self.value: Optional[RendererState] = None
        self.checked_at = float('-inf')
        self._inflight: Optional[asyncio.Task] = None

    async def _refresh(self) -> RendererState:
        value = await run_in_threadpool(self.check)
        self.value, self.checked_at = value, monotonic()
        return value

    async def get(self) -> RendererState:
        if self.value is not None and monotonic() - self.checked_at < self.ttl:
            return self.value
        task = self._inflight
        if (
            task is None
            or task.done()
            or task.get_loop() is not asyncio.get_running_loop()
        ):
            task = self._inflight = asyncio.ensure_future(self._refresh())
        try:
            # Looked up when asked, not when built, so it can be changed.
            timeout = RENDERER_TIMEOUT if self.timeout is None else self.timeout
            return await asyncio.wait_for(asyncio.shield(task), timeout)
        except asyncio.TimeoutError:
            # The broker is not answering: no renderer can be reached.
            return self.unanswered()


_renderer = CachedRenderer()


def get_renderer_state() -> CachedRenderer:
    """A dependency, so a test can answer for the broker."""
    return _renderer


# How long an answer about the audio engine is reused, in seconds. Asking it
# is a request to another service, and a page polls this.
AUDIO_ENGINE_CACHE_SECONDS = 10.0
AUDIO_ENGINE_TIMEOUT = 5.0


def check_audio_engine() -> audio_engine.EngineStatus:
    """Ask the engine. Blocking: one request, bounded by its own timeout."""
    try:
        return audio_engine.status()
    except Exception as exc:  # noqa: BLE001 - an engine that breaks is "not ok"
        return audio_engine.EngineStatus(
            configured=bool(audio_engine.engine_url()), ok=False, detail=str(exc)
        )


def audio_engine_unanswered() -> audio_engine.EngineStatus:
    return audio_engine.EngineStatus(
        configured=bool(audio_engine.engine_url()),
        ok=False,
        detail=f'the audio engine at {audio_engine.describe()} did not answer',
    )


def cached_audio_engine(check=check_audio_engine, ttl=AUDIO_ENGINE_CACHE_SECONDS):
    """The audio engine's status, kept as the renderer's is."""
    return CachedRenderer(
        check=check,
        ttl=ttl,
        timeout=AUDIO_ENGINE_TIMEOUT,
        unanswered=audio_engine_unanswered,
    )


_audio_engine = cached_audio_engine()


def get_audio_engine_state() -> CachedRenderer:
    """A dependency, so a test can answer for the audio engine."""
    return _audio_engine


async def ping_database() -> bool:
    try:
        await asyncio.wait_for(get_db().command('ping'), DB_TIMEOUT)
        return True
    except Exception:  # noqa: BLE001 - any failure to answer is "down"
        return False


def get_database_check():
    """A dependency, so a test can answer for the database."""
    return ping_database


healthAPI = APIRouter()


@healthAPI.get('/healthz')
async def healthz():
    """# Liveness

    `{"ok": true}` whenever the api process can answer, and nothing else: no
    session, no database, no broker. For container health checks.
    """
    return {'ok': True}


@healthAPI.get(
    '/health',
    response_model=Health,
    dependencies=[Depends(current_active_user)],
)
async def health(
    renderer: CachedRenderer = Depends(get_renderer_state),
    database=Depends(get_database_check),
    sound: CachedRenderer = Depends(get_audio_engine_state),
):
    """# Health

    Whether the stack can do its work: `db` is `ok` or `down`; `renderer`
    says how many render workers answered a ping (`ok` when at least one
    did); `queue.pending` is how many render jobs are waiting, or null when
    the broker could not be asked. With no worker, a queued render waits
    until one starts -- on the thin stack, which runs none, for ever.

    `audio_engine` says whether an audio engine is `configured`
    (ALFRED_AUDIO_ENGINE_URL) and whether it is `ok` -- it answered -- with
    the reason in `detail` when it is not. Transcribing captions needs both,
    and a renderer to do the mixing.

    `previews` says how many previews are being drawn (`running`), how many
    are waiting for one of those to finish (`waiting`), and how many may be
    drawn at once (`limit`, ALFRED_PREVIEW_CONCURRENCY). A preview that waits
    too long is answered 503 with Retry-After. Counted here, not asked of
    anything, so it is always the current answer.

    The renderer and the audio engine are asked at most every few seconds;
    the answer between is the last one. A ping takes about a second, so the
    first request after that pays for it.
    """
    db_ok, state, engine = await asyncio.gather(database(), renderer.get(), sound.get())
    return Health(
        api='ok',
        db='ok' if db_ok else 'down',
        renderer=RendererHealth(ok=state.workers > 0, workers=state.workers),
        queue=QueueHealth(pending=state.pending),
        previews=PreviewHealth(**vars(previews.use())),
        audio_engine=AudioEngineHealth(
            configured=engine.configured, ok=engine.ok, detail=engine.detail
        ),
    )
