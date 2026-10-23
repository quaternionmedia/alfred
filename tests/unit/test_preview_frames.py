"""Preview frames: who can fetch them, and for how long.

The EDL preview answers with something the form flow shows in a bare `<img>`,
which carries no session. It answered with a path under DATA_DIR, which an
unauthenticated static mount served at `/data` -- so its frames were public to
anyone with the name, and the name was all that protected them. The frames are
written to PREVIEW_DIR now, which nothing serves statically, and the preview
answers with a signed URL for `GET /preview/frames/{name}` (contract M1).

The single-template preview returns the image itself, so it has no reason to
leave a file anywhere, and wrote every frame into DATA_DIR for good.
"""

import os
import re
from pathlib import Path
from time import time
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from alfred import config
from alfred.core.models.render import Render
from alfred.main import app
from tests.unit.render_harness import (
    OWNER,
    TEMPLATE_EDL,
    anonymous,
    as_user,
    offline_documents,
)

NOW = 1_800_000_000

SIGNED_FRAME = re.compile(
    r'/preview/frames/(?P<name>[0-9a-f]{32}\.jpg)\?exp=\d+&sig=[A-Za-z0-9_-]{43}'
)


@pytest.fixture
def preview_dir(tmp_path, monkeypatch):
    root = tmp_path / 'previews'
    monkeypatch.setattr(config, 'PREVIEW_DIR', str(root))
    return root


@pytest.fixture
def client(monkeypatch, preview_dir):
    offline_documents(monkeypatch, Render)
    overrides = as_user(app, OWNER)
    yield TestClient(app)
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


def preview(client, t=0.5):
    res = client.post(
        f'/preview/?t={t}', json={'edl': TEMPLATE_EDL, 'width': 64, 'height': 48}
    )
    assert res.status_code == 200, res.text
    return res.json()


class TestFrameNames:
    def test_a_frame_is_named_by_a_random_uuid_alone(self, preview_dir):
        """It was a timestamp and eight hex digits: one second's frames were
        one of four billion names."""
        from alfred.core.routes.preview import frame_path

        path = Path(frame_path())
        assert path.parent == preview_dir
        assert re.fullmatch(r'[0-9a-f]{32}\.jpg', path.name)

    def test_names_do_not_repeat(self, preview_dir):
        from alfred.core.routes.preview import frame_path

        assert len({frame_path() for _ in range(50)}) == 50

    def test_the_default_directory_is_not_served_statically(self):
        """DATA_DIR was, at /data. The default is private to the api."""
        public = Path(config.STATIC_DIR).resolve()
        frames = Path(config.PREVIEW_DIR).resolve()
        assert frames != public and public not in frames.parents


class TestTheEdlPreviewAnswersWithASignedUrl:
    def test_for_a_frame_in_the_preview_directory(self, client, preview_dir):
        url = preview(client)
        match = SIGNED_FRAME.fullmatch(url)
        assert match, url
        assert (preview_dir / match['name']).is_file()

    def test_which_an_img_can_load_with_no_session(self, client, preview_dir):
        url = preview(client)
        name = SIGNED_FRAME.fullmatch(url)['name']
        anonymous(app)
        res = client.get(url)
        assert res.status_code == 200, res.text
        assert res.headers['content-type'] == 'image/jpeg'
        assert res.content == (preview_dir / name).read_bytes()

    def test_and_the_session_alone_still_works(self, client, preview_dir):
        name = SIGNED_FRAME.fullmatch(preview(client))['name']
        assert client.get(f'/preview/frames/{name}').status_code == 200

    def test_without_either_it_is_a_401(self, client, preview_dir):
        name = SIGNED_FRAME.fullmatch(preview(client))['name']
        anonymous(app)
        assert client.get(f'/preview/frames/{name}').status_code == 401

    def test_one_frame_s_url_does_not_open_another(self, client, preview_dir):
        first = preview(client)
        second_name = SIGNED_FRAME.fullmatch(preview(client, t=0.2))['name']
        anonymous(app)
        stolen = f'/preview/frames/{second_name}?{urlsplit(first).query}'
        assert client.get(stolen).status_code == 401

    def test_the_preview_itself_still_needs_a_session(self, client):
        anonymous(app)
        res = client.post(
            '/preview/?t=0', json={'edl': TEMPLATE_EDL, 'width': 64, 'height': 48}
        )
        assert res.status_code == 401


