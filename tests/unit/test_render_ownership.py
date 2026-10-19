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
    (root / 'renders').mkdir()
    monkeypatch.setattr(config, 'RENDER_DIR', str(root / 'renders'))
    return root


@pytest.fixture
def renders(library):
    """Where the worker writes finished renders (RENDER_DIR)."""
    return library / 'renders'


@pytest.fixture
def api(monkeypatch, library, tmp_path):
    monkeypatch.setattr(config, 'DELIVERY_DIR', str(tmp_path / 'delivered'))
    offline_documents(monkeypatch, Render)
    store, queue = FakeRenderStore(), FakeQueue()
    overrides = as_user(app, OWNER) + use_fakes(app, store, queue)
    yield TestClient(app), store, queue
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


def stored(store, renders, **fields):
    render = make_render(**fields)
    render.filename = render.filename or f'{render.id}.mp4'
    store.renders[render.id] = render
    if render.status in ('RENDERED', 'UPLOADED'):
        (renders / render.filename).write_bytes(b'a finished render')
    return render


class TestTheList:
    def test_a_user_sees_only_their_own(self, api, renders):
        client, store, _ = api
        mine = stored(store, renders)
        stored(store, renders, username=STRANGER.email)
        ids = [r['_id'] for r in client.get('/render').json()]
        assert ids == [str(mine.id)]

    def test_a_superuser_sees_everyone_s(self, api, renders):
        client, store, _ = api
        renders = [
            stored(store, renders),
            stored(store, renders, username=STRANGER.email),
            stored(store, renders, username=None),
        ]
        as_user(app, ADMIN)
        ids = {r['_id'] for r in client.get('/render').json()}
        assert ids == {str(r.id) for r in renders}

    def test_a_render_with_no_owner_is_listed_to_nobody_else(self, api, renders):
        client, store, _ = api
        stored(store, renders, username=None)
        assert client.get('/render').json() == []

    def test_newest_first(self, api, renders):
        client, store, _ = api
        older = stored(store, renders, id=ObjectId('6a0000000000000000000001'))
        newer = stored(store, renders, id=ObjectId('6a0000000000000000000002'))
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

    def test_someone_else_s_render_is_a_404(self, api, renders, method, path):
        client, store, queue = api
        render = stored(store, renders, status='RENDERED')
        as_user(app, STRANGER)
        assert self.call(client, method, path, render).status_code == 404
        assert render.id in store.renders, 'a stranger changed the render'
        assert (renders / render.filename).exists(), 'a stranger removed its file'
        assert queue.sent == []

    def test_a_render_with_no_owner_is_a_404_to_a_user(
        self, api, renders, method, path
    ):
        client, store, _ = api
        render = stored(store, renders, status='RENDERED', username=None)
        assert self.call(client, method, path, render).status_code == 404

    def test_a_malformed_id_is_a_422(self, api, method, path):
        client, _, _ = api
        url = path.format(id='undefined')
        kwargs = {'json': {'name': 'x'}} if method == 'put' else {}
        assert getattr(client, method)(url, **kwargs).status_code == 422


