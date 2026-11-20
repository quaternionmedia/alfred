"""The cues routes, without a database.

`GET`/`PUT /project/{id}/cues` against an in-memory stand-in for the project
collection. The database tier (`integration/test_cues_api.py`) runs the same
routes against MongoDB, and the whole-project update that keeps them.
"""

import copy

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from alfred.core.models.cues import MAX_CUES, MAX_LABEL_CHARS, Cue, checked_cues
from alfred.core.routes import cues as routes
from alfred.main import app
from tests.unit.render_harness import ADMIN, OWNER, STRANGER, as_user


class FakeCuesStore:
    """The project collection, in memory, answering as `CuesStore` does."""

    def __init__(self, *projects):
        self.projects = {p['_id']: copy.deepcopy(p) for p in projects}
        self.writes = []

    async def find(self, query):
        project = self.projects.get(query['_id'])
        if project is None:
            return None
        if 'owner' in query and project.get('owner') != query['owner']:
            return None
        return copy.deepcopy(
            {k: v for k, v in project.items() if k == '_id' or k in routes.PROJECTION}
        )

    async def set(self, project_id, fields):
        self.writes.append(copy.deepcopy(fields))
        self.projects[project_id].update(copy.deepcopy(fields))


def project(**fields):
    document = {'_id': ObjectId(), 'owner': OWNER.email, 'name': 'cued', 'logic': {}}
    document.update(fields)
    return document


@pytest.fixture
def api():
    """`api(user, *projects)`: a client and its store."""
    made = []

    def make(user, *projects):
        store = FakeCuesStore(*projects)
        made.extend(as_user(app, user))
        app.dependency_overrides[routes.get_cues_store] = lambda: store
        made.append(routes.get_cues_store)
        return TestClient(app), store

    yield make
    for dependency in made:
        app.dependency_overrides.pop(dependency, None)


def url(document):
    return f'/project/{document["_id"]}/cues'


def stored(**fields):
    """A cue as the route stores one: every field present."""
    cue = {
        'start': 0.0,
        'end': None,
        'label': 'x',
        'kind': None,
        'state': None,
        'source': None,
        'ref': None,
        'note': None,
    }
    cue.update(fields)
    return cue


CHAPTER = {'start': 0, 'end': 12.8, 'label': 'Welcome back', 'kind': 'chapter'}
EXCERPT = {
    'start': 0,
    'end': 12.8,
    'label': 'Excerpt 1: greeting',
    'kind': 'excerpt',
    'state': 'waiting',
    'ref': 'alfred-excerpt-1',
    'note': 'Welcome back, everyone.',
}
MARK = {
    'start': 40.5,
    'label': 'Check the mix here',
    'kind': 'mark',
    'source': 'editor',
}


class TestReading:
    def test_a_project_with_none(self, api):
        mine = project()
        client, _ = api(OWNER, mine)
        res = client.get(url(mine))
        assert res.status_code == 200, res.text
        assert res.json() == {'cues': []}

    def test_stored_cues_as_they_are(self, api):
        mine = project(
            cues=[stored(start=1.0, label='one'), stored(start=2.0, label='two')]
        )
        client, _ = api(OWNER, mine)
        assert [c['label'] for c in client.get(url(mine)).json()['cues']] == [
            'one',
            'two',
        ]

    def test_a_stored_cue_that_does_not_validate_is_left_out(self, api):
        mine = project(
            cues=[stored(start=1.0, label='kept'), {'start': 'soon', 'label': ''}]
        )
        client, _ = api(OWNER, mine)
        assert [c['label'] for c in client.get(url(mine)).json()['cues']] == ['kept']

    def test_somebody_else_s_project_is_not_found(self, api):
        mine = project()
        client, _ = api(STRANGER, mine)
        res = client.get(url(mine))
        assert res.status_code == 404
        assert res.json()['code'] == 'not_found'

    def test_a_superuser_reads_anyone_s(self, api):
        mine = project(cues=[stored(label='theirs')])
        client, _ = api(ADMIN, mine)
        assert client.get(url(mine)).json()['cues'][0]['label'] == 'theirs'

    def test_a_malformed_id_is_refused_before_anything_is_looked_up(self, api):
        client, store = api(OWNER)
        res = client.get('/project/not-an-id/cues')
        assert res.status_code == 422
        assert res.json()['code'] == 'invalid_id'


