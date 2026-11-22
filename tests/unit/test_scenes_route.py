"""`GET /media/{name}/scenes` and `GET /project/{id}/scenes`, without a database.

otto's measure is stood in for at `utils.measures.scene_changes`; otto's own
suite covers the measure. Pinned here: what is kept and asked, the mapping
onto a timeline with each clip's edges, and each refusal by code.
"""

import copy
import os

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from otto.exceptions import FFmpegException

from alfred import config
from alfred.core.routes import sound as sound_routes
from alfred.core.utils import measures
from alfred.core.utils.probe import ProbeCache
from alfred.main import app
from tests.unit.render_harness import OWNER, STRANGER, anonymous, as_user

MEASURED = {
    'talk.mp4': {'threshold': 0.4, 'seconds': [0.5, 1.5, 2.75, 9.0]},
    'cut.mp4': {'threshold': 0.4, 'seconds': [1.0]},
}


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'VIDEO_DIR', str(tmp_path))
    for name in ('talk.mp4', 'cut.mp4'):
        (tmp_path / name).write_bytes(b'not really a video')
    (tmp_path / 'song.mp3').write_bytes(b'not really audio')
    (tmp_path / 'still.png').write_bytes(b'not really a picture')
    return tmp_path


@pytest.fixture
def measured(monkeypatch, library):
    """otto, finding the cuts; returns the files it was asked about."""
    asked = []

    def scene_changes(path):
        asked.append(os.path.basename(path))
        return copy.deepcopy(MEASURED[os.path.basename(path)])

    monkeypatch.setattr(measures, 'scene_changes', scene_changes)
    monkeypatch.setattr(measures, '_scenes_cache', ProbeCache(size=8))
    return asked


class FakeSoundStore:
    def __init__(self, *projects):
        self.projects = {p['_id']: copy.deepcopy(p) for p in projects}

    async def find(self, query):
        project = self.projects.get(query['_id'])
        if project is None or (
            'owner' in query and project.get('owner') != query['owner']
        ):
            return None
        return copy.deepcopy({k: v for k, v in project.items() if k in ('_id', 'edl')})


def project(clips):
    return {
        '_id': ObjectId(),
        'owner': OWNER.email,
        'logic': {},
        'edl': {'clips': clips},
    }


@pytest.fixture
def api():
    made = []

    def make(user, *projects):
        store = FakeSoundStore(*projects)
        made.extend(as_user(app, user))
        app.dependency_overrides[sound_routes.get_sound_store] = lambda: store
        made.append(sound_routes.get_sound_store)
        return TestClient(app)

    yield make
    for dependency in made:
        app.dependency_overrides.pop(dependency, None)


TALK = {'type': 'video', 'name': 'videos/talk.mp4', 'duration': 2, 'inpoint': 1}
CUT = {'type': 'video', 'name': 'videos/cut.mp4', 'duration': 2}
TITLE = {'type': 'template', 'name': 'title', 'duration': 1}
SONG = {'type': 'audio', 'name': 'videos/song.mp3', 'duration': 1}


