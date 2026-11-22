"""`GET` and `POST /project/{id}/conversation`, without a database or an engine.

The project collection is the captions routes' stand-in, and the engine is a
stand-in for `language_engine.read` that records what it was asked. Pinned
here: how words become lines, what is kept, and each refusal by code.
"""

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from alfred import config
from alfred.core.models.captions import Word
from alfred.core.routes import captions as caption_routes
from alfred.core.routes import conversation as routes
from alfred.core.utils import language_engine
from alfred.core.utils.language_engine import Reading
from alfred.core.utils.probe import ProbeCache
from alfred.main import app
from tests.unit.render_harness import OWNER, STRANGER, as_user
from tests.unit.test_captions_routes import FakeCaptionsStore

WORDS = [
    {'start': 0, 'end': 0.4, 'text': 'Here', 'segment': 0, 'speaker': 'Alice'},
    {'start': 0.5, 'end': 0.9, 'text': 'are', 'segment': 0, 'speaker': 'Alice'},
    {'start': 1.0, 'end': 1.4, 'text': 'the rules.', 'segment': 0, 'speaker': 'Alice'},
    {'start': 30, 'end': 30.4, 'text': 'But', 'segment': 1},
    {'start': 30.5, 'end': 30.9, 'text': 'wait.', 'segment': 1},
]


def project(**fields):
    document = {'_id': ObjectId(), 'owner': OWNER.email, 'name': 'talk', 'logic': {}}
    document.update(fields)
    return document


@pytest.fixture
def engine(monkeypatch):
    """The engine, answering; returns the lines it was asked about."""
    monkeypatch.setattr(config, 'LANGUAGE_ENGINE_URL', 'http://words.test:8000')
    monkeypatch.setattr(routes, '_cache', ProbeCache(size=8))
    asked = []

    def read(lines, title=None, transport=None):
        asked.append((title, [(line.start, line.speaker, line.text) for line in lines]))
        return Reading(
            speakers={'Alice': {'color': '#ff6b6b', 'contributions': 1}},
            topics=[
                {
                    'name': 'Rules',
                    'color': '#00d4ff',
                    'points': [{'time': 0, 'intensity': 0.5, 'speaker': 'Alice'}],
                }
            ],
            tangents=[
                {
                    'start': 30,
                    'end': 31,
                    'type': 'orphaned',
                    'topics': [],
                    'text': 'Unknown: But wait.',
                    'resolution': None,
                }
            ],
        )

    monkeypatch.setattr(language_engine, 'read', read)
    return asked


@pytest.fixture
def api():
    made = []

    def make(user, *projects):
        store = FakeCaptionsStore(*projects)
        made.extend(as_user(app, user))
        app.dependency_overrides[caption_routes.get_captions_store] = lambda: store
        made.append(caption_routes.get_captions_store)
        return TestClient(app)

    yield make
    for dependency in made:
        app.dependency_overrides.pop(dependency, None)


def url(document):
    return f'/project/{document["_id"]}/conversation'


class TestLines:
    def test_a_line_per_stretch_of_speech_from_its_first_word(self):
        lines = routes.lines_of([Word.model_validate(w) for w in WORDS])
        assert [(line.start, line.end, line.speaker, line.text) for line in lines] == [
            (0, 1.4, 'Alice', 'Here are the rules.'),
            (30, 30.9, 'Unknown', 'But wait.'),
        ]

    def test_words_without_a_stretch_break_at_a_gap(self):
        words = [
            Word(start=0, end=0.4, text='one'),
            Word(start=0.5, end=0.9, text='two'),
            Word(start=3, end=3.4, text='three'),
        ]
        assert [line.text for line in routes.lines_of(words)] == ['one two', 'three']


class TestReading:
    def test_the_stored_words_read_and_answered_in_alfred_s_shape(self, api, engine):
        mine = project(words=WORDS)
        res = api(OWNER, mine).get(url(mine))
        assert res.status_code == 200, res.text
        body = res.json()
        assert body['speakers'] == {'Alice': {'color': '#ff6b6b', 'contributions': 1}}
        assert body['topics'][0]['name'] == 'Rules'
        assert body['tangents'][0]['type'] == 'orphaned'
        assert [line["speaker"] for line in body["lines"]] == ['Alice', 'Unknown']
        [(title, lines)] = engine
        assert title == str(mine['_id'])
        assert lines == [
            (0, 'Alice', 'Here are the rules.'),
            (30, 'Unknown', 'But wait.'),
        ]

    def test_the_words_sent_are_read_instead_and_nothing_is_stored(self, api, engine):
        mine = project(words=WORDS)
        client = api(OWNER, mine)
        sent = [{'start': 5, 'end': 6, 'text': 'Later.', 'speaker': 'Bob'}]
        res = client.post(url(mine), json={'words': sent})
        assert res.status_code == 200, res.text
        assert res.json()['lines'] == [
            {'start': 5, 'end': 6, 'speaker': 'Bob', 'text': 'Later.'}
        ]
        assert engine[-1][1] == [(5, 'Bob', 'Later.')]
        assert (
            client.get(f'/project/{mine["_id"]}/captions/words').json()['words'][0][
                'text'
            ]
            == 'Here'
        )

    def test_the_same_words_are_read_once(self, api, engine):
        mine = project(words=WORDS)
        client = api(OWNER, mine)
        client.get(url(mine))
        client.get(url(mine))
        client.post(url(mine), json={'words': WORDS})
        assert len(engine) == 1

    def test_a_speaker_named_is_another_reading(self, api, engine):
        mine = project(words=WORDS)
        client = api(OWNER, mine)
        client.get(url(mine))
        renamed = [{**w, 'speaker': 'Bob'} for w in WORDS]
        client.post(url(mine), json={'words': renamed})
        assert len(engine) == 2


class TestRefusals:
    def test_no_words_is_422(self, api, engine):
        mine = project(words=[])
        res = api(OWNER, mine).get(url(mine))
        assert res.status_code == 422
        assert res.json()['code'] == 'no_words'
        assert engine == []

    def test_no_engine_is_503(self, api, monkeypatch):
        monkeypatch.setattr(config, 'LANGUAGE_ENGINE_URL', None)
        mine = project(words=WORDS)
        res = api(OWNER, mine).get(url(mine))
        assert res.status_code == 503
        assert res.json()['code'] == 'language_engine_missing'
        assert 'ALFRED_LANGUAGE_ENGINE_URL' in res.json()['detail']

    def test_an_engine_that_fails_is_502(self, api, engine, monkeypatch):
        def fail(lines, title=None, transport=None):
            raise language_engine.LanguageEngineFailed(
                'the language engine at http://w: broke'
            )

        monkeypatch.setattr(language_engine, 'read', fail)
        mine = project(words=WORDS)
        res = api(OWNER, mine).get(url(mine))
        assert res.status_code == 502
        assert res.json()['code'] == 'language_engine_failed'

    def test_a_project_that_is_not_yours_is_404(self, api, engine):
        theirs = project(words=WORDS)
        assert api(STRANGER, theirs).get(url(theirs)).status_code == 404
        assert engine == []

    def test_a_speaker_too_long_is_refused_by_shape(self, api, engine):
        mine = project(words=WORDS)
        res = api(OWNER, mine).post(
            url(mine),
            json={'words': [{'start': 0, 'end': 1, 'text': 'x', 'speaker': 'n' * 80}]},
        )
        assert res.status_code == 422
