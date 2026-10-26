"""A project belongs to whoever created it.

Any authenticated account could list, read, overwrite and delete every project
on the server, and `DELETE /project` emptied the collection for everybody. Now
a project carries an `owner` -- the creator's email, set by the server -- and
every project route is scoped to it:

- a non-superuser sees and acts on their own projects only;
- a superuser sees and acts on all of them;
- a project stored before ownership existed has no owner and is
  superuser-only;
- somebody else's project answers 404, the same as one that does not exist.

Each test uses accounts of its own, so they hold under xdist and in any order.
"""

import pytest

pytestmark = pytest.mark.needs_db

TIMELINE = {
    'clips': [
        {
            'type': 'template',
            'name': 'makeColor',
            'duration': 2.0,
            'start': 0.0,
            'data': {'color': '#f2aa4c'},
        }
    ],
    'duration': 2.0,
}

CUE = '1\n00:00:00,000 --> 00:00:01,000\nx\n'

# Every route that addresses one project, with a body it would accept. The
# inventory in unit/test_project_route_inventory.py fails if a route is added
# without being listed somewhere like here.
SINGLE_PROJECT_ROUTES = [
    ('GET', '/project/{id}', None),
    ('PUT', '/project/{id}', {'name': 'taken over', 'logic': {}}),
    ('PUT', '/project/{id}/settings', {'destination': 'local'}),
    ('PUT', '/project/{id}/timeline', TIMELINE),
    ('GET', '/project/{id}/captions', None),
    (
        'PUT',
        '/project/{id}/captions',
        {'captions': [{'start': 0, 'end': 1, 'text': 'x'}]},
    ),
    ('GET', '/project/{id}/captions/words', None),
    ('POST', '/project/{id}/captions/import', {'format': 'srt', 'text': CUE}),
    # POST /project/{id}/captions/transcribe answers 202 or 503 for its owner,
    # not 200; integration/test_captions_api.py holds it to the same 404s.
    ('DELETE', '/project/{id}', None),
]
ROUTE_IDS = [f'{method} {path}' for method, path, _ in SINGLE_PROJECT_ROUTES]


def call(api, account, method, path, project_id, body):
    return api.request(
        method,
        path.format(id=project_id),
        json=body,
        headers=account.headers,
    )


def listed(api, account):
    res = api.get('/project', headers=account.headers)
    assert res.status_code == 200, res.text
    return res.json()


def ids(projects):
    return {p['_id'] for p in projects}


class TestCreatingAProject:
    def test_it_belongs_to_its_creator(self, make_account, make_project):
        alice = make_account('alice')
        project = make_project(alice)
        assert project['owner'] == alice.email

    def test_a_claimed_owner_is_replaced(self, api, make_account, make_project):
        """The owner comes from the session, never from the body."""
        alice, bob = make_account('alice'), make_account('bob')
        project = make_project(alice, owner=bob.email)

        assert project['owner'] == alice.email
        assert project['_id'] not in ids(listed(api, bob))

    def test_a_client_cannot_choose_the_id(self, make_account, make_project):
        """Otherwise a create could collide with a project the caller cannot see.

        The duplicate-key error would confirm the id exists -- the one thing
        the 404s elsewhere are careful not to say.
        """
        alice, bob = make_account('alice'), make_account('bob')
        bobs = make_project(bob)

        created = make_project(alice, _id=bobs['_id'])

        assert created['_id'] != bobs['_id']
        assert created['owner'] == alice.email


class TestListing:
    def test_a_user_lists_their_own_projects_and_no_others(
        self, api, make_account, make_project
    ):
        alice, bob = make_account('alice'), make_account('bob')
        alices = {make_project(alice)['_id'], make_project(alice)['_id']}
        make_project(bob)

        mine = listed(api, alice)

        assert ids(mine) == alices
        assert {p['owner'] for p in mine} == {alice.email}

    def test_a_new_account_sees_an_empty_list(self, api, make_account, make_project):
        """Not the seeded projects, not anybody else's: nothing yet."""
        make_project(make_account('someone'))
        assert listed(api, make_account('newcomer')) == []

    def test_legacy_projects_are_not_listed_for_users(
        self, api, make_account, legacy_project
    ):
        assert legacy_project['_id'] not in ids(listed(api, make_account('alice')))

    def test_a_superuser_lists_everything(
        self, api, make_account, make_project, legacy_project
    ):
        alice, bob = make_account('alice'), make_account('bob')
        everyone = {make_project(alice)['_id'], make_project(bob)['_id']}
        root = make_account('root', superuser=True)

        seen = ids(listed(api, root))

        assert everyone <= seen
        assert legacy_project['_id'] in seen


