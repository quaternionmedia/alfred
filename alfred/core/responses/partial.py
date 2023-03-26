import hashlib
import http.cookies
import inspect
import json
import os
import stat
import typing
from email.utils import formatdate
from mimetypes import guess_type

from starlette.background import BackgroundTask
from starlette.types import Receive, Scope, Send
from starlette.requests import Request
from starlette.responses import Response

try:
    import aiofiles
    from aiofiles.os import stat as aio_stat
except ImportError:  # pragma: nocover
    aiofiles = None  # type: ignore
    aio_stat = None  # type: ignore

try:
    import ujson
except ImportError:  # pragma: nocover
    ujson = None  # type: ignore


class PartialFileResponse(Response):
    chunk_size = 4096

    def __init__(
        self,
        path: str,
        status_code: int = 206,
        headers: dict = None,
        media_type: str = None,
        background: BackgroundTask = None,
        filename: str = None,
        stat_result: os.stat_result = None,
        method: str = None,
    ) -> None:
        assert aiofiles is not None, "'aiofiles' must be installed to use FileResponse"
        self.path = path
        self.status_code = status_code
        self.filename = filename
        self.send_header_only = method is not None and method.upper() == "HEAD"
        if media_type is None:
            media_type = guess_type(filename or path)[0] or "text/plain"
        self.media_type = media_type
        self.background = background
        self.init_headers(headers)
        if self.filename is not None:
            content_disposition = 'attachment; filename="{}"'.format(self.filename)
            self.headers.setdefault("content-disposition", content_disposition)
        self.stat_result = stat_result
        self.defaultSize = 1024 * 1024 * 4
        # self.size = None
        if stat_result is not None:
            # self.size = stat_result.st_size
            self.set_stat_headers(stat_result)

    def set_stat_headers(self, stat_result: os.stat_result) -> None:
        content_length = str(min(stat_result.st_size, self.defaultSize))
        last_modified = formatdate(stat_result.st_mtime, usegmt=True)
        etag_base = str(stat_result.st_mtime) + "-" + str(stat_result.st_size)
        etag = hashlib.md5(etag_base.encode()).hexdigest()

        self.headers.setdefault("content-length", content_length)
        self.headers.setdefault("last-modified", last_modified)
        self.headers.setdefault("etag", etag)
        # filesize = str(stat_result.st_size)
        # self.headers.setdefault('filesize', filesize)
        self.headers.setdefault('accept-ranges', 'bytes')
        self.size = stat_result.st_size
        # print('size: ', self.size, type(self.size), self.headers)
        self.start = 0
        self.end = self.start + int(content_length)
        # self.headers.setdefault('range', f"bytes {self.start}-{self.end}/{self.size}")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.stat_result is None:
            try:
                stat_result = await aio_stat(self.path)
                self.set_stat_headers(stat_result)
            except FileNotFoundError:
                raise RuntimeError(f"File at path {self.path} does not exist.")
            else:
                mode = stat_result.st_mode
                if not stat.S_ISREG(mode):
                    raise RuntimeError(f"File at path {self.path} is not a file.")
        request = Request(scope, receive)
        # print('got a bytes!', request.headers)
        if request.headers.get('range'):
            if request.headers['range'].startswith('bytes='):
                # print('range: ', request.headers['range'], request.headers['range'][:6], request.headers['range'].startswith('bytes='), type(request.headers['range'][:6]))

                self.range = request.headers['range'].split('bytes=')[1].split('-')
                # print('processed range: ', self.range)
                self.start = int(self.range[0])
                self.end = min(self.start + self.defaultSize, self.size)
                self.headers[
                    'content-range'
                ] = f"bytes {self.start}-{self.end - 1}/{self.size}"
                self.headers['content-length'] = str(self.end - self.start)
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.raw_headers,
            }
        )
        if self.send_header_only:
            await send({"type": "http.response.body"})
        else:
            async with aiofiles.open(self.path, mode="rb") as f:
                r = await f.seek(0, 2)
                s = await f.tell()
                assert (
                    s == self.size
                ), f'{r}, {type(s)}, {s} is not {self.size}, {type(self.size)}!'
                await f.seek(self.start)
                more_body = True
                sent = 0
                while more_body:
                    readSize = min(self.chunk_size, self.defaultSize - sent)
                    sent += readSize
                    chunk = await f.read(readSize)
                    # more_body = len(chunk) == self.chunk_size
                    more_body = readSize is not 0
                    await send(
                        {
                            "type": "http.response.body",
                            "body": chunk,
                            "more_body": more_body,
                        }
                    )
        if self.background is not None:
            await self.background()
