"""The adapter through vox's real media client, against vox's own stand-in.

`test_audio_engine.py` holds the adapter to its side of the bargain with a
fake of vox's client. These drive the real one: `vox.media.MediaEngine`,
answered in-process by `vox.engine.media_transport` -- vox's own scripted
engine, speaking whatever contract it is given -- so they fail if alfred and
vox disagree about the client, and they prove the wire is the contract's from
end to end. No socket, no ffmpeg: the stand-in reads WAV bodies, and these
write WAV files with the standard library.
"""

import dataclasses
import math
import struct
import wave

import httpx
import pytest

pytest.importorskip('vox.media', reason='the vendored vox has no media client')

from vox.contract import EngineContract  # noqa: E402
from vox.engine import EngineState, media_transport  # noqa: E402
from vox.media import (  # noqa: E402
    Analysis,
    Loudness,
    Segment,
    Silence,
    Transcript,
    Word,
)

from alfred import config  # noqa: E402
from alfred.config import resolve_audio_engine_contract  # noqa: E402
from alfred.core.utils import audio_engine  # noqa: E402

SAID = Transcript(
    text='Hello there.',
    language='en',
    segments=(
        Segment(
            0.5,
            1.2,
            'Hello there.',
            (Word(0.5, 0.8, ' Hello', 0.91), Word(0.8, 1.2, ' there.', 0.95)),
        ),
    ),
    info={'model': 'stand-in'},
)

MEASURED = Analysis(
    tempo=120.0,
    onsets=(0.5,),
    loudness=Loudness(rms_db=-20.0, peak_db=-3.0, lufs=None),
    silences=(Silence(0.0, 0.5),),
)


def tone(path, seconds=1.0, rate=16000):
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(
            b''.join(
                struct.pack('<h', int(8000 * math.sin(2 * math.pi * 440 * i / rate)))
                for i in range(int(seconds * rate))
            )
        )
    return path


def alien_of(default):
    """A contract sharing no path, parameter or key with `default`; a route
    keeps the placeholder vox puts an upload's id in."""
    spelled = {}
    for field in dataclasses.fields(default):
        value = getattr(default, field.name)
        if not isinstance(value, str) and value is not None:
            continue
        text = str(value or '')
        if text.startswith('/'):
            spelled[field.name] = (
                f'/alien/{field.name}/{{media_id}}'
                if '{media_id}' in text
                else f'/alien/{field.name}'
            )
        else:
            spelled[field.name] = f'alien_{field.name}'
    return spelled


@pytest.fixture
def standin(monkeypatch):
    """`standin(contract=None, **script)`: vox's engine, answering the
    adapter's real client in-process. Returns its state."""

    def make(contract=None, **script):
        state = EngineState(contract=contract or EngineContract(), **script)
        client = httpx.Client(transport=media_transport(state))
        monkeypatch.setattr(audio_engine, 'engine_options', lambda: {'client': client})
        monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', 'http://vox.engine')
        monkeypatch.setattr(config, 'AUDIO_ENGINE_CONTRACT', {})
        return state

    return make


def test_what_was_said_comes_back_in_alfred_s_types(standin, tmp_path):
    state = standin(transcript=SAID)
    transcript = audio_engine.transcribe(tone(tmp_path / 'said.wav'))
    [segment] = transcript.segments
    assert (segment.start, segment.end, segment.text) == (0.5, 1.2, 'Hello there.')
    assert [(w.start, w.end, w.text) for w in segment.words] == [
        (0.5, 0.8, ' Hello'),
        (0.8, 1.2, ' there.'),
    ]
    assert transcript.language == 'en'
    assert state.uploads == {}, 'the upload was not dropped'


def test_what_it_measures_comes_back_as_data(standin, tmp_path):
    standin(analysis=MEASURED)
    answer = audio_engine.analyze(
        tone(tmp_path / 'song.wav'),
        'audio/wav',
        ['tempo', 'onsets', 'loudness', 'silences'],
    )
    assert answer['tempo'] == 120.0
    assert list(answer['onsets']) == [0.5]
    assert answer['loudness'] == {'rms_db': -20.0, 'peak_db': -3.0, 'lufs': None}
    assert list(answer['silences']) == [{'start': 0.0, 'end': 0.5}]


def test_the_engine_answers(standin):
    standin()
    assert audio_engine.status() == audio_engine.EngineStatus(True, True, None)


def test_the_whole_wire_is_the_contract_s(standin, monkeypatch, tmp_path):
    """Every path, parameter and key overridden from the environment, sharing
    nothing with the default, and the engine answering that contract alone:
    a transcript still comes back, and every request went to an alien path."""
    alien = alien_of(EngineContract())
    contract = EngineContract(**alien)
    state = standin(contract=contract, transcript=SAID)
    env = {
        f'{config.AUDIO_ENGINE_CONTRACT_PREFIX}{name.upper()}': value
        for name, value in alien.items()
    }
    monkeypatch.setattr(
        config, 'AUDIO_ENGINE_CONTRACT', resolve_audio_engine_contract(env)
    )
    transcript = audio_engine.transcribe(tone(tmp_path / 'said.wav'))
    assert transcript.segments[0].text == 'Hello there.'
    assert state.requests and all(r.startswith('/alien/') for r in state.requests)


def test_a_default_engine_does_not_answer_an_alien_client(
    standin, monkeypatch, tmp_path
):
    """And the reverse: the default spelling is not secretly the alien one."""
    standin(transcript=SAID)
    alien = alien_of(EngineContract())
    monkeypatch.setattr(config, 'AUDIO_ENGINE_CONTRACT', alien)
    with pytest.raises(audio_engine.AudioEngineError):
        audio_engine.transcribe(tone(tmp_path / 'said.wav'))


def test_an_upload_larger_than_the_engine_takes_is_refused(standin, tmp_path):
    standin(media_limit=1000)
    with pytest.raises(audio_engine.AudioEngineRefused, match='413'):
        audio_engine.transcribe(tone(tmp_path / 'long.wav', seconds=2.0))


def test_a_type_the_engine_does_not_take_is_refused(standin, tmp_path):
    standin()
    with pytest.raises(audio_engine.AudioEngineRefused, match='415'):
        audio_engine.analyze(tone(tmp_path / 'x.wav'), 'text/plain')
