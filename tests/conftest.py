"""Shared test configuration and fixtures.

`STATIC_DIR` is set before anything imports `alfred.main`, which mounts a
StaticFiles directory at import time and raises if it is missing.
"""

from os import environ

if not environ.get('STATIC_DIR'):
    environ['STATIC_DIR'] = 'tests/dist'

import pytest  # noqa: E402

from otto.models import Clip, Edl, TemplateData  # noqa: E402

# --- builders -------------------------------------------------------------
#
# Tests build configs as plain dicts wherever the point is what the API
# accepts, and as models where the point is engine behavior. The dict form is
# what actually arrives over HTTP, so validating models built from dicts
# tests the real path.


def clip_dict(**overrides):
    """A minimal video clip as the editor would serialise it."""
    base = {
        'type': 'video',
        'name': 'https://example.test/clip.mp4',
        'duration': 5.0,
        'inpoint': 0.0,
        'outpoint': 5.0,
        'start': 0.0,
    }
    base.update(overrides)
    return base


def edl_dict(clips=None, **overrides):
    base = {'clips': clips if clips is not None else [clip_dict()]}
    base.update(overrides)
    return base


def render_dict(**overrides):
    """A render request as the API would receive it."""
    base = {
        'edl': edl_dict(),
        'name': 'test render',
        'project': 'testproject',
        'width': 1920,
        'height': 1080,
        'fps': 30.0,
    }
    base.update(overrides)
    return base


@pytest.fixture
def template_clip():
    """A clip needing no media file, so the engine can build it offline."""
    return Clip(
        type='template',
        name='color',
        duration=1.0,
        data=TemplateData(color='#ff0000'),
    )


@pytest.fixture
def template_edl(template_clip):
    return Edl(clips=[template_clip])


# --- fakes ----------------------------------------------------------------


class FakeHeadResponse:
    """Stands in for `requests.head` in `otto.getdata.download`."""

    def __init__(self, content_type='video/mp4', content_length='1000'):
        self.headers = {}
        if content_type is not None:
            self.headers['content-type'] = content_type
        if content_length is not None:
            self.headers['content-length'] = content_length


@pytest.fixture
def fake_head(monkeypatch):
    """Install a fake HEAD; returns a setter for the response to serve."""

    state = {'response': FakeHeadResponse()}

    def _head(url, allow_redirects=False):
        return state['response']

    monkeypatch.setattr('otto.getdata.head', _head)

    def _set(**kwargs):
        state['response'] = FakeHeadResponse(**kwargs)

    return _set


@pytest.fixture
def recorded_downloads(monkeypatch):
    """Record calls to `download_url` instead of fetching anything."""
    calls = []

    def _download_url(url, filename):
        calls.append((url, filename))

    monkeypatch.setattr('otto.getdata.download_url', _download_url)
    return calls


@pytest.fixture
def recorded_encode(monkeypatch):
    """Capture the kwargs `renderMultitrack` hands the encoder.

    Asserting on what the encoder is *asked* for keeps output-selection tests
    fast and deterministic; actually encoding is IS-4's job.
    """
    calls = []

    def _write_videofile(self, filename, **kwargs):
        calls.append({'filename': filename, **kwargs})

    monkeypatch.setattr(
        'moviepy.video.VideoClip.VideoClip.write_videofile',
        _write_videofile,
        raising=True,
    )
    return calls
