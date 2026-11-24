"""C7 -- what crosses the broker is JSON.

Celery was configured for pickle in both directions, and unpickling a message
runs whatever it names. The broker and result backend are MongoDB collections,
so write access to the database was code execution in the worker. The payloads
were pickle-shaped too -- a beanie document's `Edl`, a bson `ObjectId`, a
tuple -- so switching the serializer alone would have broken every render at
`delay()`.

The route tests record the payload with `FakeQueue`, which refuses anything
`json.dumps` cannot encode, at the same point Celery would.
"""

import json

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from otto.models import Edl

from alfred import config
from alfred.core.models.render import Render
from alfred.main import app
from tests.unit.render_harness import (
    ADMIN,
    OWNER,
    FakeQueue,
    FakeRenderStore,
    as_user,
    make_render,
    offline_documents,
    render_request,
    use_fakes,
)


class TestTheSerializer:
    def test_only_json_is_produced(self):
        assert config.CeleryConfig.task_serializer == 'json'
        assert config.CeleryConfig.result_serializer == 'json'

    def test_only_json_is_accepted(self):
        """Accepting pickle is the hole, whatever is produced."""
        assert config.CeleryConfig.accept_content == ['json']
        assert config.CeleryConfig.result_accept_content == ['json']

    def test_the_app_the_worker_runs_is_configured_with_it(self):
        from alfred.core.utils.tasks import renderer

        assert renderer.conf.task_serializer == 'json'
        assert list(renderer.conf.accept_content) == ['json']

    def test_the_task_is_registered_once_under_its_real_name(self):
        """The stale `core.utils.tasks` include registered it twice."""
        from alfred.core.utils.tasks import renderer

        assert tuple(renderer.conf.include) == ('alfred.core.utils.tasks',)


@pytest.fixture
def api(monkeypatch):
    offline_documents(monkeypatch, Render)
    store, queue = FakeRenderStore(), FakeQueue()
    overrides = as_user(app, OWNER) + use_fakes(app, store, queue)
    yield TestClient(app), store, queue
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


class TestQueueing:
    def test_a_render_is_queued_as_plain_data(self, api):
        client, store, queue = api
        res = client.post('/render', json=render_request())
        assert res.status_code == 200, res.text

        (payload,) = queue.sent
        assert json.loads(json.dumps(payload)) == payload
        assert isinstance(payload['edl'], dict)
        assert payload['renderId'] == res.json()

    def test_the_id_sent_is_the_id_stored(self, api):
        client, store, queue = api
        render_id = client.post('/render', json=render_request()).json()
        assert ObjectId(render_id) in store.renders

    def test_the_worker_rebuilds_the_same_edl(self, api):
        """The round trip the worker makes: JSON, then `Edl.parse_obj`."""
        client, store, queue = api
        client.post('/render', json=render_request())

        (payload,) = queue.sent
        sent = Edl.model_validate(json.loads(json.dumps(payload['edl'])))
        assert sent == Edl.model_validate(render_request()['edl'])


class TestRequeueing:
    def test_a_stored_render_is_requeued_as_plain_data(self, api):
        client, store, queue = api
        render = make_render()
        store.renders[render.id] = render
        as_user(app, ADMIN)

        res = client.post(f'/render/rerender/{render.id}')
        assert res.status_code == 200, res.text
        (payload,) = queue.sent
        assert json.loads(json.dumps(payload)) == payload
        assert payload['renderId'] == str(render.id)

    def test_a_malformed_id_is_a_422_not_a_500(self, api):
        client, store, queue = api
        as_user(app, ADMIN)
        assert client.post('/render/rerender/undefined').status_code == 422

    def test_a_missing_render_is_a_404_not_a_500(self, api):
        client, store, queue = api
        as_user(app, ADMIN)
        res = client.post('/render/rerender/deadbeefdeadbeefdeadbeef')
        assert res.status_code == 404


class TestTheWorkerSide:
    def test_a_string_id_becomes_the_stored_key(self):
        """A string matches no document keyed by ObjectId."""
        from alfred.core.utils.logger import DbLogger

        render_id = '6ad3c61e21ba2c869ca8b7ef'
        assert DbLogger(None, render_id).id == ObjectId(render_id)

    def test_an_object_id_is_left_alone(self):
        from alfred.core.utils.logger import DbLogger

        render_id = ObjectId()
        assert DbLogger(None, render_id).id is render_id
