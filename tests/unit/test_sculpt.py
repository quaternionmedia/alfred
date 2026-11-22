"""Running a recipe over a source (`alfred/core/utils/sculpt.py`).

One source with speech, a spike and a few pauses in it, and each operation
at its edge; then every built-in recipe over it, leaving drafts whose
timelines, captions and words are the source's cut.
"""

import pytest

from alfred.core.models.recipes import RecipeError
from alfred.core.utils import sculpt
from alfred.core.utils.recipes_builtin import BY_NAME
from alfred.core.utils.sculpt import Candidate, Source

# A minute of talk: a sentence every few seconds, a long pause at 30 s, a
# filler, and nothing said after 55 s.
SAID = [
    (1, 'Welcome', 'to', 'the', 'show.'),
    (6, 'Tonight', 'we', 'um', 'play.'),
    (11, 'First', 'the', 'rules.'),
    (16, 'You', 'roll,', 'you', 'move,', 'you', 'score.'),
    (21, 'Any', 'questions?'),
    (24, 'No.'),
    # The long pause: nothing from 25 to 34.
    (34, 'Then', 'we', 'begin.'),
    (39, 'Oh', 'no,', 'the', 'tower', 'fell!'),
    (45, 'That', 'was', 'the', 'best', 'bit', 'of', 'the', 'night.'),
    (51, 'Good', 'night.'),
]


def make_words():
    words = []
    for n, (start, *texts) in enumerate(SAID):
        for k, text in enumerate(texts):
            words.append(
                {
                    'start': start + k * 0.5,
                    'end': start + k * 0.5 + 0.4,
                    'text': text,
                    'segment': n,
                }
            )
    return words


def make_captions():
    return [
        {'start': start, 'end': start + 0.5 * len(texts), 'text': ' '.join(texts)}
        for start, *texts in SAID
    ]


def series(rate, spikes, length=60, quiet=0.1, loud=0.9):
    """One value a second, `loud` at the seconds in `spikes`, `quiet` elsewhere."""
    return {
        'rate': rate,
        'values': [loud if s in spikes else quiet for s in range(length)],
    }


@pytest.fixture
def source():
    return Source(
        clips=[
            {
                'type': 'video',
                'name': 'videos/show.mp4',
                'duration': 60,
                'start': 0,
                'inpoint': 0,
            }
        ],
        captions=make_captions(),
        words=make_words(),
        # The level and the motion both spike at 40 and 41 s, when the tower
        # fell; the level alone at 10 s, the motion alone at 50 s.
        levels=series(1, {10, 40, 41}),
        motion=series(1, {40, 41, 50}),
        silences=[{'start': 25, 'end': 34}, {'start': 52, 'end': 60}],
        # The picture cuts at 10.3 s, 34.2 s and 45.4 s.
        scenes=[10.3, 34.2, 45.4],
    )


WORDS = sculpt.spoken(make_words())
CAPTIONS = sculpt.spoken(make_captions())


class TestWindows:
    def test_each_begins_at_a_word_and_ends_at_a_word_within_its_length(self):
        found = sculpt.windows(WORDS, shortest=4, longest=8, every=5)
        assert found, 'no windows'
        starts = {w['start'] for w in WORDS}
        ends = {w['end'] for w in WORDS}
        for c in found:
            assert c.start in starts
            assert c.end in ends
            assert 4 <= c.length <= 8

    def test_a_sentence_s_end_in_range_is_preferred_to_a_later_word_s(self):
        # From 11 s: "First the rules." ends at 12.4, too soon; "You roll, you
        # move, you score." ends at 18.9, in range, and "Any" at 21.4 is later.
        found = sculpt.windows(WORDS, shortest=4, longest=10.5, every=10)
        [first] = [c for c in found if c.start == 11]
        assert first.end == 18.9

    def test_without_a_sentence_s_end_the_last_word_s_end_is_taken(self):
        words = sculpt.spoken(
            [
                {'start': 0, 'end': 0.4, 'text': 'one'},
                {'start': 3, 'end': 3.4, 'text': 'two'},
            ]
        )
        [found] = sculpt.windows(words, shortest=2, longest=5, every=2)
        assert (found.start, found.end) == (0, 3.4)

    def test_the_same_window_is_not_found_twice(self):
        found = sculpt.windows(WORDS, shortest=4, longest=8, every=0.5)
        assert len({(c.start, c.end) for c in found}) == len(found)

    def test_shortest_above_longest_is_refused(self):
        with pytest.raises(RecipeError, match='shortest'):
            sculpt.windows(WORDS, shortest=9, longest=8, every=1)

    def test_no_words_is_no_windows(self):
        assert sculpt.windows([], 8, 12, 2) == []