class TestTheFrameRoute:
    @pytest.mark.parametrize(
        'name', ['nope.jpg', f'{"0" * 32}.png', f'{"A" * 32}.jpg', '..%2Fsecret.jpg']
    )
    def test_serves_only_names_a_preview_makes(self, client, preview_dir, name):
        preview_dir.mkdir(parents=True, exist_ok=True)
        (preview_dir / 'nope.jpg').write_bytes(b'not a frame of ours')
        assert client.get(f'/preview/frames/{name}').status_code == 404

    def test_a_frame_that_is_gone_is_a_404(self, client, preview_dir):
        name = SIGNED_FRAME.fullmatch(preview(client))['name']
        (preview_dir / name).unlink()
        assert client.get(f'/preview/frames/{name}').status_code == 404


class TestTheEngineRefusingAClip:
    def test_is_a_422_naming_it_not_a_500(self, client):
        """otto raises EdlException for input it cannot build (contract C8).

        A real refusal, not a stand-in: a clip trimmed to end before it
        starts passes alfred's own checks, which are about names, and the
        engine refuses it, naming the clip and the field.
        """
        (clip,) = TEMPLATE_EDL['clips']
        inverted = {**clip, 'inpoint': 2.0, 'outpoint': 1.0}
        res = client.post(
            '/preview/?t=0',
            json={'edl': {'clips': [inverted]}, 'width': 64, 'height': 48},
        )
        assert res.status_code == 422, res.text
        detail = res.json()['detail']
        assert "('makeColor')" in detail and 'outpoint' in detail


class TestTheTemplatePreviewKeepsNothing:
    def test_the_image_comes_back_and_no_file_stays(
        self, client, preview_dir, monkeypatch
    ):
        from alfred.core.routes import preview

        written = []
        monkeypatch.setattr(
            preview,
            'private_frame_path',
            _recording(preview.private_frame_path, written),
        )

        res = client.get(
            '/preview/template/makeColor?color=%23f2aa4c&width=64&height=48&t=0.5'
        )
        assert res.status_code == 200
        assert res.headers['content-type'] == 'image/jpeg'
        assert len(res.content) > 0
        assert written, 'the frame was not written through private_frame_path'
        assert not Path(written[0]).exists(), 'the frame outlived the response'
        assert not preview_dir.exists() or not any(preview_dir.iterdir())

    def test_a_template_that_cannot_render_leaves_nothing_either(
        self, client, preview_dir, monkeypatch
    ):
        from alfred.core.routes import preview

        written = []
        monkeypatch.setattr(
            preview,
            'private_frame_path',
            _recording(preview.private_frame_path, written),
        )
        monkeypatch.setattr(
            preview, 'generateEdl', _raise(RuntimeError('cannot draw this'))
        )
        res = client.get('/preview/template/makeColor?width=64&height=48')
        assert res.status_code == 422
        assert written and not Path(written[0]).exists()

    def test_the_allowlist_still_answers_404_for_other_names(self, client):
        """A name in the path that is not a template is a missing resource."""
        assert client.get('/preview/template/rgbToDec').status_code == 404


def _recording(make_path, written):
    def recorded():
        path = make_path()
        written.append(path)
        return path

    return recorded


def _raise(exc):
    def fail(*args, **kwargs):
        raise exc

    return fail


class _FakeVideo:
    def save_frame(self, path, t=0, withmask=False):
        with open(path, 'wb') as handle:
            handle.write(b'\xff\xd8not really a jpeg')


@pytest.fixture
def built(monkeypatch):
    """The EDLs the template preview hands the engine."""
    from alfred.core.routes import preview

    edls = []

    def generate(edl, moviesize=None, **kwargs):
        edls.append(edl)
        return _FakeVideo()

    monkeypatch.setattr(preview, 'generateEdl', generate)
    return edls


class TestTheTemplatePreviewShowsTheTemplateMidClip:
    """A clip fades in over its first second unless told otherwise, so a frame
    sampled near the start -- where the editor samples a template it has just
    placed -- came out dimmed or black."""

    def test_no_fades_unless_asked_for(self, client, built):
        res = client.get('/preview/template/makeColor?color=%23f2aa4c&t=0')
        assert res.status_code == 200
        (clip,) = built[0].clips
        assert (clip.fadeIn, clip.fadeOut) == (0, 0)

    def test_fades_asked_for_are_honoured(self, client, built):
        client.get('/preview/template/makeColor?color=%23f2aa4c&fadeIn=0.5&fadeOut=1')
        (clip,) = built[0].clips
        assert (clip.fadeIn, clip.fadeOut) == (0.5, 1)

    def test_fades_are_not_passed_to_the_template_as_data(self, client, built):
        client.get('/preview/template/makeColor?color=%23f2aa4c&fadeIn=0.5')
        (clip,) = built[0].clips
        assert clip.data.color == '#f2aa4c'
        assert 'fadeIn' not in clip.data.dict(exclude_none=True)


