"""One demo project per account, under concurrency and whatever clients send.

`POST /demo/project` is find-or-insert. Two requests for one account could
both find nothing and both insert, so pressing the button from two places at
once made two demos. The demo is now the project marked `demo`, a partial
unique index on its owner refuses a second, and the request that loses the
race answers with the winner's project.

`integration/test_project_ownership.py` covers whose demo is whose; these cover
how many there are.
"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from pymongo.errors import DuplicateKeyError

pytestmark = pytest.mark.needs_db

PRESSES = 12
ROUNDS = 5


def ask(api, account):
    res = api.post('/demo/project', headers=account.headers)
    assert res.status_code == 200, res.text
    return res.json()


def marked(projects, account):
    return projects.count_documents({'owner': account.email, 'demo': True})


class AllAtOnce:
    """The projects collection, holding every upsert until all have arrived.

    Requests sent together still reach the database one after another, each a
    little behind the last, and a later one usually finds the demo an earlier
    one made: without this, the race seldom happens even with no index to stop
    it. Released together, the upserts reach MongoDB in the same moment --
    and, with the index dropped, they did make two demos.
    """

    def __init__(self, collection, expected):
        self.collection = collection
        self.expected = expected
        self.arrived = 0
        self.everyone = None

    async def find_one_and_update(self, *args, **kwargs):
        if self.everyone is None:
            self.everyone = asyncio.Event()
        self.arrived += 1
        if self.arrived == self.expected:
            self.everyone.set()
        await asyncio.wait_for(self.everyone.wait(), timeout=10)
        return await self.collection.find_one_and_update(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.collection, name)


def hold_upserts(monkeypatch, collection):
    """Route the demo route's collection through `AllAtOnce`."""
    from alfred.core.models import Project

    gate = AllAtOnce(collection, PRESSES)
    monkeypatch.setattr(Project, 'get_motor_collection', classmethod(lambda c: gate))


def press_together(api, account):
    """PRESSES requests for one account, sent from as many threads at once."""
    start = threading.Barrier(PRESSES)

    def press(_):
        start.wait()
        return api.post('/demo/project', headers=account.headers)

    with ThreadPoolExecutor(PRESSES) as pool:
        return list(pool.map(press, range(PRESSES)))


class TestSimultaneousRequests:
    def test_make_one_demo_between_them(self, api, make_account, projects, monkeypatch):
        """Every round: a new account, and every request released at once."""
        from alfred.core.models import Project

        real = Project.get_motor_collection()
        for _ in range(ROUNDS):
            alice = make_account('alice')
            hold_upserts(monkeypatch, real)

            answers = press_together(api, alice)

            assert [a.status_code for a in answers] == [200] * PRESSES, [
                a.text for a in answers if a.status_code != 200
            ]
            bodies = [a.json() for a in answers]
            assert len({b['id'] for b in bodies}) == 1, 'more than one demo was made'
            assert sum(b['created'] for b in bodies) == 1
            assert marked(projects, alice) == 1

    def test_the_database_refuses_a_second_demo(self, api, make_account, projects):
        """The guarantee is the index's, not the route's timing."""
        alice = make_account('alice')
        ask(api, alice)

        with pytest.raises(DuplicateKeyError):
            projects.insert_one({'owner': alice.email, 'demo': True, 'logic': {}})

    def test_other_accounts_are_not_constrained_by_it(
        self, api, make_account, projects
    ):
        alice, bob = make_account('alice'), make_account('bob')
        assert ask(api, alice)['id'] != ask(api, bob)['id']


class TestOnlyTheDemoIsConstrained:
    def test_an_account_may_have_several_projects_called_demo(
        self, api, make_account, make_project
    ):
        """Partial: the index counts marked demos, not names."""
        alice = make_account('alice')
        first = make_project(alice, name='Demo')
        second = make_project(alice, name='Demo')
        assert first['_id'] != second['_id']

    def test_a_client_cannot_mark_a_project_as_its_demo(
        self, api, make_account, make_project, projects
    ):
        """Otherwise a second mark would collide with the real one on the index."""
        alice = make_account('alice')
        project = make_project(alice, name='Mine', demo=True)

        assert project['demo'] is None
        assert ask(api, alice)['id'] != project['_id']
        assert marked(projects, alice) == 1

    def test_an_update_neither_marks_nor_unmarks(self, api, make_account, make_project):
        alice = make_account('alice')
        mine = make_project(alice, name='Mine')
        demo = ask(api, alice)

        for project_id, sent in ((mine['_id'], True), (demo['id'], False)):
            res = api.put(
                f'/project/{project_id}',
                json={'name': 'renamed', 'logic': {}, 'demo': sent},
                headers=alice.headers,
            )
            assert res.status_code == 200, res.text

        stored = {
            p['_id']: p['demo']
            for p in api.get('/project', headers=alice.headers).json()
        }
        assert stored[mine['_id']] is None
        assert stored[demo['id']] is True


class TestWhichProjectIsTheDemo:
    def test_a_renamed_demo_is_still_the_account_s_demo(self, api, make_account):
        alice = make_account('alice')
        demo = ask(api, alice)
        api.put(
            f'/project/{demo["id"]}',
            json={'name': 'My first video', 'logic': {}},
            headers=alice.headers,
        )

        again = ask(api, alice)

        assert again['id'] == demo['id']
        assert again['name'] == 'My first video'
        assert again['created'] is False

    def test_a_deleted_demo_can_be_made_again(self, api, make_account):
        alice = make_account('alice')
        demo = ask(api, alice)
        api.delete(f'/project/{demo["id"]}', headers=alice.headers)

        again = ask(api, alice)

        assert again['created'] is True
        assert again['id'] != demo['id']

    def test_a_demo_from_before_the_mark_is_kept(self, api, make_account, projects):
        """Named Demo, unmarked: what the generator made until now."""
        alice = make_account('alice')
        legacy = projects.insert_one(
            {'name': 'Demo', 'owner': alice.email, 'logic': {}, 'fields': []}
        ).inserted_id

        answer = ask(api, alice)

        assert answer['id'] == str(legacy)
        assert answer['created'] is False
        assert projects.count_documents({'owner': alice.email}) == 1

    def test_the_marked_demo_wins_over_a_project_merely_called_demo(
        self, api, make_account, make_project
    ):
        alice = make_account('alice')
        demo = ask(api, alice)
        api.put(
            f'/project/{demo["id"]}',
            json={'name': 'Renamed demo', 'logic': {}},
            headers=alice.headers,
        )
        make_project(alice, name='Demo')

        assert ask(api, alice)['id'] == demo['id']


def test_the_index_is_built_at_startup(api, projects):
    """Declared on the model, so `init_beanie` builds it with the app."""
    index = projects.index_information().get('one_demo_per_owner')
    assert index is not None, 'the index was not built'
    assert index['unique'] is True
    assert index['partialFilterExpression'] == {'demo': True}
