"""Compression for the responses that gain from it, and none for media.

The app gzipped every response whose client accepted it -- which a browser's
fetch() always does -- including whole videos. Video, audio and images are
compressed already, so that spent the server's CPU at level 9 for nothing,
and it dropped `Content-Length`, which is how a download shows its progress.
Each file response opted out by declaring `Content-Encoding: identity`, a
header every one of them had to remember to send and that then went out on
the wire.

This decides once, for every response, from what the response is: media
types, and any `206 Partial Content` (a byte range, which gzip would
corrupt), go out as they are. Everything else -- JSON, the SPA's scripts and
styles -- is handed to Starlette's own GZipMiddleware, used only through its
public interface, so a newer Starlette changes nothing here.
"""

from starlette.datastructures import Headers
from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Response types sent as they are. Media formats are compressed already;
# multipart/byteranges is several ranges of one, and octet-stream is any file
# whose type is unknown, which is no better a candidate.
UNCOMPRESSED_TYPES = (
    'video/',
    'audio/',
    'image/',
    'multipart/byteranges',
    'application/octet-stream',
)

# Where the real `send` waits for a response that bypasses compression. The
# compressing middleware hands the app the same scope it was given.
_RAW_SEND = 'alfred.uncompressed_send'


def is_compressible(message: Message) -> bool:
    """Whether a response, by its start message, is worth compressing."""
    if message.get('status') == 206:
        return False
    content_type = Headers(raw=message.get('headers', [])).get('content-type', '')
    return not content_type.strip().lower().startswith(UNCOMPRESSED_TYPES)


class MediaAwareGZipMiddleware:
    """GZip, except for media and byte ranges."""

    def __init__(self, app: ASGIApp, minimum_size: int = 500, compresslevel: int = 9):
        self.app = app
        self.gzip = GZipMiddleware(
            self._route, minimum_size=minimum_size, compresslevel=compresslevel
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        scope[_RAW_SEND] = send
        await self.gzip(scope, receive, send)

    async def _route(self, scope: Scope, receive: Receive, compressing: Send) -> None:
        """Send each response through compression, or around it."""
        raw = scope.pop(_RAW_SEND, compressing)
        target = compressing

        async def send(message: Message) -> None:
            nonlocal target
            if message['type'] == 'http.response.start':
                target = compressing if is_compressible(message) else raw
            await target(message)

        await self.app(scope, receive, send)
