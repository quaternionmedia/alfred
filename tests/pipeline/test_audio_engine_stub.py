"""The stub audio engine the browser suite runs against, held to its word.

`tests/stubs/audio_engine.py` answers joe's media API from what it is sent:
a segment for every stretch of sound, where the sound is. If it drifted --
heard sound that is not there, or answered in another shape -- the browser
suite's transcription specs would prove nothing, so it is pinned here.
"""

import io
import math
import struct
import wave

import pytest
from fastapi.testclient import TestClient

from tests.stubs import audio_engine as stub

pytestmark = pytest.mark.needs_ffmpeg


@pytest.fixture
def engine():
    stub.media.clear()
    stub.uploads.clear()
    return TestClient(stub.app)


def fixture_bytes(tmp_path):
    return open(stub.write_fixture(str(tmp_path)), 'rb').read()


def silence(seconds=1.0, rate=16000):
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(struct.pack('<h', 0) * int(seconds * rate))
    return buffer.getvalue()


def upload(engine, body, content_type='audio/wav'):
    return engine.post(
        '/api/media', content=body, headers={'content-type': content_type}
    )


def test_it_says_what_it_can_do(engine):
    body = engine.get('/api/media/capabilities').json()
    assert body['word_timestamps'] is True
    assert set(body['features']) == set(stub.FEATURES)
    assert engine.get('/api/health').json() == {'status': 'ok'}


def test_an_upload_is_described(engine, tmp_path):
    res = upload(engine, fixture_bytes(tmp_path))
    assert res.status_code == 201
    body = res.json()
    assert body['duration'] == pytest.approx(stub.FIXTURE_SECONDS, abs=0.01)
    assert (body['sample_rate'], body['channels'], body['has_audio']) == (
        16000,
        1,
        True,
    )
    assert stub.uploads[0]['sample_rate'] == 44100


def test_it_hears_where_the_sound_is(engine, tmp_path):
    media_id = upload(engine, fixture_bytes(tmp_path)).json()['media_id']
    body = engine.post(
        f'/api/media/{media_id}/transcribe', params={'words': True}
    ).json()
    times = [(round(s['start'], 1), round(s['end'], 1)) for s in body['segments']]
    assert times == [(a, b) for a, b, _ in stub.FIXTURE_BURSTS]
    assert [s['text'].strip() for s in body['segments']] == list(stub.SCRIPT[:2])
    first = body['segments'][0]
    assert [w['word'].strip() for w in first['words']] == stub.SCRIPT[0].split()
    assert first['words'][0]['start'] == first['start']
    assert first['words'][-1]['end'] == pytest.approx(first['end'])


def test_silence_says_nothing(engine):
    media_id = upload(engine, silence()).json()['media_id']
    body = engine.post(f'/api/media/{media_id}/transcribe').json()
    assert body['segments'] == [] and body['text'] == ''


def test_it_measures_what_it_hears(engine, tmp_path):
    media_id = upload(engine, fixture_bytes(tmp_path)).json()['media_id']
    body = engine.post(f'/api/media/{media_id}/analyze').json()
    assert body['onsets'] == [0.5, 2.0]
    assert body['silences'][0] == {'start': 0.0, 'end': 0.5}
    assert body['loudness']['lufs'] is None
    assert math.isclose(body['peaks']['rate'], 10)
    some = engine.post(
        f'/api/media/{media_id}/analyze', params={'features': 'tempo'}
    ).json()
    assert set(some) == {'duration', 'tempo'}


def test_what_it_will_not_take(engine):
    assert upload(engine, b'hello', 'text/plain').status_code == 415
    assert upload(engine, b'not audio at all', 'audio/wav').status_code == 422
    assert engine.post('/api/media/nope/transcribe').status_code == 404


def test_forgetting(engine, tmp_path):
    media_id = upload(engine, fixture_bytes(tmp_path)).json()['media_id']
    assert engine.delete(f'/api/media/{media_id}').status_code == 204
    assert engine.post(f'/api/media/{media_id}/transcribe').status_code == 404
