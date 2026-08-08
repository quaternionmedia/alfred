from typing import Optional

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers
from fastapi_users.db import BeanieUserDatabase, ObjectIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from beanie import PydanticObjectId

from ..utils.db import get_user_db, User

from alfred.config import SECRET_KEY, DEV_SKIP_AUTH, DEV_USER_EMAIL


class UserManager(
    ObjectIDIDMixin,
    BaseUserManager[User, PydanticObjectId],
):
    reset_password_token_secret = SECRET_KEY
    verification_token_secret = SECRET_KEY

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        print(f"User {user.id} has registered.")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f"User {user.id} has forgot their password. Reset token: {token}")

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f"Verification requested for user {user.id}. Verification token: {token}")


async def get_user_manager(user_db: BeanieUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET_KEY, lifetime_seconds=3600)


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
