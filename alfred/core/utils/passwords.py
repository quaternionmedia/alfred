"""Passwords hashed and checked in the thread pool, not on the event loop.

fastapi-users 10.4 hashes and checks passwords inside its coroutines, so the
work runs on the event loop. bcrypt is slow on purpose -- about 0.3 s a hash
or a check on the api image -- and the api is one process with one loop:
while a login was checked, nothing else was answered, not a preview and not
`/healthz`. A handful of logins at once held the api for seconds, and anyone
who can reach the login form can send a handful.

The library leaves no seam for it. Its methods that hash or check call
`password_helper` synchronously, between awaits on the database, so the helper
cannot be made awaitable from outside and the methods cannot be run in a
thread. `HashesOffTheLoop` replaces the five that alfred reaches --
`authenticate`, `create`, `forgot_password`, `reset_password` and `_update` --
with the library's own code, line for line, except that every `password_helper`
call is awaited through the thread pool. bcrypt releases the GIL while it
works, so the loop runs freely meanwhile.

That is a copy of security code, and a copy drifts: a fix made upstream would
go missing here without a sound. So it is guarded, loudly.

- **The release and the source it was checked against.** `CHECKED_AGAINST`
  names the fastapi-users release, and `REPLACED` holds a fingerprint of the
  source of each method replaced. Importing this module compares both with the
  installed library and raises `LibraryChanged` when either differs, so the
  api does not start. The message names what differs and what to re-check.
- **Tests that CI runs.** tests/unit/test_password_hashing.py holds the same
  check. It requires every library method that touches the password helper
  to be replaced or named in `NOT_REPLACED`. It drives each replacement and
  the library's original through the same cases, and requires the same
  outcome. And it shows the api answering `/healthz` while a login's check is
  held. tests/unit/test_blocking_calls.py knows the helper's calls block.
- **A line at every startup** (`STARTUP_LINE`, printed by main.py), so nobody
  is surprised to find it.

When fastapi-users is upgraded, the guard fails first. Read each method in
`REPLACED` in the new release, carry what changed into the copy here, then
update `CHECKED_AGAINST` and `REPLACED`. If the new release no longer hashes
on the loop, delete the copy instead.
"""

import hashlib
import inspect
from textwrap import wrap

import fastapi_users
import jwt
from fastapi_users import exceptions
from fastapi_users.jwt import decode_jwt, generate_jwt
from fastapi_users.manager import BaseUserManager
from starlette.concurrency import run_in_threadpool

CHECKED_AGAINST = '10.4.2'

# Each library method replaced: where it is in fastapi_users/manager.py at
# CHECKED_AGAINST, and the sha256 of its source as `inspect.getsource` reads it.
REPLACED = {
    'authenticate': (
        'manager.py:630',
        'd00126280591fe2fab843278baf8248364a1ded05c050808f9eb008619e74e44',
    ),
    'create': (
        'manager.py:110',
        '9ea6945bce6ccd45dba973fdf6176acf27a70c8c765f8b46b013d049910812a3',
    ),
    'forgot_password': (
        'manager.py:358',
        '5045b21bcee75c1d3e52b80b032b49f83dc4ebcdbc3720ea36442386f5b137d2',
    ),
    'reset_password': (
        'manager.py:386',
        'c67e1e47b1766ebdc3d6d2fece77428d66bd758fb0c3a89772eae36d8a99b0db',
    ),
    '_update': (
        'manager.py:659',
        '89bb1bbc4482bc168f2d57f33bf46d64045b4d89c0ccd25736931575d24c0f4b',
    ),
}

# Library methods that touch the password helper and are left as they are,
# with the reason that is safe. Anything added here must be unreachable.
NOT_REPLACED = {
    'oauth_callback': 'alfred mounts no OAuth router, so nothing calls it',
}

STARTUP_LINE = (
    f'Password hashing: alfred replaces the fastapi-users {CHECKED_AGAINST} '
    f'methods {", ".join(REPLACED)} with copies that hash and check in the '
    'thread pool (alfred/core/utils/passwords.py). Checked against that '
    'release at import; any other refuses to start.'
)


class LibraryChanged(RuntimeError):
    """The installed fastapi-users is not the one the copies were checked against."""


def fingerprint(function):
    """The sha256 of a function's source, as `inspect.getsource` reads it."""
    return hashlib.sha256(inspect.getsource(function).encode('utf-8')).hexdigest()


def library_changes(library=BaseUserManager, version=None):
    """What differs from the release the copies were checked against: one
    sentence each, and none when nothing does.

    `library` and `version` are the installed ones unless a test says
    otherwise.
    """
    installed = fastapi_users.__version__ if version is None else version
    found = []
    if installed != CHECKED_AGAINST:
        found.append(f'fastapi-users is {installed}, not {CHECKED_AGAINST}.')
    for name, (where, checked) in REPLACED.items():
        try:
            now = fingerprint(getattr(library, name))
        except (AttributeError, OSError, TypeError) as exc:
            found.append(f'BaseUserManager.{name} could not be read: {exc}.')
            continue
        if now != checked:
            found.append(
                f'BaseUserManager.{name} ({where} at {CHECKED_AGAINST}) has '
                f'changed; its source now fingerprints {now}.'
            )
    return found


