"""What the user manager refuses to do to an account, whichever route asks.

fastapi-users' routes are not ours to edit, so the account rules live on
`UserManager`, the one place every route that changes an account goes through.
These drive the manager directly, with an in-memory stand-in for the user
database; `integration/test_account_rules_api.py` asks the same of the running
app.
"""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from alfred.core.models import UserUpdate
from alfred.core.routes.users import EMAIL_IS_THE_OWNER_KEY, UserManager


class FakeUserDB:
    """Records updates instead of writing them."""

    def __init__(self):
        self.updates = []

    async def update(self, user, changes):
        self.updates.append(changes)
        for field, value in changes.items():
            setattr(user, field, value)
        return user

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
