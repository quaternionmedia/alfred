"""The cloud bucket: what an object is called, and who gets a link to it.

`BucketDestination` uploaded a render under its full server path, then asked
`generate_signed_url` -- which takes a render *id* -- to sign that path, so
every successful upload ended in "Not a valid identifier". And
`GET /render/{id}` signed a link to any render for anyone signed in.

No cloud here: the upload and the signer are replaced, and what they were
asked for is what the tests check.
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

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


@pytest.fixture
def cloud(monkeypatch):
    """Record uploads and signatures instead of making them."""
    calls = {'upload': [], 'sign': []}

    def upload(filename, directory=None):
        calls['upload'].append((filename, directory))

    def signed_url(blob_name, minutes=15):
        calls['sign'].append(blob_name)
        return f'https://storage.example/{blob_name}?signature=x'

    monkeypatch.setattr(bucket, 'upload', upload)
    monkeypatch.setattr(bucket, 'signed_url', signed_url)
    return calls


class TestTheBucketDestination:
    def test_the_object_is_named_for_the_file_and_signed_by_that_name(
        self, cloud, tmp_path
    ):
        path = tmp_path / 'renders' / '6ad3cdc433bc85ee116c7577.mp4'
        delivery = BucketDestination().deliver(str(path))

        assert cloud['upload'] == [
            ('6ad3cdc433bc85ee116c7577.mp4', str(tmp_path / 'renders'))
        ]
        assert cloud['sign'] == ['6ad3cdc433bc85ee116c7577.mp4']
        assert delivery.destination == 'bucket'
        assert delivery.location.startswith('https://storage.example/6ad3')

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

    def test_a_failed_signature_is_a_delivery_error(self, cloud, monkeypatch, tmp_path):
        def refuse(*args, **kwargs):
            raise ValueError('cannot sign without a key')

        monkeypatch.setattr(bucket, 'signed_url', refuse)
        with pytest.raises(DeliveryError):
            BucketDestination().deliver(str(tmp_path / 'x.mp4'))


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
        assert cloud['sign'] == ['stored-name.mp4']
        assert url.endswith('stored-name.mp4?signature=x')

    def test_a_malformed_id_is_still_a_422(self):
        with pytest.raises(HTTPException) as excinfo:
            bucket.generate_signed_url('undefined')
        assert excinfo.value.status_code == 422


@pytest.fixture
def api(monkeypatch):
    offline_documents(monkeypatch, Render)
    store = FakeRenderStore()
    overrides = as_user(app, OWNER) + use_fakes(app, store, FakeQueue())
    yield TestClient(app), store
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


@pytest.fixture
def signer(monkeypatch):
    from alfred.core.routes import render as routes

    signed = []

    def signed_url(blob_name, minutes=15):
        signed.append(blob_name)
        return f'https://storage.example/{blob_name}?signature=x'

    monkeypatch.setattr(routes, 'signed_url', signed_url)
    return signed


class TestTheLinkRoute:
    def test_the_owner_gets_a_link_to_their_render_s_object(self, api, signer):
        client, store = api
        render = make_render(filename='6ad3cdc433bc85ee116c7577.mp4')
        store.renders[render.id] = render
        res = client.get(f'/render/{render.id}')
        assert res.status_code == 200
        assert res.json() == (
            'https://storage.example/6ad3cdc433bc85ee116c7577.mp4?signature=x'
        )
        assert signer == ['6ad3cdc433bc85ee116c7577.mp4']

    def test_nobody_else_does(self, api, signer):
        client, store = api
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
        client, store = api
        render = make_render()
        store.renders[render.id] = render
        res = client.get(f'/render/{render.id}')
        assert res.status_code == 502
        assert 'cred.json' not in res.text
