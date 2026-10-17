"""C6 for renders -- a render is its owner's, and a superuser's.

Every render route answered for every render to anyone signed in: the list
showed all users' renders, any render could be delivered, rewritten or
deleted by id, and `DELETE /render` emptied the collection. The owner is
`render.username`, the creating user's email. A render stored without one is
a superuser's alone. Another user's render answers 404, never 403, so its id
cannot be confirmed.
"""

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from alfred import config
from alfred.core.models.render import Render
from alfred.main import app
from tests.unit.render_harness import (
    ADMIN,
    OWNER,
    STRANGER,
    FakeQueue,
    FakeRenderStore,
    as_user,
    make_render,
    offline_documents,
    use_fakes,
)


@pytest.fixture
def library(tmp_path, monkeypatch):
    root = tmp_path / 'videos'
    root.mkdir()
    monkeypatch.setattr(config, 'VIDEO_DIR', str(root))
    return root


@pytest.fixture
def api(monkeypatch, library, tmp_path):
    from alfred.core.utils import destinations

    monkeypatch.setattr(destinations, 'DATA_DIR', str(tmp_path / 'delivered'))
    offline_documents(monkeypatch, Render)
    store, queue = FakeRenderStore(), FakeQueue()
    overrides = as_user(app, OWNER) + use_fakes(app, store, queue)
    yield TestClient(app), store, queue
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


def stored(store, library, **fields):
    render = make_render(**fields)
    render.filename = render.filename or f'{render.id}.mp4'
    store.renders[render.id] = render
    if render.status in ('RENDERED', 'UPLOADED'):
        (library / render.filename).write_bytes(b'a finished render')
    return render


class TestTheList:
    def test_a_user_sees_only_their_own(self, api, library):
        client, store, _ = api
        mine = stored(store, library)
        stored(store, library, username=STRANGER.email)
        ids = [r['_id'] for r in client.get('/render').json()]
        assert ids == [str(mine.id)]

    def test_a_superuser_sees_everyone_s(self, api, library):
        client, store, _ = api
        renders = [
            stored(store, library),
            stored(store, library, username=STRANGER.email),
            stored(store, library, username=None),
        ]
        as_user(app, ADMIN)
        ids = {r['_id'] for r in client.get('/render').json()}
        assert ids == {str(r.id) for r in renders}

    def test_a_render_with_no_owner_is_listed_to_nobody_else(self, api, library):
        client, store, _ = api
        stored(store, library, username=None)
        assert client.get('/render').json() == []

    def test_newest_first(self, api, library):
        client, store, _ = api
        older = stored(store, library, id=ObjectId('6a0000000000000000000001'))
        newer = stored(store, library, id=ObjectId('6a0000000000000000000002'))
        ids = [r['_id'] for r in client.get('/render').json()]
        assert ids == [str(newer.id), str(older.id)]


ROUTES = [
    ('get', '/render/{id}'),
    ('get', '/render/{id}/status'),
    ('get', '/render/{id}/download'),
    ('post', '/render/{id}/deliver'),
    ('post', '/render/rerender/{id}'),
    ('put', '/render/{id}'),
    ('delete', '/render/{id}'),
]


@pytest.mark.parametrize('method,path', ROUTES)
class TestEveryRouteChecksTheOwner:
    def call(self, client, method, path, render):
        kwargs = {'json': {'name': 'renamed'}} if method == 'put' else {}
        return getattr(client, method)(path.format(id=render.id), **kwargs)

    def test_someone_else_s_render_is_a_404(self, api, library, method, path):
        client, store, queue = api
        render = stored(store, library, status='RENDERED')
        as_user(app, STRANGER)
        assert self.call(client, method, path, render).status_code == 404
        assert render.id in store.renders, 'a stranger changed the render'
        assert queue.sent == []

    def test_a_render_with_no_owner_is_a_404_to_a_user(
        self, api, library, method, path
    ):
        client, store, _ = api
        render = stored(store, library, status='RENDERED', username=None)
        assert self.call(client, method, path, render).status_code == 404

    def test_a_malformed_id_is_a_422(self, api, method, path):
        client, _, _ = api
        url = path.format(id='undefined')
        kwargs = {'json': {'name': 'x'}} if method == 'put' else {}
        assert getattr(client, method)(url, **kwargs).status_code == 422


