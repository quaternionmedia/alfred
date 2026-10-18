"""K2 -- a timeline's sound, transcribed into captions, as the worker does it.

What an engine heard becomes captions a person can read: long stretches of
speech are cut at word boundaries, times are clamped to the timeline, empty
text is dropped. The Celery task records where the job has got to on the
project -- `transcribing`, then `done` or `failed` with a reason in a line --
and the captions it made. The engine, the mixing and the database are stood
in for here; the pipeline tier mixes a real timeline.
"""

import pytest
from bson import ObjectId
from otto.models import Edl

from alfred.core.utils import audio_engine, tasks
from alfred.core.utils.audio_engine import Segment, Word
from alfred.core.utils.captions import (
    MAX_CAPTIONS,
    TRANSCRIPT_CHARS,
    TRANSCRIPT_SECONDS,
    TooManyCaptions,
    captions_from_transcript,
)
from alfred.core.utils.transcription import NothingToHear, sounding_timeline


def spoken(start, words, step=0.4, space=True):
    """A segment whose words are `step` seconds each, from `start`."""
    made = [
        Word(start + i * step, start + (i + 1) * step, f' {w}' if space else w)
        for i, w in enumerate(words.split())
    ]
    return Segment(start, start + len(made) * step, ' ' + words, tuple(made))


def texts(captions):
    return [c.text for c in captions]


class TestFromATranscript:
    def test_a_short_segment_is_one_caption_timed_by_its_words(self):
        [caption] = captions_from_transcript([spoken(1.0, 'Hello there.')])
        assert (caption.start, caption.end, caption.text) == (1.0, 1.8, 'Hello there.')

    def test_words_without_their_own_spaces_are_joined_with_spaces(self):
        [caption] = captions_from_transcript([spoken(0, 'no spaces here', space=False)])
        assert caption.text == 'no spaces here'

    def test_long_speech_is_cut_at_word_boundaries(self):
        words = ' '.join(f'word{i}' for i in range(60))
        captions = captions_from_transcript([spoken(0, words, step=0.1)])
        assert len(captions) > 1
        assert all(len(c.text) <= TRANSCRIPT_CHARS for c in captions)
        rejoined = ' '.join(texts(captions)).split()
        assert rejoined == words.split()

    def test_slow_speech_is_cut_by_time(self):
        captions = captions_from_transcript(
            [spoken(0, 'one two three four five six', step=2.0)]
        )
        assert all(c.end - c.start <= TRANSCRIPT_SECONDS for c in captions)
        assert len(captions) >= 2

    def test_a_full_sentence_ends_a_caption(self):
        captions = captions_from_transcript(
            [
                spoken(
                    0, 'This is a complete sentence here. And then another one follows.'
                )
            ]
        )
        assert texts(captions)[0] == 'This is a complete sentence here.'

    def test_a_segment_without_words_stands_as_it_is(self):
        segment = Segment(2.0, 4.0, ' Just the segment. ', ())
        [caption] = captions_from_transcript([segment])
        assert (caption.start, caption.end, caption.text) == (
            2.0,
            4.0,
            'Just the segment.',
        )

    def test_empty_text_is_dropped(self):
        assert captions_from_transcript([Segment(0, 1, '  ', ())]) == []

    def test_times_are_clamped_to_the_timeline(self):
        captions = captions_from_transcript(
            [
                Segment(-0.5, 1.0, 'early', ()),
                Segment(4.5, 6.0, 'late', ()),
                Segment(7, 8, 'gone', ()),
            ],
            until=5.0,
        )
        assert [(c.start, c.end) for c in captions] == [(0.0, 1.0), (4.5, 5.0)]

    def test_a_word_with_no_length_is_still_shown(self):
        segment = Segment(1.0, 1.0, 'blip', (Word(1.0, 1.0, ' blip'),))
        [caption] = captions_from_transcript([segment])
        assert caption.end > caption.start

    def test_in_order(self):
        captions = captions_from_transcript(
            [Segment(5, 6, 'b', ()), Segment(1, 2, 'a', ())]
        )
        assert texts(captions) == ['a', 'b']

    def test_more_than_a_project_carries_says_so(self):
        many = [Segment(i, i + 0.5, 'x', ()) for i in range(MAX_CAPTIONS + 1)]
        with pytest.raises(TooManyCaptions):
            captions_from_transcript(many)


class TestWhatCanBeHeard:
    def test_only_video_and_audio_clips_as_long_as_the_timeline(self):
        edl = Edl.parse_obj(
            {
                'clips': [
                    {
                        'type': 'template',
                        'name': 'title',
                        'duration': 3,
                        'data': {'text': 'x'},
                    },
                    {
                        'type': 'audio',
                        'name': 'videos/a.wav',
                        'start': 1,
                        'duration': 2,
                    },
                    {
                        'type': 'image',
                        'name': 'videos/b.png',
                        'start': 4,
                        'duration': 6,
                    },
                ]
            }
        )
        sounding = sounding_timeline(edl)
        assert [c.type for c in sounding.clips] == ['audio']
        assert sounding.duration == 10

    def test_a_silent_timeline_has_nothing(self):
        edl = Edl.parse_obj(
            {'clips': [{'type': 'template', 'name': 'makeColor', 'duration': 1}]}
        )
        assert sounding_timeline(edl) is None


