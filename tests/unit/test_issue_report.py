"""Reporting an issue with a render is for whoever may see that render.

`POST /render/{id}/report` mailed support about whatever id it was given, so
anyone signed in could send mail about another user's render, or about one
that did not exist. It now looks the render up the way every render route
does (C6): 422 for a malformed id, 404 unless the render is the caller's or the
caller is a superuser -- and only then sends anything.
"""

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from alfred.core.models.render import Render
from alfred.core.routes import issue
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
def mail(monkeypatch):
    """What the route would have emailed, instead of emailing it."""
    sent = []

    def send(**message):
        sent.append(message)
        return True

    monkeypatch.setattr(issue, 'sendMail', send)
    return sent


@pytest.fixture
def owned(monkeypatch):
    """A render belonging to OWNER, in an in-memory store."""
    offline_documents(monkeypatch, Render)
    render = make_render(username=OWNER.email)
    return FakeRenderStore(render), render


@pytest.fixture
def serve(owned):
    """A client acting as a given user against the store in `owned`."""
    store, _ = owned
    overrides = []

    def client_as(user):
        overrides.extend(as_user(app, user) + use_fakes(app, store, FakeQueue()))
        return TestClient(app)

    yield client_as
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


def report(client, render_id):
    return client.post(f'/render/{render_id}/report', json='the audio is out of sync')


def test_the_owner_can_report_an_issue(serve, owned, mail):
    _, render = owned
    assert report(serve(OWNER), render.id).status_code == 200
    assert len(mail) == 1
    assert str(render.id) in mail[0]['subject']


def test_a_superuser_can_report_an_issue_with_any_render(serve, owned, mail):
    _, render = owned
    assert report(serve(ADMIN), render.id).status_code == 200
    assert len(mail) == 1


def test_someone_elses_render_is_not_found_and_sends_nothing(serve, owned, mail):
    _, render = owned
    assert report(serve(STRANGER), render.id).status_code == 404
    assert mail == []


def test_a_render_that_does_not_exist_is_not_found(serve, mail):
    assert report(serve(OWNER), ObjectId()).status_code == 404
    assert mail == []


def test_a_malformed_id_is_refused_before_any_lookup(serve, mail):
    assert report(serve(OWNER), 'not-an-id').status_code == 422
    assert mail == []
