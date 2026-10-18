"""The adapter, vox's real media client, and an engine on the other end of a
socket.

Everything else stands in for vox at the adapter's edge. These do not: the
stub engine (`tests/stubs/audio_engine.py`) is served over HTTP on a port of
its own, and `utils.audio_engine` drives it through the vendored vox exactly
as it would drive joe -- the contract's defaults, the real client, the real
wire. They are what fails if alfred and vox disagree about the client's API.

They need vox's media client, which the vendored vox carries from its media
engine work on; until then they skip, and say why.
"""

import socket
import threading
import time

import pytest

pytest.importorskip('vox.media', reason='the vendored vox has no media client yet')

from alfred import config  # noqa: E402
from alfred.core.utils import audio_engine  # noqa: E402
from tests.pipeline.test_caption_pipeline import TIMELINE, write_bursts  # noqa: E402
from tests.stubs import audio_engine as stub  # noqa: E402

pytestmark = pytest.mark.needs_ffmpeg


@pytest.fixture(scope='module')
def served():
    """The stub engine, listening on a free port for the module."""
    import uvicorn

    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(stub.app, host='127.0.0.1', port=port, log_level='warning')
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 20
    while not server.started:
        assert time.monotonic() < deadline, 'the stub engine did not start'
        time.sleep(0.05)
    yield f'http://127.0.0.1:{port}'
    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture
def engine(served, monkeypatch):
    monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', served)
    monkeypatch.setattr(config, 'AUDIO_ENGINE_CONTRACT', {})
    stub.media.clear()
    stub.uploads.clear()
    return served


def test_it_answers(engine):
    assert audio_engine.problem() is None
    assert audio_engine.status() == audio_engine.EngineStatus(True, True, None)
    assert audio_engine.capabilities()['word_timestamps'] is True


def test_a_file_is_heard_with_word_timings(engine, tmp_path):
    transcript = audio_engine.transcribe(write_bursts(tmp_path / 'speech.wav'))
    assert [s.text.strip() for s in transcript.segments] == list(stub.SCRIPT[:2])
    first = transcript.segments[0]
    assert (round(first.start, 1), round(first.end, 1)) == (0.5, 1.5)
    assert [w.text.strip() for w in first.words] == stub.SCRIPT[0].split()
    assert stub.media == {}, 'the upload was not dropped'


def test_a_timeline_is_captioned_through_vox(engine, monkeypatch, tmp_path):
    from tests.pipeline.test_caption_pipeline import write_talking_video

    monkeypatch.setattr(config, 'VIDEO_DIR', str(tmp_path))
    write_bursts(tmp_path / 'speech.wav')
    write_talking_video(tmp_path / 'talking.mp4')
    from alfred.core.utils.transcription import transcribe_timeline

    captions, heard = transcribe_timeline(TIMELINE)
    assert heard == 3
    assert [(round(c.start, 1), round(c.end, 1)) for c in captions] == [
        (1.5, 2.5),
        (3.0, 4.2),
        (5.0, 6.0),
    ]
    [sent] = stub.uploads
    assert (sent['content_type'], sent['sample_rate'], sent['channels']) == (
        'audio/wav',
        16000,
        1,
    )


def test_a_library_file_is_analysed_in_vox_s_names(engine, tmp_path):
    path = write_bursts(tmp_path / 'speech.wav')
    analysis = audio_engine.analyze(path, 'audio/wav', ['onsets', 'silences', 'tempo'])
    assert list(analysis['onsets']) == [0.5, 2.0]
    assert analysis['silences'][0] == {'start': 0.0, 'end': 0.5}
    assert analysis['tempo'] == 120.0


def test_what_the_engine_refuses_is_a_refusal(engine):
    with pytest.raises(audio_engine.AudioEngineRefused, match='422'):
        audio_engine.analyze(__file__, 'audio/wav')


def test_an_engine_that_is_not_there_is_a_failure(monkeypatch):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        dead = probe.getsockname()[1]
    monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', f'http://127.0.0.1:{dead}')
    monkeypatch.setattr(config, 'AUDIO_ENGINE_CONTRACT', {})
    status = audio_engine.status()
    assert (status.configured, status.ok) == (True, False)
    assert f'127.0.0.1:{dead}' in status.detail
