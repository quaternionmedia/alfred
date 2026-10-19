"""K2 against a real database: captions on a project, end to end.

The routes, real authentication and real queries; the queue recorded rather
than sent, and the worker's task run in-process against the same database,
so a transcription's whole lifecycle -- queued, transcribing, done or failed --
is what a client polling `GET /project/{id}/captions` sees. The audio engine
and the mixing are stood in for at the task (`transcribe_timeline`): the
pipeline tier mixes for real, and the browser suite runs a stub engine.
"""

import pytest
from bson import ObjectId

pytestmark = pytest.mark.needs_db

SRT = '1\n00:00:02,000 --> 00:00:03,000\nLater\n\n2\n00:00:00,500 --> 00:00:01,500\nSooner\n'
TALK = {
    'clips': [
        {'type': 'audio', 'name': 'videos/talk.wav', 'duration': 4.0, 'start': 0.0}
    ]
}


class RecordingQueue:
    def __init__(self):
        self.sent = []

    def __call__(self, **kwargs):
        self.sent.append(kwargs)


@pytest.fixture
def queue(api):
    from alfred.core.routes.captions import get_captions_queue
    from alfred.main import app

    recording = RecordingQueue()
    app.dependency_overrides[get_captions_queue] = lambda: recording
    yield recording
    app.dependency_overrides.pop(get_captions_queue, None)


@pytest.fixture
def engine(monkeypatch, tmp_path):
    """An audio engine configured and usable, and a library holding talk.wav."""
    from alfred import config
    from alfred.core.utils import audio_engine

    monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', 'http://engine.test:8010')
    monkeypatch.setattr(audio_engine, 'problem', lambda: None)
    monkeypatch.setattr(config, 'VIDEO_DIR', str(tmp_path))
    (tmp_path / 'talk.wav').write_bytes(b'RIFF not really')


@pytest.fixture
def alice(make_account):
    return make_account('alice')


def captions_of(api, account, project_id):
    res = api.get(f'/project/{project_id}/captions', headers=account.headers)
    assert res.status_code == 200, res.text
    return res.json()


class TestTheRoundTrip:
    def test_saved_in_order_and_read_back(self, api, alice, make_project):
        project = make_project(alice)
        res = api.put(
            f'/project/{project["_id"]}/captions',
            json={
                'captions': [
                    {'start': 2, 'end': 3, 'text': 'Later'},
                    {'start': 0.5, 'end': 1.5, 'text': 'Sooner'},
                ],
                'style': {'position': ['left', 'top'], 'color': '#FC0'},
            },
            headers=alice.headers,
        )
        assert res.status_code == 200, res.text
        body = captions_of(api, alice, project['_id'])
        assert [c['text'] for c in body['captions']] == ['Sooner', 'Later']
        assert body['style']['position'] == ['left', 'top']
        assert body['style']['color'] == '#ffcc00'
        assert body['style']['enabled'] is False
        assert body['job'] is None

    def test_the_project_carries_them(self, api, alice, make_project):
        project = make_project(alice)
        api.put(
            f'/project/{project["_id"]}/captions',
            json={'captions': [{'start': 0, 'end': 1, 'text': 'Hi'}]},
            headers=alice.headers,
        )
        whole = api.get(f'/project/{project["_id"]}', headers=alice.headers).json()
        assert whole['captions'] == [{'start': 0.0, 'end': 1.0, 'text': 'Hi'}]

    def test_an_import_is_reviewed_not_stored(self, api, alice, make_project):
        project = make_project(alice)
        res = api.post(
            f'/project/{project["_id"]}/captions/import',
            json={'format': 'srt', 'text': SRT},
            headers=alice.headers,
        )
        assert res.status_code == 200, res.text
        assert [c['text'] for c in res.json()['captions']] == ['Sooner', 'Later']
        assert captions_of(api, alice, project['_id'])['captions'] == []


