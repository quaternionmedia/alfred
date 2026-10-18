"""The cloud bucket: what an object is called, and who gets a link to it.

`BucketDestination` uploaded a render under its full server path, then asked
`generate_signed_url` -- which takes a render *id* -- to sign that path, so
every successful upload ended in "Not a valid identifier". `GET /render/{id}`
signed a link to any render for anyone signed in. And a bucket delivery
recorded a fifteen-minute signed URL as the render's `link`, so every stored
bucket link was dead a quarter of an hour later.

A delivery now records where the object is, `gs://<bucket>/<object>`, and a
link is signed whenever one is handed out. No cloud here: the upload and the
signer are replaced, and what they were asked for is what the tests check.
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from alfred import config
from alfred.core.models.render import Render
from alfred.core.utils import bucket
from alfred.core.utils.destinations import BucketDestination, DeliveryError
from alfred.main import app
from tests.unit.render_harness import (
    OWNER,
    STRANGER,
    FakeQueue,
    FakeRenderStore,
    as_user,
    make_render,
    offline_documents,
    use_fakes,
)

NAME = '6ad3cdc433bc85ee116c7577.mp4'
# What a delivery stored before references: a v4 signed URL, long expired.
STORED_SIGNED_URL = (
    'https://storage.googleapis.com/old-bucket/6ad3cdc433bc85ee116c7577.mp4'
    '?X-Goog-Algorithm=GOOG4-RSA-SHA256&X-Goog-Expires=900&X-Goog-Signature=abc'
)


def fake_signed_url(record):
    def signed_url(blob_name, minutes=15, bucket=None):
        record.append((bucket, blob_name))
        return f'https://storage.example/{bucket or "default"}/{blob_name}?sig=fresh'

    return signed_url


@pytest.fixture
def cloud(monkeypatch):
    """Record uploads and signatures instead of making them."""
    calls = {'upload': [], 'sign': []}

    def upload(filename, directory=None):
        calls['upload'].append((filename, directory))

    monkeypatch.setattr(bucket, 'upload', upload)
    monkeypatch.setattr(bucket, 'signed_url', fake_signed_url(calls['sign']))
    return calls


class TestTheBucketDestination:
    def test_the_object_is_named_for_the_file(self, cloud, tmp_path):
        path = tmp_path / 'renders' / NAME
        delivery = BucketDestination().deliver(str(path))
        assert cloud['upload'] == [(NAME, str(tmp_path / 'renders'))]
        assert delivery.destination == 'bucket'

    def test_its_location_is_a_lasting_reference_not_a_signed_url(
        self, cloud, tmp_path
    ):
        """A signed URL is dead in fifteen minutes, and the location is what
        the render records."""
        delivery = BucketDestination().deliver(str(tmp_path / NAME))
        assert delivery.location == f'gs://{config.BUCKET_NAME}/{NAME}'
        assert cloud['sign'] == [], 'nothing needs signing to deliver'

    def test_the_name_matches_the_worker_s_automatic_upload(self, cloud, tmp_path):
        """One object per render, whichever path put it there."""
        BucketDestination().deliver(str(tmp_path / 'x.mp4'))
        ((uploaded, _),) = cloud['upload']
        assert '/' not in uploaded

    def test_a_failed_upload_is_a_delivery_error(self, monkeypatch, tmp_path):
        def refuse(*args, **kwargs):
            raise OSError('no credentials')

        monkeypatch.setattr(bucket, 'upload', refuse)
        with pytest.raises(DeliveryError, match='no credentials'):
            BucketDestination().deliver(str(tmp_path / 'x.mp4'))


class TestReferences:
    def test_a_reference_names_its_bucket_and_object(self):
        assert bucket.object_reference('x.mp4', bucket='b') == 'gs://b/x.mp4'
        assert bucket.parse_reference('gs://b/x.mp4') == ('b', 'x.mp4')

    def test_an_object_may_have_a_path(self):
        assert bucket.parse_reference('gs://b/renders/x.mp4') == ('b', 'renders/x.mp4')

    def test_a_stored_signed_url_still_names_its_object(self):
        assert bucket.parse_reference(STORED_SIGNED_URL) == ('old-bucket', NAME)

    @pytest.mark.parametrize(
        'link',
        [
            None,
            '',
            '/render/abc/download',
            'gs://',
            'gs://bucket-only',
            'https://storage.googleapis.com/b/x.mp4',  # not signed: not ours
            'https://evil.example/b/x.mp4?X-Goog-Signature=abc',
            'http://storage.googleapis.com/b/x.mp4?X-Goog-Signature=abc',
        ],
    )
    def test_anything_else_is_not_a_reference(self, link):
        assert bucket.parse_reference(link) is None


class TestTheLookupByRenderId:
    """`generate_signed_url` stays for callers that hold only an id."""

    def test_it_signs_the_render_s_object(self, cloud, monkeypatch):
        class Renders:
            @staticmethod
            def find_one(query):
                return {'filename': 'stored-name.mp4'}

        monkeypatch.setattr(
            bucket, 'get_sync_db', lambda: type('Db', (), {'Render': Renders})
        )
        url = bucket.generate_signed_url('6ad3cdc433bc85ee116c7577')
        assert cloud['sign'] == [(None, 'stored-name.mp4')]
        assert 'stored-name.mp4' in url

    def test_a_malformed_id_is_still_a_422(self):
        with pytest.raises(HTTPException) as excinfo:
            bucket.generate_signed_url('undefined')
        assert excinfo.value.status_code == 422


@pytest.fixture
def api(monkeypatch, tmp_path):
    root = tmp_path / 'videos'
    (root / 'renders').mkdir(parents=True)
    monkeypatch.setattr(config, 'VIDEO_DIR', str(root))
    monkeypatch.setattr(config, 'RENDER_DIR', str(root / 'renders'))
    offline_documents(monkeypatch, Render)
    store = FakeRenderStore()
    overrides = as_user(app, OWNER) + use_fakes(app, store, FakeQueue())
    yield TestClient(app), store, root / 'renders'
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


@pytest.fixture
def signer(monkeypatch):
    from alfred.core.routes import render as routes

    signed = []
    monkeypatch.setattr(routes, 'signed_url', fake_signed_url(signed))
    return signed


@pytest.fixture
def uploads(monkeypatch):
    uploaded = []
    monkeypatch.setattr(
        bucket, 'upload', lambda filename, directory=None: uploaded.append(filename)
    )
    return uploaded


def finished(store, renders, **fields):
    render = make_render(status='RENDERED', **fields)
    render.filename = f'{render.id}.mp4'
    store.renders[render.id] = render
    (renders / render.filename).write_bytes(b'a render')
    return render


class TestDeliveringToTheBucket:
    def test_records_the_reference_and_answers_with_a_signed_link(
        self, api, signer, uploads
    ):
        client, store, renders = api
        render = finished(store, renders)
        res = client.post(f'/render/{render.id}/deliver?destination=bucket')
        assert res.status_code == 200, res.text
        reference = f'gs://{config.BUCKET_NAME}/{render.filename}'
        assert store.renders[render.id].link == reference
        assert res.json() == {
            'destination': 'bucket',
            'location': (
                f'https://storage.example/{config.BUCKET_NAME}/{render.filename}'
                '?sig=fresh'
            ),
        }

    def test_a_link_that_cannot_be_signed_is_a_502_and_the_delivery_stands(
        self, api, uploads, monkeypatch
    ):
        from alfred.core.routes import render as routes

        def refuse(*args, **kwargs):
            raise OSError('no signing key')

        monkeypatch.setattr(routes, 'signed_url', refuse)
        client, store, renders = api
        render = finished(store, renders)
        res = client.post(f'/render/{render.id}/deliver?destination=bucket')
        assert res.status_code == 502
        assert 'uploaded' in res.json()['detail']
        assert store.renders[render.id].destination == 'bucket'
        assert store.renders[render.id].link.startswith('gs://')


class TestLinksAreSignedWhenHandedOut:
    def test_the_list_signs_a_stored_reference(self, api, signer):
        client, store, renders = api
        render = finished(store, renders, destination='bucket', link=f'gs://b/{NAME}')
        (item,) = client.get('/render').json()
        assert item['link'] == f'https://storage.example/b/{NAME}?sig=fresh'
        assert signer == [('b', NAME)]
        assert store.renders[render.id].link == f'gs://b/{NAME}', 'stored as it was'

    def test_and_signs_it_again_each_time(self, api, signer):
        client, store, renders = api
        finished(store, renders, destination='bucket', link=f'gs://b/{NAME}')
        client.get('/render')
        client.get('/render')
        assert len(signer) == 2

    def test_a_stored_signed_url_is_signed_afresh(self, api, signer):
        """What deliveries stored before references: expired, but it names
        the object."""
        client, store, renders = api
        finished(store, renders, destination='bucket', link=STORED_SIGNED_URL)
        (item,) = client.get('/render').json()
        assert item['link'] == f'https://storage.example/old-bucket/{NAME}?sig=fresh'

    def test_a_link_that_cannot_be_signed_is_null_not_an_error(self, api, monkeypatch):
        from alfred.core.routes import render as routes

        def refuse(*args, **kwargs):
            raise OSError('no credentials')

        monkeypatch.setattr(routes, 'signed_url', refuse)
        client, store, renders = api
        finished(store, renders, destination='bucket', link=f'gs://b/{NAME}')
        res = client.get('/render')
        assert res.status_code == 200
        assert res.json()[0]['link'] is None

    def test_a_local_delivery_s_link_is_the_download_route(self, api, signer):
        client, store, renders = api
        render = finished(store, renders, destination='local')
        render.link = f'/render/{render.id}/download'
        (item,) = client.get('/render').json()
        assert item['link'] == f'/render/{render.id}/download'
        assert signer == []

    def test_one_recorded_under_the_old_public_mount_is_too(self, api, signer):
        """Local deliveries were copied under /data, and that path recorded."""
        client, store, renders = api
        render = finished(store, renders, link='data/renders/old.mp4')
        (item,) = client.get('/render').json()
        assert item['link'] == f'/render/{render.id}/download'

    def test_no_link_is_no_link(self, api, signer):
        client, store, renders = api
        finished(store, renders)
        assert client.get('/render').json()[0]['link'] is None


class TestTheLinkRoute:
    def test_the_owner_gets_a_link_to_their_render_s_object(self, api, signer):
        client, store, _ = api
        render = make_render(filename=NAME)
        store.renders[render.id] = render
        res = client.get(f'/render/{render.id}')
        assert res.status_code == 200
        assert res.json() == f'https://storage.example/default/{NAME}?sig=fresh'
        assert signer == [(None, NAME)]

    def test_a_delivered_render_s_link_is_to_the_object_it_recorded(self, api, signer):
        """The bucket it went to may not be today's BUCKET_NAME."""
        client, store, _ = api
        render = make_render(
            filename=NAME, destination='bucket', link=f'gs://then/{NAME}'
        )
        store.renders[render.id] = render
        assert (
            client.get(f'/render/{render.id}')
            .json()
            .startswith('https://storage.example/then/')
        )

    def test_nobody_else_does(self, api, signer):
        client, store, _ = api
        render = make_render()
        store.renders[render.id] = render
        as_user(app, STRANGER)
        assert client.get(f'/render/{render.id}').status_code == 404
        assert signer == [], 'a link was signed for a stranger'

    def test_no_cloud_account_is_a_502_not_a_500(self, api, monkeypatch):
        """What every server without credentials answered with a traceback."""
        from alfred.core.routes import render as routes

        def refuse(*args, **kwargs):
            raise OSError('File /cred.json was not found')

        monkeypatch.setattr(routes, 'signed_url', refuse)
        client, store, _ = api
        render = make_render()
        store.renders[render.id] = render
        res = client.get(f'/render/{render.id}')
        assert res.status_code == 502
        assert 'cred.json' not in res.text
