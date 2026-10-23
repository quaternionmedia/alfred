"""M1 at the HTTP boundary: the file routes take a session or a signed URL.

Every file route needed a Bearer header, which `<video src>`, `<img src>` and
`<a download>` cannot send, so the SPA fetched whole files as blobs -- no
streaming, every render held in memory. `GET /render/{id}/download` and `GET
/videos/{name}` now admit a request with a session, as before, or with a
valid signature for exactly the path it asks for. The signed URLs are issued
by the routes that have already checked the caller: a render's `download_url`
in its status and in the list, only ever to its owner (or a superuser).

No database: see `render_harness`. The preview frames' route is covered in
`test_preview_frames.py`.
"""

from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from alfred import config
from alfred.core.models.render import Render
from alfred.core.utils import signing
from alfred.main import app
from tests.unit.render_harness import (
    ADMIN,
    OWNER,
    STRANGER,
    FakeQueue,
    FakeRenderStore,
    anonymous,
    as_user,
    make_render,
    offline_documents,
    use_fakes,
)

VIDEO_BYTES = b'\x00\x00\x00\x18ftypmp42' + bytes(range(256)) * 40


@pytest.fixture
def library(tmp_path, monkeypatch):
    from alfred.core.routes import video

    root = tmp_path / 'videos'
    (root / 'renders').mkdir(parents=True)
    monkeypatch.setattr(config, 'VIDEO_DIR', str(root))
    monkeypatch.setattr(config, 'RENDER_DIR', str(root / 'renders'))
    monkeypatch.setattr(video, 'VIDEO_DIR', str(root))
    (root / 'clip.mp4').write_bytes(VIDEO_BYTES)
    (root / 'other.mp4').write_bytes(b'another clip')
    return root


@pytest.fixture
def api(monkeypatch, library):
    offline_documents(monkeypatch, Render)
    store = FakeRenderStore()
    overrides = as_user(app, OWNER) + use_fakes(app, store, FakeQueue())
    yield TestClient(app), store
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


def finished(store, library, **fields):
    """A finished render of OWNER's, with its file where the worker writes."""
    render = make_render(status='RENDERED', progress=100, **fields)
    render.filename = f'{render.id}.mp4'
    store.renders[render.id] = render
    (library / 'renders' / render.filename).write_bytes(VIDEO_BYTES)
    return render


def with_query(path, url):
    """`path` with the query string of `url`: a signature moved elsewhere."""
    return f'{path}?{urlsplit(url).query}'


def broken_copy(url):
    """`url` with its expiry changed and its signature not: no longer valid."""
    split = urlsplit(url)
    query = parse_qs(split.query)
    return f'{split.path}?exp=1000&sig={query["sig"][0]}'


