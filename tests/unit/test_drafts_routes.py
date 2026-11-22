"""The drafts routes, without a database.

`POST`, `GET` and `DELETE /project/{id}/drafts` against an in-memory stand-in
for the project collection and a queue that records what it would send.
"""

import copy
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from alfred.core.routes import drafts as routes
from alfred.core.routes import recipes as recipe_routes
from alfred.main import app
from tests.unit.render_harness import OWNER, STRANGER, FakeQueue, as_user
from tests.unit.test_recipes_routes import FakeRecipeStore


class FakeDraftsStore:
    """The project collection, in memory, answering as `DraftsStore` does."""

    def __init__(self, *projects):
        self.projects = {p['_id']: copy.deepcopy(p) for p in projects}
        self.writes = []

    def _owned(self, document, query):
        return 'owner' not in query or document.get('owner') == query['owner']

    async def find(self, query):
        project = self.projects.get(query['_id'])
        if project is None or not self._owned(project, query):
            return None
        return copy.deepcopy(project)

    async def has_words(self, project_id):
        return bool(self.projects[project_id].get('words'))

    async def claim(self, project_id, job, stale_before):
        current = self.projects[project_id].get('drafts_job') or {}
        running = current.get('state') in ('queued', 'running')
        heard = current.get('updated_at')
        if running and not (heard is not None and heard < stale_before):
            return False
        self.projects[project_id]['drafts_job'] = copy.deepcopy(job)
        return True

    async def set(self, project_id, fields):
        self.writes.append(copy.deepcopy(fields))
        self.projects[project_id].update(copy.deepcopy(fields))

    async def drafts_of(self, query):
        found = []
        for document in self.projects.values():
            source = document.get('source') or {}
            if source.get('project') != query.get('source.project'):
                continue
            if '_id' in query and document['_id'] not in query['_id']['$in']:
                continue
            if not self._owned(document, query):
                continue
            found.append(copy.deepcopy(document))
        return sorted(found, key=lambda d: d['_id'])

    async def delete(self, query):
        ids = query['_id']['$in']
        before = len(self.projects)
        for i in ids:
            self.projects.pop(i, None)
        return before - len(self.projects)

    async def remember(self, project_id, dropped):
        kept = self.projects[project_id].setdefault('drafts_dropped', [])
        kept.extend(copy.deepcopy(dropped))


def source(**fields):
    document = {
        '_id': ObjectId(),
        'owner': OWNER.email,
        'name': 'the show',
        'logic': {},
        'edl': {
            'clips': [{'type': 'video', 'name': 'videos/show.mp4', 'duration': 60}]
        },
        'words': [{'start': 1, 'end': 1.4, 'text': 'Welcome'}],
        'cues': [],
    }
    document.update(fields)
    return document


def draft(of, number, **fields):
    document = {
        '_id': ObjectId(),
        'owner': of['owner'],
        'name': f'{of["name"]} – Highlights {number}',
        'description': 'where it came from',
        'logic': {},
        'edl': {'clips': [], 'duration': 9.5},
        'source': {
            'project': str(of['_id']),
            'recipe': 'highlights',
            'values': {},
            'spans': [[10, 19.5]],
            'scores': {'dialogue': 1.0},
            'made_at': datetime(2026, 11, 21, tzinfo=timezone.utc),
        },
    }
    document.update(fields)
    return document


@pytest.fixture
def api():
    made = []

    def make(user, *projects, queue=None, recipes=()):
        store = FakeDraftsStore(*projects)
        queue = queue or FakeQueue()
        made.extend(as_user(app, user))
        app.dependency_overrides[routes.get_drafts_store] = lambda: store
        app.dependency_overrides[routes.get_drafts_queue] = lambda: queue
        app.dependency_overrides[recipe_routes.get_recipe_store] = (
            lambda: FakeRecipeStore(*recipes)
        )
        made.extend(
            [
                routes.get_drafts_store,
                routes.get_drafts_queue,
                recipe_routes.get_recipe_store,
            ]
        )
        return TestClient(app), store, queue

    yield make
    for dependency in made:
        app.dependency_overrides.pop(dependency, None)


def url(document):
    return f'/project/{document["_id"]}/drafts'


ASK = {'recipes': [{'recipe': 'highlights', 'values': {'count': '3'}}]}