class TestAFile:
    def test_its_cuts_as_otto_finds_them(self, api, measured):
        res = api(OWNER).get('/media/videos/talk.mp4/scenes')
        assert res.status_code == 200, res.text
        assert res.json() == MEASURED['talk.mp4']
        assert measured == ['talk.mp4']

    def test_by_its_bare_name_and_once_per_version(self, api, measured):
        client = api(OWNER)
        client.get('/media/talk.mp4/scenes')
        client.get('/media/videos/talk.mp4/scenes')
        assert measured == ['talk.mp4']

    def test_it_is_kept_beside_the_library_for_another_process(
        self, api, measured, library
    ):
        api(OWNER).get('/media/videos/talk.mp4/scenes')
        measures._scenes_cache = ProbeCache(size=8)
        api(OWNER).get('/media/videos/talk.mp4/scenes')
        assert measured == ['talk.mp4']
        assert any((library / '.analyses').iterdir())

    @pytest.mark.parametrize(
        'name, what', [('still.png', 'an image'), ('song.mp3', 'an audio file')]
    )
    def test_a_file_with_no_moving_picture_is_422(self, api, measured, name, what):
        res = api(OWNER).get(f'/media/videos/{name}/scenes')
        assert res.status_code == 422
        assert res.json() == {
            'detail': f'videos/{name} is {what}: it has no moving picture',
            'code': 'no_picture',
        }
        assert measured == []

    def test_a_picture_ffmpeg_cannot_read_is_422_and_not_kept(
        self, api, measured, monkeypatch
    ):
        def fail(path):
            raise FFmpegException('ffmpeg could not read the picture of talk.mp4: nope')

        monkeypatch.setattr(measures, 'scene_changes', fail)
        res = api(OWNER).get('/media/videos/talk.mp4/scenes')
        assert res.status_code == 422
        assert res.json()['code'] == 'picture_unreadable'
        assert len(measures._scenes_cache) == 0

    def test_what_the_library_does_not_hold_is_404(self, api, measured):
        res = api(OWNER).get('/media/videos/gone.mp4/scenes')
        assert res.status_code == 404
        assert res.json()['code'] == 'not_found'

    def test_it_needs_a_session(self, api, measured):
        client = api(OWNER)
        anonymous(app)
        assert client.get('/media/videos/talk.mp4/scenes').status_code == 401


class TestATimeline:
    def test_each_clip_s_edges_and_the_cuts_in_its_window(self, api, measured):
        """Mutation: keep a file's cut outside the clip's window -- red."""
        mine = project([TITLE, TALK, CUT, SONG])
        res = api(OWNER, mine).get(f'/project/{mine["_id"]}/scenes')
        assert res.status_code == 200, res.text
        # The title has no shots. talk.mp4 plays its seconds 1 to 3 at 1 to 3
        # on the timeline: its cut at 1.5 s falls at 1.5, its cut at 2.75 at
        # 2.75, and those at 0.5 and 9 fall outside. cut.mp4 plays at 3 to 5
        # with its cut at 1 s falling at 4. Each clip's edges are shots' edges.
        assert res.json() == {'duration': 6, 'seconds': [1, 1.5, 2.75, 3, 4, 5]}
        assert measured == ['talk.mp4', 'cut.mp4']

    def test_a_project_that_is_not_yours_is_404(self, api, measured):
        theirs = project([TALK])
        assert (
            api(STRANGER, theirs).get(f'/project/{theirs["_id"]}/scenes').status_code
            == 404
        )

    def test_an_empty_timeline_is_422(self, api, measured):
        mine = project([])
        res = api(OWNER, mine).get(f'/project/{mine["_id"]}/scenes')
        assert res.status_code == 422
        assert res.json()['code'] == 'timeline_empty'

    def test_a_timeline_with_no_video_is_422(self, api, measured):
        mine = project([TITLE, SONG])
        res = api(OWNER, mine).get(f'/project/{mine["_id"]}/scenes')
        assert res.status_code == 422
        assert res.json()['code'] == 'no_picture'
        assert measured == []


class TestAsTheWorkerReadsIt:
    def test_the_timeline_s_measures_carry_the_cuts(self, measured, monkeypatch):
        """Mutation: leave the cuts out of `timeline_measures` -- red."""
        monkeypatch.setattr(
            measures,
            'sound_of',
            lambda name: (_ for _ in ()).throw(measures.NoSound('no engine')),
        )
        monkeypatch.setattr(
            measures, 'motion_of', lambda name: {'rate': 1, 'values': [0, 0]}
        )
        found = measures.timeline_measures([TITLE, TALK, CUT])
        assert found.scenes == [1, 1.5, 2.75, 3, 4, 5]

    def test_a_file_whose_cuts_cannot_be_measured_is_a_note(
        self, measured, monkeypatch
    ):
        monkeypatch.setattr(
            measures,
            'sound_of',
            lambda name: (_ for _ in ()).throw(measures.NoSound('no engine')),
        )
        monkeypatch.setattr(
            measures, 'motion_of', lambda name: {'rate': 1, 'values': [0, 0]}
        )

        def fail(path):
            raise FFmpegException('nope')

        monkeypatch.setattr(measures, 'scene_changes', fail)
        found = measures.timeline_measures([TALK])
        assert found.scenes == []
        assert any('scene changes were not measured' in note for note in found.notes)