class TestOtherSegments:
    def test_chapters_break_at_the_long_pause(self):
        found = sculpt.chapters(WORDS, pause=4)
        assert [(c.chapter, c.start) for c in found] == [(1, 1), (2, 34)]
        assert found[0].end == 24.4

    def test_sentences_join_captions_until_one_ends(self):
        captions = sculpt.spoken(
            [
                {'start': 0, 'end': 1, 'text': 'Well, as I'},
                {'start': 1, 'end': 2, 'text': 'was saying.'},
                {'start': 3, 'end': 4, 'text': 'Right?'},
                {'start': 5, 'end': 6, 'text': 'and then'},
            ]
        )
        found = sculpt.sentences(captions)
        assert [(c.start, c.end) for c in found] == [(0, 2), (3, 4), (5, 6)]

    def test_spans_are_cut_at_pauses_and_sentence_ends_within_their_length(self):
        # The captions are three and a half seconds apart at most within a
        # chapter, and nine and a half across the long pause.
        found = sculpt.spans(
            CAPTIONS, pause=3.6, chapter_pause=4, shortest=4, longest=12
        )
        assert found
        assert all(4 <= c.length <= 12 or c.length < 4 for c in found)
        assert {c.chapter for c in found} == {1, 2}
        with pytest.raises(RecipeError):
            sculpt.spans(CAPTIONS, pause=5, chapter_pause=4, shortest=4, longest=12)

    def test_silences_longer_than(self, source):
        found = sculpt.silences(source.silences, longer_than=8)
        assert [(c.start, c.end) for c in found] == [(25, 34)]


class TestScores:
    def test_dialogue_is_words_a_second_scaled_to_the_most_talkative(self):
        quiet = Candidate(start=21, end=25)  # "Any questions? No."
        busy = Candidate(start=16, end=20)  # six words
        sculpt.dialogue([quiet, busy], WORDS)
        assert busy.scores['dialogue'] == 1.0
        assert 0 < quiet.scores['dialogue'] < 1.0

    def test_spikes_count_only_where_both_level_and_motion_rise_at_once(self, source):
        tower = Candidate(start=38, end=44)
        level_only = Candidate(start=8, end=14)
        motion_only = Candidate(start=48, end=54)
        quiet = Candidate(start=1, end=7)
        note = sculpt.spikes(
            [tower, level_only, motion_only, quiet], source, 1.5, 1.5, False
        )
        assert note is None
        assert tower.scores['spikes'] == 1.0
        assert level_only.scores['spikes'] == 0
        assert motion_only.scores['spikes'] == 0
        assert quiet.scores['spikes'] == 0

    def test_a_spike_where_nobody_speaks_counts_only_when_asked(self, source):
        # Move the spike into the long pause.
        source.levels = series(1, {28})
        source.motion = series(1, {28})
        pause = Candidate(start=26, end=32)
        assert sculpt.spikes([pause], source, 1.5, 1.5, where_words=True) is None
        assert pause.scores['spikes'] == 0
        sculpt.spikes([pause], source, 1.5, 1.5, where_words=False)
        assert pause.scores['spikes'] == 1.0

    def test_without_a_measure_spikes_leave_a_note_and_no_score(self, source):
        source.motion = None
        c = Candidate(start=38, end=44)
        note = sculpt.spikes([c], source, 1.5, 1.5, True)
        assert 'motion' in note
        assert c.scores == {}


class TestSpeakers:
    @staticmethod
    def named(names):
        """The words with a speaker per stretch of speech, from `names` by segment."""
        return sculpt.spoken(
            [{**w, 'speaker': names.get(w['segment'])} for w in make_words()]
        )

    def test_each_run_of_one_speaker_s_words_is_a_turn_titled_by_the_speaker(self):
        words = self.named({0: 'Alice', 1: 'Alice', 2: 'Bob', 3: 'Bob', 4: 'Alice'})
        found = sculpt.speakers(words, '', 0.5, 60)
        assert [(c.start, c.end, c.title) for c in found] == [
            (1, 7.9, 'Alice'),
            (11, 18.9, 'Bob'),
            (21, 21.9, 'Alice'),
            (24, 51.9, 'Unknown'),
        ]
        # A turn shorter than `shortest` is left out: the question, 0.9 s.
        assert [c.title for c in sculpt.speakers(words, '', 1, 60)] == [
            'Alice',
            'Bob',
            'Unknown',
        ]

    def test_who_keeps_one_speaker_s_turns_whatever_the_case(self):
        """Mutation: match the name exactly -- red."""
        words = self.named({0: 'Alice', 2: 'Bob'})
        found = sculpt.speakers(words, ' alice ', 0.1, 60)
        assert [c.title for c in found] == ['Alice']
        assert sculpt.speakers(words, 'nobody', 0.1, 60) == []

    def test_a_short_turn_is_left_out_and_a_long_one_cut_at_word_ends(self):
        words = self.named({n: 'Alice' for n in range(10)})
        [whole] = sculpt.speakers(words, '', 1, 60)
        assert (whole.start, whole.end) == (1, 51.9)
        pieces = sculpt.speakers(words, '', 1, 20)
        assert all(c.end - c.start <= 20 for c in pieces)
        assert pieces[0].start == 1 and pieces[-1].end == 51.9
        assert sculpt.speakers(self.named({0: 'Alice'}), 'Alice', 10, 60) == []

    def test_shortest_above_longest_is_refused(self):
        with pytest.raises(RecipeError, match='speakers: shortest'):
            sculpt.speakers(WORDS, '', 9, 8)


