"""C5 -- what a render request may ask for.

Three ways a request reached further than it should have:

- `ffmpeg_params` and `bitrate` went onto ffmpeg's command line as sent.
- The output filename was interpolated from `project` and `description`, so a
  project called `../../x` made the worker write `/x_...mp4`.
- Fields the server owns -- status, owner, filename, link -- were stored as
  sent, so a render could arrive already "RENDERED", or as somebody else's.

Encoding now comes from a named preset, the file is named by the render's id,
and the readable name a download is saved under is kept separately.
"""

import inspect
import json

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from otto.render import renderMultitrack

from alfred.core.models.render import (
    Render,
    display_name_for,
    is_output_filename,
    output_filename,
    safe_name,
)
from alfred.core.utils.encoding import (
    DEFAULT_QUALITY,
    PRESETS,
    QUALITIES,
    UnknownQuality,
    preset_for,
)
from alfred.main import app
from tests.unit.render_harness import (
    ADMIN,
    OWNER,
    TEMPLATE_EDL,
    FakeQueue,
    FakeRenderStore,
    as_user,
    make_render,
    offline_documents,
    render_request,
    use_fakes,
)


@pytest.fixture
def api(monkeypatch):
    offline_documents(monkeypatch, Render)
    store, queue = FakeRenderStore(), FakeQueue()
    overrides = as_user(app, OWNER) + use_fakes(app, store, queue)
    yield TestClient(app), store, queue
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


def queued(api, **body):
    client, store, queue = api
    res = client.post('/render', json=render_request(**body))
    assert res.status_code == 200, res.text
    return store.renders[ObjectId(res.json())], queue.sent[-1]


class TestEncoderOptionsAreRefused:
    @pytest.mark.parametrize(
        'body',
        [
            {'ffmpeg_params': ['-b:v', '25M']},
            {'ffmpeg_params': ['-i', '/etc/passwd']},
            {'bitrate': ['5000k']},
            {'bitrate': ['5000k'], 'ffmpeg_params': ['-crf', '1']},
        ],
    )
    def test_they_are_a_422(self, api, body):
        client, store, queue = api
        res = client.post('/render', json=render_request(**body))
        assert res.status_code == 422
        for name in body:
            assert name in res.json()['detail']

    def test_nothing_is_stored_or_queued(self, api):
        client, store, queue = api
        client.post('/render', json=render_request(ffmpeg_params=['-y']))
        assert store.renders == {} and queue.sent == []

    def test_the_refusal_says_what_to_use_instead(self, api):
        client, store, queue = api
        res = client.post('/render', json=render_request(bitrate=['1M']))
        assert 'quality' in res.json()['detail']

    def test_null_is_the_same_as_absent(self, api):
        render, payload = queued(api, ffmpeg_params=None, bitrate=None)
        assert render.quality == DEFAULT_QUALITY


class TestQualityPresets:
    def test_the_default_is_standard(self, api):
        render, payload = queued(api)
        assert render.quality == 'standard'
        assert payload['quality'] == 'standard'

    @pytest.mark.parametrize('quality', QUALITIES)
    def test_every_preset_can_be_asked_for(self, api, quality):
        render, payload = queued(api, quality=quality)
        assert payload['quality'] == quality

    @pytest.mark.parametrize('quality', ['web', 'TV', 'ultra', 'STANDARD'])
    def test_anything_else_is_a_422(self, api, quality):
        """`web` and `TV` are what the form flow sent; they never meant anything
        to the server."""
        client, store, queue = api
        res = client.post('/render', json=render_request(quality=quality))
        assert res.status_code == 422
        assert 'draft' in res.json()['detail']

    def test_the_presets_are_the_contract(self):
        assert QUALITIES == ('draft', 'standard', 'high')

    def test_presets_map_onto_the_engine_s_own_parameters(self):
        """Nothing new is asked of otto (contract C8)."""
        accepted = set(inspect.signature(renderMultitrack).parameters)
        for preset in PRESETS.values():
            assert set(preset.encoder_args()) <= accepted

    def test_a_preset_s_bitrate_is_one_string_or_none(self):
        """`Render.bitrate` was a list, which is not what ffmpeg takes."""
        for preset in PRESETS.values():
            assert preset.bitrate is None or isinstance(preset.bitrate, str)

    def test_better_quality_asks_for_a_lower_rate_factor(self):
        crf = {
            name: int(p.ffmpeg_params[p.ffmpeg_params.index('-crf') + 1])
            for name, p in PRESETS.items()
        }
        assert crf['draft'] > crf['standard'] > crf['high']

    def test_unknown_quality_raises_when_strict(self):
        with pytest.raises(UnknownQuality):
            preset_for('web')

    def test_unknown_quality_falls_back_when_not(self):
        """For renders stored before presets, which re-render as standard."""
        assert preset_for('TV', strict=False).name == DEFAULT_QUALITY