class TestWriting:
    def test_replaces_every_cue_in_order_of_start(self, api):
        mine = project(cues=[stored(start=99.0, label='old')])
        client, store = api(OWNER, mine)
        res = client.put(url(mine), json={'cues': [MARK, CHAPTER, EXCERPT]})
        assert res.status_code == 200, res.text
        labels = [c['label'] for c in res.json()['cues']]
        # The two that start together keep their order: the chapter was sent first.
        assert labels == ['Welcome back', 'Excerpt 1: greeting', 'Check the mix here']
        assert store.writes == [{'cues': res.json()['cues']}]
        assert 'old' not in labels

    def test_the_answer_is_what_is_stored_with_every_field(self, api):
        mine = project()
        client, _ = api(OWNER, mine)
        res = client.put(url(mine), json={'cues': [EXCERPT]})
        assert res.json()['cues'] == [
            stored(
                start=0.0,
                end=12.8,
                label='Excerpt 1: greeting',
                kind='excerpt',
                state='waiting',
                ref='alfred-excerpt-1',
                note='Welcome back, everyone.',
            )
        ]

    def test_a_source_replaces_its_own_cues_and_keeps_the_rest(self, api):
        mine = project(
            cues=[
                stored(start=5.0, label='flow before', source='alfred-excerpts'),
                stored(start=40.5, label='mine', source='editor'),
            ]
        )
        client, _ = api(OWNER, mine)
        res = client.put(
            url(mine),
            json={
                'cues': [{'start': 1, 'end': 2, 'label': 'flow after'}],
                'source': 'alfred-excerpts',
            },
        )
        assert res.status_code == 200, res.text
        assert [(c['label'], c['source']) for c in res.json()['cues']] == [
            ('flow after', 'alfred-excerpts'),
            ('mine', 'editor'),
        ]

    def test_a_source_s_cues_are_stamped_with_it_whatever_they_said(self, api):
        mine = project()
        client, _ = api(OWNER, mine)
        res = client.put(
            url(mine),
            json={
                'cues': [{'start': 1, 'label': 'x', 'source': 'someone else'}],
                'source': 'me',
            },
        )
        assert res.json()['cues'][0]['source'] == 'me'

    def test_an_empty_list_with_a_source_clears_that_source_alone(self, api):
        mine = project(
            cues=[
                stored(start=5.0, label='flow', source='alfred-excerpts'),
                stored(start=40.5, label='mine', source='editor'),
            ]
        )
        client, _ = api(OWNER, mine)
        res = client.put(url(mine), json={'cues': [], 'source': 'alfred-excerpts'})
        assert [c['label'] for c in res.json()['cues']] == ['mine']

    def test_an_empty_list_without_a_source_clears_everything(self, api):
        mine = project(cues=[stored(label='a'), stored(label='b', source='editor')])
        client, _ = api(OWNER, mine)
        assert client.put(url(mine), json={'cues': []}).json() == {'cues': []}

    def test_somebody_else_s_project_is_not_written(self, api):
        mine = project()
        client, store = api(STRANGER, mine)
        res = client.put(url(mine), json={'cues': [MARK]})
        assert res.status_code == 404
        assert store.writes == []

    def test_too_many_cues_is_a_refusal_with_its_code(self, api):
        mine = project(cues=[stored(start=0.5, label='kept', source='editor')])
        client, store = api(OWNER, mine)
        many = [{'start': n, 'label': 'x'} for n in range(MAX_CUES)]
        # One over, counting the one another source already holds.
        res = client.put(url(mine), json={'cues': many, 'source': 'flow'})
        assert res.status_code == 422, res.text
        assert res.json() == {
            'detail': f'{MAX_CUES + 1} cues is more than the {MAX_CUES} a project may carry',
            'code': 'too_many_cues',
        }
        assert store.writes == []

    @pytest.mark.parametrize(
        'cue,why',
        [
            ({'start': 3, 'end': 2, 'label': 'x'}, 'must not end before it starts'),
            ({'start': -1, 'label': 'x'}, 'must not be negative'),
            ({'start': 1, 'label': '   '}, 'needs a label'),
            ({'start': 1, 'label': 'x' * (MAX_LABEL_CHARS + 1)}, 'at most'),
            ({'start': 1, 'label': 'x', 'kind': 'Not a word'}, 'is a word'),
            ({'start': 1, 'label': 'x', 'state': '9lives'}, 'is a word'),
            ({'start': 1}, 'label'),
        ],
    )
    def test_a_cue_that_cannot_be_read_is_fastapi_s_422(self, api, cue, why):
        mine = project()
        client, store = api(OWNER, mine)
        res = client.put(url(mine), json={'cues': [cue]})
        assert res.status_code == 422, res.text
        assert why in res.text
        assert store.writes == []

    def test_a_field_the_update_does_not_take_is_refused(self, api):
        mine = project()
        client, _ = api(OWNER, mine)
        res = client.put(url(mine), json={'cues': [], 'captions': []})
        assert res.status_code == 422


class TestTheModel:
    def test_text_is_one_line_and_a_kind_a_lowercase_word(self):
        cue = Cue(
            start=1.25,
            end=2.5,
            label='  Two\nlines  ',
            kind=' Excerpt ',
            note='a\r\nnote',
        )
        assert (cue.label, cue.kind, cue.note) == ('Two lines', 'excerpt', 'a\nnote')

    def test_times_are_kept_to_the_millisecond(self):
        cue = Cue(start=1.23456, end=2.34567, label='x')
        assert (cue.start, cue.end) == (1.235, 2.346)

    def test_a_point_ends_where_it_starts(self):
        assert Cue(start=4, label='x').stop == 4
        assert Cue(start=4, end=4, label='x').stop == 4

    def test_empty_optional_fields_are_none(self):
        cue = Cue(start=1, label='x', kind='', state=' ', source='', ref='', note='')
        assert (cue.kind, cue.state, cue.source, cue.ref, cue.note) == (None,) * 5

    def test_checked_cues_sorts_by_start_then_end(self):
        cues = [
            Cue(start=2, end=9, label='long'),
            Cue(start=2, end=3, label='short'),
            Cue(start=1, label='point'),
        ]
        assert [c.label for c in checked_cues(cues)] == ['point', 'short', 'long']
