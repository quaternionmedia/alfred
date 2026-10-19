"""M2 at the HTTP boundary: `GET /media`.

The library as `GET /videos` lists it -- the same files, by the same rule --
with what the editor needs to place each one, and a signed URL to load it.
`GET /videos` keeps its list of names for the clients that read it.
"""

import pytest
from fastapi.testclient import TestClient
from otto.media import UNKNOWN, MediaInfo

from alfred import config
from alfred.core.models.render import Render
from alfred.core.utils import probe as probing
from alfred.main import app
from tests.unit.render_harness import OWNER, anonymous, as_user, offline_documents

# What the engine answers for each extension: a 3.02-second 320x180 video at
# 24 fps with sound, a 1.54-second sound, a 40x30 still.
ANSWERS = {
    '.mp4': MediaInfo(duration=3.02, width=320, height=180, fps=24.0, sound=True),
    '.mp3': MediaInfo(duration=1.54, sound=True),
    '.png': MediaInfo(width=40, height=30),
}


@pytest.fixture
def library(tmp_path, monkeypatch):
    from alfred.core.routes import video

    root = tmp_path / 'videos'
    root.mkdir()
    monkeypatch.setattr(config, 'VIDEO_DIR', str(root))
    monkeypatch.setattr(config, 'RENDER_DIR', str(root / 'renders'))
    monkeypatch.setattr(video, 'VIDEO_DIR', str(root))
    return root


@pytest.fixture
def described(monkeypatch):
    """The engine answering for each file by its extension. Records what it
    was asked: each file's path, and the kind of clip it was asked as."""
    calls = []

    def probe_file(path, kind=None):
        calls.append((str(path), kind))
        return ANSWERS.get(str(path)[-4:], UNKNOWN)

    monkeypatch.setattr(probing, 'probe_file', probe_file)
    monkeypatch.setattr(probing, '_cache', probing.ProbeCache())
    return calls


@pytest.fixture
def client(monkeypatch, library, described):
    offline_documents(monkeypatch, Render)
    overrides = as_user(app, OWNER)
    yield TestClient(app)
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


class TestTheListing:
    def test_each_file_is_described(self, client, library, described):
        (library / 'clip.mp4').write_bytes(b'v' * 1234)
        (library / 'tone.mp3').write_bytes(b'a' * 10)
        (library / 'still.png').write_bytes(b'i' * 20)

        items = {item['name']: item for item in client.get('/media').json()}

        # The engine is asked about each file as the clip that would open it.
        assert sorted(kind for _, kind in described) == ['audio', 'image', 'video']

        clip = items['videos/clip.mp4']
        assert {k: v for k, v in clip.items() if k != 'url'} == {
            'name': 'videos/clip.mp4',
            'kind': 'video',
            'duration': 3.02,
            'width': 320,
            'height': 180,
            'fps': 24.0,
            'size': 1234,
        }
        assert items['videos/tone.mp3']['kind'] == 'audio'
        assert items['videos/tone.mp3']['duration'] == 1.54
        assert items['videos/tone.mp3']['width'] is None
        assert items['videos/still.png']['kind'] == 'image'
        assert items['videos/still.png']['duration'] is None
        assert (
            items['videos/still.png']['width'],
            items['videos/still.png']['height'],
        ) == (40, 30)

    def test_exactly_the_contract_s_fields(self, client, library):
        (library / 'clip.mp4').write_bytes(b'v')
        (item,) = client.get('/media').json()
        assert sorted(item) == sorted(
            ['name', 'kind', 'duration', 'width', 'height', 'fps', 'size', 'url']
        )

    def test_the_same_files_as_the_names_list(self, client, library):
        """One visibility rule: media extensions, no encoder temporaries, no
        renders, no subdirectories, nothing hidden."""
        for name in ['b.mp4', 'a.png', 'notes.txt', '.hidden.mp4', 'x.mp4.audio.m4a']:
            (library / name).write_bytes(b'x')
        (library / 'renders').mkdir()
        (library / 'renders' / 'abc.mp4').write_bytes(b'x')
        (library / '.remote-cache').mkdir()
        (library / '.remote-cache' / 'f00d.mp4').write_bytes(b'x')

        names = [item['name'] for item in client.get('/media').json()]
        assert names == client.get('/videos').json() == ['videos/a.png', 'videos/b.mp4']

    def test_the_url_loads_the_file_with_no_session(self, client, library):
        (library / 'clip.mp4').write_bytes(b'the bytes of a clip')
        (item,) = client.get('/media').json()
        assert item['url'].startswith('/videos/clip.mp4?exp=')
        anonymous(app)
        res = client.get(item['url'])
        assert res.status_code == 200
        assert res.content == b'the bytes of a clip'

    def test_a_name_with_spaces_gets_a_url_that_works(self, client, library):
        (library / 'my clip.mp4').write_bytes(b'spaced')
        (item,) = client.get('/media').json()
        assert item['name'] == 'videos/my clip.mp4'
        assert item['url'].startswith('/videos/my%20clip.mp4?')
        anonymous(app)
        assert client.get(item['url']).content == b'spaced'

    def test_files_are_probed_once_until_they_change(self, client, library, described):
        clip = library / 'clip.mp4'
        clip.write_bytes(b'one')
        client.get('/media')
        client.get('/media')
        assert len(described) == 1
        clip.write_bytes(b'two, longer')
        client.get('/media')
        assert len(described) == 2

    def test_what_ffmpeg_cannot_read_is_null_not_an_error(self, client, library):
        (library / 'odd.mkv').write_bytes(b'not really')
        (item,) = client.get('/media').json()
        assert item['kind'] == 'video'
        assert item['duration'] is None and item['width'] is None
        assert item['size'] == len(b'not really')

    def test_an_empty_library_is_an_empty_list(self, client, library):
        assert client.get('/media').json() == []

    def test_a_missing_library_is_created_and_empty(self, client, library):
        library.rmdir()
        assert client.get('/media').json() == []

    def test_it_needs_a_session(self, client, library):
        anonymous(app)
        assert client.get('/media').status_code == 401
