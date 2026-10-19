"""Passwords are hashed and checked off the event loop, by copies held to the library.

alfred/core/utils/passwords.py replaces fastapi-users' methods that hash or
check a password with copies that do it in the thread pool. A copy of security
code is safe only while it matches its original, so this file holds it there.

- `TestTheGuard`: the installed library is the release the copies were checked
  against, method by method, and anything else is refused, at import as well
  as here. Every library method that touches the password helper is replaced,
  or named as unreachable.
- `TestTheSameAsTheLibrary`: each copy and its original are driven through
  the same cases with the same stand-ins, and must do the same things in the
  same order: the same lookups, writes, hashes, checks and hooks, and the same
  answer or refusal. Only where the hashing runs may differ, and that is
  checked too.
- `TestAlfredsOwnRules`: the dev login's refusal hashes off the loop too.
- `TestWithRealBcrypt`: a hash made by either is accepted by the other, and
  an outdated hash is upgraded at login.
- `TestTheApiAnswersWhile`: `/healthz` answers while a login, a registration
  or a reset is held in its hash or check, as in test_event_loop.py.
"""

import ast
import asyncio
import importlib.util
import inspect
import re
from textwrap import dedent
from types import SimpleNamespace

import fastapi_users
import pytest
from beanie import PydanticObjectId
from fastapi_users import BaseUserManager, exceptions
from fastapi_users.db import ObjectIDIDMixin
from fastapi_users.jwt import decode_jwt, generate_jwt
from fastapi_users.manager import RESET_PASSWORD_TOKEN_AUDIENCE
from fastapi_users.password import PasswordHelper
from passlib.context import CryptContext
from passlib.hash import md5_crypt

from alfred import config
from alfred.core.models import UserCreate, UserUpdate
from alfred.core.routes import users
from alfred.core.routes.users import UserManager
from alfred.core.utils import passwords
from alfred.core.utils.passwords import HashesOffTheLoop
from tests.unit.test_event_loop import HeavyWork, answers_meanwhile, on_the_loop

# Signs the parity cases' tokens. A test value, used nowhere else.
SIGNING = 'test-only key for the password parity cases'

ALICE_ID = PydanticObjectId('64b000000000000000000001')
BOB_ID = PydanticObjectId('64b000000000000000000002')
CAROL_ID = PydanticObjectId('64b000000000000000000003')
NOBODY_ID = PydanticObjectId('64b0000000000000000000ff')
CREATED_ID = PydanticObjectId('64b000000000000000000100')


def accounts():
    """Alice, active; Bob, inactive; Carol, with an outdated hash. Fresh each
    time, since a run may change them."""
    return [
        SimpleNamespace(
            id=ALICE_ID,
            email='alice@example.com',
            hashed_password='hashed(alice password)',
            first_name='Alice',
            is_active=True,
            is_superuser=False,
            is_verified=True,
        ),
        SimpleNamespace(
            id=BOB_ID,
            email='bob@example.com',
            hashed_password='hashed(bob password)',
            first_name='Bob',
            is_active=False,
            is_superuser=False,
            is_verified=True,
        ),
        SimpleNamespace(
            id=CAROL_ID,
            email='carol@example.com',
            hashed_password='old(carol password)',
            first_name='Carol',
            is_active=True,
            is_superuser=False,
            is_verified=True,
        ),
    ]


class Helper:
    """A password helper that records what it is asked, and where.

    Deterministic, so a copy and its original can be compared call for call.
    A password hashes to `hashed(<password>)`. A stored `old(<password>)`
    checks, but asks to be replaced, as passlib does with a deprecated scheme.
    `work`, when given, holds each call until the test lets it go.
    """

    def __init__(self, work=None):
        self.work = work
        self.calls = []
        self.on_the_loop = []

    def _record(self, *call):
        self.calls.append(call)
        self.on_the_loop.append(on_the_loop())
        if self.work is not None:
            self.work.hold()

    def hash(self, password):
        self._record('hash', password)
        return f'hashed({password})'

    def verify_and_update(self, plain_password, hashed_password):
        self._record('verify_and_update', plain_password, hashed_password)
        if hashed_password == f'hashed({plain_password})':
            return True, None
        if hashed_password == f'old({plain_password})':
            return True, f'hashed({plain_password})'
        return False, None

    def generate(self):
        return 'a generated password'