class TestTheTemplatePreviewIsBuiltAtTheClipsLength:
    """A render builds a template clip to its outpoint (or duration); the
    preview built it one second past `t`. A template paced by its length --
    title's box reveal -- drew a different frame at the same `t` when cut or
    slipped, so the editor now says how long the clip is."""

    def test_the_clip_is_built_at_the_length_given(self, client, built):
        client.get('/preview/template/makeColor?color=%23f2aa4c&t=1.5&length=6')
        (clip,) = built[0].clips
        assert clip.duration == 6

    def test_without_a_length_it_is_built_one_second_past_t(self, client, built):
        client.get('/preview/template/makeColor?color=%23f2aa4c&t=1.5')
        (clip,) = built[0].clips
        assert clip.duration == 2.5

    def test_a_length_shorter_than_t_still_reaches_t(self, client, built):
        client.get('/preview/template/makeColor?color=%23f2aa4c&t=3&length=2')
        (clip,) = built[0].clips
        assert clip.duration > 3

    def test_the_length_is_not_passed_to_the_template_as_data(self, client, built):
        client.get('/preview/template/makeColor?color=%23f2aa4c&length=6')
        (clip,) = built[0].clips
        assert 'length' not in clip.data.dict(exclude_none=True)


class TestFramesExpire:
    """Every playhead move left a frame behind, for good."""

    @pytest.fixture
    def frames(self, preview_dir, monkeypatch):
        from alfred.core.routes import preview

        monkeypatch.setattr(config, 'FRAME_TTL', 3600)
        monkeypatch.setattr(preview, '_last_sweep', float('-inf'))
        preview_dir.mkdir(parents=True, exist_ok=True)

        def make(name, age, now=NOW):
            path = preview_dir / name
            path.write_bytes(b'\xff\xd8 a frame')
            stamp = now - age
            os.utime(path, (stamp, stamp))
            return path

        return make

    def test_those_older_than_the_ttl_are_removed(self, frames):
        from alfred.core.routes.preview import sweep_frames

        old = frames(f'{"a" * 32}.jpg', age=3601)
        fresh = frames(f'{"b" * 32}.jpg', age=60)
        assert sweep_frames(now=NOW, force=True) == 1
        assert not old.exists() and fresh.exists()

    def test_nothing_but_frames_is_touched(self, frames):
        """Whatever else ALFRED_PREVIEW_DIR holds is not ours to remove."""
        from alfred.core.routes.preview import sweep_frames

        other = frames('notes.txt', age=10**6)
        assert sweep_frames(now=NOW, force=True) == 0
        assert other.exists()

    def test_writing_a_frame_sweeps_at_most_once_a_minute(self, frames):
        from alfred.core.routes import preview

        frames(f'{"c" * 32}.jpg', age=4000)
        assert preview.sweep_frames(now=NOW, force=True) == 1
        frames(f'{"d" * 32}.jpg', age=4000)
        assert preview.sweep_frames(now=NOW + 30) == 0
        assert preview.sweep_frames(now=NOW + preview.SWEEP_INTERVAL) == 1

    def test_a_preview_sweeps(self, client, frames, monkeypatch):
        old = frames(f'{"e" * 32}.jpg', age=10**6, now=time())
        preview_url = client.post(
            '/preview/?t=0', json={'edl': TEMPLATE_EDL, 'width': 64, 'height': 48}
        )
        assert preview_url.status_code == 200
        assert not old.exists()

    def test_the_api_sweeps_when_it_starts(self):
        from alfred.core.routes.preview import sweep_frames_at_startup

        assert sweep_frames_at_startup in app.router.on_startup

    def test_a_preview_keeps_the_remote_media_cache_in_check_too(
        self, client, frames, monkeypatch
    ):
        """A preview is where the api fetches remote media."""
        from alfred.core.utils import storage

        swept = []
        monkeypatch.setattr(
            storage, 'sweep_remote_cache_now_and_then', lambda: swept.append(1)
        )
        res = client.post(
            '/preview/?t=0', json={'edl': TEMPLATE_EDL, 'width': 64, 'height': 48}
        )
        assert res.status_code == 200
        assert swept == [1]
