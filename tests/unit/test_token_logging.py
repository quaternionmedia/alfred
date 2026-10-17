"""Single-use tokens do not reach a production log.

A password-reset token is a credential: whoever holds one can set the
account's password. Both the reset and the verification hooks printed the
token itself, so in production, reading the log was as good as taking over
any account that asked for a reset. Under ALFRED_PRODUCTION the event is
logged and the token is not. In development the token stays in the log on
purpose -- nothing sends email, so the log is the only way to finish a reset
on a development stack.
"""

import asyncio
from types import SimpleNamespace

import pytest

from alfred import config
from alfred.core.routes.users import UserManager

TOKEN = 'eyJ.this-is-the-credential.sig'
USER = SimpleNamespace(id='6a76a53effdcf46c9c285cf5')

HOOKS = ['on_after_forgot_password', 'on_after_request_verify']


def run(hook):
    # The hooks touch nothing on the manager, so no user database is needed.
    asyncio.run(getattr(UserManager(None), hook)(USER, TOKEN))


@pytest.mark.parametrize('hook', HOOKS)
class TestInProduction:
    def test_the_token_is_not_printed(self, hook, monkeypatch, capsys):
        monkeypatch.setattr(config, 'PRODUCTION', 'true')
        run(hook)
        assert TOKEN not in capsys.readouterr().out

    def test_the_event_still_is(self, hook, monkeypatch, capsys):
        """An operator can still see that a reset or verification happened."""
        monkeypatch.setattr(config, 'PRODUCTION', 'true')
        run(hook)
        out = capsys.readouterr().out
        assert USER.id in out
        assert 'not logged' in out


@pytest.mark.parametrize('hook', HOOKS)
class TestInDevelopment:
    def test_the_token_is_printed(self, hook, monkeypatch, capsys):
        """The only way to finish the flow without an email service."""
        monkeypatch.setattr(config, 'PRODUCTION', None)
        run(hook)
        assert TOKEN in capsys.readouterr().out
