"""The sound of a timeline, in its own seconds (`alfred/core/utils/sound.py`).

The mapping of a file's analysis onto the timeline is the Audio lane's
(`website/src/lanes/arith.js`); the fixtures under `tests/fixtures/sound/`
are read here and by `website/e2e/lanes-fixtures.spec.js`, so the two stay
equal. The level over the whole timeline, and how a file's sound reaches
the engine, are the server's alone and are pinned here.
"""

import json
from pathlib import Path

import pytest
from otto.exceptions import NoSoundException

from alfred.core.utils import sound

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures' / 'sound'


def fixtures():
    files = sorted(FIXTURES.glob('*.json'))
    assert files, 'no fixtures under tests/fixtures/sound'
    return [pytest.param(path, id=path.stem) for path in files]


@pytest.mark.parametrize('path', fixtures())
def test_the_lane_s_arithmetic_matches_the_fixture(path):
    fixture = json.loads(path.read_text(encoding='utf-8'))
    at = sound.placed(fixture['given']['clips'])
    assert at == fixture['expect']['placed']
    assert [sound.silences_on(a, fixture['given']['silences']) for a in at] == (
        fixture['expect']['silences']
    )


VIDEO = {'type': 'video', 'name': 'videos/a.mp4', 'duration': 2, 'inpoint': 1}
SONG = {'type': 'audio', 'name': 'videos/song.mp3', 'duration': 1}
TITLE = {'type': 'template', 'name': 'title', 'duration': 1}


class TestLevels:
    def test_each_clip_plays_its_window_of_the_file_at_its_place(self):
        # a.mp4 at 2 a second: 0.1 a value, so second 1 to 3 of it is 0.2..0.6.
        peaks = {
            'videos/a.mp4': {
                'rate': 2,
                'values': [round(0.1 * k, 1) for k in range(10)],
            }
        }
        level = sound.levels(sound.placed([TITLE, VIDEO]), peaks.get)
        assert level['rate'] == 2
        # The title sounds nothing; the video from 1 s plays the file from 1 s.
        assert level['values'] == [0, 0, 0.2, 0.3, 0.4, 0.5]

    def test_clips_sounding_at_once_are_heard_as_the_loudest(self):
        peaks = {
            'videos/a.mp4': {'rate': 1, 'values': [0.2, 0.2, 0.2, 0.2]},
            'videos/song.mp3': {'rate': 1, 'values': [0.9]},
        }
        at = sound.placed([VIDEO])
        # The song placed under the video's first second, as a second track.
        at.append({'clip': SONG, 'index': 1, 'start': 0, 'length': 1, 'inpoint': 0})
        assert sound.levels(at, peaks.get)['values'] == [0.9, 0.2]

    def test_the_highest_file_rate_is_the_timeline_s(self):
        peaks = {
            'videos/a.mp4': {'rate': 4, 'values': [0.5] * 12},
            'videos/song.mp3': {'rate': 1, 'values': [1.0]},
        }
        level = sound.levels(sound.placed([VIDEO, SONG]), peaks.get)
        assert level['rate'] == 4
        assert len(level['values']) == 12
        assert level['values'][8:] == [1.0] * 4

    def test_a_file_without_peaks_is_silent_and_a_value_is_held_to_0_1(self):
        peaks = {
            'videos/a.mp4': {'rate': 1, 'values': [1.7, -0.2]},
            'videos/song.mp3': None,
        }
        level = sound.levels(sound.placed([{**VIDEO, 'inpoint': 0}, SONG]), peaks.get)
        assert level['values'] == [1.0, 0.0, 0.0]

    def test_the_levels_run_to_the_timeline_s_end_a_closing_title_included(self):
        peaks = {'videos/a.mp4': {'rate': 1, 'values': [0.5] * 4}}
        level = sound.levels(sound.placed([VIDEO, TITLE]), peaks.get)
        assert level['values'] == [0.5, 0.5, 0]

    def test_nothing_sounding_is_no_levels(self):
        assert sound.levels(sound.placed([TITLE]), lambda name: None) == {
            'rate': 0,
            'values': [],
        }


class TestTimelineSound:
    def test_the_whole_answer_in_timeline_seconds(self):
        analyses = {
            'videos/a.mp4': {
                'peaks': {'rate': 1, 'values': [0.1, 0.2, 0.3, 0.4]},
                'silences': [{'start': 0, 'end': 1.5}, {'start': 2.5, 'end': 2.75}],
            },
            'videos/song.mp3': {'peaks': {'rate': 1, 'values': [0.8]}, 'silences': []},
        }
        answer = sound.timeline_sound([TITLE, VIDEO, SONG], analyses)
        assert answer == {
            'duration': 4,
            'rate': 1,
            'levels': [0, 0.2, 0.3, 0.8],
            # The file's silence from 0 to 1.5 is heard from the clip's in-point
            # at 1 s, so half a second of it, at the clip's place.
            'silences': [{'start': 1, 'end': 1.5}, {'start': 2.5, 'end': 2.75}],
        }


class TestFileSound:
    def test_an_audio_file_goes_as_it_is(self, tmp_path):
        path = str(tmp_path / 'song.mp3')
        with sound.file_sound(path, 'audio', None) as sent:
            assert sent == (path, None)

    def test_a_video_s_sound_is_written_by_otto_at_the_speech_rate(
        self, tmp_path, monkeypatch
    ):
        asked = {}

        def renderSound(edl, filename, rate):
            asked.update(edl=edl, filename=filename, rate=rate)
            Path(filename).write_bytes(b'RIFF')
            return 3.0

        monkeypatch.setattr(sound, 'renderSound', renderSound)
        path = str(tmp_path / 'talk.mp4')
        with sound.file_sound(path, 'video', 3.0) as (sent, content_type):
            assert content_type == 'audio/wav'
            assert sent == asked['filename']
            assert Path(sent).exists()
        # Removed after the engine has had it.
        assert not Path(sent).exists()
        assert asked['rate'] == sound.SOUND_RATE
        [clip] = asked['edl'].clips
        assert (clip.type, clip.name, clip.duration) == ('video', path, 3.0)

    def test_a_video_of_unknown_length_goes_as_it_is(self, tmp_path):
        path = str(tmp_path / 'talk.mp4')
        with sound.file_sound(path, 'video', None) as sent:
            assert sent == (path, None)

    def test_a_video_with_no_sound_track_is_refused(self, tmp_path, monkeypatch):
        def renderSound(edl, filename, rate):
            raise NoSoundException('nothing sounds')

        monkeypatch.setattr(sound, 'renderSound', renderSound)
        with pytest.raises(sound.NoSoundTrack, match='talk.mp4'):
            with sound.file_sound(str(tmp_path / 'talk.mp4'), 'video', 3.0):
                pass