class TestScenes:
    def test_each_edge_moves_to_the_nearest_cut_within_reach(self):
        """Mutation: move an edge to a cut however far -- red."""
        found = [Candidate(start=10, end=20), Candidate(start=34.6, end=46)]
        kept = sculpt.snap_to_scenes(found, [10.3, 34.2, 45.4], within=1.0)
        assert [(c.start, c.end) for c in kept] == [(10.3, 20), (34.2, 45.4)]

    def test_an_edge_with_no_cut_in_reach_stays(self):
        [c] = sculpt.snap_to_scenes([Candidate(start=12, end=30)], [10.3, 34.2], 1.0)
        assert (c.start, c.end) == (12, 30)

    def test_a_candidate_left_with_no_length_or_a_twin_goes(self):
        found = [
            Candidate(start=10.2, end=10.5),
            Candidate(start=10, end=20),
            Candidate(start=10.4, end=20.3),
        ]
        kept = sculpt.snap_to_scenes(found, [10.3, 20.1], 0.5)
        assert [(c.start, c.end) for c in kept] == [(10.3, 20.1)]

    def test_without_a_measure_the_step_leaves_a_note(self):
        state = sculpt.State(candidates=[Candidate(start=10, end=20)])
        sculpt.apply('scenes', {'within': 1.0}, state, Source(clips=[]), [], [])
        assert state.notes == [
            'scenes: no scene change was measured, so no edge was moved'
        ]
        assert (state.candidates[0].start, state.candidates[0].end) == (10, 20)

    def test_a_recipe_s_windows_are_cut_at_the_picture_s_cuts(self, source):
        steps = [
            {'op': 'windows', 'shortest': 4, 'longest': 8, 'every': 5},
            {'op': 'scenes', 'within': 1.5},
            {'op': 'compose', 'how': 'each'},
        ]
        run = sculpt.run(steps, {}, [], source)
        edges = {edge for d in run.drafts for edge in d.spans[0]}
        assert {34.2, 45.4} & edges


class TestFilters:
    def test_top_keeps_the_highest_that_do_not_overlap_in_timeline_order(self):
        a = Candidate(start=0, end=10, scores={'dialogue': 0.5})
        b = Candidate(start=5, end=15, scores={'dialogue': 0.9})
        c = Candidate(start=20, end=30, scores={'dialogue': 0.7})
        d = Candidate(start=40, end=50, scores={'dialogue': 0.1})
        kept = sculpt.top([a, b, c, d], {'dialogue': 1.0}, count=2)
        assert kept == [b, c]

    def test_weights_change_the_order(self):
        a = Candidate(start=0, end=10, scores={'dialogue': 0.9, 'spikes': 0.0})
        b = Candidate(start=20, end=30, scores={'dialogue': 0.2, 'spikes': 1.0})
        assert sculpt.top([a, b], {'dialogue': 1, 'spikes': 1}, 1) == [b]
        assert sculpt.top([a, b], {'dialogue': 1, 'spikes': 0.5}, 1) == [a]

    def test_keep_by_length(self):
        kept = sculpt.keep([Candidate(0, 3), Candidate(0, 10), Candidate(0, 30)], 4, 12)
        assert [c.length for c in kept] == [10]

    def test_filler_ranges_match_the_word_whatever_its_punctuation(self):
        words = sculpt.spoken(
            [
                {'start': 1, 'end': 1.3, 'text': 'Um,'},
                {'start': 2, 'end': 2.3, 'text': 'well'},
                {'start': 3, 'end': 3.3, 'text': 'uh...'},
            ]
        )
        assert sculpt.filler_ranges(words, ['um', ' uh']) == [[1, 1.3], [3, 3.3]]


class TestEdits:
    def test_tighten_cuts_each_long_pause_down_to_what_is_kept(self):
        ranges = sculpt.tighten_ranges(WORDS, longer_than=4, to=0.5)
        # The pause from 24.4 to 34: half a second of it stays.
        assert ranges == [[24.9, 34]]


