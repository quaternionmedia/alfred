"""The session routes the SPA depends on, against the running app.

The SPA renews its token before expiry while it is in use, and that only works
if three things hold at the API: a token says how long it lives, refresh
exchanges a working token for a fresh one, and refresh refuses anything else.
Logout is the fastapi-users route -- the SPA posted to `/logout`, which never
existed.
"""

import jwt
import pytest

from alfred.core.routes.users import TOKEN_LIFETIME_SECONDS

pytestmark = pytest.mark.needs_db


def claims(token):
    """A token's claims, read without verifying it -- this is the client's view."""
    return jwt.decode(token, options={'verify_signature': False})


def bearer(token):
    return {'Authorization': f'Bearer {token}'}


class TestATokenSaysHowLongItLives:
    def test_it_carries_iat_beside_exp(self, make_account):
        """`exp` alone is a moment on the server's clock.

        The SPA renews shortly before expiry, judged on the browser's clock;
        with only `exp`, a browser running slow would renew a token that had
        already died. `exp - iat` is a duration in server time, so skew
        cancels.
        """
        token = claims(make_account('clock').token)
        assert isinstance(token['iat'], int)
        assert token['exp'] - token['iat'] == TOKEN_LIFETIME_SECONDS

    def test_a_refreshed_token_does_too(self, api, make_account):
        account = make_account('clock')
        res = api.post('/auth/jwt/refresh', headers=account.headers)
        token = claims(res.json()['access_token'])
        assert token['exp'] - token['iat'] == TOKEN_LIFETIME_SECONDS


class TestRefresh:
    def test_a_working_token_is_exchanged_for_one_that_works(self, api, make_account):
        account = make_account('renewer')

        res = api.post('/auth/jwt/refresh', headers=account.headers)

        assert res.status_code == 200, res.text
        fresh = res.json()['access_token']
        me = api.get('/users/me', headers=bearer(fresh))
        assert me.json()['email'] == account.email

    def test_an_anonymous_caller_is_refused(self, api):
        """Otherwise refresh would mint sessions without credentials."""
        assert api.post('/auth/jwt/refresh').status_code == 401

    def test_a_token_that_is_not_one_is_refused(self, api):
        assert api.post('/auth/jwt/refresh', headers=bearer('nope')).status_code == 401

    def test_an_expired_token_is_refused(self, api, make_account):
        """Why the SPA must renew *before* expiry, never after a 401.

        Refresh extends a session that still works; it cannot revive one. A
        token signed with the server's own key, for a real account, is still
        refused once its `exp` has passed.
        """
        from fastapi_users.jwt import generate_jwt

        from alfred.config import SECRET_KEY

        account = make_account('lapsed')
        subject = claims(account.token)['sub']
        expired = generate_jwt(
            {'sub': subject, 'aud': ['fastapi-users:auth']},
            SECRET_KEY,
            lifetime_seconds=-60,
        )

        assert api.post('/auth/jwt/refresh', headers=bearer(expired)).status_code == 401


class TestLogout:
    def test_the_real_route_accepts_a_session(self, api, make_account):
        res = api.post('/auth/jwt/logout', headers=make_account('leaver').headers)
        assert res.status_code in (200, 204), res.text

    def test_it_refuses_an_anonymous_caller(self, api):
        assert api.post('/auth/jwt/logout').status_code == 401

    def test_the_route_the_spa_used_does_not_exist(self, api):
        """`POST /logout` falls through to the static mount, which refuses POST.

        That 405 was every logout the SPA ever sent; nothing read it.
        """
        assert api.post('/logout').status_code == 405

    def test_a_token_still_works_after_logout(self, api, make_account):
        """Pinned as a property: these JWTs are stateless.

        Logging out ends a session by the client forgetting its token; the
        server keeps no revocation list, so a copy kept elsewhere stays valid
        until it expires. If revocation is ever added this goes red, which is
        the moment to decide it deliberately.
        """
        account = make_account('leaver')
        api.post('/auth/jwt/logout', headers=account.headers)
        assert api.get('/users/me', headers=account.headers).status_code == 200