def refusal(changes):
    """The message `LibraryChanged` carries: what differs, and what to do."""
    rule = '!' * 72
    advice = (
        "alfred/core/utils/passwords.py replaces BaseUserManager's "
        f'{", ".join(REPLACED)} with copies of its own, which hash and check '
        'passwords in the thread pool. A copy of security code that no longer '
        'matches the original is how an upstream fix goes missing, so the api '
        'will not start against it. Read each replaced method in the installed '
        'release, carry what changed into the copy, then update CHECKED_AGAINST '
        'and REPLACED. tests/unit/test_password_hashing.py checks the result.'
    )
    lines = ['', rule, '  PASSWORD HASHING: FASTAPI-USERS IS NOT THE RELEASE CHECKED']
    for change in changes:
        lines += [f'  - {text}' for text in wrap(change, 66)]
    lines += [f'  {text}' for text in wrap(advice, 68)]
    lines.append(rule)
    return '\n'.join(lines)


def check_library():
    """Raise `LibraryChanged` unless the installed fastapi-users is the one checked."""
    changes = library_changes()
    if changes:
        raise LibraryChanged(refusal(changes))


class HashesOffTheLoop:
    """BaseUserManager's methods that hash or check passwords, doing it in the
    thread pool.

    A manager lists this before BaseUserManager among its bases, so these are
    the methods its own overrides reach through `super()`. Each body is the
    library's, comments included, with every `password_helper` call awaited
    through `hash_password` or `check_password`. Nothing else differs; the
    tests hold each one to its original.
    """

    async def hash_password(self, password):
        """`password_helper.hash`, in the thread pool."""
        return await run_in_threadpool(self.password_helper.hash, password)

    async def check_password(self, plain_password, hashed_password):
        """`password_helper.verify_and_update`, in the thread pool."""
        return await run_in_threadpool(
            self.password_helper.verify_and_update, plain_password, hashed_password
        )

    async def create(self, user_create, safe=False, request=None):
        await self.validate_password(user_create.password, user_create)

        existing_user = await self.user_db.get_by_email(user_create.email)
        if existing_user is not None:
            raise exceptions.UserAlreadyExists()

        user_dict = (
            user_create.create_update_dict()
            if safe
            else user_create.create_update_dict_superuser()
        )
        password = user_dict.pop("password")
        user_dict["hashed_password"] = await self.hash_password(password)

        created_user = await self.user_db.create(user_dict)

        await self.on_after_register(created_user, request)

        return created_user

    async def forgot_password(self, user, request=None):
        if not user.is_active:
            raise exceptions.UserInactive()

        token_data = {
            "sub": str(user.id),
            "password_fgpt": await self.hash_password(user.hashed_password),
            "aud": self.reset_password_token_audience,
        }
        token = generate_jwt(
            token_data,
            self.reset_password_token_secret,
            self.reset_password_token_lifetime_seconds,
        )
        await self.on_after_forgot_password(user, token, request)

    async def reset_password(self, token, password, request=None):
        try:
            data = decode_jwt(
                token,
                self.reset_password_token_secret,
                [self.reset_password_token_audience],
            )
        except jwt.PyJWTError:
            raise exceptions.InvalidResetPasswordToken()  # noqa: B904 - verbatim

        try:
            user_id = data["sub"]
            password_fingerprint = data["password_fgpt"]
        except KeyError:
            raise exceptions.InvalidResetPasswordToken()  # noqa: B904 - verbatim

        try:
            parsed_id = self.parse_id(user_id)
        except exceptions.InvalidID:
            raise exceptions.InvalidResetPasswordToken()  # noqa: B904 - verbatim

        user = await self.get(parsed_id)

        valid_password_fingerprint, _ = await self.check_password(
            user.hashed_password, password_fingerprint
        )
        if not valid_password_fingerprint:
            raise exceptions.InvalidResetPasswordToken()

        if not user.is_active:
            raise exceptions.UserInactive()

        updated_user = await self._update(user, {"password": password})

        await self.on_after_reset_password(user, request)

        return updated_user

    async def authenticate(self, credentials):
        try:
            user = await self.get_by_email(credentials.username)
        except exceptions.UserNotExists:
            # Run the hasher to mitigate timing attack
            # Inspired from Django: https://code.djangoproject.com/ticket/20760
            await self.hash_password(credentials.password)
            return None

        verified, updated_password_hash = await self.check_password(
            credentials.password, user.hashed_password
        )
        if not verified:
            return None
        # Update password hash to a more robust one if needed
        if updated_password_hash is not None:
            await self.user_db.update(user, {"hashed_password": updated_password_hash})

        return user

    async def _update(self, user, update_dict):
        validated_update_dict = {}
        for field, value in update_dict.items():
            if field == "email" and value != user.email:
                try:
                    await self.get_by_email(value)
                    raise exceptions.UserAlreadyExists()
                except exceptions.UserNotExists:
                    validated_update_dict["email"] = value
                    validated_update_dict["is_verified"] = False
            elif field == "password":
                await self.validate_password(value, user)
                validated_update_dict["hashed_password"] = await self.hash_password(
                    value
                )
            else:
                validated_update_dict[field] = value
        return await self.user_db.update(user, validated_update_dict)


# At import, so a mismatch stops the api before it serves anything.
check_library()
