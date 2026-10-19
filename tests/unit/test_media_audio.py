"""`GET /media/{name}/audio`: how a library file sounds, from the audio engine.

The engine is stood in for at the adapter (`utils.audio_engine.analyze`);
`test_audio_engine.py` covers the adapter's own side. Pinned here: which
names reach the engine, what a refusal or a failure answers, and that an
unchanged file is analysed once.
"""

import os

import pytest
from fastapi.testclient import TestClient

from alfred import config
from alfred.core.routes import audio as routes
from alfred.core.utils import audio_engine
from alfred.core.utils.probe import ProbeCache
from alfred.main import app
from tests.unit.render_harness import OWNER, anonymous, as_user


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'VIDEO_DIR', str(tmp_path))
    (tmp_path / 'song.mp3').write_bytes(b'not really audio')
    (tmp_path / 'talk.mp4').write_bytes(b'not really video')
    (tmp_path / 'still.png').write_bytes(b'not really a picture')
    (tmp_path / 'speech.wav').write_bytes(b'not really a wav')
    return tmp_path


@pytest.fixture
def analysed(monkeypatch, library):
    """The engine, answering; returns the calls it was asked."""
    calls = []

    def analyze(path, content_type, features):
        calls.append((os.path.basename(path), content_type, tuple(features)))
        return {'duration': 4.0, 'tempo': 120.0, 'features': list(features)}

    monkeypatch.setattr(audio_engine, 'problem', lambda: None)
    monkeypatch.setattr(audio_engine, 'analyze', analyze)
    monkeypatch.setattr(routes, '_cache', ProbeCache(size=8))
    return calls


@pytest.fixture
def client():
    overrides = as_user(app, OWNER)
    yield TestClient(app)
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


class TestAsking:
    def test_the_analysis_of_a_library_file(self, client, analysed):
        res = client.get('/media/videos/song.mp3/audio')
        assert res.status_code == 200, res.text
        assert res.json()['tempo'] == 120.0
        assert analysed == [('song.mp3', 'audio/mpeg', audio_engine.FEATURES)]

    def test_by_its_bare_name_too(self, client, analysed):
        assert client.get('/media/song.mp3/audio').status_code == 200

    def test_a_video_is_sent_as_one(self, client, analysed):
        client.get('/media/videos/talk.mp4/audio')
        assert analysed[0][1] == 'video/mp4'

    def test_a_wav_is_sent_under_the_name_every_engine_takes(self, client, analysed):
        client.get('/media/videos/speech.wav/audio')
        assert analysed[0][1] == 'audio/wav'

    def test_some_features(self, client, analysed):
        res = client.get('/media/videos/song.mp3/audio?features=tempo,beats,tempo')
        assert res.json()['features'] == ['tempo', 'beats']

    @pytest.mark.parametrize('features', ['bpm', 'tempo,key', ','])
    def test_an_unknown_feature_is_422_and_not_asked(self, client, analysed, features):
        res = client.get(f'/media/videos/song.mp3/audio?features={features}')
        assert res.status_code == 422
        assert res.json()['code'] == 'unknown_feature'
        assert analysed == []

    @pytest.mark.parametrize(
        'name',
        [
            'videos/missing.mp3',
            'videos/../secret.mp3',
            'videos/.hidden.mp3',
            'videos/x.txt',
        ],
    )
    def test_what_the_library_does_not_hold_is_404(self, client, analysed, name):
        res = client.get(f'/media/{name}/audio')
        assert res.status_code == 404
        assert res.json() == {
            'detail': 'No such file in the media library',
            'code': 'not_found',
        }
        assert analysed == []

    def test_an_image_has_no_sound(self, client, analysed):
        res = client.get('/media/videos/still.png/audio')
        assert res.status_code == 422
        assert 'image' in res.json()['detail']
        assert res.json()['code'] == 'media_silent'

    def test_it_needs_a_session(self, client, analysed):
        anonymous(app)
        assert client.get('/media/videos/song.mp3/audio').status_code == 401


class TestTheEngine:
    def test_none_configured_is_503_with_the_reason(self, client, library, monkeypatch):
        monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', None)
        res = client.get('/media/videos/song.mp3/audio')
        assert res.status_code == 503
        assert 'ALFRED_AUDIO_ENGINE_URL' in res.json()['detail']
        assert res.json()['code'] == 'audio_engine_missing'

    def test_one_that_does_not_offer_analysis_is_503_too(
        self, client, analysed, monkeypatch
    ):
        """The engine's contract has no analysis route: configuration, so the
        same code as having no engine at all."""

        def not_offered(*args):
            raise audio_engine.NoAudioEngine(
                'the audio engine at http://e: the contract offers no analyze'
            )

        monkeypatch.setattr(audio_engine, 'analyze', not_offered)
        res = client.get('/media/videos/song.mp3/audio')
        assert res.status_code == 503
        assert res.json() == {
            'detail': 'the audio engine at http://e: the contract offers no analyze',
            'code': 'audio_engine_missing',
        }

    def test_a_refusal_of_the_file_is_422(self, client, analysed, monkeypatch):
        def refuse(*args):
            raise audio_engine.AudioEngineRefused(
                'the audio engine at http://e: no decodable audio'
            )

        monkeypatch.setattr(audio_engine, 'analyze', refuse)
        res = client.get('/media/videos/song.mp3/audio')
        assert res.status_code == 422
        assert 'no decodable audio' in res.json()['detail']
        assert res.json()['code'] == 'audio_engine_refused'

    def test_a_failure_is_502_with_the_reason(self, client, analysed, monkeypatch):
        def fail(*args):
            raise audio_engine.AudioEngineFailed(
                'the audio engine at http://e: refused'
            )

        monkeypatch.setattr(audio_engine, 'analyze', fail)
        res = client.get('/media/videos/song.mp3/audio')
        assert res.status_code == 502
        assert 'http://e' in res.json()['detail']
        assert res.json()['code'] == 'audio_engine_failed'


class TestTheCache:
    def test_an_unchanged_file_is_analysed_once(self, client, analysed):
        client.get('/media/videos/song.mp3/audio')
        client.get('/media/song.mp3/audio')
        assert len(analysed) == 1

    def test_a_changed_file_is_analysed_again(self, client, analysed, library):
        client.get('/media/videos/song.mp3/audio')
        path = library / 'song.mp3'
        path.write_bytes(b'different, and longer, audio')
        os.utime(path, ns=(1, 1))
        client.get('/media/videos/song.mp3/audio')
        assert len(analysed) == 2

    def test_other_features_are_another_answer(self, client, analysed):
        client.get('/media/videos/song.mp3/audio?features=tempo')
        client.get('/media/videos/song.mp3/audio?features=beats')
        assert len(analysed) == 2

    def test_a_failure_is_not_kept(self, client, analysed, monkeypatch):
        def fail(*args):
            raise audio_engine.AudioEngineFailed('down')

        monkeypatch.setattr(audio_engine, 'analyze', fail)
        client.get('/media/videos/song.mp3/audio')
        assert len(routes._cache) == 0
