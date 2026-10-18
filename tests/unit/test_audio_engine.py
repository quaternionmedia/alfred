"""The audio engine adapter: alfred's only door to vox, and through it the engine.

vox's media client (`vox.media.MediaEngine`) is not on vox's main branch yet,
so these drive `utils.audio_engine` against a fake of it at that boundary,
written to the client's documented API: `MediaEngine(contract, base_url,
timeout)` with `upload`, `transcribe`, `analyze`, `capabilities` and
`close(handle)`, and typed errors `EngineUnavailable`, `EngineRefused(status,
detail)` and `EngineAnswerMalformed`.

Two things are pinned besides the plumbing. The contract is vox's, built from
its defaults and overridden only from the environment -- run here with an
alien one sharing no path, parameter or key with the default, as vox's own
tests do. And no code in alfred spells a path or key of joe's: those are
vox's business, so a grep of alfred's own source must not find them.
"""

import dataclasses
import re
import types
from pathlib import Path

import pytest

from alfred import config
from alfred.config import resolve_audio_engine_contract
from alfred.core.utils import audio_engine

REPO = Path(__file__).resolve().parents[2]


class EngineUnavailable(Exception):
    pass


class EngineRefused(Exception):
    def __init__(self, status, detail):
        super().__init__(status, detail)
        self.status, self.detail = status, detail

    def __str__(self):
        return f'{self.status}: {self.detail}'


class EngineAnswerMalformed(Exception):
    pass


@dataclasses.dataclass
class Word:
    start: float
    end: float
    word: str
    probability: float


@dataclasses.dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list


@dataclasses.dataclass
class Transcript:
    text: str
    language: str
    segments: list
    info: dict


@dataclasses.dataclass
class Loudness:
    rms_db: float
    peak_db: float
    lufs: object


@dataclasses.dataclass
class Analysis:
    duration: float
    tempo: float
    loudness: Loudness


class FakeMediaEngine:
    """Records every call; answers what `answers` says, or raises it."""

    made = []

    def __init__(self, contract, base_url, timeout):
        self.contract, self.base_url, self.timeout = contract, base_url, timeout
        self.calls = []
        self.closed = []
        self.entered = self.exited = False
        FakeMediaEngine.made.append(self)

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, *exc):
        self.exited = True

    def _answer(self, name):
        answer = self.answers.get(name)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def upload(self, path_or_bytes, content_type):
        self.calls.append(('upload', path_or_bytes, content_type))
        return self._answer('upload') or 'handle-1'

    def transcribe(self, handle, language=None, words=True):
        self.calls.append(('transcribe', handle, language, words))
        return self._answer('transcribe')

    def analyze(self, handle, features):
        self.calls.append(('analyze', handle, list(features)))
        return self._answer('analyze')

    def capabilities(self):
        self.calls.append(('capabilities',))
        return self._answer('capabilities')

    def close(self, handle):
        self.closed.append(handle)


@pytest.fixture
def engine(monkeypatch):
    """A configured engine whose vox.media is the fake; returns the answers."""
    answers = {
        'transcribe': Transcript(
            text='Hello there.',
            language='en',
            segments=[
                Segment(
                    0.5,
                    1.5,
                    ' Hello there.',
                    [Word(0.5, 0.9, ' Hello', 0.9), Word(1.0, 1.5, ' there.', 0.8)],
                )
            ],
            info={},
        ),
        'analyze': Analysis(
            duration=4.0, tempo=120.0, loudness=Loudness(-20.0, -3.0, None)
        ),
        'capabilities': {'features': ['tempo'], 'word_timestamps': True},
    }
    FakeMediaEngine.answers = answers
    FakeMediaEngine.made = []
    fake = types.SimpleNamespace(
        MediaEngine=FakeMediaEngine,
        EngineUnavailable=EngineUnavailable,
        EngineRefused=EngineRefused,
        EngineAnswerMalformed=EngineAnswerMalformed,
    )
    monkeypatch.setattr(audio_engine, '_vox_media', lambda: fake)
    monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', 'http://engine.test:8010')
    monkeypatch.setattr(config, 'AUDIO_ENGINE_CONTRACT', {})
    return answers


def made():
    [engine] = FakeMediaEngine.made
    return engine


