"""The recipe routes, without a database.

`GET /recipes`, `POST /recipes`, `GET`/`PUT`/`DELETE /recipes/{id}`,
`GET /recipes/operations` and `POST /recipes/check` against an in-memory
stand-in for the recipe collection: the built-in recipes every account
reads, the caller's own, and each refusal by code.
"""

import copy

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from alfred.core.models.recipes import OPERATIONS
from alfred.core.routes import recipes as routes
from alfred.core.utils.recipes_builtin import BUILTIN
from alfred.main import app
from tests.unit.render_harness import ADMIN, OWNER, STRANGER, as_user


class FakeRecipeStore:
    def __init__(self, *documents):
        self.documents = {d['_id']: copy.deepcopy(d) for d in documents}

    def _matches(self, document, query):
        return all(
            document.get(key) == value for key, value in query.items() if key != '_id'
        )

    async def list(self, query):
        return sorted(
            (
                copy.deepcopy(d)
                for d in self.documents.values()
                if self._matches(d, query)
            ),
            key=lambda d: d['name'],
        )

    async def find(self, query):
        document = self.documents.get(query['_id'])
        if document is None or not self._matches(document, query):
            return None
        return copy.deepcopy(document)

    async def insert(self, document):
        made = ObjectId()
        self.documents[made] = {**copy.deepcopy(document), '_id': made}
        return made

    async def replace(self, recipe_id, fields):
        self.documents[recipe_id].update(copy.deepcopy(fields))

    async def delete(self, recipe_id):
        return 1 if self.documents.pop(recipe_id, None) is not None else 0


def stored(**changes):
    document = {
        '_id': ObjectId(),
        'owner': OWNER.email,
        'name': 'mine',
        'label': 'Mine',
        'description': '',
        'fields': [],
        'steps': [{'op': 'chapters'}, {'op': 'compose', 'how': 'each'}],
    }
    document.update(changes)
    return document


MINE = {
    'name': 'mine',
    'label': 'Mine',
    'steps': [{'op': 'windows'}, {'op': 'top', 'count': 3}],
}


@pytest.fixture
def api():
    made = []

    def make(user, *documents):
        store = FakeRecipeStore(*documents)
        made.extend(as_user(app, user))
        app.dependency_overrides[routes.get_recipe_store] = lambda: store
        made.append(routes.get_recipe_store)
        return TestClient(app), store

    yield make
    for dependency in made:
        app.dependency_overrides.pop(dependency, None)


class TestListing:
    def test_the_built_in_recipes_then_mine(self, api):
        client, _ = api(OWNER, stored(), stored(name='theirs', owner=STRANGER.email))
        res = client.get('/recipes')
        assert res.status_code == 200, res.text
        names = [r['name'] for r in res.json()]
        assert names == [r['name'] for r in BUILTIN] + ['mine']
        highlights = res.json()[0]
        assert highlights['builtin'] is True
        assert highlights['id'] == 'highlights'
        assert highlights['fields'][0]['attrs']['name'] == 'shortest'
        assert res.json()[-1]['builtin'] is False

    def test_a_superuser_lists_every_account_s(self, api):
        client, _ = api(ADMIN, stored(), stored(name='theirs', owner=STRANGER.email))
        names = [r['name'] for r in client.get('/recipes').json() if not r['builtin']]
        assert names == ['mine', 'theirs']


class TestOne:
    def test_a_built_in_by_its_name(self, api):
        client, _ = api(OWNER)
        res = client.get('/recipes/highlights')
        assert res.status_code == 200
        assert res.json()['steps'][0]['op'] == 'windows'

    def test_mine_by_its_id(self, api):
        mine = stored()
        client, _ = api(OWNER, mine)
        assert client.get(f'/recipes/{mine["_id"]}').json()['name'] == 'mine'

    def test_another_account_s_is_404(self, api):
        theirs = stored(owner=STRANGER.email)
        client, _ = api(OWNER, theirs)
        res = client.get(f'/recipes/{theirs["_id"]}')
        assert res.status_code == 404
        assert res.json()['code'] == 'unknown_recipe'

    def test_a_name_that_is_nothing_is_404(self, api):
        client, _ = api(OWNER)
        res = client.get('/recipes/nowhere')
        assert res.status_code == 404
        assert res.json()['code'] == 'unknown_recipe'
        assert 'highlights' in res.json()['detail']


class TestOperations:
    def test_every_operation_with_its_parameters(self, api):
        client, _ = api(OWNER)
        res = client.get('/recipes/operations')
        assert res.status_code == 200, res.text
        listed = {op['name']: op for op in res.json()}
        assert list(listed) == list(OPERATIONS)
        top = listed['top']
        assert top['kind'] == 'filter' and top['about']
        assert top['parameters']['count'] == {
            'kind': 'integer',
            'default': 25,
            'low': 1,
            'high': 500,
        }
        assert listed['compose']['parameters']['how'] == {
            'kind': 'choice',
            'default': 'each',
            'choices': ['each', 'together', 'whole'],
        }
        assert listed['spikes']['parameters']['where_words'] == {
            'kind': 'boolean',
            'default': True,
        }
        assert listed['sentences']['parameters'] == {}


