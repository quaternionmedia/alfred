"""Mail to support goes through the worker's queue.

`POST /render/{id}/report` and `POST /invoice` sent their mail over SMTP from
the request, in a thread, with no timeout. They queue it now
(`utils.support_mail`) and answer 202; the worker sends it (`tasks.mailSupport`)
with ALFRED_SMTP_TIMEOUT on every step, and tries a failure that may pass
again later. Nothing about a mail is logged but a few words naming it and why
it failed: not its text, not its subject, not an address.

The issue route's own rules are in test_issue_report.py; this is the queue,
the worker's side, the invoice, and the stacks that run them.
"""

import smtplib
from base64 import b64encode
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from alfred import config
from alfred.core.utils import email, support_mail, tasks
from alfred.core.utils.tasks import MAIL_RETRIES, MailNotSent, mailSupport
from alfred.main import app
from tests.unit.render_harness import ADMIN, OWNER, as_user
from tests.unit.test_stack_settings import stack

SUPPORT = ['support@example.com', 'help@example.com']
SECRET_TEXT = 'the body nobody should read in a log'
SECRET_SUBJECT = 'a subject nobody should read in a log'


class Outbox:
    """An SMTP server, as far as `send_mail` uses one: what it was sent, and
    the failure to answer with, if any, at the step named."""

    def __init__(self):
        self.made = []
        self.sent = []
        self.closed = 0
        self.failure = None
        self.fail_at = 'send_message'
        self.quit_fails = False

    def smtp(self, host, port, **kwargs):
        self.made.append(kwargs)
        if self.fail_at == 'connect' and self.failure is not None:
            raise self.failure
        return Connection(self)


class Connection:
    def __init__(self, outbox):
        self.outbox = outbox

    def _step(self, name):
        if self.outbox.fail_at == name and self.outbox.failure is not None:
            raise self.outbox.failure

    def starttls(self):
        self._step('starttls')

    def login(self, *args):
        self._step('login')

    def send_message(self, message):
        self._step('send_message')
        self.outbox.sent.append(message)

    def quit(self):
        if self.outbox.quit_fails:
            raise smtplib.SMTPServerDisconnected('Connection unexpectedly closed')

    def close(self):
        self.outbox.closed += 1


@pytest.fixture
def outbox(monkeypatch):
    """Mail set up, with a server that keeps what it is sent."""
    box = Outbox()
    monkeypatch.setattr(email, 'SMTP', box.smtp)
    monkeypatch.setattr(email, 'EMAIL_SERVER', 'mail.example.com')
    monkeypatch.setattr(email, 'EMAIL_USERNAME', 'alfred@example.com')
    monkeypatch.setattr(config, 'EMAIL_SENDTO', SUPPORT)
    return box


class Retried(Exception):
    """What the task's `retry` raises here, holding what it was asked."""

    def __init__(self, exc, countdown):
        super().__init__(exc, countdown)
        self.exc, self.countdown = exc, countdown


@pytest.fixture
def worker(monkeypatch):
    """Run the task as the worker would on its `tries`-th retry, recording a
    retry instead of queueing one."""

    def retry(exc=None, countdown=None, **kwargs):
        raise Retried(exc, countdown)

    monkeypatch.setattr(mailSupport, 'retry', retry)

    def run(tries=0, **job):
        job = {
            'about': 'an issue with render abc',
            'subject': SECRET_SUBJECT,
            'message': SECRET_TEXT,
            **job,
        }
        mailSupport.push_request(retries=tries)
        try:
            return mailSupport.run(**job)
        finally:
            mailSupport.pop_request()

    return run


def addresses_in(text):
    return [address for address in SUPPORT + ['alfred@example.com'] if address in text]


class TestTheSetting:
    def test_the_default_is_twenty_seconds(self, monkeypatch):
        import os

        if os.environ.get('ALFRED_SMTP_TIMEOUT'):
            pytest.skip('ALFRED_SMTP_TIMEOUT is set for this run')
        assert config.SMTP_TIMEOUT == 20


class TestTheWorkerSends:
    def test_to_support_with_the_timeout(self, outbox, worker, monkeypatch):
        monkeypatch.setattr(config, 'SMTP_TIMEOUT', 7)
        assert worker() == 'sent'
        (message,) = outbox.sent
        assert message['To'] == ', '.join(SUPPORT)
        assert message['Subject'] == SECRET_SUBJECT
        assert SECRET_TEXT in message.get_content()
        assert outbox.made == [{'timeout': 7}]

    def test_the_attachments_it_was_queued_with(self, outbox, worker):
        pdf = b'%PDF-1.4 an invoice'
        worker(attachments=[support_mail.attachment('20261001_invoice_0.pdf', pdf)])
        (message,) = outbox.sent
        (part,) = list(message.iter_attachments())
        assert part.get_filename() == '20261001_invoice_0.pdf'
        assert part.get_content_type() == 'application/pdf'
        assert part.get_content() == pdf

    def test_and_logs_only_which_mail_went(self, outbox, worker, capsys):
        worker()
        assert capsys.readouterr().out.strip() == 'mailed an issue with render abc'