class Users:
    """An in-memory user database that records what it is asked."""

    def __init__(self, *held):
        self.held = {account.id: account for account in held}
        self.log = []

    async def get(self, id):
        self.log.append(('get', str(id)))
        return self.held.get(id)

    async def get_by_email(self, email):
        self.log.append(('get_by_email', email))
        for account in self.held.values():
            if account.email.casefold() == email.casefold():
                return account
        return None

    async def create(self, fields):
        self.log.append(('create', dict(fields)))
        account = SimpleNamespace(id=CREATED_ID, **fields)
        self.held[account.id] = account
        return account

    async def update(self, user, fields):
        self.log.append(('update', user.email, dict(fields)))
        for field, value in fields.items():
            setattr(user, field, value)
        return user


def claims(token):
    """A reset token's claims, but for when it expires."""
    data = decode_jwt(token, SIGNING, [RESET_PASSWORD_TOKEN_AUDIENCE])
    data.pop('exp')
    return data


class Hooks:
    """The library's hooks, recorded rather than run, and a password rule."""

    async def validate_password(self, password, user):
        self.hooks.append(('validate_password', password))
        if password == 'short':
            raise exceptions.InvalidPasswordException(reason='too short')

    async def on_after_register(self, user, request=None):
        self.hooks.append(('registered', user.email))

    async def on_after_update(self, user, update_dict, request=None):
        self.hooks.append(('updated', user.email, dict(update_dict)))

    async def on_after_forgot_password(self, user, token, request=None):
        self.hooks.append(('forgot', user.email, claims(token)))

    async def on_after_reset_password(self, user, request=None):
        self.hooks.append(('reset', user.email))


class Library(Hooks, ObjectIDIDMixin, BaseUserManager):
    """fastapi-users' manager as it ships."""

    reset_password_token_secret = SIGNING
    verification_token_secret = SIGNING


class Copy(Hooks, ObjectIDIDMixin, HashesOffTheLoop, BaseUserManager):
    """The same manager, with alfred's copies in place of the originals."""

    reset_password_token_secret = SIGNING
    verification_token_secret = SIGNING


def described(value):
    return None if value is None else sorted(vars(value).items())


def run(manager_class, case):
    """Run `case` on a fresh manager of `manager_class`: what it did, and,
    for each hash or check, whether it ran on the event loop."""
    db, helper = Users(*accounts()), Helper()
    manager = manager_class(db, helper)
    manager.hooks = []
    held = {account.id: account for account in db.held.values()}
    try:
        outcome = ('answered', described(asyncio.run(case(manager, held))))
    except Exception as exc:
        outcome = ('refused', type(exc).__name__, getattr(exc, 'reason', None))
    did = dict(outcome=outcome, db=db.log, hashing=helper.calls, hooks=manager.hooks)
    return did, helper.on_the_loop


def reset_token(
    sub=str(ALICE_ID), fingerprint='hashed(hashed(alice password))', key=SIGNING
):
    data = {'sub': sub, 'aud': RESET_PASSWORD_TOKEN_AUDIENCE}
    if fingerprint is not None:
        data['password_fgpt'] = fingerprint
    return generate_jwt(data, key, 3600)


def login(username, password):
    credentials = SimpleNamespace(username=username, password=password)
    return lambda manager, held: manager.authenticate(credentials)


def register(safe=True, **fields):
    form = UserCreate(**{'first_name': 'Dora', **fields})
    return lambda manager, held: manager.create(form, safe=safe)


def forgot(account_id):
    return lambda manager, held: manager.forgot_password(held[account_id])


def reset(token, password='a new password'):
    return lambda manager, held: manager.reset_password(token, password)


def change(account_id, **fields):
    form = UserUpdate(**fields)
    return lambda manager, held: manager.update(form, held[account_id], safe=True)