class TestStartingARun:
    def test_queued_with_the_job_recorded(self, api):
        mine = source()
        client, store, queue = api(OWNER, mine)
        res = client.post(url(mine), json=ASK)
        assert res.status_code == 202, res.text
        job = res.json()['job']
        assert job['state'] == 'queued'
        assert job['recipes'] == ['highlights']
        assert store.projects[mine['_id']]['drafts_job']['state'] == 'queued'
        [sent] = queue.sent
        assert sent == {
            'projectId': str(mine['_id']),
            'recipes': [{'recipe': 'highlights', 'values': {'count': '3'}}],
        }

    def test_one_of_my_recipes_by_its_id(self, api):
        mine = source()
        recipe = {
            '_id': ObjectId(),
            'owner': OWNER.email,
            'name': 'mine',
            'label': 'Mine',
            'fields': [],
            'steps': [{'op': 'chapters'}],
        }
        client, _, queue = api(OWNER, mine, recipes=[recipe])
        res = client.post(url(mine), json={'recipes': [{'recipe': str(recipe['_id'])}]})
        assert res.status_code == 202, res.text
        assert queue.sent[0]['recipes'] == [
            {'recipe': str(recipe['_id']), 'values': {}}
        ]

    def test_a_source_with_no_words_is_422_and_nothing_is_queued(self, api):
        mine = source(words=[])
        client, store, queue = api(OWNER, mine)
        res = client.post(url(mine), json=ASK)
        assert res.status_code == 422
        assert res.json()['code'] == 'no_words'
        assert queue.sent == []
        assert 'drafts_job' not in store.projects[mine['_id']]

    def test_an_unknown_recipe_is_404_before_anything_is_queued(self, api):
        mine = source()
        client, _, queue = api(OWNER, mine)
        res = client.post(url(mine), json={'recipes': [{'recipe': 'nowhere'}]})
        assert res.status_code == 404
        assert res.json()['code'] == 'unknown_recipe'
        assert queue.sent == []

    def test_a_run_under_way_is_409(self, api):
        mine = source(
            drafts_job={'state': 'running', 'updated_at': datetime.now(timezone.utc)}
        )
        client, _, queue = api(OWNER, mine)
        res = client.post(url(mine), json=ASK)
        assert res.status_code == 409
        assert res.json()['code'] == 'drafts_running'
        assert queue.sent == []

    def test_a_run_unheard_from_for_long_may_be_started_over(self, api):
        stale = datetime.now(timezone.utc) - routes.STALE_AFTER - timedelta(minutes=1)
        mine = source(drafts_job={'state': 'running', 'updated_at': stale})
        client, _, _ = api(OWNER, mine)
        assert client.post(url(mine), json=ASK).status_code == 202

    def test_a_broker_that_refuses_is_503_and_the_job_says_failed(self, api):
        class Refusing:
            def __call__(self, **kwargs):
                raise ConnectionError('the broker is not answering')

        mine = source()
        client, store, _ = api(OWNER, mine, queue=Refusing())
        res = client.post(url(mine), json=ASK)
        assert res.status_code == 503
        assert res.json()['code'] == 'drafts_not_queued'
        job = store.projects[mine['_id']]['drafts_job']
        assert job['state'] == 'failed'
        assert 'could not be queued' in job['error']

    def test_too_many_recipes_or_none_is_422_by_shape(self, api):
        mine = source()
        client, _, _ = api(OWNER, mine)
        assert client.post(url(mine), json={'recipes': []}).status_code == 422
        many = {'recipes': [{'recipe': 'highlights'}] * (routes.MAX_RECIPES + 1)}
        assert client.post(url(mine), json=many).status_code == 422

    def test_a_project_that_is_not_yours_is_404(self, api):
        theirs = source()
        client, _, queue = api(STRANGER, theirs)
        assert client.post(url(theirs), json=ASK).status_code == 404
        assert queue.sent == []


