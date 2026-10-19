"""How many previews the api draws at once, and what the rest are told.

A preview -- a timeline's frame (`POST /preview/`) or a template's (`GET
/preview/template/{name}`) -- opens and decodes media, composites a frame and
encodes it. That runs in the thread pool, off the event loop, which is right;
but the pool is AnyIO's forty threads, shared with every file response, every
other route's offloaded work and `/health`'s broker ping. The editor asks for a
preview on every playhead move and every keystroke in a template's text, so a
few people editing at once, or one script, could take all forty, and then a
download or a health check waited behind somebody's frames.

So previews take a slot first: at most ALFRED_PREVIEW_CONCURRENCY run at once.
The rest wait their turn in the order they came, for at most
ALFRED_PREVIEW_WAIT seconds, and are then answered 503 with a Retry-After
header, rather than queueing for as long as the others take. They wait on the
event loop, not in a thread: a preview waiting for a slot holds no thread, so a
burst of them cannot take the pool the cap is there to protect.

`GET /health` reports the slots' use: `previews: {running, waiting, limit}`.
"""

import asyncio
from collections import deque
from dataclasses import dataclass
from functools import wraps

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from alfred import config

# When a preview turned away is worth asking for again, in seconds: the
# Retry-After it is answered with. Short, because a slot frees as soon as any
# one frame is drawn; the editor waits this long, then asks once more.
RETRY_AFTER = 2


@dataclass(frozen=True)
class Use:
    """How the slots are used: holders, those waiting for one, and the cap."""

    running: int
    waiting: int
    limit: int


class Busy(Exception):
    """No slot came free within the wait."""


class Slots:
    """At most `limit()` holders at once; the rest wait their turn, first come
    first served, for at most `wait()` seconds each.

    The limit and the wait are read each time they are needed, so a test can
    change the settings they come from. Every acquire and release happens on
    the event loop: nothing here is safe to call from a thread.
    """

    def __init__(self, limit, wait):
        self.limit = limit
        self.wait = wait
        self.running = 0
        # The turns of those waiting, oldest first: futures set when a slot is
        # theirs. Only pending ones are kept; one given up on is taken out.
        self._waiting = deque()

    def use(self) -> Use:
        return Use(running=self.running, waiting=len(self._waiting), limit=self.limit())

    def _admit(self):
        """Hand free slots to those waiting, oldest first."""
        while self._waiting and self.running < self.limit():
            turn = self._waiting.popleft()
            self.running += 1
            turn.set_result(None)

    def _leave(self, turn):
        """Out of the line, or, if the slot came just as it was given up on,
        the slot passed on to the next."""
        if turn.done():
            self.release()
        else:
            self._waiting.remove(turn)
            turn.cancel()

    async def acquire(self):
        """Take a slot, waiting up to `wait()` seconds; Busy if none came."""
        self._admit()
        if not self._waiting and self.running < self.limit():
            self.running += 1
            return
        turn = asyncio.get_running_loop().create_future()
        self._waiting.append(turn)
        try:
            # `wait`, not `wait_for`: it never cancels the turn, so a slot
            # handed over at the last moment is still seen to have been.
            await asyncio.wait((turn,), timeout=self.wait())
        except BaseException:
            # Cancelled while waiting: the request went away.
            self._leave(turn)
            raise
        if not turn.done():
            self._leave(turn)
            raise Busy()

    def release(self):
        self.running -= 1
        self._admit()


previews = Slots(
    limit=lambda: config.PREVIEW_CONCURRENCY, wait=lambda: config.PREVIEW_WAIT
)


def busy() -> HTTPException:
    """What a preview that found no slot in time is answered."""
    return HTTPException(
        status_code=503,
        detail=(
            f'The server is already drawing as many previews as it will '
            f'({previews.limit()} at once); ask again in {RETRY_AFTER} seconds.'
        ),
        headers={'Retry-After': str(RETRY_AFTER)},
    )


def preview_slot(draw):
    """`draw`, a plain-function preview route, as one that takes a slot first.

    The route becomes a coroutine that waits for a slot on the event loop, then
    runs `draw` in the thread pool as FastAPI ran it before, and gives the slot
    back however `draw` ends. No slot within ALFRED_PREVIEW_WAIT seconds is a
    503 with Retry-After (`busy`).

    `draw` keeps its parameters, name and docstring, which are what FastAPI
    reads to build the route and its documentation: it reads the parameters
    through `__wrapped__`, and decides how to call the route from the route
    itself, which is a coroutine.
    """

    @wraps(draw)
    async def drawn(*args, **kwargs):
        try:
            await previews.acquire()
        except Busy:
            raise busy() from None
        try:
            return await run_in_threadpool(draw, *args, **kwargs)
        finally:
            previews.release()

    return drawn
