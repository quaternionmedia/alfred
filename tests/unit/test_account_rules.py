"""What the user manager refuses to do to an account, whichever route asks.

fastapi-users' routes are not ours to edit, so the account rules live on
`UserManager`, the one place every route that changes an account goes through.
These drive the manager directly, with an in-memory stand-in for the user
database; `integration/test_account_rules_api.py` and
`integration/test_registration_api.py` ask the same of the running app.
"""

import asyncio
from types import SimpleNamespace

import pytest
from beanie import PydanticObjectId
from fastapi import HTTPException
from fastapi_users import exceptions

from alfred import config
from alfred.core.models import UserCreate, UserUpdate
from alfred.core.routes.users import (
    DEV_ACCOUNT_HAS_NO_PASSWORD,
    DEV_ADDRESS_IS_RESERVED,
    EMAIL_IS_THE_OWNER_KEY,
    UserManager,
)

DEV = 'dev@example.com'


class FakeUserDB:
    """Records writes instead of making them."""

    def __init__(self):
        self.updates = []
        self.created = []

    async def update(self, user, changes):
        self.updates.append(changes)
        for field, value in changes.items():
            setattr(user, field, value)
        return user

    async def create(self, fields):
        self.created.append(fields)
        return SimpleNamespace(id=PydanticObjectId(), **fields)

    async def get_by_email(self, email):
        return None


def account(**fields):
    base = dict(email='alice@example.com', is_superuser=False, first_name='Alice')
    return SimpleNamespace(**{**base, **fields})


def update(user, safe=True, **changes):
    """`PATCH /users/me` is `safe=True`; a superuser's `PATCH /users/{id}` is not."""
    db = FakeUserDB()
    manager = UserManager(db)
    asyncio.run(manager.update(UserUpdate(**changes), user, safe=safe))
    return db.updates


class TestTheEmailIsTheOwnerKey:
    """Contract M5: while ownership is keyed by email, an email cannot change.

    Projects and renders record their owner's address. Changing it left the
    account with its id and none of its work, recorded against an address that
    now matched nobody.
    """

    @pytest.mark.parametrize('safe', [True, False], ids=['own', 'by a superuser'])
    def test_a_new_address_is_refused_with_422(self, safe):
        with pytest.raises(HTTPException) as refused:
            update(account(), safe=safe, email='alice@elsewhere.example')
        assert refused.value.status_code == 422

    def test_the_refusal_says_why(self):
        with pytest.raises(HTTPException) as refused:
            update(account(), email='alice@elsewhere.example')
        assert refused.value.detail == EMAIL_IS_THE_OWNER_KEY
        assert 'projects and renders' in refused.value.detail

    def test_nothing_is_written(self):
        db = FakeUserDB()
        with pytest.raises(HTTPException):
            asyncio.run(
                UserManager(db).update(
                    UserUpdate(email='alice@elsewhere.example'), account()
                )
            )
        assert db.updates == []

    def test_a_superuser_s_own_address_is_refused_too(self):
        """Until there is a migration that carries their work across."""
        root = account(email='root@example.com', is_superuser=True)
        with pytest.raises(HTTPException):
            update(root, safe=False, email='root@elsewhere.example')

    def test_an_explicit_null_is_refused_rather_than_written(self):
        with pytest.raises(HTTPException) as refused:
            update(account(), email=None)
        assert refused.value.status_code == 422

    def test_sending_the_address_it_already_has_is_not_a_change(self):
        assert update(account(), email='alice@example.com') == [
            {'email': 'alice@example.com'}
        ]

    def test_everything_else_can_still_change(self):
        assert update(account(), first_name='Al') == [{'first_name': 'Al'}]


def register(email):
    db = FakeUserDB()
    form = UserCreate(email=email, password='a long enough password', first_name='X')
    asyncio.run(UserManager(db).create(form, safe=True))
    return db.created