TRANSIENT = [
    ConnectionRefusedError(111, 'Connection refused'),
    TimeoutError('timed out'),
    smtplib.SMTPServerDisconnected('Connection unexpectedly closed'),
    smtplib.SMTPResponseException(421, b'4.7.0 Try again later'),
    smtplib.SMTPRecipientsRefused({SUPPORT[0]: (450, b'4.2.1 mailbox busy')}),
]

PERMANENT = [
    smtplib.SMTPAuthenticationError(535, b'5.7.8 Username and Password not accepted'),
    smtplib.SMTPRecipientsRefused(
        {SUPPORT[0]: (550, f'5.1.1 <{SUPPORT[0]}> unknown'.encode())}
    ),
    smtplib.SMTPSenderRefused(553, b'5.7.1 not allowed', 'alfred@example.com'),
    smtplib.SMTPNotSupportedError('STARTTLS extension not supported by server.'),
]


class TestAFailureThatMayPass:
    @pytest.mark.parametrize('failure', TRANSIENT, ids=lambda e: type(e).__name__)
    def test_is_tried_again_later(self, outbox, worker, failure):
        outbox.failure = failure
        with pytest.raises(Retried) as retried:
            worker()
        assert retried.value.countdown == 30
        assert isinstance(retried.value.exc, MailNotSent)

    def test_each_wait_doubles_the_one_before(self, outbox, worker):
        outbox.failure, outbox.fail_at = (
            ConnectionRefusedError(111, 'refused'),
            'connect',
        )
        waits = []
        for tries in range(MAIL_RETRIES):
            with pytest.raises(Retried) as retried:
                worker(tries=tries)
            waits.append(retried.value.countdown)
        assert waits == [30, 60, 120, 240, 480]
        # About a quarter of an hour, all told.
        assert 14 * 60 < sum(waits) < 16 * 60

    def test_is_given_up_on_after_the_last_try(self, outbox, worker):
        outbox.failure = TimeoutError('timed out')
        with pytest.raises(MailNotSent) as failed:
            worker(tries=MAIL_RETRIES)
        assert f'after {MAIL_RETRIES + 1} tries' in str(failed.value)
        assert 'did not answer in time' in str(failed.value)

    def test_that_is_not_chained_to_what_smtplib_raised(self, outbox, worker):
        """smtplib's exception can carry an address; Celery logs the chain."""
        outbox.failure = TRANSIENT[-1]
        with pytest.raises(Retried) as retried:
            worker()
        assert retried.value.__context__ is None
        assert retried.value.exc.__context__ is None


class TestAFailureThatWillNot:
    @pytest.mark.parametrize('failure', PERMANENT, ids=lambda e: type(e).__name__)
    def test_fails_the_job_at_once(self, outbox, worker, failure):
        outbox.failure = failure
        with pytest.raises(MailNotSent) as failed:
            worker()
        assert 'will not try again' in str(failed.value)
        assert failed.value.__context__ is None

    def test_nor_does_mail_that_is_not_set_up(self, outbox, worker, monkeypatch):
        monkeypatch.setattr(email, 'EMAIL_SERVER', None)
        with pytest.raises(MailNotSent) as failed:
            worker()
        assert 'MailNotConfigured' in str(failed.value)
        assert outbox.made == []


class TestNothingOfTheMailIsLogged:
    @pytest.mark.parametrize(
        'failure', TRANSIENT + PERMANENT, ids=lambda e: type(e).__name__
    )
    def test_whatever_the_failure(self, outbox, worker, failure, capsys):
        outbox.failure = failure
        with pytest.raises((Retried, MailNotSent)) as raised:
            worker()
        said = capsys.readouterr().out + str(raised.value) + repr(raised.value.args)
        assert 'an issue with render abc' in said
        assert addresses_in(said) == []
        assert SECRET_TEXT not in said and SECRET_SUBJECT not in said

    def test_by_the_mail_utility_account_mail_uses_either(self, outbox, capsys):
        outbox.failure = PERMANENT[1]
        assert not email.sendMail(SUPPORT[0], SECRET_SUBJECT, SECRET_TEXT)
        said = capsys.readouterr().out
        assert 'SMTPRecipientsRefused' in said and '550' in said
        assert addresses_in(said) == []
        assert SECRET_TEXT not in said and SECRET_SUBJECT not in said


