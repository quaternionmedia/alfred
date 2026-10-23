"""A saved timeline round-trips as the editor sent it (contract M4).

`PUT /project/{id}/timeline` stored each clip through otto's model, so a clip
saved without fades came back from `GET /project/{id}` with `fadeIn: 1` and
`fadeOut: 1` -- fades nobody chose, which rendered. A saved `project.edl` now
means exactly what was sent: absent stays absent, an explicit 0 stays 0, a
`start` stays where it was put. Every route that writes a project stores its
EDL that way, and every route that answers with one serves it as stored.
"""

import pytest
from bson import ObjectId

pytestmark = pytest.mark.needs_db

PLAIN = {'type': 'template', 'name': 'makeColor', 'duration': 2.0, 'start': 0.0}
FADED = {
    'type': 'template',
    'name': 'makeColor',
    'duration': 3.0,
    'start': 2.0,
    'fadeIn': 0,
    'fadeOut': 0.5,
    'data': {'color': '#f2aa4c'},
}
TIMELINE = {'clips': [PLAIN, FADED], 'duration': 5.0}


def save_timeline(api, account, project_id, edl):
    res = api.put(f'/project/{project_id}/timeline', json=edl, headers=account.headers)
    assert res.status_code == 200, res.text
    return res.json()


def get(api, account, project_id):
    res = api.get(f'/project/{project_id}', headers=account.headers)
    assert res.status_code == 200, res.text
    return res.json()


def stored(projects, project_id):
    return projects.find_one({'_id': ObjectId(project_id)})


@pytest.fixture
def alice(make_account):
    return make_account('alice')


@pytest.fixture
def project(alice, make_project):
    return make_project(alice)


class TestTheRoundTrip:
    def test_what_was_sent_is_what_comes_back(self, api, alice, project):
        save_timeline(api, alice, project['_id'], TIMELINE)
        assert get(api, alice, project['_id'])['edl'] == TIMELINE

    def test_an_absent_fade_stays_absent(self, api, alice, project, projects):
        save_timeline(api, alice, project['_id'], TIMELINE)

        for clip in (
            stored(projects, project['_id'])['edl']['clips'][0],
            get(api, alice, project['_id'])['edl']['clips'][0],
        ):
            assert 'fadeIn' not in clip and 'fadeOut' not in clip, clip

    def test_an_explicit_zero_stays_zero(self, api, alice, project, projects):
        save_timeline(api, alice, project['_id'], TIMELINE)

        for clip in (
            stored(projects, project['_id'])['edl']['clips'][1],
            get(api, alice, project['_id'])['edl']['clips'][1],
        ):
            assert clip['fadeIn'] == 0
            assert clip['fadeOut'] == 0.5

    def test_each_start_stays_where_it_was_put(self, api, alice, project):
        save_timeline(api, alice, project['_id'], TIMELINE)
        starts = [c['start'] for c in get(api, alice, project['_id'])['edl']['clips']]
        assert starts == [0.0, 2.0]

    def test_nothing_else_is_written_in(self, api, alice, project, projects):
        """No nulls, no `relative`, no template `method`: only what was sent."""
        save_timeline(api, alice, project['_id'], TIMELINE)
        assert stored(projects, project['_id'])['edl'] == TIMELINE

    def test_the_editor_s_view_index_is_not_stored(self, api, alice, project, projects):
        sent = {'clips': [dict(PLAIN, i=0), dict(FADED, i=1)], 'duration': 5.0}
        save_timeline(api, alice, project['_id'], sent)
        assert stored(projects, project['_id'])['edl'] == TIMELINE

    def test_the_answer_to_a_save_is_the_project_as_stored(self, api, alice, project):
        """Without a `duration` sent, the answer must not invent `null` for it."""
        sent = {'clips': [PLAIN]}
        answer = save_timeline(api, alice, project['_id'], sent)
        assert answer['edl'] == sent
        assert answer == get(api, alice, project['_id'])

    def test_each_clip_is_still_validated(self, api, alice, project):
        bad = {'clips': [{'type': 'template', 'duration': 'a while'}]}
        res = api.put(
            f'/project/{project["_id"]}/timeline', json=bad, headers=alice.headers
        )
        assert res.status_code == 422


class TestEveryWayInStoresItAsSent:
    def test_creating_a_project_with_a_timeline(self, alice, make_project, projects):
        project = make_project(alice, edl=TIMELINE)
        assert project['edl'] == TIMELINE
        assert stored(projects, project['_id'])['edl'] == TIMELINE

    def test_replacing_a_project(self, api, alice, project, projects):
        res = api.put(
            f'/project/{project["_id"]}',
            json={'name': 'replaced', 'logic': {}, 'edl': TIMELINE},
            headers=alice.headers,
        )
        assert res.status_code == 200, res.text
        assert res.json()['edl'] == TIMELINE
        assert stored(projects, project['_id'])['edl'] == TIMELINE


class TestATimelineSavedBefore:
    """Clips stored with otto's defaults written in are left as they are."""

    def test_keeps_its_written_in_fades(self, api, alice, projects):
        legacy = dict(PLAIN, fadeIn=1, fadeOut=1, relative=True, inpoint=None)
        inserted = projects.insert_one(
            {
                'name': 'old',
                'logic': {},
                'owner': alice.email,
                'edl': {'clips': [legacy]},
            }
        ).inserted_id

        clip = get(api, alice, str(inserted))['edl']['clips'][0]

        assert clip['fadeIn'] == 1 and clip['fadeOut'] == 1
        assert clip['inpoint'] is None


@pytest.fixture
def interleaved(monkeypatch, projects):
    """Another write landing between a route's read and its own write.

    Each project route loads the project first (`_owned`) and writes after.
    This lets a test put a concurrent write exactly in that gap.
    """
    from alfred.main import projects as project_api

    def between(write):
        real = project_api._owned

        async def owned_then_somebody_writes(item_id, user):
            loaded = await real(item_id, user)
            projects.update_one({'_id': ObjectId(item_id)}, {'$set': write})
            return loaded

        monkeypatch.setattr(project_api, '_owned', owned_then_somebody_writes)

    return between


class TestEachSaveWritesOnlyItsOwnFields:
    """Both routes loaded the project and saved the whole document back."""

    def test_a_settings_save_keeps_a_timeline_saved_meanwhile(
        self, api, alice, project, projects, interleaved
    ):
        interleaved({'edl': TIMELINE})

        res = api.put(
            f'/project/{project["_id"]}/settings',
            json={'destination': 'local'},
            headers=alice.headers,
        )

        assert res.status_code == 200, res.text
        after = stored(projects, project['_id'])
        assert after['edl'] == TIMELINE
        assert after['destination'] == 'local'

    def test_a_timeline_save_keeps_settings_saved_meanwhile(
        self, api, alice, project, projects, interleaved
    ):
        interleaved({'destination': 'local'})

        save_timeline(api, alice, project['_id'], TIMELINE)

        after = stored(projects, project['_id'])
        assert after['destination'] == 'local'
        assert after['edl'] == TIMELINE
