"""The stub audio engine the browser suite runs against, held to its word.

`tests/stubs/audio_engine.py` answers joe's media API from what it is sent:
a segment for every stretch of sound, where the sound is. If it drifted --
heard sound that is not there, or answered in another shape -- the browser
suite's transcription specs would prove nothing, so it is pinned here.

What joe takes and states is copied below from joe's `docs/media.md`
(feat/video-audio-engine, 4ec1424): a stub that took less than joe, or said
other limits, would pass where joe refuses or refuse where joe takes.
"""

import io
import math
import struct
import wave

import pytest
from fastapi.testclient import TestClient

from tests.stubs import audio_engine as stub

pytestmark = pytest.mark.needs_ffmpeg

# joe's `formats`, as its capabilities list them.
JOE_FORMATS = [
    'audio/aac',
    'audio/flac',
    'audio/m4a',
    'audio/mp3',
    'audio/mp4',
    'audio/mpeg',
    'audio/ogg',
    'audio/vnd.wave',
    'audio/wav',
    'audio/wave',
    'audio/webm',
    'audio/x-aac',
    'audio/x-flac',
    'audio/x-m4a',
    'audio/x-wav',
    'video/matroska',
    'video/mp4',
    'video/quicktime',
    'video/webm',
    'video/x-matroska',
]
# joe's defaults: JOE_MEDIA_MAX_BYTES, JOE_MEDIA_MAX_SECONDS, JOE_MEDIA_TTL.
JOE_LIMITS = {'max_bytes': 1073741824, 'max_seconds': 7200.0, 'ttl_seconds': 3600.0}


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
    assert math.isclose(body['peaks']['rate'], 50)  # joe's default
    assert len(body['peaks']['values']) == 200
    some = engine.post(
        f'/api/media/{media_id}/analyze', params={'features': 'tempo'}
    ).json()
    assert set(some) == {'duration', 'tempo'}


def test_what_it_will_not_take(engine):
    refused = upload(engine, b'hello', 'text/plain')
    assert refused.status_code == 415
    assert refused.json()['detail'] == (
        f"unsupported media type 'text/plain'; joe takes {', '.join(JOE_FORMATS)}"
    )
    untyped = engine.post('/api/media', content=b'hello')
    assert untyped.status_code == 415
    assert untyped.json()['detail'].startswith("unsupported media type 'none'; ")
    refused = upload(engine, b'not audio at all', 'audio/wav')
    assert refused.status_code == 422
    assert refused.json()['detail'].startswith(
        'this media has no audio ffmpeg can decode'
    )
    assert engine.post('/api/media/nope/transcribe').status_code == 404
    assert engine.delete('/api/media/nope').status_code == 404


def test_it_takes_every_type_joe_takes(engine, tmp_path):
    """joe takes each format under every name browsers and platforms give it;
    the stub took thirteen of joe's twenty, and refused the rest with a 415
    joe would never send."""
    assert sorted(stub.TYPES) == JOE_FORMATS
    assert engine.get('/api/media/capabilities').json()['formats'] == JOE_FORMATS
    for alias in ('audio/vnd.wave', 'audio/x-flac', 'audio/mp3', 'video/matroska'):
        assert upload(engine, fixture_bytes(tmp_path), alias).status_code != 415, alias
    assert upload(engine, fixture_bytes(tmp_path), 'audio/vnd.wave').status_code == 201


def test_an_upload_over_the_byte_limit_is_refused_before_it_is_read(
    engine, tmp_path, monkeypatch
):
    monkeypatch.setattr(stub, 'MAX_BYTES', 1000)
    refused = upload(engine, fixture_bytes(tmp_path))
    assert refused.status_code == 413
    assert refused.json()['detail'] == (
        'media larger than 1000 bytes (JOE_MEDIA_MAX_BYTES)'
    )
    assert stub.uploads == []


