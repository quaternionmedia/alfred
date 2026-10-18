"""The demo project's find-or-insert, when another request gets there first.

Two presses of "make me a demo" used to make two demos: both requests matched
nothing and both inserted. A partial unique index now refuses the second
insert, and the request that loses answers with the winner's project. Losing
needs two requests interleaved just so, which a real database does only some of
the time -- `integration/test_demo_project_api.py` races it for real -- so this
pins the losing path itself, on a collection where the other request always
wins.
"""

import asyncio
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from alfred.core.models import Project
from alfred.core.models.project import ONE_DEMO_PER_OWNER
from alfred.core.routes import demo

ALICE = SimpleNamespace(email='alice@example.com', is_superuser=False)


class LosesTheRace:
    """A collection on which another request inserts the demo first."""

    def __init__(self, winner_survives=True):
        self.winner = None
        self.winner_survives = winner_survives
        self.asked = []

    async def find_one_and_update(self, query, update, **kwargs):
        # The other request's insert lands between this one's match and its
        # own insert, which the unique index then refuses.
        self.winner = {**update['$setOnInsert'], '_id': ObjectId()}
        raise DuplicateKeyError('E11000 duplicate key error, one_demo_per_owner')

    async def find_one(self, query):
        self.asked.append(query)
        return self.winner if self.winner_survives else None


@pytest.fixture
def collection(monkeypatch):
    def use(fake):
        monkeypatch.setattr(
            Project, 'get_motor_collection', classmethod(lambda c: fake)
        )
        return fake

    return use


def press(user=ALICE):
    return asyncio.run(demo.generateDemoProject(user=user))


class TestLosingTheRace:
    def test_answers_with_the_winner_s_demo(self, collection):
        fake = collection(LosesTheRace())
        answer = press()
        assert answer.id == str(fake.winner['_id'])
        assert answer.clips == 3

    def test_says_it_did_not_create_it(self, collection):
        collection(LosesTheRace())
        assert press().created is False

    def test_looks_for_the_account_s_marked_demo(self, collection):
        fake = collection(LosesTheRace())
        press()
        assert fake.asked == [{'owner': ALICE.email, 'demo': True}]

    def test_a_winner_deleted_meanwhile_is_a_409_not_a_500(self, collection):
        collection(LosesTheRace(winner_survives=False))
        with pytest.raises(HTTPException) as refused:
            press()
        assert refused.value.status_code == 409


class TestTheDocument:
    def test_is_marked_as_the_owner_s_demo(self):
        document = demo._demo_project_document(owner=ALICE.email)
        assert document['demo'] is True
        assert document['owner'] == ALICE.email

    def test_the_index_constrains_marked_demos_only(self):
        """Partial: an account may still have any number of projects named Demo."""
        spec = ONE_DEMO_PER_OWNER.document
        assert spec['key'] == {'owner': 1}
        assert spec['unique'] is True
        assert spec['partialFilterExpression'] == {'demo': True}


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, length):
        return self.rows[:length]


class IndexedCollection:
    """Where the startup hook builds its index."""

    def __init__(self, duplicates=None):
        self.duplicates = duplicates
        self.built = []

    async def create_indexes(self, indexes):
        if self.duplicates:
            raise DuplicateKeyError(
                'Index build failed: E11000 duplicate key error, one_demo_per_owner'
            )
        self.built.extend(indexes)

    def aggregate(self, pipeline):
        return Cursor(self.duplicates or [])


@pytest.fixture
def database(monkeypatch):
    def use(collection):
        monkeypatch.setattr(demo, 'get_db', lambda: {Project.__name__: collection})
        return collection

    return use


class TestTheIndexAtStartup:
    def test_is_built_by_a_startup_hook_of_the_app(self):
        from alfred.main import app

        assert demo.keepOneDemoPerOwner in app.router.on_startup

    def test_builds_it_on_the_projects_collection(self, database):
        projects = database(IndexedCollection())
        asyncio.run(demo.keepOneDemoPerOwner())
        assert projects.built == [ONE_DEMO_PER_OWNER]

    def test_a_build_that_fails_does_not_stop_the_app(self, database, capsys):
        """It would have, declared for beanie: `init_beanie` raises with it.

        A unique index cannot be built over duplicates, and a database can hold
        them if the index went missing under a running server.
        """
        database(IndexedCollection(duplicates=[{'_id': ALICE.email, 'demos': 2}]))

        asyncio.run(demo.keepOneDemoPerOwner())

        out = capsys.readouterr().out
        assert 'NOT ENFORCED' in out
        assert f'{ALICE.email} has 2 demo projects' in out
