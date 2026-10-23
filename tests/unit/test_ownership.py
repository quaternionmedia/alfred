"""One ownership rule, for projects and renders alike (contract M5).

Projects kept the rule in `visible_to`; renders kept a copy in `can_access` and
another in their list filter. Three copies of one rule are three places for "I
can see it in the list" and "I can open it" to disagree. They live in
`alfred.core.utils.ownership` now, and both collections go through it.

The routes' behaviour is asserted elsewhere -- projects against a database in
`integration/test_project_ownership.py`, renders in `test_render_ownership.py`.
This pins the rule itself, and that the routes have no rule of their own.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from alfred.core.utils import ownership
from alfred.core.utils.ownership import (
    changes_owner_key,
    may_access,
    owner_filter,
    owner_key,
)

ALICE = SimpleNamespace(email='alice@example.com', is_superuser=False)
BOB = SimpleNamespace(email='bob@example.com', is_superuser=False)
ROOT = SimpleNamespace(email='root@example.com', is_superuser=True)

PEOPLE = {'alice': ALICE, 'bob': BOB, 'root': ROOT}
OWNERS = {'alice': ALICE.email, 'bob': BOB.email, 'nobody': None}


def matches(query, document):
    """Whether a MongoDB equality filter matches a document."""
    return all(document.get(field) == value for field, value in query.items())


class TestTheKey:
    def test_is_the_email_today(self):
        assert owner_key(ALICE) == 'alice@example.com'


class TestTheFilter:
    def test_restricts_a_user_to_their_own(self):
        assert owner_filter(ALICE, 'owner') == {'owner': 'alice@example.com'}

    def test_uses_the_field_the_collection_keeps_its_owner_in(self):
        """`owner` on a project, `username` on a render: the same key."""
        assert owner_filter(ALICE, 'username') == {'username': 'alice@example.com'}

    def test_does_not_restrict_a_superuser(self):
        assert owner_filter(ROOT, 'owner') == {}


class TestOneRecord:
    @pytest.mark.parametrize(
        'owner,person,allowed',
        [
            ('alice', 'alice', True),
            ('alice', 'bob', False),
            ('alice', 'root', True),
            ('nobody', 'alice', False),
            ('nobody', 'root', True),
        ],
    )
    def test_who_may_reach_what(self, owner, person, allowed):
        assert may_access(OWNERS[owner], PEOPLE[person]) is allowed

    def test_an_empty_owner_is_nobody_s(self):
        assert may_access('', ALICE) is False


class TestTheListAndTheRecordAgree:
    @pytest.mark.parametrize('owner', sorted(OWNERS))
    @pytest.mark.parametrize('person', sorted(PEOPLE))
    def test_a_record_is_listed_exactly_when_it_can_be_opened(self, owner, person):
        """The property three copies of the rule could not promise."""
        document = {'owner': OWNERS[owner]}
        query = owner_filter(PEOPLE[person], 'owner')
        assert matches(query, document) == may_access(OWNERS[owner], PEOPLE[person])


class TestTheKeyCannotChangeUnderAnAccount:
    def test_a_new_address_changes_it(self):
        assert changes_owner_key(ALICE, {'email': 'alice@elsewhere.example'})

    def test_the_same_address_does_not(self):
        assert not changes_owner_key(ALICE, {'email': ALICE.email})

    def test_a_change_of_case_does(self):
        """Owner keys compare exactly; `Alice@` would match none of alice's."""
        assert changes_owner_key(ALICE, {'email': 'Alice@example.com'})

    def test_other_fields_do_not(self):
        assert not changes_owner_key(ALICE, {'first_name': 'Al', 'password': 'x'})


class TestBothCollectionsGoThroughIt:
    def test_projects_have_no_rule_of_their_own(self):
        from alfred.core.routes import project

        assert not hasattr(project, 'visible_to')
        assert project.owner_filter is ownership.owner_filter
        assert project.owner_key is ownership.owner_key

    @pytest.mark.parametrize('owner', sorted(OWNERS))
    @pytest.mark.parametrize('person', sorted(PEOPLE))
    def test_a_render_is_reachable_by_the_same_rule(self, owner, person):
        from alfred.core.routes.render import can_access

        render = SimpleNamespace(username=OWNERS[owner])
        assert can_access(render, PEOPLE[person]) == may_access(
            OWNERS[owner], PEOPLE[person]
        )

    @pytest.mark.parametrize(
        'person', ['owner', 'admin'], ids=['a user', 'a superuser']
    )
    def test_the_render_list_is_scoped_by_owner_filter(self, monkeypatch, person):
        from alfred.core.models.render import Render
        from alfred.main import app
        from tests.unit.render_harness import (
            ADMIN,
            OWNER,
            FakeQueue,
            FakeRenderStore,
            as_user,
            offline_documents,
            use_fakes,
        )

        class Recording(FakeRenderStore):
            async def list(self, query, skip, limit):
                self.query = query
                return []

        user = {'owner': OWNER, 'admin': ADMIN}[person]
        offline_documents(monkeypatch, Render)
        store = Recording()
        overrides = as_user(app, user) + use_fakes(app, store, FakeQueue())
        try:
            assert TestClient(app).get('/render').status_code == 200
        finally:
            for dependency in overrides:
                app.dependency_overrides.pop(dependency, None)

        assert store.query == owner_filter(user, 'username')