class TestWhatAnOwnerCanDo:
    def test_deliver_their_render(self, api, renders):
        client, store, _ = api
        render = stored(store, renders, status='RENDERED')
        res = client.post(f'/render/{render.id}/deliver')
        assert res.status_code == 200, res.text
        assert store.renders[render.id].destination == 'local'

    def test_a_local_delivery_links_to_the_download_route(self, api, renders, tmp_path):
        """The copy used to land under DATA_DIR, served publicly at /data, and
        its server path was the recorded link."""
        client, store, _ = api
        render = stored(store, renders, status='RENDERED')
        receipt = client.post(f'/render/{render.id}/deliver').json()

        link = f'/render/{render.id}/download'
        assert receipt == {'destination': 'local', 'location': link}
        assert store.renders[render.id].link == link
        assert (tmp_path / 'delivered' / render.filename).is_file()
        assert client.get(link).status_code == 200

    def test_deliver_only_a_finished_one(self, api, renders):
        """Mid-render the output exists and is not yet a video."""
        client, store, _ = api
        render = stored(store, renders, status=None, progress=40)
        (renders / render.filename).write_bytes(b'partial')
        assert client.post(f'/render/{render.id}/deliver').status_code == 409

    def test_rerender_their_render(self, api, renders):
        """Superuser-only before; an owner retrying is just queueing again."""
        client, store, queue = api
        render = stored(store, renders, status='failed', error='it broke')
        res = client.post(f'/render/rerender/{render.id}')
        assert res.status_code == 200
        assert len(queue.sent) == 1
        assert store.renders[render.id].error is None

    def test_relabel_their_render(self, api, renders):
        client, store, _ = api
        render = stored(store, renders, project='Old', description=None)
        res = client.put(
            f'/render/{render.id}', json={'project': 'New', 'description': 'cut 2'}
        )
        assert res.status_code == 200
        assert store.renders[render.id].project == 'New'
        assert store.renders[render.id].display_name == 'New-cut-2-64x48'

    def test_a_partial_relabel_leaves_the_rest(self, api, renders):
        client, store, _ = api
        render = stored(store, renders, project='Kept', description='also kept')
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
    def test_not_rewrite_what_the_server_records(self, api, renders, field, value):
        """`filename` decides what a download serves: pointed at another
        render's file, it would have served somebody else's video."""
        client, store, _ = api
        render = stored(store, renders)
        before = getattr(render, field)
        res = client.put(f'/render/{render.id}', json={field: value})
        assert res.status_code == 422
        assert getattr(store.renders[render.id], field) == before

    def test_delete_their_render(self, api, renders):
        client, store, _ = api
        render = stored(store, renders)
        assert client.delete(f'/render/{render.id}').status_code == 200
        assert render.id not in store.renders

    def test_deleting_a_render_removes_its_video_and_its_delivered_copy(
        self, api, renders, tmp_path
    ):
        """The record went and the bytes stayed, for good."""
        client, store, _ = api
        render = stored(store, renders, status='RENDERED')
        assert client.post(f'/render/{render.id}/deliver').status_code == 200
        delivered = tmp_path / 'delivered' / render.filename
        assert delivered.is_file()

        assert client.delete(f'/render/{render.id}').status_code == 200
        assert not (renders / render.filename).exists()
        assert not delivered.exists()

    def test_a_render_from_before_outputs_were_named_by_id_keeps_its_file(
        self, api, library
    ):
        """Its file is in the media library, where it may be in use as media."""
        client, store, _ = api
        render = make_render(status='RENDERED', filename='old_composite_name.mp4')
        store.renders[render.id] = render
        (library / render.filename).write_bytes(b'an old render')
        assert client.delete(f'/render/{render.id}').status_code == 200
        assert (library / render.filename).exists()


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

    def test_asking_for_it_deletes_nothing(self, api, renders):
        client, store, _ = api
        render = stored(store, renders)
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
    def test_may_act_on_any_render(self, api, renders, method, path):
        client, store, _ = api
        render = stored(store, renders, status='RENDERED', username=STRANGER.email)
        as_user(app, ADMIN)
        res = getattr(client, method)(path.format(id=render.id))
        assert res.status_code == 200, res.text


def traceback_length(exc):
    length, tb = 0, exc.__traceback__
    while tb is not None:
        length, tb = length + 1, tb.tb_next
    return length


class TestRefusalsLeaveNothingBehind:
    """Re-raising one shared exception instance appends every raise's traceback
    to it, keeping each request's frames alive for the life of the process.
    The render routes raise a fresh copy each time."""

    def test_repeated_404s_and_422s_do_not_grow_the_shared_instances(self, api):
        from alfred.core.routes.render import NO_OUTPUT
        from alfred.core.utils.bucket import INVALID_ID, NOT_FOUND

        client, _, _ = api
        before = [traceback_length(e) for e in (INVALID_ID, NOT_FOUND, NO_OUTPUT)]
        for _ in range(3):
            assert client.get('/render/undefined/status').status_code == 422
            missing = ObjectId()
            assert client.get(f'/render/{missing}/status').status_code == 404
        after = [traceback_length(e) for e in (INVALID_ID, NOT_FOUND, NO_OUTPUT)]
        assert after == before

    def test_a_refusal_is_still_the_same_answer(self, api):
        """Each copy says what the shared one says: its sentence and its code."""
        client, _, _ = api
        for _ in range(2):
            assert client.get('/render/undefined/status').json() == {
                'detail': 'Not a valid identifier',
                'code': 'invalid_id',
            }
