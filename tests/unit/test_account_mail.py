"""Reset and confirmation tokens reach the account's own address.

fastapi-users issues them and hands them to a hook, and the hook printed them
-- nothing delivered them, so outside development a reset could be asked for
and never finished. With mail configured they are mailed now, as a link into
the app's account page. `integration/test_password_reset_api.py` follows one
from the request to the new password.
"""

import asyncio
import re
from types import SimpleNamespace
from urllib.parse import unquote

import pytest

from alfred import config
from alfred.config import resolve_public_url
from alfred.core.routes.users import UserManager
from alfred.core.utils import account_mail
from alfred.core.utils.account_mail import RESET, VERIFY

TOKEN = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl'
SITE = 'https://alfred.example.com'
ALICE = SimpleNamespace(id='6a76a53effdcf46c9c285cf5', email='alice@example.com')


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(config, 'EMAIL_SERVER', 'smtp.example.com')
    monkeypatch.setattr(config, 'EMAIL_USERNAME', 'alfred@example.com')
    monkeypatch.setattr(config, 'PUBLIC_URL', SITE)


@pytest.fixture
def outbox(monkeypatch):
    """What would have been sent, sent inline instead of on the mail thread."""
    sent = []

    def send_mail(to, subject, message, attachments=None, timeout=None):
        sent.append(dict(to=to, subject=subject, body=message, timeout=timeout))
        return True

    monkeypatch.setattr(account_mail, 'sendMail', send_mail)
    monkeypatch.setattr(account_mail, 'dispatch', lambda send: send())
    return sent


def token_in(body):
    return unquote(re.search(r'token=(\S+)', body).group(1))


class TestWhenItIsSent:
    def test_with_a_server_and_an_address_to_link_to(self, configured):
        assert account_mail.configured()

    @pytest.mark.parametrize(
        'missing', ['EMAIL_SERVER', 'EMAIL_USERNAME', 'PUBLIC_URL']
    )
    def test_not_without_any_one_of_them(self, configured, monkeypatch, missing):
        monkeypatch.setattr(config, missing, None)
        assert not account_mail.configured()

    def test_unconfigured_nothing_is_sent(self, configured, monkeypatch, outbox):
        monkeypatch.setattr(config, 'PUBLIC_URL', None)
        assert account_mail.deliver(RESET, ALICE.email, TOKEN, 3600) is False
        assert outbox == []


class TestTheResetMail:
    def test_goes_to_the_account_s_address(self, configured, outbox):
        assert account_mail.deliver(RESET, ALICE.email, TOKEN, 3600) is True
        [mail] = outbox
        assert mail['to'] == ALICE.email
        assert 'password' in mail['subject'].lower()

    def test_links_to_the_reset_page_with_the_token(self, configured, outbox):
        account_mail.deliver(RESET, ALICE.email, TOKEN, 3600)
        body = outbox[0]['body']
        assert f'{SITE}/#!/account/reset?token=' in body
        assert token_in(body) == TOKEN

    def test_says_how_long_the_link_works(self, configured, outbox):
        account_mail.deliver(RESET, ALICE.email, TOKEN, 3600)
        assert 'within an hour' in outbox[0]['body']

    def test_does_not_wait_forever_on_the_mail_server(self, configured, outbox):
        account_mail.deliver(RESET, ALICE.email, TOKEN, 3600)
        assert outbox[0]['timeout'] == config.SMTP_TIMEOUT

    def test_waits_as_long_as_alfred_smtp_timeout_says(
        self, configured, outbox, monkeypatch
    ):
        monkeypatch.setattr(config, 'SMTP_TIMEOUT', 7)
        account_mail.deliver(RESET, ALICE.email, TOKEN, 3600)
        assert outbox[0]['timeout'] == 7


class TestTheConfirmationMail:
    def test_links_to_the_confirmation_page(self, configured, outbox):
        account_mail.deliver(VERIFY, ALICE.email, TOKEN, 3600)
        body = outbox[0]['body']
        assert f'{SITE}/#!/account/verify?token=' in body
        assert token_in(body) == TOKEN


class TestTheLink:
    def test_quotes_the_token(self, configured):
        """A JWT is URL-safe; the link stays a link whatever the token holds."""
        assert account_mail.link(RESET, 'a+b/c d').endswith('token=a%2Bb%2Fc%20d')

    @pytest.mark.parametrize(
        'seconds,words',
        [(3600, 'an hour'), (7200, '2 hours'), (1800, '30 minutes')],
    )
    def test_lifetimes_read_as_words(self, seconds, words):
        assert account_mail.lifetime(seconds) == words


class TestThePublicUrl:
    """The link's address comes from configuration, never from a request.

    A reset link built on the asking request's Host header would carry the
    account owner's token to whatever host the asker named.
    """

    def test_is_taken_as_given(self):
        assert resolve_public_url({'ALFRED_PUBLIC_URL': SITE}) == SITE

    def test_loses_a_trailing_slash(self):
        assert resolve_public_url({'ALFRED_PUBLIC_URL': f' {SITE}/ '}) == SITE

    @pytest.mark.parametrize('value', ['', 'alfred.example.com', 'ftp://x', 'https://'])
    def test_anything_but_an_http_url_is_unset(self, value):
        assert resolve_public_url({'ALFRED_PUBLIC_URL': value}) is None

    def test_absent_is_unset(self):
        assert resolve_public_url({}) is None


class TestTheHooks:
    """What fastapi-users calls when a token is issued."""

    def run(self, hook):
        asyncio.run(getattr(UserManager(None), hook)(ALICE, TOKEN))

    def test_a_reset_is_mailed(self, configured, outbox):
        self.run('on_after_forgot_password')
        assert token_in(outbox[0]['body']) == TOKEN
        assert '/account/reset' in outbox[0]['body']

    def test_a_confirmation_is_mailed(self, configured, outbox):
        self.run('on_after_request_verify')
        assert '/account/verify' in outbox[0]['body']

    def test_in_production_the_log_says_so_without_the_token(
        self, configured, outbox, monkeypatch, capsys
    ):
        monkeypatch.setattr(config, 'PRODUCTION', 'true')
        self.run('on_after_forgot_password')
        out = capsys.readouterr().out
        assert TOKEN not in out
        assert 'mailed' in out
        assert outbox, 'the mail still went'


class TestTheMailUtility:
    """`sendMail` takes the timeout account mail passes it."""

    def smtp(self, monkeypatch):
        from alfred.core.utils import email

        made = []

        class FakeSMTP:
            def __init__(self, *args, **kwargs):
                made.append(kwargs)

            def starttls(self):
                pass

            def login(self, *args):
                pass

            def send_message(self, message):
                pass

            def quit(self):
                pass

        monkeypatch.setattr(email, 'SMTP', FakeSMTP)
        monkeypatch.setattr(email, 'EMAIL_SERVER', 'mail.example.com')
        monkeypatch.setattr(email, 'EMAIL_USERNAME', 'alfred@example.com')
        return email, made

    def test_passes_a_timeout_to_the_connection(self, monkeypatch):
        email, made = self.smtp(monkeypatch)
        assert email.sendMail('a@example.com', 'subject', 'body', timeout=5)
        assert made == [{'timeout': 5}]

    def test_leaves_smtplib_s_default_without_one(self, monkeypatch):
        """For a caller that passes none; every mail alfred sends passes
        ALFRED_SMTP_TIMEOUT."""
        email, made = self.smtp(monkeypatch)
        assert email.sendMail('a@example.com', 'subject', 'body')
        assert made == [{}]
