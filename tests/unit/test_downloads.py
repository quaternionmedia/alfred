"""C3 -- getting a file back, whole or in ranges.

`PartialFileResponse` answered 206 to every request and stopped at 4 MB, with
or without a Range header. The editor's video preview fetches media whole, so
any clip over 4 MB played truncated -- measured on a dev stack: a 45,688,593
byte file came back as exactly 4,194,304 bytes, labelled 206. And a range was
served for 4 MB from its start, wherever it asked to end.

`GET /render/{id}/download` is new: the only way to get a render back from a
server with no cloud bucket.
"""

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from alfred import config
from alfred.core.models.render import Render
from alfred.main import app
from tests.unit.render_harness import (
    ADMIN,
    OWNER,
    STRANGER,
    FakeQueue,
    FakeRenderStore,
    as_user,
    make_render,
    offline_documents,
    use_fakes,
)

# Past the old 4 MB cap, and not a multiple of any chunk size.
BIG = 4 * 1024 * 1024 + 123_457


@pytest.fixture
def library(tmp_path, monkeypatch):
    from alfred.core.routes import video

    root = tmp_path / 'videos'
    root.mkdir()
    monkeypatch.setattr(config, 'VIDEO_DIR', str(root))
    (root / 'renders').mkdir()
    monkeypatch.setattr(config, 'RENDER_DIR', str(root / 'renders'))
    monkeypatch.setattr(video, 'VIDEO_DIR', str(root))
    return root


@pytest.fixture
def renders(library):
    """Where the worker writes finished renders (RENDER_DIR)."""
    return library / 'renders'


@pytest.fixture
def big_file(library):
    path = library / 'big.mp4'
    path.write_bytes(bytes(i % 251 for i in range(BIG)))
    return path


@pytest.fixture
def api(monkeypatch, library):
    offline_documents(monkeypatch, Render)
    store = FakeRenderStore()
    overrides = as_user(app, OWNER) + use_fakes(app, store, FakeQueue())
    yield TestClient(app), store
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


class TestWholeAndPartialFiles:
    """Through `GET /videos/{file}`, the route the editor's preview uses."""

    def test_no_range_is_the_whole_file_with_200(self, api, big_file):
        client, _ = api
        res = client.get('/videos/big.mp4')
        assert res.status_code == 200
        assert len(res.content) == BIG
        assert res.content == big_file.read_bytes()
        assert res.headers['content-length'] == str(BIG)
        assert res.headers['accept-ranges'] == 'bytes'

    def test_it_is_not_gzipped_for_a_client_that_accepts_gzip(self, api, big_file):
        """What fetch() sends. The app's GZipMiddleware recompressed whole
        videos for it, and dropped the length a progress bar needs."""
        client, _ = api
        res = client.get('/videos/big.mp4', headers={'Accept-Encoding': 'gzip'})
        assert res.headers.get('content-encoding') != 'gzip'
        assert res.headers['content-length'] == str(BIG)
        assert len(res.content) == BIG

    def test_a_range_is_exactly_that_range(self, api, big_file):
        client, _ = api
        res = client.get('/videos/big.mp4', headers={'Range': 'bytes=100-199'})
        assert res.status_code == 206
        assert res.content == big_file.read_bytes()[100:200]
        assert res.headers['content-range'] == f'bytes 100-199/{BIG}'
        assert res.headers['content-length'] == '100'

    def test_an_open_range_runs_to_the_end_past_4_mb(self, api, big_file):
        client, _ = api
        res = client.get('/videos/big.mp4', headers={'Range': 'bytes=0-'})
        assert res.status_code == 206
        assert len(res.content) == BIG
        assert res.headers['content-range'] == f'bytes 0-{BIG - 1}/{BIG}'

    def test_a_range_late_in_a_large_file(self, api, big_file):
        client, _ = api
        start = BIG - 10
        res = client.get('/videos/big.mp4', headers={'Range': f'bytes={start}-'})
        assert res.status_code == 206
        assert res.content == big_file.read_bytes()[start:]

    def test_a_suffix_range_is_the_last_bytes(self, api, big_file):
        client, _ = api
        res = client.get('/videos/big.mp4', headers={'Range': 'bytes=-10'})
        assert res.status_code == 206
        assert res.content == big_file.read_bytes()[-10:]

    def test_a_range_past_the_end_is_a_416(self, api, big_file):
        client, _ = api
        res = client.get('/videos/big.mp4', headers={'Range': f'bytes={BIG}-'})
        assert res.status_code == 416


