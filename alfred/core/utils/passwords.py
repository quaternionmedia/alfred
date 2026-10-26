"""Passwords hashed and checked in a pool of their own, not on the event loop.

`HashesOffTheLoop` holds copies of the five fastapi-users methods that hash or
check a password: the library's code line for line, but for awaiting every
`password_helper` call in a pool of HASHES_AT_ONCE threads of its own. Importing this module refuses any
release but CHECKED_AGAINST, and any original that changed (`LibraryChanged`).
Why, and how to upgrade: docs/api/auth.md#password-hashing.
"""

import asyncio
import hashlib
import inspect
from concurrent.futures import ThreadPoolExecutor
from textwrap import wrap

import fastapi_users
import jwt
from fastapi_users import exceptions
from fastapi_users.jwt import decode_jwt, generate_jwt
from fastapi_users.manager import BaseUserManager

CHECKED_AGAINST = '15.0.5'

# Argon2 takes 64 MiB a hash; more logins than this wait their turn.
HASHES_AT_ONCE = 4
_hashing = ThreadPoolExecutor(HASHES_AT_ONCE, thread_name_prefix='password')

# Each library method replaced: where it is in fastapi_users/manager.py at
# CHECKED_AGAINST, and the sha256 of its source as `inspect.getsource` reads it.
REPLACED = {
    'authenticate': (
        'manager.py:636',
        'e453ea340730cf50c47dfa131f0708706fcaaf1d196c5dcb93c07dc023903188',
    ),
    'create': (
        'manager.py:110',
        '3d1328456778ffce42a3ec59f4ba5611468084c7336a533d07da4573df472cb7',
    ),
    'forgot_password': (
        'manager.py:358',
        '785379634e5059ec0baccd44c8fdd98fd0034bb5fb5952b733db62f73a456595',
    ),
    'reset_password': (
        'manager.py:386',
        'f0c5df8b888017290be39b6cb3ea30567d28392e573a069875972729af73cb3e',
    ),
    '_update': (
        'manager.py:667',
        '1c49e7a79f770662558dc24d0ae60074ff4c03b60f83e23e82a02bc75f34936b',
    ),
}

# Library methods that touch the password helper and are left as they are,
# with the reason that is safe. Anything added here must be unreachable.
NOT_REPLACED = {
    'oauth_callback': 'alfred mounts no OAuth router, so nothing calls it',
}

STARTUP_LINE = (
    f'Password hashing: alfred replaces the fastapi-users {CHECKED_AGAINST} '
    f'methods {", ".join(REPLACED)} with copies that hash and check in a pool '
    f'of {HASHES_AT_ONCE} threads (alfred/core/utils/passwords.py). Checked '
    'against that release at import; any other refuses to start.'
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
        'passwords off the event loop. A copy of security code that no longer '
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
    """BaseUserManager's methods that hash or check passwords, off the loop.

    Listed before BaseUserManager in a manager's bases. Each body is the
    library's, comments included; only the `password_helper` calls differ.
    """

    async def hash_password(self, password):
        """`password_helper.hash`, in the hashing pool."""
        return await asyncio.get_running_loop().run_in_executor(
            _hashing, self.password_helper.hash, password
        )

    async def check_password(self, plain_password, hashed_password):
        """`password_helper.verify_and_update`, in the hashing pool."""
        return await asyncio.get_running_loop().run_in_executor(
            _hashing,
            self.password_helper.verify_and_update,
            plain_password,
            hashed_password,
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
            elif field == "password" and value is not None:
                await self.validate_password(value, user)
                validated_update_dict["hashed_password"] = await self.hash_password(
                    value
                )
            else:
                validated_update_dict[field] = value
        return await self.user_db.update(user, validated_update_dict)


# At import, so a mismatch stops the api before it serves anything.
check_library()
