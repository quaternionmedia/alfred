"""Single-use tokens do not reach a production log.

A password-reset token is a credential: whoever holds one can set the
account's password. Both the reset and the verification hooks printed the
token itself, so in production, reading the log was as good as taking over
any account that asked for a reset. Under ALFRED_PRODUCTION the event is
logged and the token is not. In development the token stays in the log on
purpose -- without mail configured, the log is the only way to finish a reset
on a development stack.

The mail itself is `test_account_mail.py`'s. These run with it unconfigured,
whatever the environment says, and with it delivered nowhere when it is.
"""

import asyncio
from types import SimpleNamespace

import pytest

from alfred import config
from alfred.core.routes.users import UserManager
from alfred.core.utils import account_mail

TOKEN = 'eyJ.this-is-the-credential.sig'
USER = SimpleNamespace(id='6a76a53effdcf46c9c285cf5', email='someone@example.com')

HOOKS = ['on_after_forgot_password', 'on_after_request_verify']


@pytest.fixture(autouse=True)
def no_mail(monkeypatch):
    monkeypatch.setattr(config, 'PUBLIC_URL', None)
    monkeypatch.setattr(account_mail, 'dispatch', lambda send: None)


@pytest.fixture
def mail_configured(monkeypatch):
    monkeypatch.setattr(config, 'EMAIL_SERVER', 'smtp.example.com')
    monkeypatch.setattr(config, 'EMAIL_USERNAME', 'alfred@example.com')
    monkeypatch.setattr(config, 'PUBLIC_URL', 'https://alfred.example.com')


def run(hook):
    # The hooks touch nothing on the manager, so no user database is needed.
    asyncio.run(getattr(UserManager(None), hook)(USER, TOKEN))


@pytest.mark.parametrize('hook', HOOKS)
class TestInProduction:
    def test_the_token_is_not_printed(self, hook, monkeypatch, capsys):
        monkeypatch.setattr(config, 'PRODUCTION', 'true')
        run(hook)
        assert TOKEN not in capsys.readouterr().out

    def test_nor_when_it_is_mailed(self, hook, monkeypatch, capsys, mail_configured):
        monkeypatch.setattr(config, 'PRODUCTION', 'true')
        run(hook)
        out = capsys.readouterr().out
        assert TOKEN not in out
        assert 'mailed' in out

    def test_the_event_still_is(self, hook, monkeypatch, capsys):
        """An operator can still see that a reset or verification happened."""
        monkeypatch.setattr(config, 'PRODUCTION', 'true')
        run(hook)
        out = capsys.readouterr().out
        assert USER.id in out
        assert 'not logged' in out

    def test_and_why_nothing_was_mailed(self, hook, monkeypatch, capsys):
        """Otherwise a reset that never arrives says nothing anywhere."""
        monkeypatch.setattr(config, 'PRODUCTION', 'true')
        run(hook)
        assert 'ALFRED_PUBLIC_URL' in capsys.readouterr().out


@pytest.mark.parametrize('hook', HOOKS)
class TestInDevelopment:
    def test_the_token_is_printed(self, hook, monkeypatch, capsys):
        """The only way to finish the flow without an email service."""
        monkeypatch.setattr(config, 'PRODUCTION', None)
        run(hook)
        assert TOKEN in capsys.readouterr().out