class TestTheDownloadUrl:
    def test_the_status_of_a_finished_render_carries_one(self, api, library):
        client, store = api
        render = finished(store, library)
        url = client.get(f'/render/{render.id}/status').json()['download_url']
        assert url.startswith(f'/render/{render.id}/download?exp=')

    def test_which_downloads_with_no_session(self, api, library):
        client, store = api
        render = finished(store, library)
        url = client.get(f'/render/{render.id}/status').json()['download_url']
        anonymous(app)
        res = client.get(url)
        assert res.status_code == 200, res.text
        assert res.content == VIDEO_BYTES
        assert res.headers['content-type'] == 'video/mp4'
        assert res.headers['content-disposition'].startswith('attachment;')

    def test_and_can_be_streamed_in_ranges(self, api, library):
        """What a `<video>` does with it: ask for ranges as it plays."""
        client, store = api
        render = finished(store, library)
        url = client.get(f'/render/{render.id}/status').json()['download_url']
        anonymous(app)
        res = client.get(url, headers={'Range': 'bytes=10-19'})
        assert res.status_code == 206
        assert res.content == VIDEO_BYTES[10:20]

    def test_each_listed_render_carries_one(self, api, library):
        client, store = api
        render = finished(store, library)
        queued = make_render()
        store.renders[queued.id] = queued
        listed = {r['_id']: r for r in client.get('/render').json()}
        assert listed[str(render.id)]['download_url'].startswith(
            f'/render/{render.id}/download?'
        )
        assert listed[str(queued.id)]['download_url'] is None

    def test_the_list_keeps_every_field_it_had(self, api, library):
        """Additive: a client reading the documents finds what it read before."""
        client, store = api
        render = finished(store, library, project='Kept')
        (item,) = client.get('/render').json()
        assert item['_id'] == str(render.id)
        assert item['project'] == 'Kept'
        assert item['filename'] == render.filename
        assert 'edl' in item and 'status' in item

    @pytest.mark.parametrize(
        'status,progress', [(None, None), (None, 40), ('failed', 0)]
    )
    def test_there_is_none_until_the_render_has_finished(
        self, api, library, status, progress
    ):
        client, store = api
        render = finished(store, library)
        render.status, render.progress = status, progress
        assert client.get(f'/render/{render.id}/status').json()['download_url'] is None

    def test_there_is_none_when_the_file_is_gone(self, api, library):
        """A URL that would only answer 409 is no use to anyone."""
        client, store = api
        render = finished(store, library)
        (library / 'renders' / render.filename).unlink()
        assert client.get(f'/render/{render.id}/status').json()['download_url'] is None


class TestItIsOnlyIssuedToWhoeverMayHaveIt:
    def test_a_stranger_gets_no_status_and_so_no_url(self, api, library):
        client, store = api
        render = finished(store, library)
        as_user(app, STRANGER)
        res = client.get(f'/render/{render.id}/status')
        assert res.status_code == 404
        assert 'download' not in res.text

    def test_a_stranger_s_list_holds_no_url_for_it(self, api, library):
        client, store = api
        finished(store, library)
        as_user(app, STRANGER)
        assert client.get('/render').json() == []

    def test_a_superuser_gets_one_for_any_render(self, api, library):
        client, store = api
        render = finished(store, library, username=STRANGER.email)
        as_user(app, ADMIN)
        url = client.get(f'/render/{render.id}/status').json()['download_url']
        anonymous(app)
        assert client.get(url).status_code == 200

    def test_no_session_gets_no_status_either(self, api, library):
        client, store = api
        render = finished(store, library)
        anonymous(app)
        assert client.get(f'/render/{render.id}/status').status_code == 401
        assert client.get('/render').status_code == 401


class TestTheDownloadRouteRefuses:
    def test_no_session_and_no_signature(self, api, library):
        client, store = api
        render = finished(store, library)
        anonymous(app)
        res = client.get(f'/render/{render.id}/download')
        assert res.status_code == 401

    def test_a_signature_for_another_render(self, api, library):
        client, store = api
        mine = finished(store, library)
        other = finished(store, library)
        url = client.get(f'/render/{mine.id}/status').json()['download_url']
        anonymous(app)
        res = client.get(with_query(f'/render/{other.id}/download', url))
        assert res.status_code == 401
        assert res.json()['detail'] == 'This media link is not valid'

    def test_an_expired_signature(self, api, library):
        client, store = api
        render = finished(store, library)
        url = client.get(f'/render/{render.id}/status').json()['download_url']
        split = urlsplit(url)
        sig = parse_qs(split.query)['sig'][0]
        exp = parse_qs(split.query)['exp'][0]
        anonymous(app)
        # Signed for a moment already past: a real signature, out of time.
        past = signing.media_url(split.path, ttl=-3600)
        assert client.get(past).status_code == 401
        assert 'expired' in client.get(past).json()['detail']
        # And the issued one, with its expiry moved, is no longer signed.
        assert (
            client.get(f'{split.path}?exp={int(exp) + 60}&sig={sig}').status_code == 401
        )

    def test_a_tampered_signature(self, api, library):
        client, store = api
        render = finished(store, library)
        url = client.get(f'/render/{render.id}/status').json()['download_url']
        anonymous(app)
        assert (
            client.get(url[:-2] + ('AA' if url[-2:] != 'AA' else 'BB')).status_code
            == 401
        )

    def test_a_signature_for_the_status_route(self, api, library):
        """A signature opens a file route; the session routes ignore it."""
        client, store = api
        render = finished(store, library)
        signed = signing.media_url(f'/render/{render.id}/status')
        anonymous(app)
        assert client.get(signed).status_code == 401