CASES = {
    # authenticate
    'a login': login('alice@example.com', 'alice password'),
    'a wrong password': login('alice@example.com', 'not her password'),
    'an unknown address, hashed anyway': login('nobody@example.com', 'a guess'),
    'an inactive account, refused by the route': login(
        'bob@example.com', 'bob password'
    ),
    'an outdated hash, upgraded': login('carol@example.com', 'carol password'),
    # create
    'a registration': register(email='dora@example.com', password='dora password'),
    'a registration by a superuser': register(
        safe=False,
        email='dora@example.com',
        password='dora password',
        is_superuser=True,
    ),
    'an address already registered': register(
        email='alice@example.com', password='dora password'
    ),
    'a password refused at registration': register(
        email='dora@example.com', password='short'
    ),
    # forgot_password
    'a reset asked for': forgot(ALICE_ID),
    'a reset asked for by an inactive account': forgot(BOB_ID),
    # reset_password
    'a reset': reset(reset_token()),
    'a reset with no token at all': reset('not-a-token'),
    'a reset with a token signed elsewhere': reset(
        reset_token(key='another test-only key, not the one above')
    ),
    'a reset with a token missing its fingerprint': reset(
        reset_token(fingerprint=None)
    ),
    'a reset with a token naming no valid id': reset(reset_token(sub='not-an-id')),
    'a reset for nobody': reset(reset_token(sub=str(NOBODY_ID))),
    'a reset with a token already used': reset(
        reset_token(fingerprint='hashed(an older hash)')
    ),
    'a reset for an inactive account': reset(
        reset_token(sub=str(BOB_ID), fingerprint='hashed(hashed(bob password))')
    ),
    'a reset to a password refused': reset(reset_token(), password='short'),
    # _update, through update
    'a new password': change(ALICE_ID, password='a new password'),
    'a new password refused': change(ALICE_ID, password='short'),
    'a free address': change(ALICE_ID, email='alice@elsewhere.example'),
    'an address taken': change(ALICE_ID, email='carol@example.com'),
    'a new name': change(ALICE_ID, first_name='Al'),
}


class TestTheGuard:
    def test_the_installed_fastapi_users_is_the_release_checked(self):
        assert passwords.library_changes() == [], passwords.refusal(
            passwords.library_changes()
        )

    def test_another_release_is_refused(self):
        assert passwords.library_changes(version='10.4.3') == [
            f'fastapi-users is 10.4.3, not {passwords.CHECKED_AGAINST}.'
        ]

    def test_a_changed_method_is_refused_by_name(self):
        class Changed(BaseUserManager):
            async def authenticate(self, credentials):
                return None

        [changed] = passwords.library_changes(library=Changed)
        assert changed.startswith(
            'BaseUserManager.authenticate (manager.py:630 at 10.4.2) has changed;'
        )

    def test_a_method_gone_is_refused(self):
        changes = passwords.library_changes(library=object)
        assert len(changes) == len(passwords.REPLACED)
        assert all('could not be read' in change for change in changes)

    def test_the_refusal_says_what_to_check_and_where(self):
        message = passwords.refusal(['fastapi-users is 11.0.0, not 10.4.2.'])
        assert 'FASTAPI-USERS IS NOT THE RELEASE CHECKED' in message
        assert '- fastapi-users is 11.0.0, not 10.4.2.' in message
        flat = ' '.join(message.split())
        assert 'alfred/core/utils/passwords.py' in flat
        assert 'update CHECKED_AGAINST and REPLACED' in flat

    def test_the_api_does_not_start_against_another_release(self, monkeypatch):
        """The module refuses at import, so nothing that imports it -- the
        api -- gets as far as serving."""
        monkeypatch.setattr(fastapi_users, '__version__', '10.4.3')
        spec = importlib.util.spec_from_file_location(
            'passwords_against_another_release', passwords.__file__
        )
        module = importlib.util.module_from_spec(spec)
        with pytest.raises(RuntimeError, match='fastapi-users is 10.4.3') as refused:
            spec.loader.exec_module(module)
        assert type(refused.value).__name__ == 'LibraryChanged'

    def test_every_library_method_that_uses_the_helper_is_accounted_for(self):
        """A release that hashed somewhere new would hash on the loop there."""
        uses = {
            name
            for name, function in inspect.getmembers(
                BaseUserManager, inspect.isfunction
            )
            if re.search(r'password_helper\.\w+\(', inspect.getsource(function))
        }
        assert uses == set(passwords.REPLACED) | set(passwords.NOT_REPLACED)

    def test_alfred_s_manager_reaches_every_copy(self):
        """Its own overrides call `super()`, which must land on a copy."""
        mro = UserManager.__mro__
        assert mro.index(HashesOffTheLoop) < mro.index(BaseUserManager)
        for name in passwords.REPLACED:
            assert name in vars(HashesOffTheLoop)
            owner = next(cls for cls in mro if name in vars(cls))
            assert owner is not BaseUserManager, name

    def test_the_copies_never_call_the_originals(self):
        """A copy that called `super()` would run the original, on the loop."""
        tree = ast.parse(dedent(inspect.getsource(HashesOffTheLoop)))
        calls = [
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == 'super'
        ]
        assert calls == []

    def test_what_is_not_replaced_cannot_be_reached(self):
        """fastapi-users names its OAuth routes `oauth:<client>.<backend>...`."""
        from alfred.main import app

        assert passwords.NOT_REPLACED.keys() == {'oauth_callback'}
        names = [getattr(route, 'name', '') or '' for route in app.routes]
        assert [name for name in names if name.startswith('oauth:')] == []

    def test_the_api_names_the_override_at_startup(self, capsys):
        from alfred import main

        assert main.namePasswordHashingOverride in main.app.router.on_startup
        asyncio.run(main.namePasswordHashingOverride())
        line = capsys.readouterr().out.strip()
        assert line == passwords.STARTUP_LINE
        assert 'alfred/core/utils/passwords.py' in line
        assert passwords.CHECKED_AGAINST in line
        assert all(name in line for name in passwords.REPLACED)