class TestTheContract:
    def test_vox_s_defaults_when_nothing_is_overridden(self, engine):
        from vox.contract import EngineContract

        audio_engine.transcribe('/tmp/x.wav')
        assert made().contract == EngineContract()

    def test_the_url_and_timeout_are_the_settings(self, engine, monkeypatch):
        monkeypatch.setattr(config, 'AUDIO_ENGINE_TIMEOUT', 42)
        audio_engine.transcribe('/tmp/x.wav')
        assert (made().base_url, made().timeout) == ('http://engine.test:8010', 42)

    def test_an_alien_contract_reaches_the_client_untouched(self, engine, monkeypatch):
        """Every field overridden from the environment, sharing nothing with
        the default: what reaches vox is exactly that, so nothing between the
        settings and the wire spells anything of its own."""
        from vox.contract import EngineContract

        default = EngineContract()

        def alien_spelling(name):
            spelled = str(getattr(default, name) or '')
            if not spelled.startswith('/'):
                return f'alien_{name}'
            # A route naming where an upload's id goes keeps the placeholder:
            # vox's own, not any engine's, and vox insists on it.
            placeholder = '{media_id}'
            return (
                f'/alien/{name}/{placeholder}'
                if placeholder in spelled
                else f'/alien/{name}'
            )

        alien = {
            field.name: alien_spelling(field.name)
            for field in dataclasses.fields(EngineContract)
        }
        env = {
            f'{config.AUDIO_ENGINE_CONTRACT_PREFIX}{name.upper()}': value
            for name, value in alien.items()
        }
        monkeypatch.setattr(
            config, 'AUDIO_ENGINE_CONTRACT', resolve_audio_engine_contract(env)
        )
        audio_engine.transcribe('/tmp/x.wav')
        sent = made().contract
        assert sent == EngineContract(**alien)
        for field in dataclasses.fields(EngineContract):
            assert getattr(sent, field.name) != getattr(default, field.name), field.name

    def test_none_says_an_engine_does_not_offer_it(self):
        env = {'ALFRED_AUDIO_ENGINE_CONTRACT_CONVERSATION': 'None'}
        assert resolve_audio_engine_contract(env) == {'conversation': None}

    def test_empty_is_unset(self):
        assert (
            resolve_audio_engine_contract({'ALFRED_AUDIO_ENGINE_CONTRACT_HEALTH': ' '})
            == {}
        )

    def test_other_settings_are_not_contract_fields(self):
        env = {
            'ALFRED_AUDIO_ENGINE_URL': 'http://x',
            'ALFRED_AUDIO_ENGINE_TIMEOUT': '5',
        }
        assert resolve_audio_engine_contract(env) == {}

    def test_a_name_that_is_not_a_field_is_a_problem_not_a_silence(
        self, engine, monkeypatch
    ):
        monkeypatch.setattr(config, 'AUDIO_ENGINE_CONTRACT', {'helth': '/up'})
        reason = audio_engine.problem()
        assert 'ALFRED_AUDIO_ENGINE_CONTRACT_HELTH' in reason
        with pytest.raises(audio_engine.NoAudioEngine):
            audio_engine.transcribe('/tmp/x.wav')
        assert FakeMediaEngine.made == []


class TestTranscribing:
    def test_upload_then_transcribe_with_words_then_forget(self, engine):
        transcript = audio_engine.transcribe(
            '/tmp/timeline.wav', 'audio/wav', language='de'
        )
        calls = made().calls
        assert calls[0] == ('upload', '/tmp/timeline.wav', 'audio/wav')
        assert calls[1] == ('transcribe', 'handle-1', 'de', True)
        assert made().closed == ['handle-1']
        assert made().entered and made().exited
        assert transcript.language == 'en'

    def test_segments_and_words_in_alfred_s_own_types(self, engine):
        [segment] = audio_engine.transcribe('/tmp/x.wav').segments
        assert isinstance(segment, audio_engine.Segment)
        assert (segment.start, segment.end, segment.text) == (0.5, 1.5, ' Hello there.')
        assert [(w.start, w.end, w.text) for w in segment.words] == [
            (0.5, 0.9, ' Hello'),
            (1.0, 1.5, ' there.'),
        ]

    def test_dicts_are_read_as_well_as_dataclasses(self, engine):
        engine['transcribe'] = {
            'segments': [
                {
                    'start': 0,
                    'end': 1,
                    'text': 'x',
                    'words': [{'start': 0, 'end': 1, 'word': 'x'}],
                }
            ],
            'language': 'en',
        }
        [segment] = audio_engine.transcribe('/tmp/x.wav').segments
        assert segment.words[0].text == 'x'

    def test_segments_without_times_are_dropped(self, engine):
        engine['transcribe'] = {'segments': [{'start': None, 'end': 1, 'text': 'x'}]}
        assert audio_engine.transcribe('/tmp/x.wav').segments == ()

    def test_the_upload_is_forgotten_when_transcribing_fails(self, engine):
        engine['transcribe'] = EngineUnavailable('connection refused')
        with pytest.raises(audio_engine.AudioEngineFailed):
            audio_engine.transcribe('/tmp/x.wav')
        assert made().closed == ['handle-1']


