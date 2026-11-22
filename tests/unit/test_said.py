"""What was said over stretches of a file, from the projects that play it
(`alfred/core/utils/said.py`): a recording, a draft cut from it, and a draft
of that draft, each saying what it holds in the file's own seconds.
"""

from alfred.core.utils import said as said_module
from alfred.core.utils.said import heard, intersect, merged, said, subtract

FILE = 'videos/talk.mp4'


def word(start, end, text, **fields):
    return {'start': start, 'end': end, 'text': text, **fields}


def clip(inpoint, duration, name=FILE, kind='video'):
    return {'type': kind, 'name': name, 'inpoint': inpoint, 'duration': duration}


# The recording: the whole of a minute of the file, a word a second, and a
# caption every four seconds.
RECORDING = {
    'edl': {'clips': [clip(0, 60)]},
    'words': [word(s + 0.1, s + 0.6, f'w{s}', segment=s // 4) for s in range(60)],
    'captions': [
        {'start': s, 'end': s + 4, 'text': ' '.join(f'w{t}' for t in range(s, s + 4))}
        for s in range(0, 60, 4)
    ],
}

# A draft of 40 to 50 s of the file, at the start of its timeline, where a
# person corrected one word and deleted the words of 46 to 48 s.
DRAFT = {
    'edl': {'clips': [clip(40, 10)]},
    'words': [
        word(
            t - 40 + 0.1,
            t - 40 + 0.6,
            'corrected' if t == 44 else f'w{t}',
            speaker='Ann',
        )
        for t in range(40, 50)
        if t not in (46, 47)
    ],
    'captions': [{'start': 0, 'end': 10, 'text': 'the draft says'}],
}


class TestSpans:
    def test_merged_intersected_and_subtracted(self):
        assert merged([(3, 4), (1, 2), (2, 2.5)]) == [(1, 2.5), (3, 4)]
        assert intersect([(0, 10)], [(2, 3), (8, 12)]) == [(2, 3), (8, 10)]
        assert subtract([(0, 10)], [(2, 3), (8, 12)]) == [(0, 2), (3, 8)]


class TestWhatAProjectHears:
    def test_its_words_and_captions_in_the_file_s_seconds(self):
        plays, words, captions = heard(DRAFT, FILE)
        assert plays == [(40, 50)]
        assert words[0] == {'start': 40.1, 'end': 40.6, 'text': 'w40', 'speaker': 'Ann'}
        assert captions == [{'start': 40, 'end': 50, 'text': 'the draft says'}]

    def test_another_file_and_a_template_say_nothing_of_this_one(self):
        other = {
            'edl': {
                'clips': [
                    clip(0, 5, name='videos/other.mp4'),
                    clip(0, 5, kind='template'),
                ]
            },
            'words': [word(1, 2, 'elsewhere'), word(6, 7, 'titled')],
        }
        assert heard(other, FILE) == ([], [], [])

    def test_a_word_is_moved_by_the_clip_its_middle_is_in(self):
        two = {
            'edl': {'clips': [clip(10, 5), clip(30, 5)]},
            'words': [word(4.8, 5.4, 'across')],
        }
        _, words, _ = heard(two, FILE)
        # Its middle, 5.1 s, is in the second clip, which plays 30 s on.
        assert words == [{'start': 30.0, 'end': 30.4, 'text': 'across'}]


class TestWhatWasSaid:
    def test_the_nearest_source_that_plays_a_second_says_it(self):
        found = said([DRAFT, RECORDING], FILE, 43, 53)
        texts = [w['text'] for w in found['words']]
        # 43 to 50 s from the draft, its correction and its deletion kept; 50
        # to 53 s from the recording, which the draft does not play.
        assert texts == ['w43', 'corrected', 'w45', 'w48', 'w49', 'w50', 'w51', 'w52']
        assert found['words'][1]['speaker'] == 'Ann'

    def test_a_caption_past_the_stretch_is_cut_to_it_and_says_what_is_left(self):
        found = said([RECORDING], FILE, 50, 55)
        assert found['captions'] == [
            # 48 to 52 s, of which 50 to 52 s is in the stretch.
            {'start': 50, 'end': 52, 'text': 'w50 w51'},
            {'start': 52, 'end': 55, 'text': 'w52 w53 w54'},
        ]

    def test_a_stretch_no_source_plays_is_silent(self):
        assert said([DRAFT], FILE, 55, 58) == {'words': [], 'captions': []}
        assert said([], FILE, 0, 5) == {'words': [], 'captions': []}

    def test_without_a_nearer_source_the_farther_one_says_it(self):
        texts = [w['text'] for w in said([RECORDING], FILE, 45, 48)['words']]
        assert texts == ['w45', 'w46', 'w47']

    def test_the_answer_is_in_the_order_it_is_said(self):
        found = said([DRAFT, RECORDING], FILE, 30, 60)
        starts = [w['start'] for w in found['words']]
        assert starts == sorted(starts)
        assert len(found['words']) == 30 - 2

    def test_times_are_kept_to_the_millisecond(self):
        assert said_module.MS == 0.001
        odd = {'edl': {'clips': [clip(1.23456, 2)]}, 'words': [word(0.1, 0.2, 'x')]}
        assert said([odd], FILE, 0, 5)['words'][0]['start'] == 1.335
