"""Every project route, the rule they share, and who owns the seeded projects.

The behaviour -- your projects and nobody else's, superusers see all, legacy
projects are superuser-only -- is asserted against a database in
`integration/test_project_ownership.py`. What is pinned here needs no
database: the complete list of project routes, so one added later has to be
looked at rather than slipping past ownership because the crud router made it
easy; the visibility rule itself; and the seed owner setting.
"""

import inspect
from types import SimpleNamespace

import pytest
from fastapi import params

from alfred.config import DEFAULT_DEV_USER_EMAIL, resolve_seed_owner
from alfred.core.models import Project
from alfred.core.routes.project import visible_to
from alfred.core.routes.users import current_active_user

# The whole surface. A route added here is a decision about who may use it;
# add it to the integration tests' SINGLE_PROJECT_ROUTES (or equivalent) in
# the same change.
INVENTORY = {
    ('GET', '/project'),
    ('POST', '/project'),
    ('GET', '/project/{item_id}'),
    ('PUT', '/project/{item_id}'),
    ('DELETE', '/project/{item_id}'),
    ('PUT', '/project/{item_id}/settings'),
    ('PUT', '/project/{item_id}/timeline'),
}


def project_routes():
    from alfred.main import app

    return [
        route
        for route in app.routes
        if getattr(route, 'path', '').startswith('/project')
        and hasattr(route, 'methods')
    ]


def mounted():
    return {
        (method, route.path) for route in project_routes() for method in route.methods
    }


class TestTheRoutes:
    def test_the_inventory_is_exactly_what_is_mounted(self):
        assert mounted() == INVENTORY

    def test_there_is_no_bulk_delete(self):
        """`DELETE /project` emptied the collection, from any account."""
        assert ('DELETE', '/project') not in mounted()

    @pytest.mark.parametrize('method,path', sorted(INVENTORY))
    def test_each_handler_is_handed_the_caller(self, method, path):
        """Scoping needs the user inside the handler, not just at the door.

        The router is mounted behind `current_active_user`, which keeps
        anonymous callers out but tells the handler nothing -- every route
        passed that gate before and still served every project to everyone.
        So this looks at the handler's own parameters.
        """
        [route] = [
            r for r in project_routes() if r.path == path and method in r.methods
        ]
        defaults = [
            p.default for p in inspect.signature(route.endpoint).parameters.values()
        ]
        assert any(
            isinstance(d, params.Depends) and d.dependency is current_active_user
            for d in defaults
        ), f'{method} {path} does not receive the calling user'


class TestTheRule:
    def test_a_superuser_is_not_filtered(self):
        root = SimpleNamespace(is_superuser=True, email='root@example.com')
        assert visible_to(root) == {}

    def test_anyone_else_is_filtered_to_their_own(self):
        alice = SimpleNamespace(is_superuser=False, email='alice@example.com')
        assert visible_to(alice) == {'owner': 'alice@example.com'}

    def test_ownership_is_optional_on_the_model(self):
        """Projects stored before ownership must still load.

        Required, every one of them would fail validation on read -- for
        superusers too, who are the only ones meant to see them.
        """
        assert 'owner' in Project.__fields__
        assert not Project.__fields__['owner'].required


class TestTheSeedOwner:
    def test_development_seeds_belong_to_the_dev_user(self):
        """So ALFRED_DEV_SKIP_AUTH opens onto the projects it always did."""
        assert resolve_seed_owner({}) == DEFAULT_DEV_USER_EMAIL

    def test_a_renamed_dev_user_is_followed(self):
        env = {'ALFRED_DEV_USER_EMAIL': 'me@example.org'}
        assert resolve_seed_owner(env) == 'me@example.org'

    def test_production_seeds_have_no_owner(self):
        """Superuser-only, rather than given to a development default."""
        assert resolve_seed_owner({'ALFRED_PRODUCTION': 'true'}) is None

    @pytest.mark.parametrize('production', [{}, {'ALFRED_PRODUCTION': 'true'}])
    def test_an_explicit_owner_wins(self, production):
        env = {**production, 'ALFRED_SEED_OWNER': ' admin@example.com '}
        assert resolve_seed_owner(env) == 'admin@example.com'

    def test_empty_means_unset(self):
        assert resolve_seed_owner({'ALFRED_SEED_OWNER': ''}) == DEFAULT_DEV_USER_EMAIL


class TestTheSeedPayload:
    def test_owned_copies_carry_the_owner(self):
        from alfred.seed import owned_by

        assert {p['owner'] for p in owned_by('a@example.com')} == {'a@example.com'}

    def test_no_owner_leaves_the_field_out(self):
        """How a project with no owner is stored: absent, not a string."""
        from alfred.seed import owned_by

        assert all('owner' not in p for p in owned_by(None))

    def test_the_module_level_seed_is_not_touched(self):
        """`insert_many` writes `_id` into what it is given; copies absorb it."""
        from alfred.seed import owned_by, seed

        for copy in owned_by('a@example.com'):
            copy['_id'] = 'written by the driver'
        assert all('_id' not in p and 'owner' not in p for p in seed)
