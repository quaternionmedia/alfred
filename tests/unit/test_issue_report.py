"""Reporting an issue with a render is for whoever may see that render.

`POST /render/{id}/report` mailed support about whatever id it was given, so
anyone signed in could send mail about another user's render, or about one
that did not exist. It now looks the render up the way every render route
does (C6): 422 for a malformed id, 404 unless the render is the caller's or the
caller is a superuser -- and only then sends anything.

The mail is queued for the worker rather than sent from the request
(`utils.support_mail`), so "sends" here is "queues": the route answers 202
with the job, and the worker sends it.
"""

from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from alfred.core.models.render import Render
from alfred.core.utils import support_mail
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
    """What the route would have queued for the worker to mail, instead of
    queueing it; with mail set up."""
    sent = []

    def queue(**job):
        sent.append(job)
        return SimpleNamespace(id='job-1')

    monkeypatch.setattr(support_mail, 'support_mail_configured', lambda: True)
    app.dependency_overrides[support_mail.get_mail_queue] = lambda: queue
    yield sent
    app.dependency_overrides.pop(support_mail.get_mail_queue, None)


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
    res = report(serve(OWNER), render.id)
    assert res.status_code == 202, res.text
    assert res.json() == {'state': 'queued', 'job': 'job-1'}
    assert len(mail) == 1
    assert str(render.id) in mail[0]['subject']
    assert mail[0]['message'] == 'the audio is out of sync'


def test_a_superuser_can_report_an_issue_with_any_render(serve, owned, mail):
    _, render = owned
    assert report(serve(ADMIN), render.id).status_code == 202
    assert len(mail) == 1


def test_the_job_names_the_render_and_carries_no_address(serve, owned, mail):
    """The worker sends to EMAIL_SENDTO itself, and logs the mail by `about`:
    the render, and nothing a mail holds."""
    _, render = owned
    report(serve(OWNER), render.id)
    (job,) = mail
    assert set(job) == {'about', 'subject', 'message', 'attachments'}
    assert job['about'] == f'an issue with render {render.id}'
    assert job['attachments'] == []
    assert '@' not in repr(job)


def test_without_mail_set_up_it_is_a_503_and_nothing_is_queued(
    serve, owned, mail, monkeypatch
):
    _, render = owned
    monkeypatch.setattr(support_mail, 'support_mail_configured', lambda: False)
    res = report(serve(OWNER), render.id)
    assert res.status_code == 503
    assert res.json() == {'detail': support_mail.NOT_CONFIGURED}
    assert mail == []


def test_a_queue_that_will_not_take_it_is_a_503_that_logs_no_report(
    serve, owned, mail, capsys
):
    _, render = owned

    def broken(**job):
        raise ConnectionError(f'broker down while sending {job}')

    app.dependency_overrides[support_mail.get_mail_queue] = lambda: broken
    res = report(serve(OWNER), render.id)
    assert res.status_code == 503
    assert res.json() == {'detail': 'The mail could not be queued; try again later.'}
    logged = capsys.readouterr().out
    assert 'ConnectionError' in logged
    assert 'out of sync' not in logged


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
