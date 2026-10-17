"""Drive the real app's render routes without a database.

Not a test module (no `test_` prefix): helpers the render-route tests share.
They are plain functions and classes rather than fixtures, so a test module
imports what it uses and wraps it in fixtures of its own; importing fixtures
across modules is something ruff rightly reports as a redefinition.

Three things stand between a route and a unit test, and each has a seam:

- **Authentication.** Every render route depends on `current_active_user`
  (and some on `current_active_superuser`); `as_user` swaps both for a fixed
  user through FastAPI's dependency overrides.
- **Storage.** `Render` is a beanie Document, and constructing one --
  which FastAPI does to parse a request body -- calls `get_motor_collection()`,
  which raises until `init_beanie` has run against a live MongoDB.
  `offline_documents` makes construction work without one, and the routes
  reach the collection only through `RenderStore`, which `FakeRenderStore`
  replaces.
- **The queue.** `FakeQueue` records what would have been sent to the worker.
"""

import json
from dataclasses import dataclass, field
from typing import Optional

from beanie import PydanticObjectId
from fastapi import HTTPException


@dataclass
class FakeUser:
    """Stands in for the fastapi-users User the routes receive."""

    email: str
    is_superuser: bool = False
    is_active: bool = True
    is_verified: bool = True
    id: PydanticObjectId = field(default_factory=PydanticObjectId)


OWNER = FakeUser('owner@example.com')
STRANGER = FakeUser('stranger@example.com')
ADMIN = FakeUser('admin@example.com', is_superuser=True)


def offline_documents(monkeypatch, *documents):
    """Let beanie Documents be constructed with no database behind them."""
    for document in documents:
        monkeypatch.setattr(
            document, 'get_motor_collection', classmethod(lambda cls: None)
        )


def as_user(app, user):
    """Serve every request as `user`. Returns the overridden dependencies.

    The superuser dependency answers 403 for anyone else, as fastapi-users'
    own does.
    """
    from alfred.core.routes.users import current_active_superuser, current_active_user

    def superuser():
        if not user.is_superuser:
            raise HTTPException(status_code=403, detail='Forbidden')
        return user

    app.dependency_overrides[current_active_user] = lambda: user
    app.dependency_overrides[current_active_superuser] = superuser
    return [current_active_user, current_active_superuser]


class FakeQueue:
    """Records tasks instead of sending them, and insists they are JSON.

    Celery's serializer is JSON-only (C7), so a payload `json.dumps` cannot
    encode would fail at `delay()` in production. Failing here, at the same
    point, keeps such a payload from passing a unit test.
    """

    def __init__(self):
        self.sent = []

    def __call__(self, **kwargs):
        json.dumps(kwargs)
        self.sent.append(kwargs)


class FakeRenderStore:
    """An in-memory stand-in for the render collection."""

    def __init__(self, *renders):
        self.renders = {render.id: render for render in renders}

    async def get(self, render_id) -> Optional[object]:
        return self.renders.get(PydanticObjectId(render_id))

    async def insert(self, render):
        self.renders[render.id] = render

    async def update(self, render_id, fields):
        render = self.renders[PydanticObjectId(render_id)]
        for name, value in fields.items():
            setattr(render, name, value)


TEMPLATE_EDL = {
    'clips': [
        {
            'type': 'template',
            'name': 'makeColor',
            'duration': 1.0,
            'data': {'color': '#f2aa4c'},
        }
    ],
    'duration': 1.0,
}


def render_request(**overrides):
    """A render request body as the editor sends one."""
    body = {
        'edl': TEMPLATE_EDL,
        'name': 'harness render',
        'project': 'harness',
        'width': 64,
        'height': 48,
        'duration': 1.0,
    }
    body.update(overrides)
    return body


def make_render(**fields):
    """A stored render document. Needs `offline_documents` in effect."""
    from alfred.core.models.render import Render

    render_id = fields.pop('id', None) or PydanticObjectId()
    document = {**render_request(), 'username': OWNER.email}
    document.update(fields)
    render = Render.parse_obj(document)
    render.id = render_id
    return render


def use_fakes(app, store, queue):
    """Route storage and the queue to the fakes. Returns the overrides."""
    from alfred.core.routes.render import get_render_queue, get_render_store

    app.dependency_overrides[get_render_store] = lambda: store
    app.dependency_overrides[get_render_queue] = lambda: queue
    return [get_render_store, get_render_queue]