class TestTheConnection:
    def test_is_closed_not_quit_when_a_step_fails(self, outbox):
        outbox.failure = smtplib.SMTPServerDisconnected('gone')
        with pytest.raises(smtplib.SMTPServerDisconnected):
            email.send_mail(SUPPORT, 's', 'm')
        assert outbox.closed == 1

    def test_a_goodbye_that_fails_after_the_mail_went_is_not_a_failure(self, outbox):
        """Raised, it would send the mail again on the retry."""
        outbox.quit_fails = True
        email.send_mail(SUPPORT, 's', 'm')
        assert len(outbox.sent) == 1


# --- the invoice ------------------------------------------------------------


@pytest.fixture
def admin_client():
    overrides = as_user(app, ADMIN)
    yield TestClient(app)
    for dependency in overrides + [support_mail.get_mail_queue]:
        app.dependency_overrides.pop(dependency, None)


@pytest.fixture
def queued(monkeypatch):
    """The jobs the routes queue, with mail set up."""
    jobs = []

    def queue(**job):
        jobs.append(job)
        return SimpleNamespace(id='job-7')

    monkeypatch.setattr(support_mail, 'support_mail_configured', lambda: True)
    app.dependency_overrides[support_mail.get_mail_queue] = lambda: queue
    return jobs


INVOICE = '/invoice?client=c@example.com&startDate=2026-09-01&endDate=2026-10-01'


@pytest.fixture
def invoices(tmp_path, monkeypatch):
    """The invoice generator, writing two pages where the test says."""
    from alfred.core.routes import admin

    made = []

    def generate(client, start, end):
        paths = []
        for page in range(2):
            path = tmp_path / f'20261001_alfred invoice_{page}.pdf'
            path.write_bytes(f'%PDF page {page}'.encode())
            paths.append(str(path))
        made.append(client)
        return paths

    monkeypatch.setattr(admin, 'generate_invoice', generate)
    return made


class TestTheInvoice:
    def test_is_queued_with_its_pages_and_answers_202(
        self, admin_client, queued, invoices
    ):
        res = admin_client.post(INVOICE)
        assert res.status_code == 202, res.text
        assert res.json() == {'state': 'queued', 'job': 'job-7'}
        (job,) = queued
        assert job['about'] == 'an invoice'
        assert job['subject'] == 'alfred invoice'
        assert job['message'] == config.INVOICE_EMAIL_BODY
        assert [a['content'] for a in job['attachments']] == [
            b64encode(b'%PDF page 0').decode(),
            b64encode(b'%PDF page 1').decode(),
        ]
        assert invoices == ['c@example.com']

    def test_the_job_names_no_client(self, admin_client, queued, invoices):
        admin_client.post(INVOICE)
        (job,) = queued
        assert 'c@example.com' not in repr({**job, 'attachments': None})

    def test_without_mail_set_up_nothing_is_made(
        self, admin_client, invoices, monkeypatch
    ):
        monkeypatch.setattr(support_mail, 'support_mail_configured', lambda: False)
        res = admin_client.post(INVOICE)
        assert res.status_code == 503
        assert res.json() == {
            'detail': support_mail.NOT_CONFIGURED,
            'code': 'mail_not_configured',
        }
        assert invoices == []

    def test_is_for_superusers(self, queued, invoices):
        overrides = as_user(app, OWNER)
        try:
            res = TestClient(app).post(INVOICE)
        finally:
            for dependency in overrides + [support_mail.get_mail_queue]:
                app.dependency_overrides.pop(dependency, None)
        assert res.status_code == 403
        assert queued == [] and invoices == []


class TestWhatIsConfigured:
    def test_support_mail_needs_a_server_a_sender_and_recipients(self, monkeypatch):
        for name in ('EMAIL_SERVER', 'EMAIL_USERNAME', 'EMAIL_SENDTO'):
            monkeypatch.setattr(email, 'EMAIL_SERVER', 'mail.example.com')
            monkeypatch.setattr(email, 'EMAIL_USERNAME', 'alfred@example.com')
            monkeypatch.setattr(email, 'EMAIL_SENDTO', SUPPORT)
            assert email.support_mail_configured()
            monkeypatch.setattr(email, name, None)
            assert not email.support_mail_configured(), name


# --- the stacks -------------------------------------------------------------


@pytest.mark.parametrize('name', ['dev', 'thin', 'production'])
def test_the_worker_has_the_mail_settings(name):
    """The worker sends support mail, so it loads `.email` as the api does."""
    assert '.email' in stack(name)['renderer']['env_file']
    assert '.email' in stack(name)['api']['env_file']


def test_the_task_is_registered_with_the_worker():
    assert 'alfred.core.utils.tasks.mailSupport' in tasks.renderer.tasks
