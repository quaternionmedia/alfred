"""Shared test configuration and fixtures.

`STATIC_DIR` is set before anything imports `alfred.main`, which mounts a
StaticFiles directory at import time and raises if it is missing.
"""

from os import environ

if not environ.get('STATIC_DIR'):
    environ['STATIC_DIR'] = 'tests/dist'

import shutil  # noqa: E402

import pytest  # noqa: E402

from otto.models import Clip, Edl, TemplateData  # noqa: E402

# --- environment markers --------------------------------------------------
#
# Registering a marker in pyproject.toml only names it; nothing acts on it.
# Without this hook a needs_docker test on a machine with no docker binary
# raises FileNotFoundError from subprocess, which reads as a broken test suite
# rather than an absent tool. `./al pytest` runs in a container that has no
# Docker CLI, so that is not a hypothetical.
#
# Skip on absence, never on failure: if the tool is present and the test fails,
# that is a real result and must stay red.


def _has_docker():
    return shutil.which('docker') is not None


def _has_ffmpeg():
    """Resolve ffmpeg the way the code under test does, not via PATH.

    A PATH check is wrong here and quietly costs coverage: moviepy encodes
    through imageio_ffmpeg's bundled binary, so the real encode test passes on
    machines with no ffmpeg on PATH at all -- this one included. Probing PATH
    skipped a test that was passing, which is worse than the error it was
    meant to prevent, because a skip looks like a pass.
    """
    if shutil.which('ffmpeg'):
        return True
    try:
        import imageio_ffmpeg

        return bool(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        return False


_EXTERNAL_TOOLS = {
    'needs_docker': (_has_docker, 'no docker binary available'),
    'needs_ffmpeg': (_has_ffmpeg, 'no ffmpeg available to moviepy'),
}


def pytest_collection_modifyitems(config, items):
    available = {marker: probe() for marker, (probe, _) in _EXTERNAL_TOOLS.items()}
    for item in items:
        for marker, (_, reason) in _EXTERNAL_TOOLS.items():
            if marker in item.keywords and not available[marker]:
                item.add_marker(pytest.mark.skip(reason=reason))


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
        # `size` comes off the clip, not the kwargs: the requested resolution
        # is baked into the composite rather than passed to the encoder, so
        # without capturing it here nothing can assert that moviesize survived
        # the trip from renderMultitrack into the clip graph.
        calls.append({'filename': filename, 'size': tuple(self.size), **kwargs})

    monkeypatch.setattr(
        'moviepy.video.VideoClip.VideoClip.write_videofile',
        _write_videofile,
        raising=True,
    )
    return calls
