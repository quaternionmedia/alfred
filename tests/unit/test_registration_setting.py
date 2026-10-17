"""ALFRED_ALLOW_REGISTRATION, and the default it overrides.

Open by default in development, closed by default under ALFRED_PRODUCTION, and
an explicit value wins in either direction. The route's behaviour under each
outcome is asserted against the running app in
`integration/test_registration_api.py`; these pin the parsing, which is where
a flag like this usually goes wrong.
"""

import pytest

from alfred.config import resolve_allow_registration

PRODUCTION = {'ALFRED_PRODUCTION': 'true'}


class TestTheDefaults:
    def test_development_is_open(self):
        """Registering is how a development stack gets a user at all."""
        assert resolve_allow_registration({}) is True

    @pytest.mark.parametrize('production', ['true', '1', 'yes', 'anything'])
    def test_production_is_closed(self, production):
        """Presence is the signal, not truthiness.

        ALFRED_PRODUCTION is read everywhere as a bare `environ.get`, so any
        non-empty value marks a production process. Parsing it more strictly
        here would let `ALFRED_PRODUCTION=0` open registration on a server
        the rest of the code treats as production.
        """
        assert resolve_allow_registration({'ALFRED_PRODUCTION': production}) is False


class TestAnExplicitValueWins:
    @pytest.mark.parametrize('value', ['1', 'true', 'TRUE', 'yes', 'on', ' true '])
    def test_it_opens_production(self, value):
        env = {**PRODUCTION, 'ALFRED_ALLOW_REGISTRATION': value}
        assert resolve_allow_registration(env) is True

    @pytest.mark.parametrize('value', ['0', 'false', 'False', 'no', 'off'])
    def test_it_closes_development(self, value):
        assert resolve_allow_registration({'ALFRED_ALLOW_REGISTRATION': value}) is False

    @pytest.mark.parametrize('value', ['maybe', 'enabled', 'y', '2'])
    def test_an_unrecognised_value_closes_it(self, value):
        """The same rule as the auth bypass: ambiguity fails closed.

        Applied in development too, where the default is open. Someone who
        wrote a value meant to decide something, and a guess in the open
        direction is the one that matters if they meant "no".
        """
        assert resolve_allow_registration({'ALFRED_ALLOW_REGISTRATION': value}) is False


class TestEmptyMeansUnset:
    """Compose passes an unset host variable through as an empty string.

    `X=${X:-}` in a compose file hands the container `X=''` when nobody set
    it. If that read as an explicit "no", adding such a passthrough would
    silently close registration on every development stack.
    """

    @pytest.mark.parametrize('empty', ['', ' '])
    def test_development_stays_open(self, empty):
        assert resolve_allow_registration({'ALFRED_ALLOW_REGISTRATION': empty}) is True

    @pytest.mark.parametrize('empty', ['', ' '])
    def test_production_stays_closed(self, empty):
        env = {**PRODUCTION, 'ALFRED_ALLOW_REGISTRATION': empty}
        assert resolve_allow_registration(env) is False


class TestTheRouteIsGated:
    """The setting only matters if the register route consults it."""

    def test_the_register_route_carries_the_check(self):
        from alfred.core.routes.auth import registration_is_open
        from alfred.main import app

        [route] = [
            r
            for r in app.routes
            if getattr(r, 'path', None) == '/auth/register'
            and 'POST' in getattr(r, 'methods', ())
        ]
        calls = [d.call for d in route.dependant.dependencies]
        assert registration_is_open in calls

    def test_the_route_is_still_mounted(self):
        """Closed answers 403 with a reason; it does not vanish.

        Unmounted, `POST /auth/register` would fall through to the static
        mount and answer 405 -- "wrong method" -- which the SPA could not tell
        apart from a client bug.
        """
        from alfred.main import app

        assert '/auth/register' in {getattr(r, 'path', None) for r in app.routes}