class TestSomebodyElsesProject:
    @pytest.mark.parametrize('method,path,body', SINGLE_PROJECT_ROUTES, ids=ROUTE_IDS)
    def test_answers_404(self, api, make_account, make_project, method, path, body):
        alice, bob = make_account('alice'), make_account('bob')
        project = make_project(alice)

        res = call(api, bob, method, path, project['_id'], body)

        assert res.status_code == 404, res.text

    @pytest.mark.parametrize('method,path,body', SINGLE_PROJECT_ROUTES, ids=ROUTE_IDS)
    def test_is_indistinguishable_from_one_that_does_not_exist(
        self, api, make_account, make_project, method, path, body
    ):
        """404 rather than 403, and the same 404.

        A different status or detail for "exists, not yours" would let anyone
        probe which ids are real.
        """
        alice, bob = make_account('alice'), make_account('bob')
        project = make_project(alice)

        theirs = call(api, bob, method, path, project['_id'], body)
        nobodys = call(api, bob, method, path, 'deadbeefdeadbeefdeadbeef', body)

        assert (theirs.status_code, theirs.json()) == (
            nobodys.status_code,
            nobodys.json(),
        )

    @pytest.mark.parametrize('method,path,body', SINGLE_PROJECT_ROUTES, ids=ROUTE_IDS)
    def test_is_left_exactly_as_it_was(
        self, api, make_account, make_project, method, path, body
    ):
        alice, bob = make_account('alice'), make_account('bob')
        project = make_project(alice, edl=TIMELINE, name='alice keeps this')

        call(api, bob, method, path, project['_id'], body)

        after = api.get(f'/project/{project["_id"]}', headers=alice.headers)
        assert after.status_code == 200, 'the project is gone'
        assert after.json() == project


class TestYourOwnProject:
    @pytest.mark.parametrize('method,path,body', SINGLE_PROJECT_ROUTES, ids=ROUTE_IDS)
    def test_the_owner_can(self, api, make_account, make_project, method, path, body):
        alice = make_account('alice')
        project = make_project(alice)

        res = call(api, alice, method, path, project['_id'], body)

        assert res.status_code == 200, res.text

    def test_deleting_returns_the_project_and_removes_it(
        self, api, make_account, make_project
    ):
        """The crud router returned the driver's DeleteResult here.

        That is not a Project, so response validation failed and every
        successful delete answered 500 -- after deleting.
        """
        alice = make_account('alice')
        project = make_project(alice)

        res = api.delete(f'/project/{project["_id"]}', headers=alice.headers)

        assert res.status_code == 200, res.text
        assert res.json()['_id'] == project['_id']
        gone = api.get(f'/project/{project["_id"]}', headers=alice.headers)
        assert gone.status_code == 404

    def test_a_malformed_id_is_still_422(self, api, make_account):
        """Scoping the lookup must not turn "not an id" into "not found"."""
        alice = make_account('alice')
        for method, path, body in SINGLE_PROJECT_ROUTES:
            res = call(api, alice, method, path, 'undefined', body)
            assert res.status_code == 422, f'{method} {path}: {res.text}'


class TestOwnershipCannotBeTransferred:
    def test_an_update_naming_another_owner_keeps_the_real_one(
        self, api, make_account, make_project
    ):
        alice, bob = make_account('alice'), make_account('bob')
        project = make_project(alice)

        res = api.put(
            f'/project/{project["_id"]}',
            json={'name': 'mine now', 'logic': {}, 'owner': bob.email},
            headers=alice.headers,
        )

        assert res.status_code == 200, res.text
        assert res.json()['owner'] == alice.email
        assert project['_id'] not in ids(listed(api, bob))

    def test_an_update_that_omits_the_owner_does_not_orphan_the_project(
        self, api, make_account, make_project
    ):
        """The update writes every field of its body, present or not.

        A body without `owner` -- which is every body the SPA has ever sent --
        would otherwise write null, and the project would drop out of its own
        owner's list into the superuser-only pile.
        """
        alice = make_account('alice')
        project = make_project(alice)

        api.put(
            f'/project/{project["_id"]}',
            json={'name': 'renamed', 'logic': {}},
            headers=alice.headers,
        )

        assert project['_id'] in ids(listed(api, alice))

    def test_a_superuser_edit_leaves_the_owner_alone(
        self, api, make_account, make_project
    ):
        alice = make_account('alice')
        root = make_account('root', superuser=True)
        project = make_project(alice)

        res = api.put(
            f'/project/{project["_id"]}',
            json={'name': 'tidied', 'logic': {}},
            headers=root.headers,
        )

        assert res.json()['owner'] == alice.email


