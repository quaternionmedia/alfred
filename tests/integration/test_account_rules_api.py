"""The account rules, asked of the running app.

`unit/test_account_rules.py` drives the user manager directly. These go through
fastapi-users' own routes, with real logins, because the rules live on the
manager precisely so that every route reaching it obeys them -- which only the
routes can show.
"""

import pytest

pytestmark = pytest.mark.needs_db


def me(api, account):
    res = api.get('/users/me', headers=account.headers)
    assert res.status_code == 200, res.text
    return res.json()


class TestAnAccountKeepsItsEmail:
    """Contract M5: ownership is keyed by email, so the email cannot change."""

    def test_patching_your_own_is_refused_with_the_reason(self, api, make_account):
        alice = make_account('alice')

        res = api.patch(
            '/users/me', json={'email': 'alice-new@example.com'}, headers=alice.headers
        )

        assert res.status_code == 422, res.text
        assert 'projects and renders' in res.json()['detail']

    def test_the_account_is_left_as_it_was(
        self, api, make_account, make_project, log_in
    ):
        """Same address, same login, and still the owner of its projects."""
        alice = make_account('alice')
        project = make_project(alice)

        api.patch(
            '/users/me', json={'email': 'alice-new@example.com'}, headers=alice.headers
        )

        assert me(api, alice)['email'] == alice.email
        assert log_in(alice.email)
        listed = api.get('/project', headers=alice.headers).json()
        assert project['_id'] in {p['_id'] for p in listed}

    def test_a_superuser_cannot_change_anyone_s(self, api, make_account, users):
        alice = make_account('alice')
        root = make_account('root', superuser=True)
        alice_id = me(api, alice)['id']

        res = api.patch(
            f'/users/{alice_id}',
            json={'email': 'alice-new@example.com'},
            headers=root.headers,
        )

        assert res.status_code == 422, res.text
        assert users.find_one({'email': alice.email}) is not None

    def test_nor_their_own(self, api, make_account):
        root = make_account('root', superuser=True)
        root_id = me(api, root)['id']

        res = api.patch(
            f'/users/{root_id}',
            json={'email': 'root-new@example.com'},
            headers=root.headers,
        )

        assert res.status_code == 422, res.text

    def test_sending_the_same_address_is_fine(self, api, make_account):
        alice = make_account('alice')
        res = api.patch('/users/me', json={'email': alice.email}, headers=alice.headers)
        assert res.status_code == 200, res.text

    def test_the_rest_of_the_account_can_change(self, api, make_account):
        alice = make_account('alice')
        res = api.patch('/users/me', json={'first_name': 'Al'}, headers=alice.headers)
        assert res.status_code == 200, res.text
        assert me(api, alice)['first_name'] == 'Al'

    def test_a_superuser_can_still_edit_an_account(self, api, make_account):
        alice = make_account('alice')
        root = make_account('root', superuser=True)
        alice_id = me(api, alice)['id']

        res = api.patch(
            f'/users/{alice_id}', json={'first_name': 'Alicia'}, headers=root.headers
        )

        assert res.status_code == 200, res.text
        assert me(api, alice)['first_name'] == 'Alicia'
