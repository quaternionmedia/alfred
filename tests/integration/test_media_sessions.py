"""M1 with real sessions: a file route takes a token or a signed URL.

The unit tier replaces the session dependency, so it cannot show that the
file routes still recognise a real token -- they read the session through an
optional dependency of their own, so that a request with none can still be
admitted by a signature. Here the tokens are fastapi-users' own, from the
login route, and the render lives in MongoDB.
"""

import pytest
from bson import ObjectId

from alfred import config

pytestmark = pytest.mark.needs_db

VIDEO_BYTES = b'\x00\x00\x00\x18ftypmp42' + b'frames' * 500

TIMELINE = {
    'clips': [
        {
            'type': 'template',
            'name': 'makeColor',
            'duration': 1.0,
            'start': 0.0,
            'data': {'color': '#f2aa4c'},
        }
    ],
    'duration': 1.0,
}


@pytest.fixture
def library(tmp_path, monkeypatch):
    from alfred.core.routes import video

    root = tmp_path / 'videos'
    (root / 'renders').mkdir(parents=True)
    monkeypatch.setattr(config, 'VIDEO_DIR', str(root))
    monkeypatch.setattr(config, 'RENDER_DIR', str(root / 'renders'))
    monkeypatch.setattr(video, 'VIDEO_DIR', str(root))
    (root / 'clip.mp4').write_bytes(VIDEO_BYTES)
    return root


@pytest.fixture
def renders(api, db):
    from alfred.core.models.render import Render

    return db[Render.get_motor_collection().name]


@pytest.fixture
def finished_render(renders, library):
    """`finished_render(account)`: a finished render of theirs, file and all."""

    def make(account):
        render_id = ObjectId()
        renders.insert_one(
            {
                '_id': render_id,
                'edl': TIMELINE,
                'username': account.email,
                'status': 'RENDERED',
                'progress': 100,
                'filename': f'{render_id}.mp4',
                'display_name': 'integration',
            }
        )
        (library / 'renders' / f'{render_id}.mp4').write_bytes(VIDEO_BYTES)
        return str(render_id)

    return make


def test_the_owner_s_token_gets_a_url_that_needs_no_token(
    api, make_account, finished_render
):
    owner = make_account('owner')
    render_id = finished_render(owner)

    status = api.get(f'/render/{render_id}/status', headers=owner.headers)
    assert status.status_code == 200, status.text
    url = status.json()['download_url']
    assert url.startswith(f'/render/{render_id}/download?exp=')

    res = api.get(url)
    assert res.status_code == 200
    assert res.content == VIDEO_BYTES


def test_the_owner_s_token_alone_still_downloads(api, make_account, finished_render):
    owner = make_account('owner')
    render_id = finished_render(owner)
    res = api.get(f'/render/{render_id}/download', headers=owner.headers)
    assert res.status_code == 200
    assert res.content == VIDEO_BYTES


def test_another_account_s_token_gets_a_404_and_no_url(
    api, make_account, finished_render
):
    owner, other = make_account('owner'), make_account('other')
    render_id = finished_render(owner)
    assert (
        api.get(f'/render/{render_id}/status', headers=other.headers).status_code == 404
    )
    assert (
        api.get(f'/render/{render_id}/download', headers=other.headers).status_code
        == 404
    )
    listed = api.get('/render', headers=other.headers).json()
    assert render_id not in [r['_id'] for r in listed]


def test_no_token_and_no_signature_is_a_401(api, make_account, finished_render):
    render_id = finished_render(make_account('owner'))
    assert api.get(f'/render/{render_id}/download').status_code == 401


def test_a_bad_token_is_no_session(api, make_account, finished_render):
    render_id = finished_render(make_account('owner'))
    res = api.get(
        f'/render/{render_id}/download',
        headers={'Authorization': 'Bearer not-a-token'},
    )
    assert res.status_code == 401


def test_a_bad_token_does_not_spoil_a_good_signature(
    api, make_account, finished_render
):
    owner = make_account('owner')
    render_id = finished_render(owner)
    url = api.get(f'/render/{render_id}/status', headers=owner.headers).json()[
        'download_url'
    ]
    res = api.get(url, headers={'Authorization': 'Bearer not-a-token'})
    assert res.status_code == 200


def test_library_files_take_a_token_or_a_signature(api, make_account, library):
    from alfred.core.utils.signing import media_url

    account = make_account('viewer')
    assert api.get('/videos/clip.mp4', headers=account.headers).status_code == 200
    assert api.get('/videos/clip.mp4').status_code == 401
    assert api.get(media_url('/videos/clip.mp4')).status_code == 200
