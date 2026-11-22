"""Cues against a real database: written, read back, kept by a whole-project
update, and scoped to their owner.
"""

import pytest

pytestmark = pytest.mark.needs_db


@pytest.fixture
def alice(make_account):
    return make_account('alice')


def cues_of(api, account, project_id):
    res = api.get(f'/project/{project_id}/cues', headers=account.headers)
    assert res.status_code == 200, res.text
    return res.json()['cues']


class TestTheRoundTrip:
    def test_written_read_back_and_kept_by_a_project_update(
        self, api, alice, make_project
    ):
        project = make_project(alice)
        sent = [
            {
                'start': 12.8,
                'end': 30.1,
                'label': 'Excerpt 2',
                'kind': 'excerpt',
                'state': 'waiting',
            },
            {'start': 0, 'end': 12.8, 'label': 'Welcome back', 'kind': 'chapter'},
        ]
        res = api.put(
            f'/project/{project["_id"]}/cues',
            json={'cues': sent, 'source': 'alfred-excerpts'},
            headers=alice.headers,
        )
        assert res.status_code == 200, res.text
        labels = [c['label'] for c in res.json()['cues']]
        assert labels == ['Welcome back', 'Excerpt 2']
        assert all(c['source'] == 'alfred-excerpts' for c in res.json()['cues'])
        assert cues_of(api, alice, project['_id']) == res.json()['cues']

        # The whole-project update keeps them, as it keeps the captions.
        res = api.put(
            f'/project/{project["_id"]}',
            json={'name': 'renamed', 'logic': {}},
            headers=alice.headers,
        )
        assert res.status_code == 200, res.text
        assert [c['label'] for c in cues_of(api, alice, project['_id'])] == labels
        assert res.json()['name'] == 'renamed'

    def test_a_project_is_created_without_cues_whatever_was_sent(
        self, api, alice, make_project
    ):
        project = make_project(alice, cues=[{'start': 1, 'label': 'sent along'}])
        assert cues_of(api, alice, project['_id']) == []

    def test_each_source_replaces_its_own(self, api, alice, make_project):
        project = make_project(alice)
        path = f'/project/{project["_id"]}/cues'
        api.put(
            path,
            json={'cues': [{'start': 5, 'label': 'flow'}], 'source': 'flow'},
            headers=alice.headers,
        )
        api.put(
            path,
            json={'cues': [{'start': 9, 'label': 'mine'}], 'source': 'editor'},
            headers=alice.headers,
        )
        res = api.put(
            path,
            json={'cues': [{'start': 6, 'label': 'flow again'}], 'source': 'flow'},
            headers=alice.headers,
        )
        assert [(c['label'], c['source']) for c in res.json()['cues']] == [
            ('flow again', 'flow'),
            ('mine', 'editor'),
        ]


class TestScope:
    def test_another_account_sees_and_writes_nothing(
        self, api, alice, make_account, make_project
    ):
        bob = make_account('bob')
        project = make_project(alice)
        api.put(
            f'/project/{project["_id"]}/cues',
            json={'cues': [{'start': 1, 'label': 'x'}]},
            headers=alice.headers,
        )
        assert (
            api.get(f'/project/{project["_id"]}/cues', headers=bob.headers).status_code
            == 404
        )
        res = api.put(
            f'/project/{project["_id"]}/cues', json={'cues': []}, headers=bob.headers
        )
        assert res.status_code == 404
        assert len(cues_of(api, alice, project['_id'])) == 1
