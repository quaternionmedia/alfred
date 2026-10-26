"""K2 -- the captions routes, without a database.

`GET`/`PUT /project/{id}/captions`, `GET .../words`, `POST .../import` and
`POST .../transcribe`, against an in-memory stand-in for the project
collection and a queue that records what it would send. The database tier
(`integration/test_captions_api.py`) runs the same routes against MongoDB.
"""

import copy
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from alfred import config
from alfred.core.models.captions import RUNNING
from alfred.core.routes import captions as routes
from alfred.core.utils import audio_engine
from alfred.core.utils.captions import MAX_CAPTIONS, MAX_WORDS
from alfred.main import app
from tests.unit.render_harness import ADMIN, OWNER, STRANGER, FakeQueue, as_user


class FakeCaptionsStore:
    """The project collection, in memory, answering as `CaptionsStore` does."""

    def __init__(self, *projects):
        self.projects = {p['_id']: copy.deepcopy(p) for p in projects}
        self.writes = []
        self.projections = []

    async def find(self, query, projection=routes.PROJECTION):
        self.projections.append(projection)
        project = self.projects.get(query['_id'])
        if project is None:
            return None
        if 'owner' in query and project.get('owner') != query['owner']:
            return None
        # The projection's fields, and the id.
        return copy.deepcopy(
            {k: v for k, v in project.items() if k == '_id' or k in projection}
        )

    async def find_words(self, query):
        return await self.find(query, routes.WORDS)

    async def set(self, project_id, fields):
        self.writes.append(copy.deepcopy(fields))
        self.projects[project_id].update(copy.deepcopy(fields))

    async def claim(self, project_id, job, stale_before):
        current = self.projects[project_id].get('captions_job') or {}
        running = current.get('state') in RUNNING
        heard = current.get('updated_at')
        if running and not (heard is not None and heard < stale_before):
            return False
        self.projects[project_id]['captions_job'] = copy.deepcopy(job)
        return True


class RefusingQueue:
    def __call__(self, **kwargs):
        raise ConnectionError('the broker is not answering')


def project(**fields):
    document = {
        '_id': ObjectId(),
        'owner': OWNER.email,
        'name': 'captioned',
        'logic': {},
        'edl': {
            'clips': [
                {'type': 'video', 'name': 'videos/talk.mp4', 'duration': 4, 'start': 0},
                {
                    'type': 'template',
                    'name': 'makeColor',
                    'duration': 2,
                    'start': 4,
                    'data': {'color': '#000000'},
                },
            ]
        },
    }
    document.update(fields)
    return document


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'VIDEO_DIR', str(tmp_path))
    (tmp_path / 'talk.mp4').write_bytes(b'not really a video')
    return tmp_path


@pytest.fixture
def engine(monkeypatch):
    """An audio engine that is configured and usable."""
    monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', 'http://engine.test:8010')
    monkeypatch.setattr(audio_engine, 'problem', lambda: None)


@pytest.fixture
def api(library):
    """`api(user, *projects, queue=None)`: a client, its store and its queue."""
    made = []

    def make(user, *projects, queue=None):
        store, queue = FakeCaptionsStore(*projects), queue or FakeQueue()
        made.extend(as_user(app, user))
        app.dependency_overrides[routes.get_captions_store] = lambda: store
        app.dependency_overrides[routes.get_captions_queue] = lambda: queue
        made.extend([routes.get_captions_store, routes.get_captions_queue])
        return TestClient(app), store, queue

    yield make
    for dependency in made:
        app.dependency_overrides.pop(dependency, None)


def url(document, tail=''):
    return f'/project/{document["_id"]}/captions{tail}'