class TestFailures:
    def test_unavailable_names_the_engine(self, engine):
        engine['upload'] = EngineUnavailable('connection refused')
        with pytest.raises(audio_engine.AudioEngineFailed) as raised:
            audio_engine.transcribe('/tmp/x.wav')
        assert 'http://engine.test:8010' in str(raised.value)
        assert 'connection refused' in str(raised.value)

    def test_a_refusal_of_the_input_is_its_own_kind(self, engine):
        engine['upload'] = EngineRefused(422, 'no decodable audio')
        with pytest.raises(audio_engine.AudioEngineRefused, match='no decodable audio'):
            audio_engine.analyze('/tmp/x.mp4', 'video/mp4')

    def test_a_server_error_is_a_failure(self, engine):
        engine['transcribe'] = EngineRefused(500, 'model crashed')
        with pytest.raises(audio_engine.AudioEngineFailed, match='model crashed'):
            audio_engine.transcribe('/tmp/x.wav')

    def test_a_malformed_answer_is_a_failure(self, engine):
        engine['transcribe'] = EngineAnswerMalformed('segments is not a list')
        with pytest.raises(
            audio_engine.AudioEngineFailed, match='segments is not a list'
        ):
            audio_engine.transcribe('/tmp/x.wav')

    def test_anything_else_is_a_failure_with_its_name(self, engine):
        engine['upload'] = KeyError('media_id')
        with pytest.raises(audio_engine.AudioEngineFailed, match='KeyError'):
            audio_engine.transcribe('/tmp/x.wav')

    def test_one_line_and_bounded(self, engine):
        engine['upload'] = EngineUnavailable('first line\n' + 'x' * 1000)
        with pytest.raises(audio_engine.AudioEngineFailed) as raised:
            audio_engine.transcribe('/tmp/x.wav')
        assert '\n' not in str(raised.value)
        assert len(str(raised.value)) <= audio_engine.REASON_LIMIT

    def test_credentials_in_the_url_are_never_repeated(self, engine, monkeypatch):
        monkeypatch.setattr(
            config, 'AUDIO_ENGINE_URL', 'http://me:secret@engine.test:8010/'
        )
        engine['upload'] = EngineUnavailable('refused')
        with pytest.raises(audio_engine.AudioEngineFailed) as raised:
            audio_engine.transcribe('/tmp/x.wav')
        assert 'secret' not in str(raised.value)
        assert audio_engine.describe() == 'http://engine.test:8010'


class TestAnalysis:
    def test_the_features_asked_for_and_plain_data_back(self, engine):
        answer = audio_engine.analyze(
            '/tmp/song.mp3', 'audio/mpeg', ['tempo', 'loudness']
        )
        assert made().calls[0] == ('upload', '/tmp/song.mp3', 'audio/mpeg')
        assert made().calls[1] == ('analyze', 'handle-1', ['tempo', 'loudness'])
        assert answer == {
            'duration': 4.0,
            'tempo': 120.0,
            'loudness': {'rms_db': -20.0, 'peak_db': -3.0, 'lufs': None},
        }
        assert made().closed == ['handle-1']

    def test_all_features_by_default(self, engine):
        audio_engine.analyze('/tmp/song.mp3', 'audio/mpeg')
        assert made().calls[1][2] == list(audio_engine.FEATURES)

    def test_an_answer_that_is_not_data_is_a_failure(self, engine):
        engine['analyze'] = 'tempo is 120'
        with pytest.raises(audio_engine.AudioEngineFailed):
            audio_engine.analyze('/tmp/song.mp3', 'audio/mpeg')