class TestSuperusers:
    @pytest.mark.parametrize('method,path,body', SINGLE_PROJECT_ROUTES, ids=ROUTE_IDS)
    def test_can_act_on_anybodys_project(
        self, api, make_account, make_project, method, path, body
    ):
        alice = make_account('alice')
        root = make_account('root', superuser=True)
        project = make_project(alice)

        res = call(api, root, method, path, project['_id'], body)

        assert res.status_code == 200, res.text


class TestLegacyProjects:
    """Stored before ownership: nobody can be shown to own them."""

    @pytest.mark.parametrize('method,path,body', SINGLE_PROJECT_ROUTES, ids=ROUTE_IDS)
    def test_are_404_for_users(
        self, api, make_account, legacy_project, method, path, body
    ):
        alice = make_account('alice')
        res = call(api, alice, method, path, legacy_project['_id'], body)
        assert res.status_code == 404, res.text

    @pytest.mark.parametrize('method,path,body', SINGLE_PROJECT_ROUTES, ids=ROUTE_IDS)
    def test_are_open_to_superusers(
        self, api, make_account, legacy_project, method, path, body
    ):
        root = make_account('root', superuser=True)
        res = call(api, root, method, path, legacy_project['_id'], body)
        assert res.status_code == 200, res.text

    def test_a_superuser_edit_does_not_assign_an_owner(
        self, api, make_account, legacy_project, projects
    ):
        """Editing is not claiming. It stays superuser-only."""
        from bson import ObjectId

        root = make_account('root', superuser=True)
        api.put(
            f'/project/{legacy_project["_id"]}/settings',
            json={'destination': 'local'},
            headers=root.headers,
        )

        stored = projects.find_one({'_id': ObjectId(legacy_project['_id'])})
        assert stored.get('owner') is None


class TestNoBulkDelete:
    @pytest.mark.parametrize('superuser', [False, True], ids=['user', 'superuser'])
    def test_delete_on_the_collection_is_not_a_route(
        self, api, make_account, make_project, superuser
    ):
        """`DELETE /project` deleted every project, from any account.

        Gone rather than scoped: 405, and nothing is removed.
        """
        alice = make_account('alice')
        project = make_project(alice)
        caller = make_account('caller', superuser=superuser)

        res = api.delete('/project', headers=caller.headers)

        assert res.status_code == 405
        still = api.get(f'/project/{project["_id"]}', headers=alice.headers)
        assert still.status_code == 200


class TestTheDemoProject:
    def test_it_belongs_to_whoever_asked(self, api, make_account):
        alice, bob = make_account('alice'), make_account('bob')

        demo = api.post('/demo/project', headers=alice.headers).json()

        mine = api.get(f'/project/{demo["id"]}', headers=alice.headers)
        assert mine.status_code == 200
        assert mine.json()['owner'] == alice.email
        theirs = api.get(f'/project/{demo["id"]}', headers=bob.headers)
        assert theirs.status_code == 404

    def test_each_account_gets_its_own(self, api, make_account):
        """It was idempotent by name across the server.

        Under ownership that would have handed the second account to ask a
        demo it could not open.
        """
        alice, bob = make_account('alice'), make_account('bob')

        alices = api.post('/demo/project', headers=alice.headers).json()
        bobs = api.post('/demo/project', headers=bob.headers).json()

        assert alices['id'] != bobs['id']
        assert alices['created'] and bobs['created']

    def test_asking_twice_returns_the_same_one(self, api, make_account):
        alice = make_account('alice')

        first = api.post('/demo/project', headers=alice.headers).json()
        second = api.post('/demo/project', headers=alice.headers).json()

        assert second['id'] == first['id']
        assert second['created'] is False
        demos = [p for p in listed(api, alice) if p['name'] == first['name']]
        assert len(demos) == 1


class TestSeededProjects:
    """Seeded into the empty database when the app started."""

    def test_they_belong_to_the_seed_owner(self, api, projects):
        from alfred.config import SEED_OWNER
        from alfred.seed import seed

        names = {p['name'] for p in seed}
        stored = list(projects.find({'name': {'$in': sorted(names)}}))

        assert stored, 'nothing was seeded'
        assert {p.get('owner') for p in stored} == {SEED_OWNER}

    def test_users_do_not_see_them(self, api, make_account, projects):
        from alfred.seed import seed

        names = {p['name'] for p in seed}
        assert not names & {p['name'] for p in listed(api, make_account('alice'))}

    def test_superusers_do(self, api, make_account):
        from alfred.seed import seed

        root = make_account('root', superuser=True)
        names = {p['name'] for p in seed}
        assert names <= {p['name'] for p in listed(api, root)}
