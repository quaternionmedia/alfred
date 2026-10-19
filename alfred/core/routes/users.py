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
    """Whether `email` is the auth bypass account's address, in any case.

    In any case, because fastapi-users finds accounts by address
    case-insensitively: `DEV@example.com` is the same login as
    `dev@example.com`. Read through the module, so the tests can rename it.
    """
    return bool(email) and email.casefold() == config.DEV_USER_EMAIL.casefold()


NOT_MAILED = (
    'no mail was sent: that needs EMAIL_SERVER, EMAIL_USERNAME and ' 'ALFRED_PUBLIC_URL'
)


def announce_token(purpose, user, token, mailed=False):
    """Note that a single-use token was issued -- and, outside production, show it.

    Both of these printed the token itself, every time. A password-reset
    token is a credential: whoever holds it can set the account's password,
    so a production log that recorded them made reading the logs equivalent
    to taking over any account that asked for a reset. Under
    ALFRED_PRODUCTION the event is logged, with whether the link was mailed
    and why not, and the token is not.

    In development the token stays in the log on purpose: a development stack
    rarely has mail configured, and then the log is the only way to finish a
    reset or a verification.

    Read through the module at call time, so the tests can switch modes
    without re-importing.
    """
    delivery = 'a link was mailed to the account' if mailed else NOT_MAILED
    if config.PRODUCTION:
        print(
            f'{purpose} requested for user {user.id}; {delivery}. The token is '
            'not logged in production.',
            flush=True,
        )
    else:
        print(
            f'{purpose} requested for user {user.id}; {delivery}. Token: {token}',
            flush=True,
        )


class UserManager(
    ObjectIDIDMixin,
    # Before the library: its methods that hash or check a password are
    # replaced by copies that do it in the thread pool, so a login does not
    # hold the event loop. The overrides below reach those through `super()`.
    HashesOffTheLoop,
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

    async def create(self, user_create, safe=False, request=None):
        """Create an account -- but never at the dev account's address.

        The auth bypass acts as ALFRED_DEV_USER_EMAIL, and owns what
        development creates for it: the seeded projects and its demo. That
        account is made by the bypass on first use, so on a stack where the
        bypass had never run, the address was free -- and with registration
        open, whoever registered it owned the dev seeds, and became the
        account the bypass would act as. Refused with 400 and a reason, like
        fastapi-users' own refusals here, before anything is looked up.
        """
        if is_dev_address(user_create.email):
            raise HTTPException(status_code=400, detail=DEV_ADDRESS_IS_RESERVED)
        return await super().create(user_create, safe=safe, request=request)

    async def validate_password(self, password, user):
        """No password is ever set on the dev account.

        It stores `!dev-no-login` where a hash belongs, so no password matches
        it and the account cannot be logged into once the bypass is off --
        and it is a superuser. Every route that sets a password comes through
        here -- a reset, a superuser's `PATCH /users/{id}` -- so this is where
        that property is kept.
        """
        if is_dev_address(getattr(user, 'email', None)):
            raise exceptions.InvalidPasswordException(
                reason=DEV_ACCOUNT_HAS_NO_PASSWORD
            )
        return await super().validate_password(password, user)

    async def authenticate(self, credentials):
        """A login -- refused for the dev account like a wrong password.

        It was refused, but as a 500: fastapi-users hands the stored value to
        passlib to verify, and `!dev-no-login` is not a hash passlib can
        identify, so every attempt raised. A 400 is the answer any wrong
        password gets. The hash runs anyway, so the refusal takes as long --
        in the thread pool, as every other hash does.
        """
        if is_dev_address(credentials.username):
            await self.hash_password(credentials.password)
            return None
        return await super().authenticate(credentials)

    async def forgot_password(self, user, request=None):
        """Issue a reset token -- except to the dev account, which has no use for one.

        It could not be used (see `validate_password`), and there is nobody at
        the address to read it. The route answers 202 either way, as it does
        for an address with no account, so this says nothing to the caller.
        """
        if is_dev_address(user.email):
            return
        return await super().forgot_password(user, request)

    async def verify(self, token, request=None):
        """Confirm an address -- and answer with the account as the API shows it.

        fastapi-users' `POST /auth/verify` returns what this returns, under
        `response_model=UserRead`. Given the beanie document, FastAPI dumps it
        by alias, its id comes out as `_id`, and `UserRead` has no `id`: every
        confirmation that succeeded answered 500, after confirming. Nothing
        called it until the confirmation link was mailed.
        """
        return UserRead.from_orm(await super().verify(token, request))

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        print(f"User {user.id} has registered.")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        """Mail the reset link, when mail is configured; and say so in the log.

        Nothing delivered these tokens, so outside development -- where the
        log is not somewhere the person asking can read -- a reset could be
        asked for and never finished. See `utils.account_mail`.
        """
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