class TestTheRestOfTheProject:
    def test_saving_the_whole_project_keeps_the_captions(
        self, api, alice, make_project, projects
    ):
        """A body from a client that read the project before captions existed
        leaves them out; that must not wipe them, or the job."""
        project = make_project(alice)
        api.put(
            f'/project/{project["_id"]}/captions',
            json={'captions': [{'start': 0, 'end': 1, 'text': 'Kept'}]},
            headers=alice.headers,
        )
        projects.update_one(
            {'_id': ObjectId(project['_id'])},
            {'$set': {'captions_job': {'state': 'done', 'segments': 1}}},
        )
        res = api.put(
            f'/project/{project["_id"]}',
            json={'name': 'renamed', 'logic': {}, 'captions': [], 'captions_job': None},
            headers=alice.headers,
        )
        assert res.status_code == 200, res.text
        body = captions_of(api, alice, project['_id'])
        assert [c['text'] for c in body['captions']] == ['Kept']
        assert body['job']['state'] == 'done'

    def test_saving_the_timeline_keeps_the_captions(self, api, alice, make_project):
        project = make_project(alice)
        api.put(
            f'/project/{project["_id"]}/captions',
            json={'captions': [{'start': 0, 'end': 1, 'text': 'Kept'}]},
            headers=alice.headers,
        )
        api.put(f'/project/{project["_id"]}/timeline', json=TALK, headers=alice.headers)
        assert captions_of(api, alice, project['_id'])['captions'][0]['text'] == 'Kept'

    def test_a_new_project_s_captions_are_put_in_order(self, api, alice, make_project):
        project = make_project(
            alice,
            captions=[
                {'start': 5, 'end': 6, 'text': 'b'},
                {'start': 1, 'end': 2, 'text': 'a'},
            ],
            captions_job={'state': 'transcribing'},
        )
        assert [c['text'] for c in project['captions']] == ['a', 'b']
        assert project['captions_job'] is None
        assert project['caption_style']['enabled'] is False

    def test_a_new_project_with_more_than_it_carries_is_refused_by_code(
        self, api, alice
    ):
        """As the captions route refuses them: the sentence, and its code."""
        many = [{'start': n, 'end': n + 0.5, 'text': 'x'} for n in range(1001)]
        res = api.post(
            '/project',
            json={'name': 'too many', 'logic': {}, 'captions': many},
            headers=alice.headers,
        )
        assert (res.status_code, res.json()) == (
            422,
            {
                'detail': '1001 captions is more than the 1000 a project may carry',
                'code': 'too_many_captions',
            },
        )

    def test_the_project_says_whether_its_captions_are_drawn(
        self, api, alice, make_project
    ):
        """GET /project/{id} carries the captions and the style, `enabled`
        stated -- what an API client reads to render the project."""
        project = make_project(alice)
        api.put(
            f'/project/{project["_id"]}/captions',
            json={'captions': [{'start': 0, 'end': 1, 'text': 'Hi'}]},
            headers=alice.headers,
        )
        whole = api.get(f'/project/{project["_id"]}', headers=alice.headers).json()
        assert whole['caption_style']['enabled'] is False
        api.put(
            f'/project/{project["_id"]}/captions',
            json={'captions': whole['captions'], 'style': {'enabled': True}},
            headers=alice.headers,
        )
        whole = api.get(f'/project/{project["_id"]}', headers=alice.headers).json()
        assert whole['caption_style']['enabled'] is True