class TestTheWorkerEncodesFromThePreset:
    def run(self, monkeypatch, recorded_encode, **kwargs):
        from alfred.core.utils import tasks

        failures = []

        class NullLogger:
            """Enough of DbLogger for the task, recording only failures."""

            def __init__(self, task, render_id):
                pass

            def rendered(self):
                pass

            def uploaded(self):
                pass

            def failed(self, *args, **kwargs):
                failures.append(kwargs.get('exc'))

        monkeypatch.setattr(tasks, 'upload', lambda *a, **k: None)
        monkeypatch.setattr(tasks, 'DbLogger', NullLogger)
        render_id = str(ObjectId())
        tasks.renderRemote.apply(
            kwargs=dict(
                edl=TEMPLATE_EDL,
                filename=output_filename(render_id),
                renderId=render_id,
                moviesize=[64, 48],
                **kwargs,
            )
        )
        assert not failures, f'the render failed: {failures}'
        assert len(recorded_encode) == 1, 'nothing reached the encoder'
        return recorded_encode[0]

    @pytest.mark.parametrize('quality', QUALITIES)
    def test_the_named_preset_reaches_the_encoder(
        self, monkeypatch, recorded_encode, quality
    ):
        call = self.run(monkeypatch, recorded_encode, quality=quality)
        assert call['ffmpeg_params'] == list(PRESETS[quality].ffmpeg_params)
        assert call['audio_bitrate'] == PRESETS[quality].audio_bitrate

    def test_encoder_options_from_an_old_job_are_ignored(
        self, monkeypatch, recorded_encode
    ):
        call = self.run(
            monkeypatch,
            recorded_encode,
            ffmpeg_params=['-i', '/etc/passwd'],
            bitrate=['9000k'],
        )
        assert '/etc/passwd' not in call['ffmpeg_params']
        assert call['bitrate'] is None


class TestTheOutputFilename:
    def test_it_is_the_id_alone(self, api):
        render, payload = queued(api, project='../../x', description='a/b')
        assert render.filename == f'{render.id}.mp4'
        assert payload['filename'] == render.filename

    def test_nothing_from_the_request_reaches_it(self, api):
        render, _ = queued(api, project='../../etc', name='..\\x')
        assert '/' not in render.filename and '..' not in render.filename

    def test_the_worker_check_accepts_exactly_these(self):
        render_id = ObjectId()
        assert is_output_filename(output_filename(render_id))
        for name in ['../x.mp4', 'x.mp4', f'{render_id}.mp4/..', f'/{render_id}.mp4']:
            assert not is_output_filename(name)


class TestTheDisplayName:
    def test_it_is_readable(self, api):
        render, _ = queued(api, project='Car advert', description='final cut')
        assert render.display_name == 'Car-advert-final-cut-64x48'

    @pytest.mark.parametrize(
        'text,expected',
        [
            ('../../etc/passwd', 'etc-passwd'),
            ('..', 'render'),
            ('', 'render'),
            (None, 'render'),
            ('.hidden', 'hidden'),
            ('Café crème', 'Cafe-creme'),
            ('a"b;c\r\nd', 'a-b-c-d'),
            ('x' * 200, 'x' * 80),
        ],
    )
    def test_it_is_safe_as_a_file_name(self, text, expected):
        assert safe_name(text) == expected

    def test_it_survives_a_render_with_no_labels(self, monkeypatch):
        offline_documents(monkeypatch, Render)
        render = make_render(project=None, name=None, width=None, height=None)
        assert display_name_for(render) == 'render'


class TestServerOwnedFields:
    def test_what_a_client_sends_for_them_is_discarded(self, api):
        render, _ = queued(
            api,
            status='RENDERED',
            progress=100,
            username='somebody@example.com',
            filename='../../evil.mp4',
            link='https://evil.example/x',
            destination='bucket',
            display_name='../evil',
        )
        assert render.status is None and render.progress is None
        assert render.username == OWNER.email
        assert render.filename == f'{render.id}.mp4'
        assert render.link is None and render.destination is None
        assert '..' not in render.display_name

    def test_a_client_cannot_choose_the_id(self, api):
        chosen = str(ObjectId())
        render, _ = queued(api, _id=chosen)
        assert str(render.id) != chosen


class TestFrameSize:
    @pytest.mark.parametrize('width', [0, -1, 15, 7681, 100000])
    def test_out_of_range_is_a_422(self, api, width):
        client, store, queue = api
        res = client.post('/render', json=render_request(width=width))
        assert res.status_code == 422

    def test_null_means_the_default(self, api):
        render, payload = queued(api, width=None, height=None)
        assert payload['moviesize'] == [1920, 1080]


class TestFrameRate:
    """Bounded like the frame size, now the engine encodes at the rate asked
    for. It used to encode at 30 whatever a request said."""

    @pytest.mark.parametrize('fps', [0, -24, 0.5, 121, 1e6])
    def test_out_of_range_is_a_422(self, api, fps):
        client, store, queue = api
        res = client.post('/render', json=render_request(fps=fps))
        assert res.status_code == 422
        assert 'fps' in res.json()['detail']
        assert store.renders == {} and queue.sent == []

    @pytest.mark.parametrize('fps', [1, 23.976, 29.97, 60, 120])
    def test_a_real_rate_reaches_the_worker(self, api, fps):
        render, payload = queued(api, fps=fps)
        assert payload['fps'] == fps

    def test_null_means_the_default(self, api):
        render, payload = queued(api, fps=None)
        assert payload['fps'] == 30.0


class TestRequeueingAnOldRender:
    def test_it_is_renamed_to_its_id_and_given_a_known_quality(self, api):
        client, store, queue = api
        old = make_render(
            filename='../../x_320x180_TV_1.0s_20200101-000000.mp4', quality='TV'
        )
        store.renders[old.id] = old
        as_user(app, ADMIN)

        res = client.post(f'/render/rerender/{old.id}')
        assert res.status_code == 200, res.text
        (payload,) = queue.sent
        assert payload['filename'] == f'{old.id}.mp4'
        assert payload['quality'] == DEFAULT_QUALITY
        assert store.renders[old.id].filename == f'{old.id}.mp4'
        assert json.loads(json.dumps(payload)) == payload