class TestListing:
    def test_the_job_and_the_drafts_of_this_source(self, api):
        mine = source(
            drafts_job={'state': 'done', 'made': 2, 'recipes': ['highlights']}
        )
        other = source(name='another')
        first, second = draft(mine, 1), draft(mine, 2)
        elsewhere = draft(other, 1)
        client, _, _ = api(OWNER, mine, other, first, second, elsewhere)
        res = client.get(url(mine))
        assert res.status_code == 200, res.text
        body = res.json()
        assert body['job']['state'] == 'done'
        assert [d['id'] for d in body['drafts']] == [
            str(first['_id']),
            str(second['_id']),
        ]
        assert body['drafts'][0]['duration'] == 9.5
        assert body['drafts'][0]['source']['spans'] == [[10, 19.5]]
        assert body['drafts'][0]['source']['scores'] == {'dialogue': 1.0}

    def test_no_run_yet_is_a_null_job_and_no_drafts(self, api):
        mine = source()
        client, _, _ = api(OWNER, mine)
        assert client.get(url(mine)).json() == {'job': None, 'drafts': []}

    def test_another_account_s_drafts_of_my_source_are_not_listed(self, api):
        mine = source()
        theirs = draft(mine, 1, owner=STRANGER.email)
        client, _, _ = api(OWNER, mine, theirs)
        assert client.get(url(mine)).json()['drafts'] == []


class TestDropping:
    def test_the_drafts_named_go_with_their_cues(self, api):
        first, second = None, None
        mine = source()
        first, second = draft(mine, 1), draft(mine, 2)
        mine['cues'] = [
            {
                'start': 10,
                'end': 19.5,
                'label': 'Highlights 1',
                'source': 'alfred-drafts',
                'ref': str(first['_id']),
            },
            {
                'start': 30,
                'end': 39,
                'label': 'Highlights 2',
                'source': 'alfred-drafts',
                'ref': str(second['_id']),
            },
            {'start': 0, 'end': 5, 'label': 'Chapter 1', 'source': 'alfred-excerpts'},
        ]
        client, store, _ = api(OWNER, mine, first, second)
        res = client.request('DELETE', url(mine), json={'drafts': [str(first['_id'])]})
        assert res.status_code == 200, res.text
        assert res.json() == {'dropped': [str(first['_id'])]}
        assert first['_id'] not in store.projects
        assert second['_id'] in store.projects
        assert [c['label'] for c in store.projects[mine['_id']]['cues']] == [
            'Highlights 2',
            'Chapter 1',
        ]
        # The source remembers what it dropped, with what the draft carried.
        [kept] = store.projects[mine['_id']]['drafts_dropped']
        assert kept['id'] == str(first['_id'])
        assert kept['name'] == first['name']
        assert kept['recipe'] == first['source']['recipe']
        assert kept['spans'] == first['source']['spans']
        assert kept['scores'] == first['source']['scores']
        assert kept['duration'] == first['edl']['duration']
        assert kept['dropped_at'] is not None

    def test_nothing_is_remembered_when_nothing_is_dropped(self, api):
        """Mutation: remember before checking every id -- red."""
        mine = source()
        first = draft(mine, 1)
        client, store, _ = api(OWNER, mine, first)
        res = client.request(
            'DELETE', url(mine), json={'drafts': [str(first['_id']), str(ObjectId())]}
        )
        assert res.status_code == 422
        assert 'drafts_dropped' not in store.projects[mine['_id']]

    def test_a_project_that_is_not_a_draft_of_this_source_drops_nothing(self, api):
        mine = source()
        other = source(name='another')
        first = draft(mine, 1)
        client, store, _ = api(OWNER, mine, other, first)
        res = client.request(
            'DELETE', url(mine), json={'drafts': [str(first['_id']), str(other['_id'])]}
        )
        assert res.status_code == 422
        assert res.json()['code'] == 'not_a_draft'
        assert str(other['_id']) in res.json()['detail']
        assert first['_id'] in store.projects

    def test_an_id_that_is_not_one_is_422(self, api):
        mine = source()
        client, _, _ = api(OWNER, mine)
        res = client.request('DELETE', url(mine), json={'drafts': ['nope']})
        assert res.status_code == 422
        assert res.json()['code'] == 'not_a_draft'

    def test_another_account_cannot_drop_my_drafts(self, api):
        mine = source()
        first = draft(mine, 1)
        client, store, _ = api(STRANGER, mine, first)
        res = client.request('DELETE', url(mine), json={'drafts': [str(first['_id'])]})
        assert res.status_code == 404
        assert first['_id'] in store.projects