class TestNoEngine:
    def test_unconfigured(self, monkeypatch):
        monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', None)
        assert 'ALFRED_AUDIO_ENGINE_URL' in audio_engine.problem()
        with pytest.raises(audio_engine.NoAudioEngine):
            audio_engine.transcribe('/tmp/x.wav')

    @pytest.mark.parametrize('url', ['engine:8010', 'ftp://engine', 'http://'])
    def test_not_an_http_url(self, monkeypatch, url):
        monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', url)
        assert 'http(s) URL' in audio_engine.problem()

    def test_a_vox_without_its_media_client(self, monkeypatch):
        """Today's vendored vox: the engine is configured and cannot be asked,
        and that is said, rather than discovered by a failing job."""
        monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', 'http://engine.test:8010')

        def missing():
            raise ImportError("cannot import name 'media' from 'vox'")

        monkeypatch.setattr(audio_engine, '_vox_media', missing)
        assert 'vox.media' in audio_engine.problem()
        status = audio_engine.status()
        assert (status.configured, status.ok) == (True, False)
        assert 'vox.media' in status.detail


class TestStatus:
    def test_answering(self, engine):
        assert audio_engine.status() == audio_engine.EngineStatus(True, True, None)

    def test_not_answering(self, engine):
        engine['capabilities'] = EngineUnavailable('connection refused')
        status = audio_engine.status()
        assert (status.configured, status.ok) == (True, False)
        assert 'connection refused' in status.detail

    def test_not_configured(self, monkeypatch):
        monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', None)
        status = audio_engine.status()
        assert (status.configured, status.ok) == (False, False)


# What only joe -- or vox's defaults, which are joe's -- would spell. None of
# it may appear in alfred's own source: alfred reaches the engine through
# vox's contract, and spelling one of these here would be a second contract.
JOE_SPELLINGS = (
    '/api/media',
    '/api/voice',
    '/api/audio',
    '/api/health',
    'media_id',
    'word_timestamps',
    'speech_model',
)


def alfred_sources():
    root = REPO / 'alfred'
    for path in root.rglob('*.py'):
        relative = path.relative_to(root).parts
        if relative[0] in ('otto', 'vox'):
            continue
        yield path


@pytest.mark.parametrize('spelling', JOE_SPELLINGS)
def test_alfred_spells_nothing_of_the_engine_s(spelling):
    found = [
        str(path.relative_to(REPO))
        for path in alfred_sources()
        if spelling in path.read_text(encoding='utf-8')
    ]
    assert not found, f'{spelling!r} is spelled in {found}; it belongs to vox'


IMPORTS_VOX = re.compile(r'^\s*(from\s+vox(\.\w+)*\s+import|import\s+vox\b)', re.M)


def test_only_the_adapter_imports_vox():
    importers = [
        str(path.relative_to(REPO))
        for path in alfred_sources()
        if IMPORTS_VOX.search(path.read_text(encoding='utf-8'))
    ]
    assert importers == [str(Path('alfred/core/utils/audio_engine.py'))]


class TestWhatVoxRefuses:
    def test_a_capability_its_contract_leaves_out_is_no_engine_to_ask(
        self, engine, monkeypatch
    ):
        """vox refuses, by name and before any request, a route its contract
        leaves None: configuration, answered as no engine (503), not as an
        engine that failed."""

        class EngineDoesNotOffer(Exception):
            pass

        import alfred.core.utils.audio_engine as adapter

        fake = adapter._vox_media()
        fake.EngineDoesNotOffer = EngineDoesNotOffer
        engine['analyze'] = EngineDoesNotOffer(
            'the engine at http://engine.test:8010 does not offer analysis'
        )
        with pytest.raises(audio_engine.NoAudioEngine, match='does not offer analysis'):
            audio_engine.analyze('/tmp/x.mp3', 'audio/mpeg')

    def test_a_contract_vox_itself_refuses_is_a_problem(self, engine, monkeypatch):
        import vox.contract

        class Strict(vox.contract.EngineContract):
            def __post_init__(self):
                raise ValueError('media_transcribe must name {media_id} once')

        monkeypatch.setattr(vox.contract, 'EngineContract', Strict)
        assert 'media_transcribe must name' in audio_engine.problem()

    def test_feature_names_are_vox_s(self):
        assert 'silences' in audio_engine.FEATURES
        assert 'silence' not in audio_engine.FEATURES