class TestTranscribing:
    def test_no_engine_is_503(self, api, alice, make_project, queue, monkeypatch):
        from alfred import config

        monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', None)
        project = make_project(alice, edl=TALK)
        res = api.post(
            f'/project/{project["_id"]}/captions/transcribe', headers=alice.headers
        )
        assert res.status_code == 503
        assert res.json()['code'] == 'audio_engine_missing'
        assert queue.sent == []

    def test_the_whole_lifecycle(
        self, api, alice, make_project, queue, engine, monkeypatch
    ):
        from alfred.core.models.captions import Caption
        from alfred.core.utils import tasks

        project = make_project(alice, edl=TALK)
        res = api.post(
            f'/project/{project["_id"]}/captions/transcribe', headers=alice.headers
        )
        assert res.status_code == 202, res.text
        assert queue.sent == [{'projectId': project['_id']}]
        assert captions_of(api, alice, project['_id'])['job']['state'] == 'queued'

        again = api.post(
            f'/project/{project["_id"]}/captions/transcribe', headers=alice.headers
        )
        assert again.status_code == 409

        seen = []

        def transcribe_timeline(edl):
            # Mid-job, the client sees it under way.
            seen.append(captions_of(api, alice, project['_id'])['job']['state'])
            return [Caption(start=0.5, end=1.5, text='Heard')], 1

        monkeypatch.setattr(tasks, 'transcribe_timeline', transcribe_timeline)
        tasks.transcribeCaptions(**queue.sent[0])

        assert seen == ['transcribing']
        body = captions_of(api, alice, project['_id'])
        assert body['job']['state'] == 'done'
        assert body['job']['segments'] == 1
        assert body['job']['engine'] == 'http://engine.test:8010'
        assert body['captions'] == [{'start': 0.5, 'end': 1.5, 'text': 'Heard'}]

        # Done, so it may be asked for again.
        assert (
            api.post(
                f'/project/{project["_id"]}/captions/transcribe', headers=alice.headers
            ).status_code
            == 202
        )

    def test_a_failure_is_there_to_be_read(
        self, api, alice, make_project, queue, engine, monkeypatch
    ):
        from alfred.core.utils import audio_engine, tasks

        project = make_project(alice, edl=TALK)
        api.post(
            f'/project/{project["_id"]}/captions/transcribe', headers=alice.headers
        )

        def unreachable(edl):
            raise audio_engine.AudioEngineFailed(
                'the audio engine at http://engine.test:8010: connection refused'
            )

        monkeypatch.setattr(tasks, 'transcribe_timeline', unreachable)
        tasks.transcribeCaptions(**queue.sent[0])
        job = captions_of(api, alice, project['_id'])['job']
        assert job['state'] == 'failed'
        assert (
            job['error']
            == 'the audio engine at http://engine.test:8010: connection refused'
        )

    def test_somebody_else_s_is_404(
        self, api, alice, make_account, make_project, queue, engine
    ):
        project = make_project(alice, edl=TALK)
        bob = make_account('bob')
        res = api.post(
            f'/project/{project["_id"]}/captions/transcribe', headers=bob.headers
        )
        assert res.status_code == 404
        assert queue.sent == []

    def test_one_stored_before_ownership_is_a_superuser_s(
        self, api, make_account, legacy_project, projects, queue, engine
    ):
        projects.update_one(
            {'_id': ObjectId(legacy_project['_id'])}, {'$set': {'edl': TALK}}
        )
        user, admin = make_account('user'), make_account('admin', superuser=True)
        path = f'/project/{legacy_project["_id"]}/captions/transcribe'
        assert api.post(path, headers=user.headers).status_code == 404
        assert api.post(path, headers=admin.headers).status_code == 202


class TestRenders:
    def test_a_render_keeps_its_captions_and_a_rerender_draws_them(
        self, api, alice, make_project
    ):
        from alfred.core.routes.render import get_render_queue
        from alfred.main import app

        sent = []
        app.dependency_overrides[get_render_queue] = lambda: lambda **kw: sent.append(
            kw
        )
        try:
            body = {
                'edl': {
                    'clips': [
                        {
                            'type': 'template',
                            'name': 'makeColor',
                            'duration': 2,
                            'data': {'color': '#000000'},
                        }
                    ]
                },
                'name': 'captioned',
                'width': 320,
                'height': 180,
                'captions': [{'start': 0, 'end': 1, 'text': 'On screen'}],
                'caption_style': {'position': ['center', 'top']},
            }
            res = api.post('/render', json=body, headers=alice.headers)
            assert res.status_code == 200, res.text
            render_id = res.json().replace('"', '')
            again = api.post(f'/render/rerender/{render_id}', headers=alice.headers)
            assert again.status_code == 200, again.text
        finally:
            app.dependency_overrides.pop(get_render_queue, None)

        for payload in sent:
            [caption] = [c for c in payload['edl']['clips'] if c['name'] == 'textBox']
            assert caption['data']['text'] == 'On screen'
            assert caption['data']['position'] == ['center', 'top']
        assert len(sent) == 2

        renders = api.get('/render', headers=alice.headers).json()
        [stored] = [r for r in renders if r['_id'] == render_id]
        assert stored['captions'] == [{'start': 0.0, 'end': 1.0, 'text': 'On screen'}]
        assert [c['name'] for c in stored['edl']['clips']] == ['makeColor']


def test_health_says_there_is_no_audio_engine(api, make_account, monkeypatch):
    from alfred import config
    from alfred.core.routes.health import cached_audio_engine, get_audio_engine_state
    from alfred.main import app

    monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', None)
    fresh = cached_audio_engine()
    app.dependency_overrides[get_audio_engine_state] = lambda: fresh
    try:
        body = api.get('/health', headers=make_account('watcher').headers).json()
    finally:
        app.dependency_overrides.pop(get_audio_engine_state, None)
    assert body['audio_engine']['configured'] is False
    assert body['audio_engine']['ok'] is False
    assert 'ALFRED_AUDIO_ENGINE_URL' in body['audio_engine']['detail']