class TestCompose:
    def test_each_candidate_is_a_draft_cut_from_the_source(self, source):
        state = sculpt.State(
            candidates=[Candidate(start=39, end=50, scores={'dialogue': 1.0})]
        )
        [draft] = sculpt.compose(state, source)
        assert draft.number == 1
        assert draft.spans == [[39, 50]]
        assert draft.timeline['duration'] == 11
        [clip] = draft.timeline['clips']
        assert (clip['inpoint'], clip['outpoint'], clip['start']) == (39, 50, 0)
        assert [w['text'] for w in draft.timeline['words']][:2] == ['Oh', 'no,']
        assert draft.timeline['words'][0]['start'] == 0
        assert draft.timeline['captions'][0]['text'] == 'Oh no, the tower fell!'
        assert 'scored dialogue 1.00' in draft.description

    def test_together_takes_the_best_up_to_the_target_in_order(self, source):
        state = sculpt.State(
            candidates=[
                Candidate(start=1, end=5, scores={'s': 0.2}),
                Candidate(start=39, end=44, scores={'s': 1.0}),
                Candidate(start=45, end=51, scores={'s': 0.8}),
            ],
            how='together',
            target=11,
        )
        [draft] = sculpt.compose(state, source)
        assert draft.spans == [[39, 44], [45, 51]]
        assert draft.timeline['duration'] == 11
        assert len(draft.timeline['clips']) == 2

    def test_the_whole_source_with_its_edits(self, source):
        state = sculpt.State(how='whole', edits=[[24.9, 34]])
        [draft] = sculpt.compose(state, source)
        assert draft.timeline['duration'] == pytest.approx(60 - 9.1)
        assert draft.spans == [[0, 60]]

    def test_nothing_kept_is_no_draft(self, source):
        assert sculpt.compose(sculpt.State(), source) == []


class TestResolve:
    FIELDS = [{'type': 'Text', 'attrs': {'name': 'count', 'defaultValue': '7'}}]

    def test_a_value_sent_beats_the_field_s_default_beats_the_operation_s(self):
        step = {'op': 'top', 'count': {'var': 'count'}}
        assert sculpt.resolve(step, {'count': '3'}, self.FIELDS)['count'] == 3
        assert sculpt.resolve(step, {}, self.FIELDS)['count'] == 7
        assert sculpt.resolve(step, {}, [])['count'] == 25

    def test_a_value_out_of_range_is_refused_when_it_runs(self):
        with pytest.raises(RecipeError, match='count: 0 is below 1'):
            sculpt.resolve(
                {'op': 'top', 'count': {'var': 'count'}}, {'count': '0'}, self.FIELDS
            )


class TestTheBuiltInRecipes:
    def run(self, name, source, **values):
        recipe = BY_NAME[name]
        return sculpt.run(recipe['steps'], values, recipe['fields'], source)

    def test_highlights_leaves_shorts_scored_by_dialogue_and_spikes(self, source):
        run = self.run('highlights', source, shortest='4', longest='8', count='3')
        assert run.notes == []
        assert 1 <= len(run.drafts) <= 3
        for draft in run.drafts:
            assert 4 <= draft.timeline['duration'] <= 8
            assert set(draft.scores) == {'dialogue', 'spikes'}
            assert draft.timeline['words']
        # The tower falling, the two spiking seconds, is in one of them.
        assert any(s <= 40 and 41 <= e for [s, e] in (d.spans[0] for d in run.drafts))

    def test_teaser_is_one_draft_of_about_the_target(self, source):
        [draft] = self.run(
            'teaser', source, shortest='4', longest='8', target='12'
        ).drafts
        assert draft.timeline['duration'] <= 12
        assert len(draft.spans) >= 1

    def test_chapters_are_two(self, source):
        drafts = self.run('chapters', source).drafts
        assert [d.spans for d in drafts] == [[[1, 24.4]], [[34, 51.9]]]
        assert 'chapter 2' in drafts[1].description

    def test_excerpts_follow_the_flow_s_proposal(self, source):
        run = self.run('excerpts', source, shortest='4', longest='20')
        assert run.drafts
        assert all(d.timeline['captions'] for d in run.drafts)

    def test_tight_cut_is_one_draft_shorter_than_the_source(self, source):
        [draft] = self.run('tight-cut', source).drafts
        assert draft.timeline['duration'] < 60
        assert 'um' not in [w['text'] for w in draft.timeline['words']]

    def test_quotes_are_tall_with_their_captions_drawn(self, source):
        run = self.run('quotes', source, count='2')
        assert len(run.drafts) == 2
        for draft in run.drafts:
            assert draft.render_settings == {'width': 1080, 'height': 1920}
            assert draft.captions_drawn is True

    def test_a_source_with_no_words_leaves_a_note_and_no_drafts(self):
        empty = Source(
            clips=[{'type': 'video', 'name': 'videos/a.mp4', 'duration': 10}]
        )
        run = self.run('highlights', empty)
        assert run.drafts == []
        assert run.notes[-1] == 'no stretch of the source was found to keep'