class TestTheSameAsTheLibrary:
    @pytest.mark.parametrize('case', list(CASES))
    def test_the_copy_does_what_the_library_does(self, case):
        library, _ = run(Library, CASES[case])
        copy, _ = run(Copy, CASES[case])
        assert copy == library

    @pytest.mark.parametrize('case', list(CASES))
    def test_only_the_copy_hashes_off_the_loop(self, case):
        _, library = run(Library, CASES[case])
        _, copy = run(Copy, CASES[case])
        assert library == [True] * len(library)
        assert copy == [False] * len(copy)

    def test_the_cases_reach_every_hash_and_check(self):
        """Each copy's every helper call is exercised by some case."""
        seen = set()
        for case in CASES.values():
            did, _ = run(Copy, case)
            seen.update(call[0] for call in did['hashing'])
        assert seen == {'hash', 'verify_and_update'}

    def test_an_unknown_address_costs_a_hash(self):
        """The library's timing equaliser: no account still hashes."""
        did, _ = run(Copy, CASES['an unknown address, hashed anyway'])
        assert did['hashing'] == [('hash', 'a guess')]
        assert did['outcome'] == ('answered', None)

    def test_an_outdated_hash_is_replaced(self):
        did, _ = run(Copy, CASES['an outdated hash, upgraded'])
        assert did['db'][-1] == (
            'update',
            'carol@example.com',
            {'hashed_password': 'hashed(carol password)'},
        )


class TestAlfredsOwnRules:
    """What alfred's UserManager adds on top of the copies."""

    @pytest.fixture
    def dev_address(self, monkeypatch):
        monkeypatch.setattr(config, 'DEV_USER_EMAIL', 'dev@example.com')

    def test_the_dev_login_is_hashed_off_the_loop_and_refused(self, dev_address):
        db, helper = Users(*accounts()), Helper()
        credentials = SimpleNamespace(username='DEV@example.com', password='x')
        assert asyncio.run(UserManager(db, helper).authenticate(credentials)) is None
        assert helper.calls == [('hash', 'x')]
        assert helper.on_the_loop == [False]
        assert db.log == []

    def test_everyone_else_logs_in_through_the_copy(self, dev_address):
        db, helper = Users(*accounts()), Helper()
        credentials = SimpleNamespace(
            username='alice@example.com', password='alice password'
        )
        user = asyncio.run(UserManager(db, helper).authenticate(credentials))
        assert user.id == ALICE_ID
        assert helper.on_the_loop == [False]


class TestWithRealBcrypt:
    """The stand-in helper above proves the order of things; these prove the
    real hashes agree."""

    def manager(self, manager_class, held, helper):
        manager = manager_class(Users(*held), helper)
        manager.hooks = []
        return manager

    @pytest.mark.parametrize(
        'hashed_by, checked_by', [(Copy, Library), (Library, Copy)]
    )
    def test_a_hash_from_either_logs_in_with_the_other(self, hashed_by, checked_by):
        helper = PasswordHelper()
        form = UserCreate(
            email='dora@example.com', password='dora password', first_name='Dora'
        )
        dora = asyncio.run(self.manager(hashed_by, [], helper).create(form, safe=True))
        assert dora.hashed_password.startswith('$2b$')

        checker = self.manager(checked_by, [dora], helper)
        right = SimpleNamespace(username=dora.email, password='dora password')
        wrong = SimpleNamespace(username=dora.email, password='not hers')
        assert asyncio.run(checker.authenticate(right)) is dora
        assert asyncio.run(checker.authenticate(wrong)) is None

    def test_an_outdated_hash_is_upgraded_to_bcrypt(self):
        context = CryptContext(schemes=['bcrypt', 'md5_crypt'], deprecated='auto')
        helper = PasswordHelper(context)
        erin = SimpleNamespace(
            id=ALICE_ID,
            email='erin@example.com',
            hashed_password=md5_crypt.hash('erin password'),
            is_active=True,
        )
        manager = self.manager(Copy, [erin], helper)
        credentials = SimpleNamespace(username=erin.email, password='erin password')

        assert asyncio.run(manager.authenticate(credentials)) is erin
        assert erin.hashed_password.startswith('$2b$')
        assert asyncio.run(manager.authenticate(credentials)) is erin


