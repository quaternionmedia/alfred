"""K2 -- a render with captions draws them, and a rerender draws them again.

`POST /render` takes optional `captions` and `caption_style`. The render keeps
them beside its timeline, and the worker's payload carries one textBox clip
per caption after the timeline's own -- made for the render's own frame, and
made again when it is re-queued.
"""

import json

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from alfred.core.models.render import Render
from alfred.core.utils.captions import MAX_CAPTIONS
from alfred.main import app
from tests.unit.render_harness import (
    OWNER,
    FakeQueue,
    FakeRenderStore,
    as_user,
    make_render,
    offline_documents,
    render_request,
    use_fakes,
)

CAPTIONS = [
    {'start': 0.2, 'end': 0.6, 'text': 'First'},
    {'start': 0.0, 'end': 0.4, 'text': 'Earlier'},
]


@pytest.fixture
def api(monkeypatch):
    offline_documents(monkeypatch, Render)
    store, queue = FakeRenderStore(), FakeQueue()
    overrides = as_user(app, OWNER) + use_fakes(app, store, queue)
    yield TestClient(app), store, queue
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


def queue_one(api, **body):
    client, store, queue = api
    res = client.post('/render', json=render_request(**body))
    assert res.status_code == 200, res.text
    return store.renders[ObjectId(res.json())], queue.sent[-1]


def caption_clips_in(payload):
    return [c for c in payload['edl']['clips'] if c.get('name') == 'textBox']


class TestQueueing:
    def test_the_captions_follow_the_timeline_s_own_clips(self, api):
        render, payload = queue_one(api, captions=CAPTIONS)
        names = [c['name'] for c in payload['edl']['clips']]
        assert names == ['makeColor', 'textBox', 'textBox']
        assert [c['data']['text'] for c in caption_clips_in(payload)] == [
            'Earlier',
            'First',
        ]

    def test_made_for_the_render_s_frame(self, api):
        render, payload = queue_one(api, captions=CAPTIONS, width=640, height=360)
        clip = caption_clips_in(payload)[0]
        assert clip['clipsize'][0] == 640
        assert clip['data']['fontsize'] == 18  # 54 at 1080 lines, so 18 at 360

    def test_the_style_is_applied(self, api):
        _, payload = queue_one(
            api,
            captions=CAPTIONS,
            caption_style={'color': '#ffcc00', 'position': 'top'},
        )
        data = caption_clips_in(payload)[0]['data']
        assert (data['color'], data['position']) == ('#ffcc00', 'top')

    def test_a_disabled_style_draws_none(self, api):
        render, payload = queue_one(
            api, captions=CAPTIONS, caption_style={'enabled': False}
        )
        assert caption_clips_in(payload) == []
        assert len(render.captions) == 2  # kept, not drawn

    def test_none_draws_none(self, api):
        _, payload = queue_one(api)
        assert caption_clips_in(payload) == []

    def test_captions_past_the_timeline_are_cut_there(self, api):
        """The harness's timeline is one second long."""
        _, payload = queue_one(
            api,
            captions=[
                {'start': 0.5, 'end': 3, 'text': 'over'},
                {'start': 2, 'end': 3, 'text': 'past'},
            ],
        )
        clips = caption_clips_in(payload)
        assert [(c['start'], c['duration']) for c in clips] == [(0.5, 0.5)]

    def test_the_render_keeps_its_timeline_as_sent(self, api):
        render, _ = queue_one(api, captions=CAPTIONS)
        assert [c.name for c in render.edl.clips] == ['makeColor']
        assert [c.text for c in render.captions] == ['Earlier', 'First']

    def test_the_payload_is_json(self, api):
        _, payload = queue_one(
            api, captions=CAPTIONS, caption_style={'position': ['left', 'top']}
        )
        json.dumps(payload)

    def test_too_many_is_422_and_nothing_is_queued(self, api):
        client, store, queue = api
        many = [
            {'start': i, 'end': i + 0.5, 'text': 'x'} for i in range(MAX_CAPTIONS + 1)
        ]
        res = client.post('/render', json=render_request(captions=many))
        assert res.status_code == 422
        assert store.renders == {} and queue.sent == []

    @pytest.mark.parametrize(
        'caption',
        [{'start': 1, 'end': 0.5, 'text': 'x'}, {'start': 0, 'end': 1, 'text': ''}],
    )
    def test_a_caption_that_cannot_be_shown_is_422(self, api, caption):
        client, store, queue = api
        res = client.post('/render', json=render_request(captions=[caption]))
        assert res.status_code == 422
        assert queue.sent == []


class TestRerendering:
    def test_a_rerender_draws_them_again(self, api, monkeypatch):
        client, store, queue = api
        render = make_render(captions=CAPTIONS, caption_style={'color': '#00ff00'})
        store.renders[render.id] = render
        res = client.post(f'/render/rerender/{render.id}')
        assert res.status_code == 200, res.text
        clips = caption_clips_in(queue.sent[-1])
        assert [c['data']['text'] for c in clips] == ['Earlier', 'First']
        assert clips[0]['data']['color'] == '#00ff00'