@pytest.fixture
def dev_address(monkeypatch):
    """The suite's own value, whatever the environment says."""
    monkeypatch.setattr(config, 'DEV_USER_EMAIL', DEV)
    return DEV


class TestTheDevAccountsAddressIsReserved:
    """The auth bypass's account owns the dev seeds and its demo.

    It is created by the bypass on first use, so where the bypass had never
    run the address was free, and anyone who registered it owned all of that.
    """

    @pytest.mark.parametrize('email', [DEV, 'DEV@example.com', 'Dev@Example.COM'])
    def test_registering_it_is_refused_in_any_case(self, dev_address, email):
        with pytest.raises(HTTPException) as refused:
            register(email)
        assert refused.value.status_code == 400
        assert refused.value.detail == DEV_ADDRESS_IS_RESERVED

    def test_nothing_is_created(self, dev_address):
        db = FakeUserDB()
        form = UserCreate(email=DEV, password='a long enough password', first_name='X')
        with pytest.raises(HTTPException):
            asyncio.run(UserManager(db).create(form, safe=True))
        assert db.created == []

    def test_a_renamed_dev_account_is_the_one_reserved(self, monkeypatch):
        monkeypatch.setattr(config, 'DEV_USER_EMAIL', 'me@example.org')
        with pytest.raises(HTTPException):
            register('me@example.org')
        assert register(DEV), 'the default address is an ordinary one now'

    def test_any_other_address_registers(self, dev_address):
        [created] = register('developer@example.com')
        assert created['email'] == 'developer@example.com'


class TestTheDevAccountNeverGetsAPassword:
    """It stores `!dev-no-login`, so it cannot be logged into with the bypass off.

    It is a superuser, so that property is worth keeping against every route
    that sets a password, not only registration.
    """

    def dev_account(self):
        return SimpleNamespace(
            id=PydanticObjectId(),
            email=DEV,
            hashed_password='!dev-no-login',
            is_active=True,
            is_superuser=True,
        )

    @pytest.mark.parametrize('address', [DEV, 'DEV@example.com'])
    def test_logging_in_as_it_is_a_wrong_password(self, dev_address, address):
        """Not a 500: the stored value is not a hash passlib can identify."""
        credentials = SimpleNamespace(username=address, password='anything')
        assert asyncio.run(UserManager(FakeUserDB()).authenticate(credentials)) is None

    def test_no_password_validates_for_it(self, dev_address):
        manager = UserManager(FakeUserDB())
        with pytest.raises(exceptions.InvalidPasswordException) as refused:
            asyncio.run(
                manager.validate_password('anything at all', self.dev_account())
            )
        assert refused.value.reason == DEV_ACCOUNT_HAS_NO_PASSWORD

    def test_so_a_superuser_cannot_set_one(self, dev_address):
        """`PATCH /users/{id}` with a password reaches `_update`, then here."""
        db = FakeUserDB()
        with pytest.raises(exceptions.InvalidPasswordException):
            asyncio.run(
                UserManager(db).update(
                    UserUpdate(password='a long enough password'),
                    self.dev_account(),
                    safe=False,
                )
            )
        assert db.updates == []

    def test_no_reset_token_is_issued_for_it(self, dev_address, monkeypatch):
        issued = []

        async def record(self, user, token, request=None):
            issued.append(token)

        monkeypatch.setattr(UserManager, 'on_after_forgot_password', record)
        asyncio.run(UserManager(FakeUserDB()).forgot_password(self.dev_account()))
        assert issued == []

    def test_everyone_else_still_gets_one(self, dev_address, monkeypatch):
        issued = []

        async def record(self, user, token, request=None):
            issued.append(token)

        monkeypatch.setattr(UserManager, 'on_after_forgot_password', record)
        alice = SimpleNamespace(
            id=PydanticObjectId(), email='alice@example.com', is_active=True
        )
        alice.hashed_password = UserManager(FakeUserDB()).password_helper.hash('x')
        asyncio.run(UserManager(FakeUserDB()).forgot_password(alice))
        assert len(issued) == 1
