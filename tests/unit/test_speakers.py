"""Speaker turns onto a timeline, and the words they name
(`alfred/core/utils/speakers.py`): arithmetic, no engine."""

from alfred.core.utils import sound, speakers
from alfred.core.utils.speakers import counted, named, turns_on

TALK = {'type': 'video', 'name': 'videos/talk.mp4', 'duration': 10, 'inpoint': 5}
SONG = {'type': 'audio', 'name': 'videos/song.mp3', 'duration': 4}
TITLE = {'type': 'template', 'name': 'title', 'duration': 2}
# talk.mp4's voices, in its own seconds: A from 3 to 9, B from 9 to 14, A again.
TALK_TURNS = [
    {'start': 3.0, 'end': 9.0, 'speaker': 'A'},
    {'start': 9.0, 'end': 14.0, 'speaker': 'B'},
    {'start': 14.5, 'end': 20.0, 'speaker': 'A'},
]
SONG_TURNS = [{'start': 0.0, 'end': 4.0, 'speaker': 'A'}]


def heard(turns):
    return lambda name: turns.get(name)


class TestTurnsOnTheTimeline:
    def test_a_file_s_turns_are_moved_through_the_clip_s_window(self):
        """Mutation: forget the clip's inpoint -- red, every turn lands late."""
        at = sound.placed([TITLE, TALK])
        found = turns_on(at, heard({'videos/talk.mp4': TALK_TURNS}))
        # The title has no voice. talk.mp4 plays its 5 to 15 s at 2 to 12 s on
        # the timeline: A's turn from 3 is held to the clip's start, B's to 12.
        assert found == [
            {'start': 2.0, 'end': 6.0, 'speaker': 'A'},
            {'start': 6.0, 'end': 11.0, 'speaker': 'B'},
            {'start': 11.5, 'end': 12.0, 'speaker': 'A'},
        ]

    def test_two_files_letters_are_told_apart_by_the_file_s_number(self):
        at = sound.placed([TALK, SONG])
        found = turns_on(
            at,
            heard({'videos/talk.mp4': TALK_TURNS[:1], 'videos/song.mp3': SONG_TURNS}),
        )
        assert [t['speaker'] for t in found] == ['1A', '2A']
        assert found[1] == {'start': 10.0, 'end': 14.0, 'speaker': '2A'}

    def test_a_file_not_heard_has_no_turns_and_the_prefix_counts_the_files_that_sound(
        self,
    ):
        found = turns_on(
            sound.placed([TALK, SONG]), heard({'videos/song.mp3': SONG_TURNS})
        )
        assert found == [{'start': 10.0, 'end': 14.0, 'speaker': '2A'}]


WORDS = [
    {'start': 2.0, 'end': 2.4, 'text': 'Hello', 'segment': 0},
    {'start': 2.5, 'end': 2.9, 'text': 'there.', 'segment': 0},
    {'start': 6.2, 'end': 6.6, 'text': 'Hi.', 'segment': 1},
    {'start': 12.5, 'end': 12.9, 'text': 'Later.', 'segment': 2},
    {'start': 7.0, 'end': 7.4, 'text': 'Named', 'segment': 1, 'speaker': 'Alice'},
]
TURNS = [
    {'start': 2.0, 'end': 6.0, 'speaker': 'A'},
    {'start': 6.0, 'end': 11.0, 'speaker': 'B'},
]


class TestNaming:
    def test_each_unnamed_word_takes_the_turn_its_middle_falls_in(self):
        """Mutation: name a word by its start alone, or name named words too -- red."""
        words, count = named(WORDS, TURNS)
        assert [w.get('speaker') for w in words] == ['A', 'A', 'B', None, 'Alice']
        assert count == 3
        # The words themselves are untouched.
        assert WORDS[0].get('speaker') is None

    def test_no_turns_name_nothing(self):
        words, count = named(WORDS, [])
        assert count == 0 and words == [dict(w) for w in WORDS]

    def test_where_turns_overlap_the_one_starting_latest_over_the_word_wins(self):
        over = TURNS + [{'start': 5.9, 'end': 6.5, 'speaker': 'C'}]
        words, _ = named(WORDS[2:3], over)
        assert words[0]['speaker'] == 'B'
        words, _ = named(WORDS[2:3], [{'start': 5.9, 'end': 6.5, 'speaker': 'C'}])
        assert words[0]['speaker'] == 'C'

    def test_the_count_per_speaker(self):
        words, _ = named(WORDS, TURNS)
        assert counted(words) == {'A': 2, 'B': 1, 'Alice': 1}
        assert speakers.counted([]) == {}
