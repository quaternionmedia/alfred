from time import time
from typing import Optional

from beanie import PydanticObjectId
from fastapi import Depends, HTTPException, Request
from fastapi_users import BaseUserManager, FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import BeanieUserDatabase, ObjectIDIDMixin
from fastapi_users.jwt import generate_jwt

from alfred import config
from alfred.config import DEV_SKIP_AUTH, DEV_USER_EMAIL, SECRET_KEY

from ..utils.db import User, get_user_db
from ..utils.ownership import changes_owner_key

EMAIL_IS_THE_OWNER_KEY = (
    "An account's email address cannot be changed: its projects and renders "
    'are recorded against it, and changing it would leave them behind.'
)


def announce_token(purpose, user, token):
    """Note that a single-use token was issued -- and, outside production, show it.

    Both of these printed the token itself, every time. A password-reset
    token is a credential: whoever holds it can set the account's password,
    so a production log that recorded them made reading the logs equivalent
    to taking over any account that asked for a reset. Under
    ALFRED_PRODUCTION the event is logged and the token is not.

    In development the token stays in the log on purpose. Nothing here sends
    email, so the log is the only way to finish a reset or a verification on
    a development stack, and that is exactly where somebody needs to.

    Read through the module at call time, so the tests can switch modes
    without re-importing.
    """
    if config.PRODUCTION:
        print(
            f'{purpose} requested for user {user.id}. The token is not logged '
            'in production.',
            flush=True,
        )
    else:
        print(f'{purpose} requested for user {user.id}. Token: {token}', flush=True)


class UserManager(
    ObjectIDIDMixin,
    BaseUserManager[User, PydanticObjectId],
):
    reset_password_token_secret = SECRET_KEY
    verification_token_secret = SECRET_KEY

    async def update(self, user_update, user, safe=False, request=None):
        """Change an account -- but never its owner key (contract M5).

        Projects and renders record their owner by email, so an email change
        was an ownership change nobody asked for: the account kept its id and
        lost every project and render recorded against the old address, which
        went on matching nobody. Refused with 422, for superusers editing
        anyone too, until the key is the user id (docs/ownership.md).

        Here rather than on a route because both `PATCH /users/me` and
        `PATCH /users/{id}` arrive through this method, and neither route is
        ours to edit. Sending the address the account already has is not a
        change, and passes.
        """
        if changes_owner_key(user, user_update.create_update_dict_superuser()):
            raise HTTPException(status_code=422, detail=EMAIL_IS_THE_OWNER_KEY)
        return await super().update(user_update, user, safe=safe, request=request)

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        print(f"User {user.id} has registered.")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        announce_token('Password reset', user, token)

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        announce_token('Verification', user, token)


async def get_user_manager(user_db: BeanieUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

# How long a token works. The SPA renews it before this runs out, for as long
# as somebody is using the app; see website/src/User.js.
TOKEN_LIFETIME_SECONDS = 3600


class IssuedAtJWTStrategy(JWTStrategy):
    """fastapi-users' JWTs, also saying when they were issued.

    A token carried `exp` and nothing else about time, and `exp` is a moment
    on the server's clock. The SPA renews a token shortly before it expires,
    and judging "shortly before" against the browser's clock is only right
    when the two clocks agree: a browser running ten minutes slow would ask
    to renew a token that had already died, and the person would be sent to
    log in mid-edit. With `iat` beside it, the lifetime is `exp - iat` --
    both server time, so any skew cancels -- and the browser counts that down
    on its own clock from the moment it received the token.

    Validation is unchanged apart from PyJWT checking `iat` is not in the
    future, which it cannot be when the same server issues and reads it.
    """

    async def write_token(self, user) -> str:
        data = {
            'sub': str(user.id),
            'aud': self.token_audience,
            'iat': int(time()),
        }
        return generate_jwt(
            data, self.encode_key, self.lifetime_seconds, algorithm=self.algorithm
        )


def get_jwt_strategy() -> JWTStrategy:
    return IssuedAtJWTStrategy(
        secret=SECRET_KEY, lifetime_seconds=TOKEN_LIFETIME_SECONDS
    )


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)
fastapi_users = FastAPIUsers[User, PydanticObjectId](get_user_manager, [auth_backend])

_current_active_user = fastapi_users.current_user(active=True)
_current_active_superuser = fastapi_users.current_user(
    active=True, verified=True, superuser=True
)


async def get_dev_user() -> User:
    """The account the auth bypass acts as, created on first use.

    A real persisted User rather than a stand-in object, because routes do
    more than gate on it -- `render.py` attributes records to `user.id`. A
    fake would let those paths behave differently under the bypass than under
    real auth, which defeats the point of developing against it.

    Superuser and verified, so the admin routes are reachable too; the bypass
    is all-or-nothing by design. Anything finer grained is auth work, and auth
    is the next phase.
    """
    user = await User.find_one(User.email == DEV_USER_EMAIL)
    if user is None:
        user = User(
            email=DEV_USER_EMAIL,
            # Required by the User document. Its absence is why the first
            # version of this raised a 500 rather than serving the request --
            # the bypass has to satisfy the same model as a registered user,
            # which is the point of persisting a real one.
            first_name='Dev',
            # Not a usable credential: fastapi-users compares against a hash,
            # and this is not one, so no password can ever match it. The
            # bypass account cannot be logged into even when the bypass is off.
            hashed_password='!dev-no-login',
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        await user.create()
    return user


if DEV_SKIP_AUTH:
    # Swapped wholesale rather than branching inside a dependency, so that
    # with the flag off the real fastapi-users dependencies are the only thing
    # wired into the app and the bypass is not in the request path at all.
    current_active_user = get_dev_user
    current_active_superuser = get_dev_user
else:
    current_active_user = _current_active_user
    current_active_superuser = _current_active_superuser
