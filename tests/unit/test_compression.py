"""Compression for what gains from it, and none for media.

Every response was gzipped for any client that accepted it, whole videos
included: no gain (they are compressed already), the server's CPU spent at
level 9, and `Content-Length` dropped, which is how a download shows its
progress. Each file route opted out with a `Content-Encoding: identity`
header. Now the middleware decides by what a response is.
"""

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from alfred import config
from alfred.core.models.render import Render
from alfred.core.responses.compression import MediaAwareGZipMiddleware, is_compressible
from alfred.main import app
from tests.unit.render_harness import OWNER, as_user, offline_documents

GZIP = {'Accept-Encoding': 'gzip'}
VIDEO = bytes(range(256)) * 400  # compressible, as real video is not


@pytest.fixture
def client(tmp_path, monkeypatch):
    from alfred.core.routes import video

    root = tmp_path / 'videos'
    root.mkdir()
    (root / 'clip.mp4').write_bytes(VIDEO)
    (root / 'still.png').write_bytes(VIDEO)
    monkeypatch.setattr(config, 'VIDEO_DIR', str(root))
    monkeypatch.setattr(video, 'VIDEO_DIR', str(root))
    offline_documents(monkeypatch, Render)
    overrides = as_user(app, OWNER)
    yield TestClient(app)
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


class TestThroughTheApp:
    def test_a_video_goes_out_as_it_is(self, client):
        res = client.get('/videos/clip.mp4', headers=GZIP)
        assert res.status_code == 200
        assert 'content-encoding' not in res.headers
        assert res.headers['content-length'] == str(len(VIDEO))
        assert res.content == VIDEO

    def test_so_does_an_image(self, client):
        res = client.get('/videos/still.png', headers=GZIP)
        assert 'content-encoding' not in res.headers
        assert res.headers['content-length'] == str(len(VIDEO))

    def test_and_a_byte_range(self, client):
        res = client.get('/videos/clip.mp4', headers={**GZIP, 'Range': 'bytes=0-999'})
        assert res.status_code == 206
        assert 'content-encoding' not in res.headers
        assert res.content == VIDEO[:1000]

    def test_json_is_still_compressed(self, client):
        res = client.get('/openapi.json', headers=GZIP)
        assert res.status_code == 200
        assert res.headers['content-encoding'] == 'gzip'
        assert res.json()['info']['title'] == 'Alfred API'

    def test_nothing_is_compressed_for_a_client_that_did_not_ask(self, client):
        res = client.get('/openapi.json', headers={'Accept-Encoding': 'identity'})
        assert 'content-encoding' not in res.headers


class TestTheDecision:
    @pytest.mark.parametrize(
        'content_type',
        [
            'video/mp4',
            'audio/mpeg',
            'image/jpeg',
            'IMAGE/PNG',
            'multipart/byteranges; boundary=x',
            'application/octet-stream',
        ],
    )
    def test_media_is_not_compressed(self, content_type):
        start = {'status': 200, 'headers': [(b'content-type', content_type.encode())]}
        assert not is_compressible(start)

    @pytest.mark.parametrize(
        'content_type',
        [
            'application/json',
            'text/html; charset=utf-8',
            'text/css',
            'application/javascript',
        ],
    )
    def test_text_is(self, content_type):
        start = {'status': 200, 'headers': [(b'content-type', content_type.encode())]}
        assert is_compressible(start)

    def test_a_partial_response_never_is(self):
        start = {'status': 206, 'headers': [(b'content-type', b'text/plain')]}
        assert not is_compressible(start)


class TestOnItsOwn:
    """The middleware around a bare app: a decision made per response."""

    def make(self):
        def text(request):
            return JSONResponse({'words': 'many ' * 400})

        def video(request):
            return Response(b'\x00' * 5000, media_type='video/mp4')

        inner = Starlette(routes=[Route('/text', text), Route('/video', video)])
        return TestClient(MediaAwareGZipMiddleware(inner))

    def test_text_and_video_from_one_app(self):
        client = self.make()
        assert client.get('/text', headers=GZIP).headers['content-encoding'] == 'gzip'
        video = client.get('/video', headers=GZIP)
        assert 'content-encoding' not in video.headers
        assert video.content == b'\x00' * 5000