class TestReading:
    def test_a_project_with_none(self, api):
        mine = project()
        client, _, _ = api(OWNER, mine)
        res = client.get(url(mine))
        assert res.status_code == 200, res.text
        assert res.json() == {
            'captions': [],
            'style': {
                'enabled': False,
                'fontsize': None,
                'color': None,
                'bg': None,
                'position': None,
                'align': None,
                'font': None,
            },
            'job': None,
        }

    def test_what_is_stored(self, api):
        stamped = datetime(2026, 10, 18, 12, 0, 0)
        mine = project(
            captions=[{'start': 1, 'end': 2, 'text': 'Hi'}],
            caption_style={'enabled': False, 'color': '#ffcc00'},
            captions_job={
                'state': 'done',
                'error': None,
                'engine': 'http://e',
                'segments': 1,
                'updated_at': stamped,
            },
        )
        client, _, _ = api(OWNER, mine)
        body = client.get(url(mine)).json()
        assert body['captions'] == [{'start': 1.0, 'end': 2.0, 'text': 'Hi'}]
        assert body['style']['enabled'] is False and body['style']['color'] == '#ffcc00'
        assert body['job']['state'] == 'done'
        # Stored naive, as MongoDB hands it back: it is UTC, and says so.
        assert body['job']['updated_at'].endswith('+00:00')

    def test_a_stored_caption_that_does_not_validate_is_left_out(self, api):
        mine = project(
            captions=[
                {'start': 2, 'end': 1, 'text': 'x'},
                {'start': 0, 'end': 1, 'text': 'ok'},
            ]
        )
        client, _, _ = api(OWNER, mine)
        assert [c['text'] for c in client.get(url(mine)).json()['captions']] == ['ok']

    def test_somebody_else_s_is_404(self, api):
        theirs = project()
        client, _, _ = api(STRANGER, theirs)
        assert client.get(url(theirs)).status_code == 404

    def test_a_superuser_reaches_any(self, api):
        theirs = project()
        client, _, _ = api(ADMIN, theirs)
        assert client.get(url(theirs)).status_code == 200

    def test_a_malformed_id_is_422(self, api):
        client, _, _ = api(OWNER)
        assert client.get('/project/nope/captions').status_code == 422


