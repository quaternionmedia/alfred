"""The library written to: `POST /media` and `DELETE /media/{name}`.

No database: the routes touch the filesystem alone, a library standing in for
VIDEO_DIR. The names a file may have are `test_media_names.py`'s rule, applied
here on the way in.
"""

import pytest
from fastapi.testclient import TestClient

from alfred.core.models.render import Render
from alfred.core.routes import media as media_routes
from alfred.main import app
from tests.unit.render_harness import OWNER, as_user, offline_documents


@pytest.fixture
def library(tmp_path, monkeypatch):
    """A library standing in for VIDEO_DIR, with one clip."""
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
    overrides = as_user(app, OWNER)
    yield TestClient(app)
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


def upload(client, name, content=b'RIFF not really', replace=False):
    query = '?replace=true' if replace else ''
    return client.post(f'/media{query}', files={'file': (name, content)})


def listed(client):
    res = client.get('/videos')
    assert res.status_code == 200, res.text
    return res.json()


class TestUploading:
    def test_a_file_is_kept_under_its_name_and_listed(self, client, library):
        res = upload(client, 'talk.wav')
        assert res.status_code == 201, res.text
        item = res.json()
        assert item['name'] == 'videos/talk.wav'
        assert item['kind'] == 'audio'
        assert item['size'] == len(b'RIFF not really')
        assert item['url'].startswith('/videos/talk.wav?')
        assert (library / 'talk.wav').read_bytes() == b'RIFF not really'
        assert 'videos/talk.wav' in listed(client)
        # Nothing half written is left beside it.
        assert sorted(p.name for p in library.iterdir()) == ['clip.mp4', 'talk.wav']

    def test_a_directory_in_the_name_is_dropped(self, client, library):
        """A browser sends the file's name; a client sending a path gets the file kept
        under its last segment, inside the library."""
        res = upload(client, 'holiday/day one.mp4')
        assert res.status_code == 201, res.text
        assert res.json()['name'] == 'videos/day one.mp4'
        assert (library / 'day one.mp4').exists()

    # A part with no file name at all is FastAPI's own 422, with no code.
    @pytest.mark.parametrize('name', ['notes.txt', '.hidden.mp4', 'TEMP_MPY_x.mp4'])
    def test_a_name_the_library_cannot_hold_is_refused(self, client, library, name):
        res = upload(client, name)
        assert res.status_code == 422, res.text
        assert res.json()['code'] == 'media_name_refused'
        assert sorted(p.name for p in library.iterdir()) == ['clip.mp4']

    def test_a_name_in_the_library_is_refused_unless_replaced(self, client, library):
        res = upload(client, 'clip.mp4', b'new bytes')
        assert res.status_code == 409, res.text
        assert res.json()['code'] == 'media_exists'
        assert (library / 'clip.mp4').read_bytes() == b'0123456789' * 100

        res = upload(client, 'clip.mp4', b'new bytes', replace=True)
        assert res.status_code == 201, res.text
        assert (library / 'clip.mp4').read_bytes() == b'new bytes'

    def test_past_the_limit_is_refused_and_nothing_is_left(
        self, client, library, monkeypatch
    ):
        """Mutation: keep the bytes written before the limit -- red."""
        monkeypatch.setattr(media_routes, 'UPLOAD_LIMIT', 8)
        res = upload(client, 'big.wav', b'0123456789')
        assert res.status_code == 413, res.text
        assert res.json()['code'] == 'media_too_large'
        assert sorted(p.name for p in library.iterdir()) == ['clip.mp4']

    def test_the_arriving_file_is_never_listed(self, library):
        """The copy takes the name only once the whole of it is there."""
        from alfred.core.utils.media import is_library_filename

        assert not is_library_filename('talk.wav' + media_routes.ARRIVING)


class TestDeleting:
    def test_a_library_file_is_removed_by_either_name(self, client, library):
        res = client.delete('/media/videos/clip.mp4')
        assert res.status_code == 200, res.text
        assert res.json() == {'name': 'videos/clip.mp4'}
        assert not (library / 'clip.mp4').exists()
        assert listed(client) == []

        (library / 'clip.mp4').write_bytes(b'again')
        assert client.delete('/media/clip.mp4').status_code == 200
        assert not (library / 'clip.mp4').exists()

    @pytest.mark.parametrize(
        'name', ['videos/missing.mp4', 'videos/../.secret_key', 'videos/clip.mp4/audio']
    )
    def test_what_the_library_does_not_hold_is_not_found(self, client, library, name):
        res = client.delete(f'/media/{name}')
        assert res.status_code == 404, res.text
        assert res.json()['code'] == 'not_found'
        assert (library / 'clip.mp4').exists()
