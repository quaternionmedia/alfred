"""The development auth bypass, and the guards that keep it in development.

`ALFRED_DEV_SKIP_AUTH=1` serves every request as a fixed superuser and lets the
SPA skip its login screen. That is a deliberate hole in the only thing standing
between the API and the internet, so most of what is tested here is not the
feature -- it is the set of conditions under which the feature refuses to exist.

Auth proper is the next phase. These tests are written so that phase can move
the bypass without wondering what it guaranteed: everything asserted below is a
property the bypass must keep, or a way it must fail.
"""

import pytest

from alfred.config import resolve_dev_skip_auth


class TestDefaultsToOff:
    """Absence, emptiness, and every spelling of "no"."""

    def test_absent_variable_leaves_auth_on(self):
        assert resolve_dev_skip_auth({}) is False

    @pytest.mark.parametrize(
        'value',
        ['', '0', 'false', 'False', 'no', 'off', 'nope', ' ', 'disabled'],
    )
    def test_falsy_and_unrecognised_spellings_leave_auth_on(self, value):
        """Unrecognised means off, not on.

        `bool(environ.get(...))` -- the obvious implementation -- treats the
        string '0' and the string 'false' as true, because both are non-empty.
        Those are precisely the two values someone writes when they mean to
        turn the flag off. For a switch that disables authentication the
        ambiguous case has to fail towards staying locked.
        """
        assert resolve_dev_skip_auth({'ALFRED_DEV_SKIP_AUTH': value}) is False

    @pytest.mark.parametrize('value', ['1', 'true', 'TRUE', 'yes', 'on', ' true '])
    def test_explicit_opt_in_turns_auth_off(self, value):
        assert resolve_dev_skip_auth({'ALFRED_DEV_SKIP_AUTH': value}) is True


class TestRefusesProduction:
    """The bypass and production must never coexist in a running process."""

    def test_combining_with_production_raises_rather_than_ignoring(self):
        """Refuse to boot, rather than quietly resolving the contradiction.

        Silently ignoring the flag would be defensible, and is what most
        implementations do. It is the wrong choice here: the operator who set
        it believes it took effect, and the process comes up looking healthy
        either way. Refusing to start is the only outcome that gets noticed.
        """
        with pytest.raises(RuntimeError) as excinfo:
            resolve_dev_skip_auth(
                {'ALFRED_DEV_SKIP_AUTH': '1', 'ALFRED_PRODUCTION': 'true'}
            )
        assert 'ALFRED_PRODUCTION' in str(excinfo.value)

    @pytest.mark.parametrize('production', ['true', '1', 'yes', 'anything'])
    def test_any_production_value_refuses(self, production):
        """Presence is the signal, not truthiness.

        ALFRED_PRODUCTION is read elsewhere as a bare `environ.get`, so any
        non-empty value marks a production process. Applying stricter parsing
        here would let ALFRED_PRODUCTION=0 disagree with the rest of the
        codebase, in the unsafe direction.
        """
        with pytest.raises(RuntimeError):
            resolve_dev_skip_auth(
                {'ALFRED_DEV_SKIP_AUTH': '1', 'ALFRED_PRODUCTION': production}
            )

    def test_production_alone_is_not_an_error(self):
        assert resolve_dev_skip_auth({'ALFRED_PRODUCTION': 'true'}) is False


class TestWiringUnderTheDefault:
    """With the flag off, the bypass must not be in the request path at all."""

    def test_the_real_dependency_is_wired_when_the_flag_is_off(self):
        """Not merely inactive -- absent.

        The test suite runs with the flag unset, so this asserts the shipped
        default. `current_active_user` must be fastapi-users' dependency
        itself, not a wrapper that decides per request: a wrapper is a thing
        that can be got wrong later, and this way there is nothing to get
        wrong.
        """
        from alfred.config import DEV_SKIP_AUTH
        from alfred.core.routes import users

        assert DEV_SKIP_AUTH is False, 'the suite must run with auth enabled'
        assert users.current_active_user is users._current_active_user
        assert users.current_active_superuser is users._current_active_superuser
        assert users.current_active_user is not users.get_dev_user

    def test_the_dev_account_address_survives_response_validation(self):
        """The bypass address must satisfy the schema it is serialised through.

        `dev@localhost` was the first default. The User document stored it
        happily, so the account was created and every gated route worked --
        but UserRead types email as EmailStr, which rejects an address with no
        TLD, so /users/me alone returned 500. A bypass that authenticates you
        everywhere except the endpoint used to check who you are is worse than
        one that plainly does not work.
        """
        from pydantic import BaseModel, EmailStr

        from alfred.config import DEV_USER_EMAIL

        class _Probe(BaseModel):
            email: EmailStr

        _Probe(email=DEV_USER_EMAIL)  # raises if the default is unusable

        # RFC 2606 reserves the .test/.example/.invalid/.localhost TLDs and
        # the example.com/net/org second-level domains. Only the latter group
        # survives EmailStr, which rejects reserved TLDs -- so that is what
        # this can require. dev@alfred.invalid was rejected for exactly that
        # reason after dev@localhost was rejected for lacking a TLD at all.
        domain = DEV_USER_EMAIL.rsplit('@', 1)[-1].lower()
        assert domain in {'example.com', 'example.net', 'example.org'}, (
            f'{DEV_USER_EMAIL} is not in an RFC 2606 reserved domain, so it '
            'could reach a real inbox if something tries to mail it'
        )

    def test_the_dev_account_cannot_be_logged_into(self):
        """The bypass account holds an unusable password hash.

        It is a real, persisted, superuser account that outlives any single
        run with the flag on -- so it must not become a way in once the flag
        is off again. fastapi-users verifies a candidate password against a
        stored hash; '!dev-no-login' is not a hash any hasher produces, so
        verification cannot succeed for any input.
        """
        import inspect

        from alfred.core.routes import users

        source = inspect.getsource(users.get_dev_user)
        assert "hashed_password='!dev-no-login'" in source
        assert 'is_superuser=True' in source, (
            'if the dev account stops being a superuser this test should be '
            'updated deliberately, not silently'
        )