def stored(store, renders, **fields):
    """A render in the store, with its output file written if it finished."""
    render = make_render(**fields)
    render.filename = render.filename or f'{render.id}.mp4'
    store.renders[render.id] = render
    if render.status in ('RENDERED', 'UPLOADED'):
        (renders / render.filename).write_bytes(b'\x00\x00\x00\x18ftypmp42' * 1000)
    return render


class TestTheDownloadRoute:
    def test_a_finished_render_downloads_as_an_attachment(self, api, renders):
        client, store = api
        render = stored(
            store, renders, status='RENDERED', display_name='Car-advert-64x48'
        )
        res = client.get(f'/render/{render.id}/download')
        assert res.status_code == 200
        assert res.headers['content-type'] == 'video/mp4'
        assert res.headers['content-disposition'] == (
            'attachment; filename="Car-advert-64x48.mp4"'
        )
        assert res.content == (renders / render.filename).read_bytes()

    def test_it_supports_ranges(self, api, renders):
        client, store = api
        render = stored(store, renders, status='UPLOADED')
        res = client.get(
            f'/render/{render.id}/download', headers={'Range': 'bytes=0-9'}
        )
        assert res.status_code == 206
        assert len(res.content) == 10
        assert res.headers['content-range'].startswith('bytes 0-9/')

    def test_a_render_without_a_display_name_gets_one(self, api, renders):
        """Renders stored before display names existed."""
        client, store = api
        render = stored(
            store, renders, status='RENDERED', project='Old project', display_name=None
        )
        res = client.get(f'/render/{render.id}/download')
        assert 'filename="Old-project-64x48.mp4"' in res.headers['content-disposition']

    def test_a_stored_display_name_is_sanitised_again(self, api, renders):
        client, store = api
        render = stored(store, renders, status='RENDERED', display_name='../x"; y')
        disposition = client.get(f'/render/{render.id}/download').headers[
            'content-disposition'
        ]
        assert disposition == 'attachment; filename="x-y.mp4"'

    @pytest.mark.parametrize(
        'status,progress', [(None, None), (None, 40), ('failed', 0)]
    )
    def test_an_unfinished_render_is_a_409(self, api, renders, status, progress):
        """Mid-render the file exists and is not yet a video."""
        client, store = api
        render = stored(store, renders, status=status, progress=progress)
        (renders / render.filename).write_bytes(b'partial')
        assert client.get(f'/render/{render.id}/download').status_code == 409

    def test_a_finished_render_whose_file_is_gone_is_a_409(self, api, renders):
        client, store = api
        render = stored(store, renders, status='RENDERED')
        (renders / render.filename).unlink()
        assert client.get(f'/render/{render.id}/download').status_code == 409

    def test_a_stored_name_outside_the_output_directory_finds_nothing(
        self, api, renders, tmp_path
    ):
        """Old renders' names came from the request, `../` and all."""
        client, store = api
        (tmp_path / 'secret.mp4').write_bytes(b'not yours')
        render = stored(store, renders, status='RENDERED', filename='../secret.mp4')
        assert client.get(f'/render/{render.id}/download').status_code == 409

    def test_a_render_finished_before_the_render_directory_still_downloads(
        self, api, library
    ):
        """Finished renders used to be written into the media library itself,
        under their old composite names."""
        client, store = api
        render = make_render(
            status='RENDERED', filename='demo_320x180_1.0s_20260101-000000_x.mp4'
        )
        store.renders[render.id] = render
        (library / render.filename).write_bytes(b'an old render')
        res = client.get(f'/render/{render.id}/download')
        assert res.status_code == 200
        assert res.content == b'an old render'

    def test_renders_are_not_part_of_the_media_library(self, api, renders):
        """Written beside the media, every user's renders were listed to
        everyone, and served to anyone who asked by name."""
        client, store = api
        render = stored(store, renders, status='RENDERED')
        assert client.get('/videos').json() == []
        assert client.get(f'/videos/{render.filename}').status_code == 404
        assert client.get('/videos/renders').status_code == 404

    def test_someone_else_s_render_is_a_404(self, api, renders):
        client, store = api
        render = stored(store, renders, status='RENDERED')
        as_user(app, STRANGER)
        assert client.get(f'/render/{render.id}/download').status_code == 404

    def test_a_superuser_can_download_any_render(self, api, renders):
        client, store = api
        render = stored(store, renders, status='RENDERED')
        as_user(app, ADMIN)
        assert client.get(f'/render/{render.id}/download').status_code == 200

    def test_a_malformed_id_is_a_422(self, api):
        client, _ = api
        assert client.get('/render/undefined/download').status_code == 422

    def test_a_missing_render_is_a_404(self, api):
        client, _ = api
        assert client.get(f'/render/{ObjectId()}/download').status_code == 404