class TestTheSessionStillWorks:
    def test_the_owner_downloads_without_a_signature(self, api, library):
        client, store = api
        render = finished(store, library)
        assert client.get(f'/render/{render.id}/download').status_code == 200

    def test_a_stranger_with_a_session_but_no_signature_gets_a_404(self, api, library):
        client, store = api
        render = finished(store, library)
        as_user(app, STRANGER)
        assert client.get(f'/render/{render.id}/download').status_code == 404

    def test_a_bad_signature_does_not_cost_the_owner_their_session(self, api, library):
        """Bearer or signature: a stale link from the owner still opens."""
        client, store = api
        render = finished(store, library)
        stale = broken_copy(signing.media_url(f'/render/{render.id}/download'))
        assert client.get(stale).status_code == 200

    def test_a_signed_url_is_a_capability_whoever_holds_it(self, api, library):
        """Documented, not accidental: until it expires, the URL is the
        permission, as with any signed link."""
        client, store = api
        render = finished(store, library)
        url = client.get(f'/render/{render.id}/status').json()['download_url']
        as_user(app, STRANGER)
        assert client.get(url).status_code == 200


class TestLibraryFiles:
    def test_a_signed_url_serves_the_file_with_no_session(self, api, library):
        client, _ = api
        url = signing.media_url('/videos/clip.mp4')
        anonymous(app)
        res = client.get(url)
        assert res.status_code == 200
        assert res.content == VIDEO_BYTES
        assert res.headers['content-type'] == 'video/mp4'

    def test_and_in_ranges(self, api, library):
        client, _ = api
        url = signing.media_url('/videos/clip.mp4')
        anonymous(app)
        res = client.get(url, headers={'Range': 'bytes=0-9'})
        assert res.status_code == 206
        assert res.content == VIDEO_BYTES[:10]

    def test_not_another_file(self, api, library):
        client, _ = api
        url = signing.media_url('/videos/clip.mp4')
        anonymous(app)
        assert client.get(with_query('/videos/other.mp4', url)).status_code == 401

    def test_not_the_listing(self, api, library):
        client, _ = api
        url = signing.media_url('/videos')
        anonymous(app)
        assert client.get(url).status_code == 401

    def test_no_session_and_no_signature_is_a_401(self, api, library):
        client, _ = api
        anonymous(app)
        assert client.get('/videos/clip.mp4').status_code == 401

    def test_a_signature_does_not_make_a_missing_file_exist(self, api, library):
        client, _ = api
        url = signing.media_url('/videos/missing.mp4')
        anonymous(app)
        assert client.get(url).status_code == 404

    @pytest.mark.parametrize(
        'name,media_type',
        [
            ('a.webm', 'video/webm'),
            ('a.mkv', 'video/x-matroska'),
            ('a.png', 'image/png'),
            ('a.mp3', 'audio/mpeg'),
            ('a.m4a', 'audio/mp4'),
            ('a.opus', 'audio/ogg'),
            ('a.flac', 'audio/flac'),
        ],
    )
    def test_each_kind_is_served_as_itself(self, api, library, name, media_type):
        """An extension Python did not know was served as text/plain."""
        client, _ = api
        (library / name).write_bytes(b'media')
        res = client.get(f'/videos/{name}')
        assert res.status_code == 200
        assert res.headers['content-type'].split(';')[0] == media_type
