"""Preview frames: who can fetch them, and for how long.

DATA_DIR is served by an unauthenticated static mount, `/data`. The EDL
preview has to write there -- it answers with a name the form flow shows in an
`<img>` -- so its frames get names nobody can guess. The single-template
preview returns the image itself, so it has no reason to leave a file anywhere,
and wrote every frame into DATA_DIR for good.
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alfred.core.models.render import Render
from alfred.main import app
from tests.unit.render_harness import (
    OWNER,
    TEMPLATE_EDL,
    as_user,
    offline_documents,
)


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    from alfred.core.routes import preview

    root = tmp_path / 'data'
    monkeypatch.setattr(preview, 'DATA_DIR', str(root))
    return root


@pytest.fixture
def client(monkeypatch, data_dir):
    offline_documents(monkeypatch, Render)
    overrides = as_user(app, OWNER)
    yield TestClient(app)
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


class TestPublicFrameNames:
    def test_a_frame_is_named_by_a_random_uuid_alone(self, data_dir):
        """It was a timestamp and eight hex digits: one second's frames were
        one of four billion names."""
        from alfred.core.routes.preview import frame_path

        path = Path(frame_path())
        assert path.parent == data_dir
        assert re.fullmatch(r'[0-9a-f]{32}\.jpg', path.name)

    def test_names_do_not_repeat(self, data_dir):
        from alfred.core.routes.preview import frame_path

        assert len({frame_path() for _ in range(50)}) == 50

    def test_the_edl_preview_answers_with_such_a_name(self, client, data_dir):
        res = client.post(
            '/preview/?t=0.5', json={'edl': TEMPLATE_EDL, 'width': 64, 'height': 48}
        )
        assert res.status_code == 200, res.text
        path = Path(res.json())
        assert re.fullmatch(r'[0-9a-f]{32}\.jpg', path.name)
        assert (data_dir / path.name).is_file()


class TestTheTemplatePreviewKeepsNothing:
    def test_the_image_comes_back_and_no_file_stays(
        self, client, data_dir, monkeypatch
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
        assert not data_dir.exists() or not any(data_dir.iterdir())

    def test_a_template_that_cannot_render_leaves_nothing_either(
        self, client, data_dir, monkeypatch
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
