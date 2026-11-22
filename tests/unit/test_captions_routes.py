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

    async def sources(self, project_id, names, scope):
        """As `CaptionsStore.sources`: the draft's sources up the chain, then
        the other projects in scope that play one of `names` and hold words."""

        def reachable(project):
            return project is not None and all(
                project.get(k) == v for k, v in scope.items()
            )

        seen = {project_id}
        chain = []
        current = self.projects.get(project_id)
        while reachable(current):
            parent = (current.get('source') or {}).get('project')
            if (
                not parent
                or not ObjectId.is_valid(str(parent))
                or ObjectId(str(parent)) in seen
            ):
                break
            seen.add(ObjectId(str(parent)))
            current = self.projects.get(ObjectId(str(parent)))
            if reachable(current):
                chain.append(copy.deepcopy(current))
        others = [
            copy.deepcopy(p)
            for pid, p in sorted(
                self.projects.items(), key=lambda kv: kv[0], reverse=True
            )
            if pid not in seen
            and reachable(p)
            and p.get('words')
            and any(
                c.get('name') in names for c in (p.get('edl') or {}).get('clips') or []
            )
        ]
        others.sort(key=lambda p: bool(p.get('source')))
        return chain + others

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
    monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', 'http://engine.test:1059')
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
        assert body['job']['updated_at'].endswith('Z')

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

    def test_however_many_are_stored(self, api):
        mine = project()
        client, store, _ = api(OWNER, mine)
        many = [{'start': i, 'end': i + 1, 'text': 'x'} for i in range(5000)]
        res = client.put(url(mine), json={'captions': many})
        assert res.status_code == 200, res.text
        assert len(res.json()['captions']) == 5000
        assert len(store.writes[-1]['captions']) == 5000

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

    def test_however_many_are_kept(self, api):
        mine = project()
        client, store, _ = api(OWNER, mine)
        many = [{'start': 0, 'end': 0, 'text': 'x'}] * 60_000
        res = client.put(url(mine), json={'captions': [], 'words': many})
        assert res.status_code == 200, res.text
        assert len(store.writes[-1]['words']) == 60_000


# What the editor sends after an edit: the clips placed, the first now shorter.
TIMELINE = {
    'clips': [
        {
            'type': 'video',
            'name': 'videos/talk.mp4',
            'duration': 3,
            'start': 0,
            'inpoint': 0,
            'outpoint': 3,
            'fadeIn': 0,
            'fadeOut': 0,
        },
        {
            'type': 'template',
            'name': 'makeColor',
            'duration': 2,
            'start': 3,
            'fadeIn': 0,
            'fadeOut': 0,
            'data': {'color': '#000000'},
        },
    ],
    'duration': 5,
}


def heard_by(clips, words, captions=(), **fields):
    """A project of OWNER's whose timeline plays `clips` and says `words`."""
    return project(
        edl={'clips': clips},
        words=[{'start': a, 'end': b, 'text': t} for a, b, t in words],
        captions=[{'start': a, 'end': b, 'text': t} for a, b, t in captions],
        **fields,
    )


TALK = 'videos/talk.mp4'


def talk(inpoint, duration):
    return {'type': 'video', 'name': TALK, 'inpoint': inpoint, 'duration': duration}


