"""The signing key is checked at startup, and a bad one is announced.

ALFRED_SECRET_KEY signs every session, password-reset and verification token.
Missing, nothing can be signed and every login answers 500 without saying why.
Empty, PyJWT refuses it, and every login answers 500 as well.
Short, under ALFRED_PRODUCTION, it can be recovered from any one token, and
then anyone can mint a session for any account.

Announced, not enforced: the process still boots either way. Whether a
production process should refuse to start is an open decision, and these
tests pin the current answer so changing it is deliberate.
"""

import asyncio

import pytest

from alfred.config import MIN_SECRET_KEY_LENGTH, secret_key_problem

PRODUCTION = {'ALFRED_PRODUCTION': 'true'}
SHORT = 'k' * (MIN_SECRET_KEY_LENGTH - 1)
LONG = 'k' * MIN_SECRET_KEY_LENGTH


class TestTheCheck:
    @pytest.mark.parametrize('env', [{}, PRODUCTION], ids=['development', 'production'])
    def test_an_unset_key_is_a_problem_everywhere(self, env):
        """Not production-only: no key means no login at all.

        Found by running the e2e stack, whose api got no key and whose
        global setup failed at the first login with a bare 500.
        """
        assert 'not set' in secret_key_problem(dict(env))

    @pytest.mark.parametrize('env', [{}, PRODUCTION], ids=['development', 'production'])
    def test_an_empty_key_is_announced_as_unusable_everywhere(self, env):
        """The committed `.secret_key` stub sets exactly this."""
        problem = secret_key_problem({**env, 'ALFRED_SECRET_KEY': ''})
        assert 'empty' in problem
        assert 'every login will fail' in problem
        assert 'not set' not in problem

    def test_pyjwt_refuses_an_empty_key(self):
        """Pins why the empty key is a failure, not a forgery risk."""
        import jwt

        with pytest.raises(jwt.InvalidKeyError):
            jwt.encode({'sub': 'anyone'}, '', algorithm='HS256')

    def test_a_short_key_is_a_problem_in_production(self):
        problem = secret_key_problem({**PRODUCTION, 'ALFRED_SECRET_KEY': SHORT})
        assert str(MIN_SECRET_KEY_LENGTH) in problem

    def test_a_long_enough_key_is_fine_in_production(self):
        assert secret_key_problem({**PRODUCTION, 'ALFRED_SECRET_KEY': LONG}) is None

    def test_a_short_key_is_fine_in_development(self):
        """Development keys are stubs; nothing there is worth forging."""
        assert secret_key_problem({'ALFRED_SECRET_KEY': SHORT}) is None

    def test_the_report_never_contains_the_key(self):
        """A warning that printed the key would be the leak it warns about."""
        key = 'Do-not-print-me-0123456789'
        problem = secret_key_problem({**PRODUCTION, 'ALFRED_SECRET_KEY': key})
        assert key not in problem


class TestTheStartupBanner:
    def run_hook(self):
        from alfred.main import warnIfSecretKeyIsWeak

        # Returns normally in every case: announced, never refused.
        asyncio.run(warnIfSecretKeyIsWeak())

    def test_a_short_production_key_is_announced(self, monkeypatch, capsys):
        monkeypatch.setenv('ALFRED_PRODUCTION', 'true')
        monkeypatch.setenv('ALFRED_SECRET_KEY', SHORT)
        self.run_hook()
        out = capsys.readouterr().out
        assert 'SIGNING KEY' in out
        assert SHORT not in out

    def test_a_missing_key_is_announced(self, monkeypatch, capsys):
        monkeypatch.delenv('ALFRED_PRODUCTION', raising=False)
        monkeypatch.delenv('ALFRED_SECRET_KEY', raising=False)
        self.run_hook()
        assert 'not set' in capsys.readouterr().out

    def test_an_empty_key_is_announced(self, monkeypatch, capsys):
        monkeypatch.delenv('ALFRED_PRODUCTION', raising=False)
        monkeypatch.setenv('ALFRED_SECRET_KEY', '')
        self.run_hook()
        assert 'is empty' in capsys.readouterr().out

    def test_a_good_key_says_nothing(self, monkeypatch, capsys):
        monkeypatch.setenv('ALFRED_PRODUCTION', 'true')
        monkeypatch.setenv('ALFRED_SECRET_KEY', LONG)
        self.run_hook()
        assert capsys.readouterr().out == ''