class TestWhatAnOwnerCanDo:
    def test_deliver_their_render(self, api, library):
        client, store, _ = api
        render = stored(store, library, status='RENDERED')
        res = client.post(f'/render/{render.id}/deliver')
        assert res.status_code == 200, res.text
        assert store.renders[render.id].destination == 'local'

    def test_deliver_only_a_finished_one(self, api, library):
        """Mid-render the output exists and is not yet a video."""
        client, store, _ = api
        render = stored(store, library, status=None, progress=40)
        (library / render.filename).write_bytes(b'partial')
        assert client.post(f'/render/{render.id}/deliver').status_code == 409

    def test_rerender_their_render(self, api, library):
        """Superuser-only before; an owner retrying is just queueing again."""
        client, store, queue = api
        render = stored(store, library, status='failed', error='it broke')
        res = client.post(f'/render/rerender/{render.id}')
        assert res.status_code == 200
        assert len(queue.sent) == 1
        assert store.renders[render.id].error is None

    def test_relabel_their_render(self, api, library):
        client, store, _ = api
        render = stored(store, library, project='Old', description=None)
        res = client.put(
            f'/render/{render.id}', json={'project': 'New', 'description': 'cut 2'}
        )
        assert res.status_code == 200
        assert store.renders[render.id].project == 'New'
        assert store.renders[render.id].display_name == 'New-cut-2-64x48'

    def test_a_partial_relabel_leaves_the_rest(self, api, library):
        client, store, _ = api
        render = stored(store, library, project='Kept', description='also kept')
        client.put(f'/render/{render.id}', json={'name': 'only this'})
        assert store.renders[render.id].project == 'Kept'
        assert store.renders[render.id].description == 'also kept'

    @pytest.mark.parametrize(
        'field,value',
        [
            ('filename', 'someone-elses.mp4'),
            ('username', 'stranger@example.com'),
            ('status', 'RENDERED'),
            ('link', 'https://evil.example/'),
            ('edl', {'clips': []}),
        ],
    )
    def test_not_rewrite_what_the_server_records(self, api, library, field, value):
        """`filename` decides what a download serves: pointed at another
        render's file, it would have served somebody else's video."""
        client, store, _ = api
        render = stored(store, library)
        before = getattr(render, field)
        res = client.put(f'/render/{render.id}', json={field: value})
        assert res.status_code == 422
        assert getattr(store.renders[render.id], field) == before

    def test_delete_their_render(self, api, library):
        client, store, _ = api
        render = stored(store, library)
        assert client.delete(f'/render/{render.id}').status_code == 200
        assert render.id not in store.renders


class TestNoBulkDelete:
    def test_there_is_no_delete_on_the_collection(self):
        methods = {
            method
            for route in app.routes
            if getattr(route, 'path', None) == '/render'
            for method in getattr(route, 'methods', ())
        }
        assert 'DELETE' not in methods
        assert {'GET', 'POST'} <= methods

    def test_asking_for_it_deletes_nothing(self, api, library):
        client, store, _ = api
        render = stored(store, library)
        assert client.delete('/render').status_code == 405
        assert render.id in store.renders


class TestASuperuser:
    @pytest.mark.parametrize(
        'method,path',
        [
            ('get', '/render/{id}/status'),
            ('get', '/render/{id}/download'),
            ('post', '/render/{id}/deliver'),
            ('post', '/render/rerender/{id}'),
            ('delete', '/render/{id}'),
        ],
    )
    def test_may_act_on_any_render(self, api, library, method, path):
        client, store, _ = api
        render = stored(store, library, status='RENDERED', username=STRANGER.email)
        as_user(app, ADMIN)
        res = getattr(client, method)(path.format(id=render.id))
        assert res.status_code == 200, res.text