def test_a_sound_longer_than_the_limit_is_refused(engine, tmp_path, monkeypatch):
    monkeypatch.setattr(stub, 'MAX_SECONDS', 2.0)
    refused = upload(engine, fixture_bytes(tmp_path))
    assert refused.status_code == 413
    assert refused.json()['detail'] == (
        "this media's sound is longer than 2 seconds (JOE_MEDIA_MAX_SECONDS)"
    )
    assert stub.media == {}


def test_a_video_with_no_sound_track_is_refused_as_joe_refuses_it(engine, tmp_path):
    import subprocess

    import imageio_ffmpeg

    silent = tmp_path / 'silent.mp4'
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            '-nostdin',
            '-v',
            'error',
            '-y',
            '-f',
            'lavfi',
            '-i',
            'testsrc=size=64x36:rate=10:duration=1',
            '-pix_fmt',
            'yuv420p',
            str(silent),
        ],
        check=True,
    )
    res = upload(engine, silent.read_bytes(), 'video/mp4')
    assert res.status_code == 422
    assert res.json()['detail'] == 'this media has no audio stream'


def test_segments_are_trimmed_and_their_words_join_back_into_them(engine, tmp_path):
    media_id = upload(engine, fixture_bytes(tmp_path)).json()['media_id']
    body = engine.post(f'/api/media/{media_id}/transcribe').json()
    for segment in body['segments']:
        assert segment['text'] == segment['text'].strip()
        assert ''.join(w['word'] for w in segment['words']).strip() == segment['text']
    assert body['info']['words'] is True


def test_forgetting(engine, tmp_path):
    media_id = upload(engine, fixture_bytes(tmp_path)).json()['media_id']
    assert engine.delete(f'/api/media/{media_id}').status_code == 204
    assert engine.post(f'/api/media/{media_id}/transcribe').status_code == 404


def test_what_joe_s_capabilities_also_say(engine):
    """joe's limits, as joe states them. The stub said 100 MiB and four hours,
    where joe takes a gibibyte and two hours."""
    body = engine.get('/api/media/capabilities').json()
    assert {key: body[key] for key in JOE_LIMITS} == JOE_LIMITS


def test_the_analysis_takes_joe_s_options(engine, tmp_path):
    media_id = upload(engine, fixture_bytes(tmp_path)).json()['media_id']
    body = engine.post(
        f'/api/media/{media_id}/analyze',
        params={'features': 'peaks,silence', 'peaks_rate': 4, 'silence_min': 0.6},
    ).json()
    assert body['peaks']['rate'] == 4
    assert len(body['peaks']['values']) == 16  # four seconds, four a second
    # Only the silences of 0.6 s or more: the last one, 3.2 to 4.0.
    assert body['silences'] == [{'start': 3.2, 'end': 4.0}]


def test_the_analysis_reads_its_features_and_refuses_as_joe_does(engine, tmp_path):
    media_id = upload(engine, fixture_bytes(tmp_path)).json()['media_id']
    analyze = f'/api/media/{media_id}/analyze'
    every = {'duration', 'tempo', 'beats', 'onsets', 'loudness', 'silences', 'peaks'}
    # Absent or empty is every feature; names are trimmed and lower-cased.
    assert set(engine.post(analyze, params={'features': ''}).json()) == every
    some = engine.post(analyze, params={'features': ' Tempo , ONSETS '}).json()
    assert set(some) == {'duration', 'tempo', 'onsets'}

    unknown = engine.post(analyze, params={'features': 'tempo,pitch'})
    assert unknown.status_code == 422
    assert unknown.json() == {
        'detail': "unknown feature 'pitch'; joe measures "
        'tempo, beats, onsets, loudness, silence, peaks'
    }
    # A parameter out of bounds is one sentence, `where: what`, not FastAPI's
    # list. The what is pydantic's own words, which differ between the
    # pydantic this image locks and the one joe runs.
    bounded = engine.post(analyze, params={'peaks_rate': 0})
    assert bounded.status_code == 422
    assert set(bounded.json()) == {'detail'}
    assert bounded.json()['detail'].startswith('peaks_rate: ')
    assert 'greater than or equal to 1' in bounded.json()['detail']