class TestWhatWasSaid:
    """`POST /project/{id}/captions/said`: what a draft's sources say over
    the stretches of a file its timeline now plays and holds no words for."""

    def chain(self):
        recording = heard_by(
            [talk(0, 30)],
            [(t + 0.1, t + 0.6, f'w{t}') for t in range(30)],
            [(20, 24, 'w20 w21 w22 w23')],
        )
        teaser = heard_by(
            [talk(10, 5), talk(20, 5)],
            [(0.1, 0.6, 'w10'), (5.1, 5.6, 'twenty, corrected')],
            source={'project': str(recording['_id']), 'recipe': 'teaser'},
        )
        quote = heard_by(
            [talk(20, 1)],
            [],
            source={'project': str(teaser['_id']), 'recipe': 'quotes'},
        )
        return recording, teaser, quote

    def test_each_stretch_from_the_nearest_source_that_plays_it(self, api):
        recording, teaser, quote = self.chain()
        client, store, _ = api(OWNER, recording, teaser, quote)
        res = client.post(
            url(quote, '/said'),
            json={'windows': [{'name': TALK, 'start': 20, 'end': 27}]},
        )
        assert res.status_code == 200, res.text
        [stretch] = res.json()['said']
        assert (stretch['name'], stretch['start'], stretch['end']) == (TALK, 20, 27)
        texts = [w['text'] for w in stretch['words']]
        # 20 to 25 s from the teaser, which corrected a word and holds no other
        # there; 25 to 27 s from the recording, which the teaser does not play.
        assert texts == ['twenty, corrected', 'w25', 'w26']
        assert stretch['words'][0]['start'] == 20.1
        # The recording's caption at 20 s is in a stretch the teaser plays.
        assert stretch['captions'] == []
        assert not store.writes

    def test_a_caption_running_past_the_stretch_is_cut_to_it(self, api):
        recording, _, _ = self.chain()
        draft = heard_by([talk(0, 1)], [], source={'project': str(recording['_id'])})
        client, _, _ = api(OWNER, recording, draft)
        res = client.post(
            url(draft, '/said'),
            json={'windows': [{'name': TALK, 'start': 22, 'end': 26}]},
        )
        assert res.json()['said'][0]['captions'] == [
            {'start': 22.0, 'end': 24.0, 'text': 'w22 w23'}
        ]

    def test_another_project_playing_the_file_is_read_when_no_source_is(self, api):
        recording, _, _ = self.chain()
        fresh = heard_by([talk(0, 2)], [])
        client, _, _ = api(OWNER, recording, fresh)
        res = client.post(
            url(fresh, '/said'),
            json={'windows': [{'name': TALK, 'start': 5, 'end': 7}]},
        )
        assert [w['text'] for w in res.json()['said'][0]['words']] == ['w5', 'w6']

    def test_nobody_else_s_projects_are_read(self, api):
        recording, _, _ = self.chain()
        theirs = {**recording, '_id': ObjectId(), 'owner': STRANGER.email}
        fresh = heard_by([talk(0, 2)], [])
        client, _, _ = api(OWNER, theirs, fresh)
        res = client.post(
            url(fresh, '/said'),
            json={'windows': [{'name': TALK, 'start': 5, 'end': 7}]},
        )
        assert res.json()['said'][0]['words'] == []

    def test_a_project_not_yours_is_not_found(self, api):
        recording, _, quote = self.chain()
        client, _, _ = api(STRANGER, recording, quote)
        res = client.post(
            url(quote, '/said'),
            json={'windows': [{'name': TALK, 'start': 0, 'end': 1}]},
        )
        assert res.status_code == 404

    @pytest.mark.parametrize(
        'body',
        [
            {'windows': [{'name': TALK, 'start': -1, 'end': 1}]},
            {'windows': [{'name': '', 'start': 0, 'end': 1}]},
            {'windows': [{'name': TALK, 'start': 0, 'end': 1, 'extra': 1}]},
            {'windows': [{'name': TALK, 'start': 0, 'end': 1}] * 51},
            {},
        ],
    )
    def test_a_body_out_of_shape_is_refused(self, api, body):
        _, _, quote = self.chain()
        client, _, _ = api(OWNER, quote)
        assert client.post(url(quote, '/said'), json=body).status_code == 422


class TestTheTimeline:
    """An edit moves the timeline, its captions and its words together, and
    they are saved together: one request, one write."""

    def test_saved_with_the_captions_and_the_words_in_one_write(self, api):
        mine = project(words=WORDS)
        client, store, _ = api(OWNER, mine)
        res = client.put(
            url(mine),
            json={
                'captions': [{'start': 0.5, 'end': 0.9, 'text': 'Hello'}],
                'words': WORDS[:1],
                'timeline': TIMELINE,
            },
        )
        assert res.status_code == 200, res.text
        assert [set(write) for write in store.writes] == [
            {'captions', 'caption_style', 'words', 'edl'}
        ]
        # Stored as sent, as the timeline route stores it: no defaults written in.
        assert store.projects[mine['_id']]['edl'] == TIMELINE
        assert 'edl' not in res.json()

    def test_left_out_it_is_kept(self, api):
        mine = project()
        client, store, _ = api(OWNER, mine)
        client.put(url(mine), json={'captions': [], 'words': WORDS})
        assert store.projects[mine['_id']]['edl'] == project()['edl']

    @pytest.mark.parametrize(
        'timeline',
        [{'clips': 'none'}, {'clips': [{'duration': 'long'}]}, {'duration': 4}],
    )
    def test_one_otto_cannot_read_is_422_and_nothing_is_written(self, api, timeline):
        mine = project(words=WORDS)
        client, store, _ = api(OWNER, mine)
        res = client.put(
            url(mine), json={'captions': [], 'words': [], 'timeline': timeline}
        )
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
        assert job['engine'] == 'http://engine.test:1059'
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
        monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', 'http://engine.test:1059')

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
