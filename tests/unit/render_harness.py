"""Drive the real app's render routes without a database.

Not a test module (no `test_` prefix): helpers the render-route tests share.
They are plain functions and classes rather than fixtures, so a test module
imports what it uses and wraps it in fixtures of its own; importing fixtures
across modules is something ruff rightly reports as a redefinition.

Two things stand between a route and a unit test, and each has a seam:

- **Authentication.** Every render route depends on `current_active_user`;
  `as_user` swaps it for a fixed user through FastAPI's dependency overrides.
- **Storage.** `Render` is a beanie Document, and constructing one --
  which FastAPI does to parse a request body -- calls `get_motor_collection()`,
  which raises until `init_beanie` has run against a live MongoDB.
  `offline_documents` makes construction work without one, which is enough
  for every route that refuses a request before it stores anything.
"""

from dataclasses import dataclass, field

from beanie import PydanticObjectId


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
    """Serve every request as `user`. Returns the override, for clearing."""
    from alfred.core.routes.users import current_active_user

    app.dependency_overrides[current_active_user] = lambda: user
    return current_active_user