class TestSaving:
    def test_captions_in_order_and_the_style(self, api):
        mine = project()
        client, store, _ = api(OWNER, mine)
        res = client.put(
            url(mine),
            json={
                'captions': [
                    {'start': 3, 'end': 4, 'text': 'Second'},
                    {'start': 1, 'end': 2, 'text': ' First '},
                ],
                'style': {'fontsize': 40, 'position': ['left', 'bottom'], 'bg': 'none'},
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert [c['text'] for c in body['captions']] == ['First', 'Second']
        assert body['style']['position'] == ['left', 'bottom']
        stored = store.projects[mine['_id']]
        assert [c['start'] for c in stored['captions']] == [1.0, 3.0]
        assert stored['caption_style']['bg'] == ''
        # Not said, and never said before: not drawn, and stored as such.
        assert stored['caption_style']['enabled'] is False
        assert body['style']['enabled'] is False

    def test_only_those_fields_are_written(self, api):
        mine = project(caption_style={'enabled': True})
        client, store, _ = api(OWNER, mine)
        client.put(url(mine), json={'captions': [{'start': 0, 'end': 1, 'text': 'x'}]})
        assert [set(write) for write in store.writes] == [{'captions'}]

    def test_a_project_s_first_captions_are_not_drawn_until_someone_says(self, api):
        """A project's style always states `enabled` once it has captions,
        and states false until it is set: imported or transcribed captions
        are often still being corrected."""
        mine = project()
        client, store, _ = api(OWNER, mine)
        res = client.put(
            url(mine), json={'captions': [{'start': 0, 'end': 1, 'text': 'x'}]}
        )
        assert res.json()['style']['enabled'] is False
        assert store.projects[mine['_id']]['caption_style']['enabled'] is False

    @pytest.mark.parametrize('enabled', [True, False])
    def test_enabled_as_sent(self, api, enabled):
        mine = project(caption_style={'enabled': not enabled})
        client, store, _ = api(OWNER, mine)
        res = client.put(
            url(mine), json={'captions': [], 'style': {'enabled': enabled}}
        )
        assert res.json()['style']['enabled'] is enabled
        assert store.projects[mine['_id']]['caption_style']['enabled'] is enabled

    def test_a_style_without_enabled_keeps_the_one_stored(self, api):
        mine = project(caption_style={'enabled': True, 'color': '#123456'})
        client, store, _ = api(OWNER, mine)
        res = client.put(
            url(mine), json={'captions': [], 'style': {'color': '#abcdef'}}
        )
        stored = store.projects[mine['_id']]['caption_style']
        assert (stored['enabled'], stored['color']) == (True, '#abcdef')
        assert res.json()['style']['enabled'] is True

    def test_a_style_left_out_is_kept(self, api):
        mine = project(caption_style={'enabled': True, 'color': '#123456'})
        client, store, _ = api(OWNER, mine)
        client.put(url(mine), json={'captions': []})
        assert store.projects[mine['_id']]['caption_style']['color'] == '#123456'

    @pytest.mark.parametrize(
        'caption',
        [
            {'start': -1, 'end': 1, 'text': 'x'},
            {'start': 2, 'end': 2, 'text': 'x'},
            {'start': 0, 'end': 1, 'text': '   '},
            {'start': 0, 'end': 1, 'text': 'x' * 501},
            {'start': 0, 'end': 1},
        ],
    )
    def test_a_caption_that_cannot_be_shown_is_422(self, api, caption):
        mine = project()
        client, store, _ = api(OWNER, mine)
        res = client.put(url(mine), json={'captions': [caption]})
        assert res.status_code == 422
        assert store.writes == []

    def test_too_many_is_422(self, api):
        mine = project()
        client, store, _ = api(OWNER, mine)
        many = [
            {'start': i, 'end': i + 1, 'text': 'x'} for i in range(MAX_CAPTIONS + 1)
        ]
        res = client.put(url(mine), json={'captions': many})
        assert res.status_code == 422
        assert str(MAX_CAPTIONS) in res.json()['detail']
        assert store.writes == []

    def test_other_fields_are_422(self, api):
        mine = project()
        client, store, _ = api(OWNER, mine)
        res = client.put(
            url(mine), json={'captions': [], 'captions_job': {'state': 'done'}}
        )
        assert res.status_code == 422
        assert store.writes == []

    def test_somebody_else_s_is_404_and_untouched(self, api):
        theirs = project()
        client, store, _ = api(STRANGER, theirs)
        res = client.put(url(theirs), json={'captions': []})
        assert res.status_code == 404
        assert store.writes == []


WORDS = [
    {'start': 0.5, 'end': 0.9, 'text': 'Hello', 'segment': 0},
    {'start': 0.9, 'end': 1.3, 'text': 'there.', 'segment': 0},
    {'start': 2.0, 'end': 2.0, 'text': 'Oh', 'segment': 1},
]


class TestTheWords:
    def test_none_until_there_has_been_a_transcription(self, api):
        mine = project()
        client, _, _ = api(OWNER, mine)
        res = client.get(url(mine, '/words'))
        assert res.status_code == 200, res.text
        assert res.json() == {'words': []}

    def test_what_is_stored_in_the_order_stored(self, api):
        mine = project(words=list(reversed(WORDS)))
        client, store, _ = api(OWNER, mine)
        assert client.get(url(mine, '/words')).json() == {
            'words': list(reversed(WORDS))
        }
        # Words only.
        assert store.projections == [routes.WORDS]

    def test_the_captions_route_does_not_carry_them(self, api):
        """It is polled during a transcription."""
        mine = project(words=WORDS)
        client, store, _ = api(OWNER, mine)
        assert 'words' not in client.get(url(mine)).json()
        assert 'words' not in store.projections[-1]

    def test_a_stored_word_that_does_not_validate_is_left_out(self, api):
        mine = project(words=[{'start': 2, 'end': 1, 'text': 'back'}, WORDS[0]])
        client, _, _ = api(OWNER, mine)
        assert client.get(url(mine, '/words')).json() == {'words': [WORDS[0]]}

    def test_somebody_else_s_is_404(self, api):
        theirs = project(words=WORDS)
        client, _, _ = api(STRANGER, theirs)
        assert client.get(url(theirs, '/words')).status_code == 404

    def test_a_malformed_id_is_422(self, api):
        client, _, _ = api(OWNER)
        assert client.get('/project/nope/captions/words').status_code == 422

    def test_saved_with_the_captions_in_one_write(self, api):
        mine = project(words=WORDS)
        client, store, _ = api(OWNER, mine)
        cut = [{'start': 0.5, 'end': 0.9, 'text': ' Hello ', 'segment': 0}]
        res = client.put(
            url(mine),
            json={
                'captions': [{'start': 0.5, 'end': 0.9, 'text': 'Hello'}],
                'words': cut,
            },
        )
        assert res.status_code == 200, res.text
        assert 'words' not in res.json()
        assert [set(write) for write in store.writes] == [
            {'captions', 'caption_style', 'words'}
        ]
        assert store.projects[mine['_id']]['words'] == [
            {'start': 0.5, 'end': 0.9, 'text': 'Hello', 'segment': 0}
        ]
        assert client.get(url(mine, '/words')).json()['words'][0]['text'] == 'Hello'

    def test_left_out_they_are_kept_and_sent_empty_they_are_gone(self, api):
        mine = project(words=WORDS)
        client, store, _ = api(OWNER, mine)
        client.put(url(mine), json={'captions': []})
        assert store.projects[mine['_id']]['words'] == WORDS
        client.put(url(mine), json={'captions': [], 'words': []})
        assert store.projects[mine['_id']]['words'] == []

    @pytest.mark.parametrize(
        'word',
        [
            {'start': -1, 'end': 1, 'text': 'x'},
            {'start': 2, 'end': 1, 'text': 'x'},
            {'start': 0, 'end': 1, 'text': '  '},
            {'start': 0, 'end': 1, 'text': 'x' * 101},
            {'start': 0, 'end': 1, 'text': 'x', 'segment': -1},
            {'start': 0, 'text': 'x'},
        ],
    )
    def test_a_word_that_is_not_one_is_422(self, api, word):
        mine = project()
        client, store, _ = api(OWNER, mine)
        res = client.put(url(mine), json={'captions': [], 'words': [word]})
        assert res.status_code == 422
        assert store.writes == []

    def test_more_than_a_project_keeps_is_422(self, api):
        mine = project()
        client, store, _ = api(OWNER, mine)
        many = [{'start': 0, 'end': 0, 'text': 'x'}] * (MAX_WORDS + 1)
        res = client.put(url(mine), json={'captions': [], 'words': many})
        assert res.status_code == 422
        assert store.writes == []


class TestImporting:
    SRT = '1\n00:00:01,000 --> 00:00:02,000\nOne\n\n2\n00:00:03,000 --> 00:00:03,000\nNone long\n'

    def test_parsed_and_not_stored(self, api):
        mine = project()
        client, store, _ = api(OWNER, mine)
        res = client.post(
            url(mine, '/import'), json={'format': 'srt', 'text': self.SRT}
        )
        assert res.status_code == 200, res.text
        assert res.json() == {
            'captions': [{'start': 1.0, 'end': 2.0, 'text': 'One'}],
            'skipped': 1,
        }
        assert store.writes == []

    @pytest.mark.parametrize(
        'format, text',
        [
            ('vtt', 'WEBVTT\n\n00:01.000 --> 00:02.000\nOne\n'),
            ('json', '[{"start": 1, "end": 2, "text": "One"}]'),
        ],
    )
    def test_each_format(self, api, format, text):
        mine = project()
        client, _, _ = api(OWNER, mine)
        res = client.post(url(mine, '/import'), json={'format': format, 'text': text})
        assert res.json()['captions'] == [{'start': 1.0, 'end': 2.0, 'text': 'One'}]

    def test_an_unreadable_file_names_its_line(self, api):
        mine = project()
        client, _, _ = api(OWNER, mine)
        res = client.post(
            url(mine, '/import'), json={'format': 'srt', 'text': 'nonsense\nmore'}
        )
        assert res.status_code == 422
        assert 'line 1' in res.json()['detail']

    def test_an_unknown_format_is_422(self, api):
        mine = project()
        client, _, _ = api(OWNER, mine)
        res = client.post(url(mine, '/import'), json={'format': 'ass', 'text': ''})
        assert res.status_code == 422

    def test_too_large_is_422(self, api):
        mine = project()
        client, _, _ = api(OWNER, mine)
        text = 'x' * (routes.MAX_IMPORT_CHARS + 1)
        res = client.post(url(mine, '/import'), json={'format': 'srt', 'text': text})
        assert res.status_code == 422

    def test_somebody_else_s_is_404(self, api):
        theirs = project()
        client, _, _ = api(STRANGER, theirs)
        res = client.post(
            url(theirs, '/import'), json={'format': 'srt', 'text': self.SRT}
        )
        assert res.status_code == 404


class TestTranscribing:
    def test_queued(self, api, engine):
        mine = project()
        client, store, queue = api(OWNER, mine)
        res = client.post(url(mine, '/transcribe'))
        assert res.status_code == 202, res.text
        job = res.json()['job']
        assert job['state'] == 'queued'
        assert job['engine'] == 'http://engine.test:8010'
        assert queue.sent == [{'projectId': str(mine['_id'])}]
        assert store.projects[mine['_id']]['captions_job']['state'] == 'queued'

    def test_no_engine_is_503_with_the_reason(self, api, monkeypatch):
        monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', None)
        mine = project()
        client, _, queue = api(OWNER, mine)
        res = client.post(url(mine, '/transcribe'))
        assert res.status_code == 503
        assert 'ALFRED_AUDIO_ENGINE_URL' in res.json()['detail']
        assert queue.sent == []

    def test_an_engine_this_build_cannot_reach_is_503(self, api, monkeypatch):
        monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', 'http://engine.test:8010')

        def missing():
            raise ImportError('no vox.media')

        monkeypatch.setattr(audio_engine, '_vox_media', missing)
        mine = project()
        client, _, queue = api(OWNER, mine)
        res = client.post(url(mine, '/transcribe'))
        assert res.status_code == 503
        assert 'vox.media' in res.json()['detail']

    def test_while_one_runs_another_is_409(self, api, engine):
        mine = project()
        client, _, queue = api(OWNER, mine)
        assert client.post(url(mine, '/transcribe')).status_code == 202
        second = client.post(url(mine, '/transcribe'))
        assert second.status_code == 409
        assert len(queue.sent) == 1

    @pytest.mark.parametrize('state', ['done', 'failed'])
    def test_after_one_settles_another_may_start(self, api, engine, state):
        mine = project(
            captions_job={'state': state, 'updated_at': datetime.now(timezone.utc)}
        )
        client, _, _ = api(OWNER, mine)
        assert client.post(url(mine, '/transcribe')).status_code == 202

    def test_one_unheard_from_for_too_long_is_abandoned(self, api, engine):
        long_ago = (
            datetime.now(timezone.utc) - routes.stale_after() - timedelta(minutes=1)
        )
        mine = project(captions_job={'state': 'transcribing', 'updated_at': long_ago})
        client, _, _ = api(OWNER, mine)
        assert client.post(url(mine, '/transcribe')).status_code == 202

    def test_no_timeline_is_422(self, api, engine):
        mine = project(edl=None)
        client, _, queue = api(OWNER, mine)
        res = client.post(url(mine, '/transcribe'))
        assert res.status_code == 422
        assert 'no saved timeline' in res.json()['detail']
        assert queue.sent == []

    def test_a_timeline_with_nothing_to_hear_is_422(self, api, engine):
        silent = {
            'clips': [
                {
                    'type': 'template',
                    'name': 'makeColor',
                    'duration': 2,
                    'data': {'color': '#000000'},
                }
            ]
        }
        mine = project(edl=silent)
        client, _, queue = api(OWNER, mine)
        res = client.post(url(mine, '/transcribe'))
        assert res.status_code == 422
        assert 'nothing to transcribe' in res.json()['detail']

    def test_a_timeline_the_server_will_not_play_is_422(self, api, engine):
        outside = {'clips': [{'type': 'audio', 'name': '/etc/passwd', 'duration': 2}]}
        mine = project(edl=outside)
        client, _, queue = api(OWNER, mine)
        res = client.post(url(mine, '/transcribe'))
        assert res.status_code == 422
        assert 'absolute paths' in res.json()['detail']
        assert queue.sent == []

    def test_a_queue_that_will_not_take_it_fails_the_job_and_says_so(self, api, engine):
        mine = project()
        client, store, _ = api(OWNER, mine, queue=RefusingQueue())
        res = client.post(url(mine, '/transcribe'))
        assert res.status_code == 503
        job = store.projects[mine['_id']]['captions_job']
        assert job['state'] == 'failed'
        assert 'broker' in job['error']
        # Failed, so it can be asked for again at once.
        client2, _, _ = api(OWNER, store.projects[mine['_id']])
        assert client2.post(url(mine, '/transcribe')).status_code == 202

    def test_somebody_else_s_is_404_and_nothing_is_queued(self, api, engine):
        theirs = project()
        client, store, queue = api(STRANGER, theirs)
        assert client.post(url(theirs, '/transcribe')).status_code == 404
        assert queue.sent == [] and 'captions_job' not in store.projects[theirs['_id']]
