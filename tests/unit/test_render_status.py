"""C2 -- what a render is doing, and why it failed.

Anything waiting on a render fetched every render the caller could see and
searched for its own, then interpreted the stored status itself; and a failed
render said only that it had failed, because the reason was printed to the
worker's log. `GET /render/{id}/status` answers for one render, with a derived
`state` and a stored `error`.
"""

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from alfred import config
from alfred.core.models.render import Render, RenderStatus, render_state
from alfred.core.utils import logger
from alfred.core.utils.media import MediaNameError
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


@pytest.mark.parametrize(
    'status,progress,state',
    [
        (None, None, 'queued'),
        (None, 0, 'queued'),
        (None, 0.5, 'rendering'),
        (None, 99, 'rendering'),
        ('RENDERED', 100, 'rendered'),
        ('RENDERED', None, 'rendered'),
        ('UPLOADED', 100, 'rendered'),
        ('failed', None, 'failed'),
        ('failed', 42, 'failed'),
    ],
)
def test_the_state_is_derived_as_the_contract_says(status, progress, state):
    assert render_state(status, progress) == state


@pytest.fixture
def api(monkeypatch):
    offline_documents(monkeypatch, Render)
    store = FakeRenderStore()
    overrides = as_user(app, OWNER) + use_fakes(app, store, FakeQueue())
    yield TestClient(app), store
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


def stored(store, **fields):
    render = make_render(**fields)
    store.renders[render.id] = render
    return render


class TestTheRoute:
    def test_it_answers_exactly_the_contract_s_fields(self, api):
        client, store = api
        render = stored(store, filename='x.mp4', status='RENDERED', progress=100)

        res = client.get(f'/render/{render.id}/status')
        assert res.status_code == 200
        assert res.json() == {
            'id': str(render.id),
            'state': 'rendered',
            'status': 'RENDERED',
            'progress': 100.0,
            'filename': 'x.mp4',
            'destination': None,
            'error': None,
        }

    def test_a_failure_carries_its_reason(self, api):
        client, store = api
        render = stored(store, status='failed', error='no such file')
        body = client.get(f'/render/{render.id}/status').json()
        assert body['state'] == 'failed' and body['error'] == 'no such file'

    @pytest.mark.parametrize('stored_progress,shown', [(150, 100.0), (-3, 0.0)])
    def test_progress_is_kept_within_0_to_100(self, api, stored_progress, shown):
        render = make_render(progress=stored_progress)
        assert RenderStatus.of(render).progress == shown

    def test_a_malformed_id_is_a_422(self, api):
        client, store = api
        assert client.get('/render/undefined/status').status_code == 422

    def test_a_missing_render_is_a_404(self, api):
        client, store = api
        assert client.get(f'/render/{ObjectId()}/status').status_code == 404

    def test_someone_else_s_render_is_a_404(self, api):
        """404, not 403: a stranger cannot learn the id exists."""
        client, store = api
        render = stored(store)
        as_user(app, STRANGER)
        assert client.get(f'/render/{render.id}/status').status_code == 404

    def test_a_superuser_sees_any_render(self, api):
        client, store = api
        render = stored(store)
        as_user(app, ADMIN)
        assert client.get(f'/render/{render.id}/status').status_code == 200

    def test_a_render_without_an_owner_is_a_superuser_s_alone(self, api):
        """Stored before renders recorded who made them."""
        client, store = api
        render = stored(store, username=None)
        assert client.get(f'/render/{render.id}/status').status_code == 404
        as_user(app, ADMIN)
        assert client.get(f'/render/{render.id}/status').status_code == 200


class TestTheReason:
    def test_it_is_one_line(self):
        exc = OSError('MoviePy error: failed to read\nHere are the file infos:\n...')
        assert logger.failure_reason(exc) == 'OSError: MoviePy error: failed to read'

    def test_it_is_short(self):
        reason = logger.failure_reason(RuntimeError('x' * 5000))
        assert len(reason) <= logger.REASON_LIMIT
        assert reason.endswith('...')

    def test_library_paths_read_as_the_clip_named_them(self, monkeypatch):
        """The worker opens /app/videos/x.mp4; the clip said videos/x.mp4."""
        monkeypatch.setattr(config, 'VIDEO_DIR', '/app/videos')
        exc = OSError('MoviePy error: the file /app/videos/x.mp4 could not be found!')
        assert logger.failure_reason(exc) == (
            'OSError: MoviePy error: the file videos/x.mp4 could not be found!'
        )

    def test_our_own_refusals_are_not_prefixed(self):
        """Their messages are already written for the caller."""
        exc = MediaNameError("clip 1: '/etc/hostname': absolute paths are not allowed")
        assert logger.failure_reason(exc).startswith('clip 1:')

    def test_an_exception_with_no_message_still_says_something(self):
        assert logger.failure_reason(KeyError()) == 'KeyError'


class RecordingCollection:
    def __init__(self):
        self.updates = []

    def update_one(self, query, update):
        self.updates.append((query, update))


class TestTheWorkerRecordsIt:
    @pytest.fixture
    def collection(self, monkeypatch):
        collection = RecordingCollection()

        class FakeDb:
            Render = collection

        monkeypatch.setattr(logger, 'db', FakeDb)
        return collection

    def test_a_failure_stores_status_and_reason(self, collection):
        render_id = ObjectId()
        logger.DbLogger(None, str(render_id)).failed(exc=ValueError('bad clip'))
        assert collection.updates == [
            (
                {'_id': render_id},
                {'$set': {'status': 'failed', 'error': 'ValueError: bad clip'}},
            )
        ]

    def test_finishing_clears_a_previous_reason(self, collection):
        """A re-queued render that succeeds is no longer explained by its
        last failure."""
        logger.DbLogger(None, str(ObjectId())).rendered()
        ((_, update),) = collection.updates
        assert update['$set']['error'] is None

    def test_a_job_failing_outside_the_task_body_marks_its_own_render(self, collection):
        """`on_failure` used `self.log`, which was the previous job's logger."""
        from alfred.core.utils.tasks import renderRemote

        render_id = ObjectId()
        renderRemote.on_failure(
            RuntimeError('worker lost'), 'task', (), {'renderId': str(render_id)}, None
        )
        assert collection.updates == [
            (
                {'_id': render_id},
                {'$set': {'status': 'failed', 'error': 'RuntimeError: worker lost'}},
            )
        ]

    def test_a_job_with_no_render_id_is_not_an_error(self, collection):
        from alfred.core.utils.tasks import renderRemote

        renderRemote.on_failure(RuntimeError('x'), 'task', (), {}, None)
        assert collection.updates == []

    def test_a_refused_clip_is_recorded_with_the_refusal(self, collection):
        """End to end through the task: the reason reaches the document."""
        from alfred.core.utils.tasks import renderRemote

        render_id = ObjectId()
        renderRemote.apply(
            kwargs=dict(
                edl={'clips': [{'type': 'video', 'name': '/etc/hostname'}]},
                filename=f'{render_id}.mp4',
                renderId=str(render_id),
            )
        )
        ((query, update),) = collection.updates
        assert query == {'_id': render_id}
        assert update['$set']['status'] == 'failed'
        assert 'absolute paths are not allowed' in update['$set']['error']
