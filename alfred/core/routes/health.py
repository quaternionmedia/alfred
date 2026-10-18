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

from ..utils import tasks
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
    pending: Optional[int]


class Health(BaseModel):
    """`GET /health` (contract M3)."""

    api: Literal['ok']
    db: Literal['ok', 'down']
    renderer: RendererHealth
    queue: QueueHealth


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
    tests) never awaits another loop's task.
    """

    def __init__(self, check=check_renderer, ttl=RENDERER_CACHE_SECONDS):
        self.check = check
        self.ttl = ttl
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
            return await asyncio.wait_for(asyncio.shield(task), RENDERER_TIMEOUT)
        except asyncio.TimeoutError:
            # The broker is not answering: no renderer can be reached.
            return RendererState(workers=0, pending=None)


_renderer = CachedRenderer()


def get_renderer_state() -> CachedRenderer:
    """A dependency, so a test can answer for the broker."""
    return _renderer


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
):
    """# Health

    Whether the stack can do its work: `db` is `ok` or `down`; `renderer`
    says how many render workers answered a ping (`ok` when at least one
    did); `queue.pending` is how many render jobs are waiting, or null when
    the broker could not be asked. With no worker, a queued render waits
    until one starts -- on the thin stack, which runs none, for ever.

    The renderer is asked at most every few seconds; the answer between is
    the last one. A ping takes about a second, so the first request after
    that pays for it.
    """
    db_ok, state = await asyncio.gather(database(), renderer.get())
    return Health(
        api='ok',
        db='ok' if db_ok else 'down',
        renderer=RendererHealth(ok=state.workers > 0, workers=state.workers),
        queue=QueueHealth(pending=state.pending),
    )