class FakeCollection:
    def __init__(self, *documents):
        self.documents = {d['_id']: dict(d) for d in documents}
        self.updates = []

    def find_one(self, query, projection=None):
        document = self.documents.get(query['_id'])
        return dict(document) if document else None

    def update_one(self, query, update):
        self.updates.append(update['$set'])
        if query['_id'] in self.documents:
            self.documents[query['_id']].update(update['$set'])


@pytest.fixture
def projects(monkeypatch):
    """`projects(*documents)`: the collection the task writes to."""

    def make(*documents):
        collection = FakeCollection(*documents)
        monkeypatch.setattr(tasks, 'get_sync_db', lambda: {tasks.PROJECTS: collection})
        return collection

    return make


EDL = {'clips': [{'type': 'audio', 'name': 'videos/talk.wav', 'duration': 3}]}


def heard(monkeypatch, outcome):
    """Have the timeline 'transcribed' to `outcome`, or raise it."""
    calls = []

    def transcribe_timeline(edl):
        calls.append(edl)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(tasks, 'transcribe_timeline', transcribe_timeline)
    return calls


class TestTheTask:
    def test_transcribing_then_done_with_the_captions(self, projects, monkeypatch):
        from alfred.core.models.captions import Caption

        project_id = ObjectId()
        collection = projects({'_id': project_id, 'edl': EDL})
        calls = heard(monkeypatch, ([Caption(start=0.5, end=1.5, text='Hi')], 3))

        tasks.transcribeCaptions(projectId=str(project_id))

        assert calls == [EDL]
        states = [u['captions_job']['state'] for u in collection.updates]
        assert states == ['transcribing', 'done']
        stored = collection.documents[project_id]
        assert stored['captions'] == [{'start': 0.5, 'end': 1.5, 'text': 'Hi'}]
        assert stored['captions_job']['segments'] == 3
        assert stored['captions_job']['error'] is None
        assert stored['captions_job']['updated_at'] is not None

    def test_an_engine_failure_is_recorded_plainly(self, projects, monkeypatch):
        project_id = ObjectId()
        collection = projects({'_id': project_id, 'edl': EDL})
        heard(
            monkeypatch,
            audio_engine.AudioEngineFailed('the audio engine at http://e: refused'),
        )

        tasks.transcribeCaptions(projectId=str(project_id))

        job = collection.documents[project_id]['captions_job']
        assert job['state'] == 'failed'
        assert job['error'] == 'the audio engine at http://e: refused'
        assert 'captions' not in collection.documents[project_id]

    def test_nothing_to_hear_is_recorded_plainly(self, projects, monkeypatch):
        project_id = ObjectId()
        collection = projects({'_id': project_id, 'edl': EDL})
        heard(monkeypatch, NothingToHear('the timeline has no video or audio clips'))
        tasks.transcribeCaptions(projectId=str(project_id))
        assert collection.documents[project_id]['captions_job']['error'] == (
            'the timeline has no video or audio clips'
        )

    def test_anything_else_is_recorded_with_its_name(self, projects, monkeypatch):
        project_id = ObjectId()
        collection = projects({'_id': project_id, 'edl': EDL})
        heard(monkeypatch, OSError('disk full\nand more'))
        tasks.transcribeCaptions(projectId=str(project_id))
        assert (
            collection.documents[project_id]['captions_job']['error']
            == 'OSError: disk full'
        )

    def test_a_project_without_a_timeline(self, projects, monkeypatch):
        project_id = ObjectId()
        collection = projects({'_id': project_id})
        calls = heard(monkeypatch, ([], 0))
        tasks.transcribeCaptions(projectId=str(project_id))
        assert calls == []
        job = collection.documents[project_id]['captions_job']
        assert (job['state'], job['error']) == (
            'failed',
            'the project has no saved timeline to transcribe',
        )

    def test_a_project_deleted_while_it_waited_is_left_alone(
        self, projects, monkeypatch
    ):
        collection = projects()
        calls = heard(monkeypatch, ([], 0))
        tasks.transcribeCaptions(projectId=str(ObjectId()))
        assert calls == [] and collection.updates == []

    def test_what_escapes_the_task_still_fails_the_job(self, projects):
        project_id = ObjectId()
        collection = projects({'_id': project_id, 'edl': EDL})
        tasks.transcribeCaptions.on_failure(
            RuntimeError('worker lost'),
            'task-1',
            (),
            {'projectId': str(project_id)},
            None,
        )
        job = collection.documents[project_id]['captions_job']
        assert (job['state'], job['error']) == ('failed', 'RuntimeError: worker lost')

    def test_the_engine_is_recorded_without_credentials(self, projects, monkeypatch):
        from alfred import config

        monkeypatch.setattr(
            config, 'AUDIO_ENGINE_URL', 'http://me:pw@engine.test:8010/'
        )
        project_id = ObjectId()
        collection = projects({'_id': project_id, 'edl': EDL})
        heard(monkeypatch, ([], 0))
        tasks.transcribeCaptions(projectId=str(project_id))
        assert collection.documents[project_id]['captions_job']['engine'] == (
            'http://engine.test:8010'
        )