class TestChecking:
    def test_a_good_recipe_is_answered_tidied_and_stored_nowhere(self, api):
        client, store = api(OWNER)
        res = client.post('/recipes/check', json={**MINE, 'label': '  Mine  '})
        assert res.status_code == 200, res.text
        assert res.json() == {
            'name': 'mine',
            'label': 'Mine',
            'description': '',
            'fields': [],
            'steps': MINE['steps'],
        }
        assert store.documents == {}

    def test_a_rule_broken_names_the_step(self, api):
        client, store = api(OWNER)
        res = client.post(
            '/recipes/check', json={**MINE, 'steps': [{'op': 'top', 'count': 900}]}
        )
        assert res.status_code == 422
        assert res.json() == {
            'detail': 'step 1 (top): count: 900 is above 500',
            'code': 'recipe_refused',
        }
        assert store.documents == {}

    def test_a_step_naming_no_operation(self, api):
        client, _ = api(OWNER)
        res = client.post('/recipes/check', json={**MINE, 'steps': [{'op': 'dance'}]})
        assert res.status_code == 422
        assert res.json()['code'] == 'unknown_operation'
        assert res.json()['detail'].startswith("step 1: 'dance' is not an operation")


class TestDeleting:
    def test_mine_is_deleted(self, api):
        mine = stored()
        client, store = api(OWNER, mine)
        res = client.delete(f'/recipes/{mine["_id"]}')
        assert res.status_code == 200, res.text
        assert res.json() == {'deleted': str(mine['_id'])}
        assert store.documents == {}
        assert client.get(f'/recipes/{mine["_id"]}').status_code == 404

    def test_another_account_s_is_404_and_kept(self, api):
        theirs = stored(owner=STRANGER.email)
        client, store = api(OWNER, theirs)
        res = client.delete(f'/recipes/{theirs["_id"]}')
        assert res.status_code == 404
        assert res.json()['code'] == 'unknown_recipe'
        assert theirs['_id'] in store.documents

    def test_a_built_in_cannot_be_deleted(self, api):
        client, _ = api(OWNER)
        res = client.delete('/recipes/highlights')
        assert res.status_code == 422
        assert res.json()['code'] == 'invalid_id'
        assert client.get('/recipes/highlights').status_code == 200


class TestWriting:
    def test_a_recipe_of_mine_is_stored_with_me_as_its_owner(self, api):
        client, store = api(OWNER)
        res = client.post('/recipes', json=MINE)
        assert res.status_code == 200, res.text
        made = res.json()
        assert made['builtin'] is False
        assert ObjectId.is_valid(made['id'])
        [document] = store.documents.values()
        assert document['owner'] == OWNER.email
        assert document['steps'] == MINE['steps']

    def test_it_is_then_listed_and_readable(self, api):
        client, _ = api(OWNER)
        made = client.post('/recipes', json=MINE).json()
        assert client.get(f'/recipes/{made["id"]}').json()['label'] == 'Mine'
        assert 'mine' in [r['name'] for r in client.get('/recipes').json()]

    def test_a_step_naming_no_operation_is_422(self, api):
        client, store = api(OWNER)
        res = client.post('/recipes', json={**MINE, 'steps': [{'op': 'shuffle'}]})
        assert res.status_code == 422
        assert res.json()['code'] == 'unknown_operation'
        assert store.documents == {}

    def test_a_rule_broken_is_422(self, api):
        client, _ = api(OWNER)
        res = client.post(
            '/recipes', json={**MINE, 'steps': [{'op': 'top', 'count': 900}]}
        )
        assert res.status_code == 422
        assert res.json()['code'] == 'recipe_refused'
        assert 'step 1 (top): count: 900 is above 500' == res.json()['detail']

    def test_mine_is_replaced_whole(self, api):
        mine = stored()
        client, store = api(OWNER, mine)
        res = client.put(f'/recipes/{mine["_id"]}', json={**MINE, 'label': 'Renamed'})
        assert res.status_code == 200, res.text
        assert res.json()['label'] == 'Renamed'
        assert store.documents[mine['_id']]['steps'] == MINE['steps']
        assert store.documents[mine['_id']]['owner'] == OWNER.email

    def test_another_account_s_cannot_be_replaced(self, api):
        theirs = stored(owner=STRANGER.email)
        client, store = api(OWNER, theirs)
        res = client.put(f'/recipes/{theirs["_id"]}', json=MINE)
        assert res.status_code == 404
        assert res.json()['code'] == 'unknown_recipe'
        assert store.documents[theirs['_id']]['name'] == 'mine'

    def test_a_built_in_cannot_be_replaced(self, api):
        client, _ = api(OWNER)
        res = client.put('/recipes/highlights', json=MINE)
        assert res.status_code == 422
        assert res.json()['code'] == 'invalid_id'

    def test_a_field_the_editor_cannot_draw_is_refused(self, api):
        client, _ = api(OWNER)
        res = client.post(
            '/recipes',
            json={**MINE, 'fields': [{'type': 'Dial', 'attrs': {'name': 'x'}}]},
        )
        assert res.status_code == 422
        assert res.json()['code'] == 'recipe_refused'
