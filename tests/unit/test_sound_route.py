"""`GET /project/{id}/sound`: a timeline's level and silences, without a database.

The project collection is stood in for, and the files' analyses are answered
by a stand-in for `routes.audio.library_analysis`, whose own refusals
`test_media_audio.py` pins. What is pinned here: the mapping onto the
timeline through the route, which files are asked about, and each refusal by
code.
"""

import copy

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from alfred import config
from alfred.core.errors import Code, Refusal
from alfred.core.routes import sound as routes
from alfred.core.utils import audio_engine
from alfred.main import app
from tests.unit.render_harness import ADMIN, OWNER, STRANGER, as_user

ANALYSES = {
    'videos/talk.mp4': {
        'peaks': {'rate': 1, 'values': [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]},
        'silences': [{'start': 2, 'end': 3}],
    },
    'videos/song.mp3': {'peaks': {'rate': 1, 'values': [0.9, 0.9]}, 'silences': []},
}


class FakeSoundStore:
    def __init__(self, *projects):
        self.projects = {p['_id']: copy.deepcopy(p) for p in projects}

    async def find(self, query):
        project = self.projects.get(query['_id'])
        if project is None:
            return None
        if 'owner' in query and project.get('owner') != query['owner']:
            return None
        return copy.deepcopy({k: v for k, v in project.items() if k in ('_id', 'edl')})


def project(clips, **fields):
    document = {
        '_id': ObjectId(),
        'owner': OWNER.email,
        'name': 'heard',
        'logic': {},
        'edl': {'clips': clips},
    }
    document.update(fields)
    return document


TALK = {
    'type': 'video',
    'name': 'videos/talk.mp4',
    'duration': 2,
    'inpoint': 1,
    'start': 0,
}
SONG = {'type': 'audio', 'name': 'videos/song.mp3', 'duration': 2, 'start': 2}
TITLE = {'type': 'template', 'name': 'title', 'duration': 1, 'start': 4}


@pytest.fixture
def engine(monkeypatch):
    monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', 'http://engine.test:1059')
    monkeypatch.setattr(audio_engine, 'problem', lambda: None)


@pytest.fixture
def analysed(monkeypatch, engine):
    """The files' analyses, as kept; returns what was asked."""
    asked = []

    async def library_analysis(name, features):
        asked.append((name, tuple(features)))
        if name not in ANALYSES:
            raise Refusal(Code.NOT_FOUND, 'No such file in the media library')
        return ANALYSES[name]

    monkeypatch.setattr(routes, 'library_analysis', library_analysis)
    return asked


@pytest.fixture
def api():
    made = []

    def make(user, *projects):
        store = FakeSoundStore(*projects)
        made.extend(as_user(app, user))
        app.dependency_overrides[routes.get_sound_store] = lambda: store
        made.append(routes.get_sound_store)
        return TestClient(app)

    yield make
    for dependency in made:
        app.dependency_overrides.pop(dependency, None)


def url(document):
    return f'/project/{document["_id"]}/sound'


class TestHearing:
    def test_the_timeline_s_sound_in_its_own_seconds(self, api, analysed):
        mine = project([TALK, SONG, TITLE])
        res = api(OWNER, mine).get(url(mine))
        assert res.status_code == 200, res.text
        assert res.json() == {
            'duration': 5,
            'rate': 1,
            'levels': [0.2, 0.3, 0.9, 0.9, 0],
            'silences': [{'start': 1, 'end': 2}],
        }
        # Each file once, for the two features the mapping reads.
        assert analysed == [
            ('videos/talk.mp4', routes.FEATURES),
            ('videos/song.mp3', routes.FEATURES),
        ]

    def test_a_file_played_twice_is_asked_about_once(self, api, analysed):
        mine = project([TALK, {**TALK, 'start': 2}])
        assert api(OWNER, mine).get(url(mine)).status_code == 200
        assert len(analysed) == 1

    def test_a_superuser_hears_any_project(self, api, analysed):
        theirs = project([TALK])
        assert api(ADMIN, theirs).get(url(theirs)).status_code == 200


class TestRefusals:
    def test_a_project_that_is_not_yours_is_404(self, api, analysed):
        theirs = project([TALK])
        res = api(STRANGER, theirs).get(url(theirs))
        assert res.status_code == 404
        assert res.json()['code'] == 'not_found'
        assert analysed == []

    def test_a_malformed_id_is_422(self, api, analysed):
        res = api(OWNER).get('/project/not-an-id/sound')
        assert res.status_code == 422
        assert res.json()['code'] == 'invalid_id'

    def test_an_empty_timeline_is_422(self, api, analysed):
        mine = project([])
        res = api(OWNER, mine).get(url(mine))
        assert res.status_code == 422
        assert res.json()['code'] == 'timeline_empty'

    def test_a_timeline_with_nothing_to_hear_is_422(self, api, analysed):
        mine = project([TITLE])
        res = api(OWNER, mine).get(url(mine))
        assert res.status_code == 422
        assert res.json()['code'] == 'timeline_silent'
        assert analysed == []

    def test_no_engine_is_503_and_nothing_is_asked(self, api, analysed, monkeypatch):
        monkeypatch.setattr(
            audio_engine, 'problem', lambda: 'No audio engine is configured'
        )
        mine = project([TALK])
        res = api(OWNER, mine).get(url(mine))
        assert res.status_code == 503
        assert res.json()['code'] == 'audio_engine_missing'
        assert analysed == []

    def test_a_file_the_library_does_not_hold_is_404(self, api, analysed):
        mine = project([{**TALK, 'name': 'videos/gone.mp4'}])
        res = api(OWNER, mine).get(url(mine))
        assert res.status_code == 404
        assert res.json()['code'] == 'not_found'