@pytest.fixture
def held(monkeypatch):
    """The api's user manager on an in-memory database, its every hash and
    check held until the test lets it go."""
    from alfred.main import app

    work = HeavyWork()
    work.db, work.helper = Users(*accounts()), Helper(work)
    work.forgot = None

    async def record(self, user, token, request=None):
        work.forgot = token

    # Kept, not mailed or printed: a reset token is a credential.
    monkeypatch.setattr(UserManager, 'on_after_forgot_password', record)
    monkeypatch.setattr(config, 'ALLOW_REGISTRATION', True)
    app.dependency_overrides[users.get_user_manager] = lambda: UserManager(
        work.db, work.helper
    )
    yield work
    app.dependency_overrides.pop(users.get_user_manager, None)


def app_reset_token(account, fingerprint):
    data = {
        'sub': str(account),
        'password_fgpt': fingerprint,
        'aud': RESET_PASSWORD_TOKEN_AUDIENCE,
    }
    return generate_jwt(data, UserManager.reset_password_token_secret, 3600)


class TestTheApiAnswersWhile:
    def test_a_login_is_checked(self, held):
        res = answers_meanwhile(
            held,
            lambda api: api.post(
                '/auth/jwt/login',
                data={'username': 'alice@example.com', 'password': 'alice password'},
            ),
        )
        assert res.status_code == 200, res.text
        assert res.json()['token_type'] == 'bearer'
        assert held.helper.calls[0][0] == 'verify_and_update'

    def test_a_login_for_nobody_is_hashed(self, held):
        res = answers_meanwhile(
            held,
            lambda api: api.post(
                '/auth/jwt/login',
                data={'username': 'nobody@example.com', 'password': 'a guess'},
            ),
        )
        assert res.status_code == 400
        assert res.json() == {'detail': 'LOGIN_BAD_CREDENTIALS'}
        assert held.helper.calls == [('hash', 'a guess')]

    def test_a_registration_is_hashed(self, held):
        res = answers_meanwhile(
            held,
            lambda api: api.post(
                '/auth/register',
                json={
                    'email': 'dora@example.com',
                    'password': 'dora password',
                    'first_name': 'Dora',
                },
            ),
        )
        assert res.status_code == 201, res.text
        assert res.json()['email'] == 'dora@example.com'

    def test_a_reset_is_asked_for(self, held):
        res = answers_meanwhile(
            held,
            lambda api: api.post(
                '/auth/forgot-password', json={'email': 'alice@example.com'}
            ),
        )
        assert res.status_code == 202, res.text
        assert held.forgot

    def test_a_password_is_reset(self, held):
        token = app_reset_token(ALICE_ID, 'hashed(hashed(alice password))')
        res = answers_meanwhile(
            held,
            lambda api: api.post(
                '/auth/reset-password',
                json={'token': token, 'password': 'a new password'},
            ),
        )
        assert res.status_code == 200, res.text
        assert [call[0] for call in held.helper.calls] == ['verify_and_update', 'hash']
        assert held.db.held[ALICE_ID].hashed_password == 'hashed(a new password)'

    def test_an_inactive_account_is_refused_like_a_wrong_password(self, held):
        """By the route, after the check, as with the library's manager."""
        res = answers_meanwhile(
            held,
            lambda api: api.post(
                '/auth/jwt/login',
                data={'username': 'bob@example.com', 'password': 'bob password'},
            ),
        )
        assert res.status_code == 400
        assert res.json() == {'detail': 'LOGIN_BAD_CREDENTIALS'}
        assert held.helper.calls[0][0] == 'verify_and_update'
