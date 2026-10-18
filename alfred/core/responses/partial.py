"""A file response that honours HTTP Range requests.

This was a hand-written response that answered `206 Partial Content` to every
request and stopped after 4 MB, Range header or not. A client asking for the
whole file -- the editor's video preview fetches media into a blob -- got the
first 4 MB, with a status claiming that was a deliberate part, and anything
longer played truncated. A Range request was served for 4 MB from its start,
wherever it had asked to end.

Starlette's FileResponse has done this properly since 0.39: the whole file
with 200 when no range is asked for, 206 with a correct `Content-Range` for a
range, `multipart/byteranges` for several, 416 for a range past the end, and
`If-Range`. So this is that, kept under the name the routes import, with one
correction: a suffix range longer than the file.

Compression is not this response's business: media and byte ranges are left
uncompressed by the app's middleware (`compression.py`), for every route.
"""

import os
import re

import anyio
from starlette.responses import FileResponse
from starlette.types import Receive, Scope, Send

_SUFFIX = re.compile(r'^\s*-\s*(\d+)\s*$')
# Whether a Range header asks for a suffix at all: `-N` first, or after a comma.
_HAS_SUFFIX = re.compile(rb'[=,]\s*-')


def clamp_suffix_ranges(header: str, size: int) -> str:
    """`header` with every suffix range longer than the file made the whole file.

    `bytes=-N` asks for the last N bytes, and RFC 9110 (14.1.2) says a file
    shorter than N is sent whole. Starlette computes a negative start for it
    and answers 416 -- so a player asking for the last 64 KB of a short clip,
    as some do to find its index, was refused. `bytes=-0` is still nothing.
    """
    unit, _, ranges = header.partition('=')
    if unit.strip().lower() != 'bytes' or not ranges:
        return header
    specs = []
    for spec in ranges.split(','):
        match = _SUFFIX.match(spec)
        if match and int(match[1]) > size:
            spec = '0-'
        specs.append(spec)
    return f'{unit}={",".join(specs)}'


class PartialFileResponse(FileResponse):
    """A whole file for a plain request; the requested bytes for a Range one."""

    # `status_code` named, with its default, because FastAPI reads it from
    # this signature to document a route that declares this response class --
    # behind a bare `**kwargs` it found none, and /openapi.json answered 500.
    def __init__(self, path, status_code: int = 200, **kwargs):
        super().__init__(path, status_code=status_code, **kwargs)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await super().__call__(await self._clamped(scope), receive, send)

    async def _clamped(self, scope: Scope) -> Scope:
        """The scope, with a suffix range past the file's start clamped."""
        headers = scope.get('headers', [])
        found = [value for key, value in headers if key == b'range']
        if not found or not _HAS_SUFFIX.search(found[0]):
            return scope
        try:
            size = (await anyio.to_thread.run_sync(os.stat, self.path)).st_size
        except OSError:
            # The response itself says what is wrong with the file.
            return scope
        header = found[0].decode('latin-1')
        clamped = clamp_suffix_ranges(header, size)
        if clamped == header:
            return scope
        replaced = [
            (key, clamped.encode('latin-1') if key == b'range' else value)
            for key, value in headers
        ]
        return {**scope, 'headers': replaced}
