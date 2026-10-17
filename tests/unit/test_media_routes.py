"""C4 at the HTTP boundary: the routes that take or serve media names.

`test_media_names.py` pins the rule; these pin that every route which hands a
name to the engine applies it, before anything is stored or queued, and that
the library routes list and serve exactly what the rule accepts.

No database: every request here is refused before the route reaches storage,
or touches only the filesystem. See `render_harness`.
"""

import pytest
from fastapi.testclient import TestClient

from alfred.core.models.render import Render
from alfred.main import app
from tests.unit.render_harness import OWNER, as_user, offline_documents


@pytest.fixture
def library(tmp_path, monkeypatch):
    """An empty media library standing in for VIDEO_DIR, with one clip."""
    from alfred import config
    from alfred.core.routes import video

    root = tmp_path / 'videos'
    root.mkdir()
    (root / 'clip.mp4').write_bytes(b'0123456789' * 100)
    monkeypatch.setattr(config, 'VIDEO_DIR', str(root))
    monkeypatch.setattr(video, 'VIDEO_DIR', str(root))
    return root


@pytest.fixture
def client(monkeypatch, library):
    offline_documents(monkeypatch, Render)
    override = as_user(app, OWNER)
    yield TestClient(app)
    app.dependency_overrides.pop(override, None)


def render_request(*clips):
    return {
        'edl': {'clips': list(clips), 'duration': 1.0},
        'project': 'media routes',
        'width': 64,
        'height': 48,
    }


def video(name):
    return {'type': 'video', 'name': name, 'duration': 1.0}


REFUSED_NAMES = [
    '/etc/hostname',
    'videos/../.secret_key',
    'videos\\clip.mp4',
    'https://example.test/clip.mp4',
    'file:///etc/hostname',
    'videos/missing.mp4',
    'clip.mp4',
]


class TestRenderRefusesBadMedia:
    @pytest.mark.parametrize('name', REFUSED_NAMES)
    def test_a_bad_media_name_is_a_422(self, client, name):
        res = client.post('/render', json=render_request(video(name)))
        assert res.status_code == 422, res.text
        assert 'clip 1' in res.json()['detail']

    def test_the_refusal_happens_before_anything_is_stored(self, client):
        """Nothing behind the route exists here, so a 422 proves the order.

        Had the route reached the insert, it would have failed on the absent
        database with a 500 instead.
        """
        res = client.post('/render', json=render_request(video('/etc/hostname')))
        assert res.status_code == 422

    def test_a_template_outside_the_allowlist_is_a_422(self, client):
        """The template allowlist applies to renders, not only to previews."""
        clip = {'type': 'template', 'name': 'rgbToDec', 'duration': 1.0}
        res = client.post('/render', json=render_request(clip))
        assert res.status_code == 422
        assert 'rgbToDec' in res.json()['detail']

    def test_an_unknown_clip_type_is_a_422(self, client):
        res = client.post(
            '/render', json=render_request({'type': 'bogus', 'name': 'x'})
        )
        assert res.status_code == 422

    def test_an_empty_timeline_is_a_422(self, client):
        res = client.post('/render', json=render_request())
        assert res.status_code == 422


class TestPreviewRefusesBadMedia:
    @pytest.mark.parametrize('name', REFUSED_NAMES)
    def test_a_bad_media_name_is_a_422(self, client, name):
        res = client.post('/preview/?t=0', json=render_request(video(name)))
        assert res.status_code == 422, res.text

    def test_a_template_outside_the_allowlist_is_a_422(self, client):
        """This answered 500: the name reached `getattr(otto.templates, ...)`."""
        clip = {'type': 'template', 'name': 'rgbToDec', 'duration': 1.0}
        res = client.post('/preview/?t=0', json=render_request(clip))
        assert res.status_code == 422


class TestTheLibraryRoutes:
    def test_the_list_names_media_the_way_clips_use_it(self, client, library):
        assert client.get('/videos').json() == ['videos/clip.mp4']

    def test_the_list_holds_only_files_a_clip_can_use(self, client, library):
        (library / 'renders').mkdir()
        (library / '.hidden.mp4').write_bytes(b'x')
        assert client.get('/videos').json() == ['videos/clip.mp4']

    def test_a_listed_file_is_served(self, client, library):
        res = client.get('/videos/clip.mp4')
        assert res.status_code in (200, 206)
        assert res.content == (library / 'clip.mp4').read_bytes()

    def test_a_missing_file_is_a_404_not_a_500(self, client):
        assert client.get('/videos/nope.mp4').status_code == 404

    def test_a_name_the_list_would_not_offer_is_not_served(self, client, library):
        """`..` and `.` are normalised away by any client before they arrive;
        a hidden file is the case that does reach the route."""
        (library / '.hidden.mp4').write_bytes(b'x')
        assert client.get('/videos/.hidden.mp4').status_code == 404
