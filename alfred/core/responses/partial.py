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
`If-Range`. So this is that, kept under the name the routes import.
"""

from starlette.responses import FileResponse


class PartialFileResponse(FileResponse):
    """A whole file for a plain request; the requested bytes for a Range one."""

    # `status_code` named, with its default, because FastAPI reads it from
    # this signature to document a route that declares this response class --
    # behind a bare `**kwargs` it found none, and /openapi.json answered 500.
    def __init__(self, path, status_code: int = 200, **kwargs):
        super().__init__(path, status_code=status_code, **kwargs)
        # Sent as stored, not gzipped on the way out. The app's GZipMiddleware
        # compresses every response whose encoding is not already declared,
        # and a browser's fetch() asks for gzip -- so each video the editor
        # loaded was recompressed at level 9, gaining nothing (video is already
        # compressed), costing the server the CPU, and dropping Content-Length,
        # which is how a download shows its progress. Declaring the encoding
        # is how that middleware is told to leave a response alone.
        self.headers.setdefault('content-encoding', 'identity')
