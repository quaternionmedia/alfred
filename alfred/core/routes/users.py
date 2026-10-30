from time import time
from typing import Optional

from beanie import PydanticObjectId
from fastapi import Depends, HTTPException, Request
from fastapi_users import BaseUserManager, FastAPIUsers, exceptions
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import BeanieUserDatabase, ObjectIDIDMixin
from fastapi_users.jwt import generate_jwt

from alfred import config
from alfred.config import DEV_SKIP_AUTH, DEV_USER_EMAIL, SECRET_KEY

from ..models import UserRead
from ..utils import account_mail
from ..utils.db import User, get_user_db
from ..utils.ownership import changes_owner_key
from ..utils.passwords import HashesOffTheLoop

EMAIL_IS_THE_OWNER_KEY = (
    "An account's email address cannot be changed: its projects and renders "
    'are recorded against it, and changing it would leave them behind.'
)

DEV_ADDRESS_IS_RESERVED = (
    "That address belongs to this server's development login and cannot be "
    'registered. Use another address.'
)

DEV_ACCOUNT_HAS_NO_PASSWORD = (
    'The development login has no password, and cannot be given one.'
)


def is_dev_address(email):
    """Whether `email` is the auth bypass account's address, in any case, as
    fastapi-users looks addresses up. Read through the module, so tests can
    rename it."""
    return bool(email) and email.casefold() == config.DEV_USER_EMAIL.casefold()


NOT_MAILED = (
    'no mail was sent: that needs EMAIL_SERVER, EMAIL_USERNAME and ' 'ALFRED_PUBLIC_URL'
)


def announce_token(purpose, user, token, mailed=False):
    """Log that a single-use token was issued, and whether it was mailed.

    The token is a credential: it is logged only in development, and only when
    it was not mailed, as the one way to finish a reset there (AGENTS.md,
    "Logging and secrets"). Read through the module, so tests can switch modes.
    """
    delivery = 'a link was mailed to the account' if mailed else NOT_MAILED
    if config.PRODUCTION:
        print(
            f'{purpose} requested for user {user.id}; {delivery}. The token is '
            'not logged in production.',
            flush=True,
        )
    elif mailed:
        print(
            f'{purpose} requested for user {user.id}; {delivery}. The token went '
            'by mail, so it is not logged.',
            flush=True,
        )
    else:
        print(
            f'{purpose} requested for user {user.id}; {delivery}. Token: {token}',
            flush=True,
        )


class UserManager(
    ObjectIDIDMixin,
    # Before the library, so hashing runs off the loop; the overrides below
    # reach it through `super()` (docs/api/auth.md#password-hashing).
    HashesOffTheLoop,
    BaseUserManager[User, PydanticObjectId],
):
    reset_password_token_secret = SECRET_KEY
    verification_token_secret = SECRET_KEY

    async def update(self, user_update, user, safe=False, request=None):
        """Change an account, but never its email, the owner key (contract M5).

        422, for a superuser too, until the key is the user id
        (docs/ownership.md). Here because `PATCH /users/me` and
        `PATCH /users/{id}` both come through it. The same address passes.
        """
        if changes_owner_key(user, user_update.create_update_dict_superuser()):
            raise HTTPException(status_code=422, detail=EMAIL_IS_THE_OWNER_KEY)
        return await super().update(user_update, user, safe=safe, request=request)

    async def create(self, user_create, safe=False, request=None):
        """Create an account, but never at the dev account's address, whose
        owner would own the dev seeds and be who the bypass acts as. 400, with
        a reason, before anything is looked up (docs/dev-auth.md)."""
        if is_dev_address(user_create.email):
            raise HTTPException(status_code=400, detail=DEV_ADDRESS_IS_RESERVED)
        return await super().create(user_create, safe=safe, request=request)

    async def validate_password(self, password, user):
        """No password is ever set on the dev account, a superuser nobody may
        log into. Every route that sets a password comes through here."""
        if is_dev_address(getattr(user, 'email', None)):
            raise exceptions.InvalidPasswordException(
                reason=DEV_ACCOUNT_HAS_NO_PASSWORD
            )
        return await super().validate_password(password, user)

    async def authenticate(self, credentials):
        """A login, refused for the dev account like a wrong password: a 400,
        not the 500 of `!dev-no-login` reaching the hasher. The hash still
        runs, so the refusal takes as long."""
        if is_dev_address(credentials.username):
            await self.hash_password(credentials.password)
            return None
        return await super().authenticate(credentials)

    async def forgot_password(self, user, request=None):
        """A reset token, except for the dev account, which cannot use one.
        The route answers 202 either way."""
        if is_dev_address(user.email):
            return
        return await super().forgot_password(user, request)

    async def verify(self, token, request=None):
        """Confirm an address, answered as `UserRead`: the document dumps its
        id as `_id`, which `UserRead` lacks, and the route would answer 500."""
        return UserRead.model_validate(await super().verify(token, request))

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        print(f"User {user.id} has registered.")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        """Mail the reset link when mail is configured, and log the event."""
        mailed = account_mail.deliver(
            account_mail.RESET,
            user.email,
            token,
            self.reset_password_token_lifetime_seconds,
        )
        announce_token('Password reset', user, token, mailed)

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        """Mail the confirmation link, as a reset link is mailed."""
        mailed = account_mail.deliver(
            account_mail.VERIFY,
            user.email,
            token,
            self.verification_token_lifetime_seconds,
        )
        announce_token('Verification', user, token, mailed)


async def get_user_manager(user_db: BeanieUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

# How long a token works. The SPA renews it before this runs out, for as long
# as somebody is using the app; see website/src/User.js.
TOKEN_LIFETIME_SECONDS = 3600


class IssuedAtJWTStrategy(JWTStrategy):
    """fastapi-users' JWTs, with `iat` beside `exp`.

    `exp - iat` is the lifetime in server time, so the SPA counts it down on
    its own clock and renews in time however far the two clocks disagree.
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
    """The account the auth bypass acts as, created on first use: a real,
    verified superuser, so routes behave as under real auth (docs/dev-auth.md).
    """
    user = await User.find_one(User.email == DEV_USER_EMAIL)
    if user is None:
        user = User(
            email=DEV_USER_EMAIL,
            # Required by the User document.
            first_name='Dev',
            # Not a hash: no password matches it, bypass on or off.
            hashed_password='!dev-no-login',
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        await user.create()
    return user


if DEV_SKIP_AUTH:
    # Swapped wholesale: with the flag off, the bypass is not in any request path.
    current_active_user = get_dev_user
    current_active_superuser = get_dev_user
else:
    current_active_user = _current_active_user
    current_active_superuser = _current_active_superuser
