"""Every refusal code: in the table, and on the wire.

alfred's own refusals answer `{"detail", "code"}` (`alfred/core/errors.py`),
and a client switches on the code rather than the wording -- qmcp does, to
tell the two 503s a transcription can meet apart. So a code is a promise, and
these tests hold it: the table in docs/api/errors.md lists exactly the codes
alfred has, each with its status; every code is answered by a real request
through the app, its `detail` the sentence it always was; and the modules the
table covers raise no refusal without a code.
"""

import ast
import asyncio
import re
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from otto.exceptions import FFmpegException
from otto.models import Edl

from alfred import config
from alfred.core.errors import REFUSALS, Code, Refusal
from alfred.core.models.cues import MAX_CUES
from alfred.core.models.recipes import OPERATIONS
from alfred.core.models.render import Render
from alfred.core.routes import captions as caption_routes
from alfred.core.routes import cues as cue_routes
from alfred.core.routes import drafts as draft_routes
from alfred.core.routes import media as media_routes
from alfred.core.routes import recipes as recipe_routes
from alfred.core.routes import render as render_routes
from alfred.core.routes.templates import TEMPLATE_NAMES
from alfred.core.utils import audio_engine, bucket, concurrency, measures, support_mail
from alfred.core.utils.captions import CaptionFormatError, parse
from alfred.core.utils.concurrency import RETRY_AFTER
from alfred.core.utils.encoding import QUALITIES
from alfred.core.utils.media import RefusedEdl, check_edl
from alfred.core.utils.recipes_builtin import BY_NAME
from alfred.main import app
from tests.unit.render_harness import (
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
from tests.unit.test_preview_slots import preview_requests

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / 'docs' / 'api' / 'errors.md'

# The modules whose every refusal carries a code: the project, captions and
# render routes and the id refusals they share; how a library file sounds; the
# preview slots; and mail to support, from the issue report and the invoice.
COVERED = [
    'alfred/core/routes/admin.py',
    'alfred/core/routes/audio.py',
    'alfred/core/routes/captions.py',
    'alfred/core/routes/cues.py',
    'alfred/core/routes/drafts.py',
    'alfred/core/routes/issue.py',
    'alfred/core/routes/motion.py',
    'alfred/core/routes/project.py',
    'alfred/core/routes/recipes.py',
    'alfred/core/routes/render.py',
    'alfred/core/routes/sound.py',
    'alfred/core/utils/bucket.py',
    'alfred/core/utils/concurrency.py',
    'alfred/core/utils/support_mail.py',
]


def table_rows():
    """`{code: status}` from the table's rows: `| \\`code\\` | status | ...`."""
    rows = re.findall(
        r'^\|\s*`([a-z_]+)`\s*\|\s*(\d{3})\s*\|', TABLE.read_text('utf-8'), re.M
    )
    found = {}
    for code, status in rows:
        assert code not in found, f'{code} is in the table twice'
        found[code] = int(status)
    return found


def test_every_code_has_a_status_and_a_meaning():
    assert set(REFUSALS) == set(Code)
    assert all(meaning.means for meaning in REFUSALS.values())


def test_the_table_lists_every_code_with_its_status_and_nothing_else():
    """Mutation: give a code another status, or leave one out of the table --
    red."""
    assert table_rows() == {code.value: REFUSALS[code].status for code in Code}


def test_a_refusal_answers_its_code_s_status_with_its_sentence_as_detail():
    refusal = Refusal(Code.TRANSCRIPTION_RUNNING, 'busy')
    assert (refusal.status_code, refusal.detail) == (409, 'busy')
    assert refusal.body() == {'detail': 'busy', 'code': 'transcription_running'}
    with pytest.raises(ValueError):
        Refusal('not_a_code', 'no such code')


def uncoded(source):
    """Lines that build a refusal some other way than `Refusal`: an
    HTTPException under any name, or a JSON response of its own."""
    lines = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            name = getattr(node.func, 'id', getattr(node.func, 'attr', ''))
            if name.endswith('HTTPException') or name == 'JSONResponse':
                lines.append(node.lineno)
    return lines


def test_the_guard_sees_each_way_round_it():
    assert uncoded('raise HTTPException(status_code=422, detail="no")') == [1]
    assert uncoded('raise StarletteHTTPException(422)') == [1]
    assert uncoded('return responses.JSONResponse({"detail": "no"}, 422)') == [1]
    assert uncoded('raise Refusal(Code.NOT_FOUND, "no")') == []


@pytest.mark.parametrize('module', COVERED)
def test_a_covered_module_raises_no_refusal_without_a_code(module):
    """Every refusal these modules build is a `Refusal`. Mutation: put one
    `HTTPException(...)` back in render.py -- red."""
    bare = uncoded((ROOT / module).read_text('utf-8'))
    assert bare == [], f'{module} refuses without a code at lines {bare}'


# --- a request for every code ----------------------------------------------


class Projects:
    """The project collection, as the captions routes use it."""

    def __init__(self):
        self.projects = {}
        self.claims = True

    def add(self, **fields):
        document = {'_id': ObjectId(), 'owner': OWNER.email, **fields}
        self.projects[document['_id']] = document
        return document['_id']

    async def find(self, query):
        return self.projects.get(query['_id'])

    async def set(self, project_id, fields):
        self.projects[project_id].update(fields)

    async def claim(self, project_id, job, stale_before):
        return self.claims


class Recipes:
    """The recipe collection, in memory, holding nothing of the caller's."""

    async def list(self, query):
        return []

    async def find(self, query):
        return None

    async def insert(self, document):
        return ObjectId()

    async def replace(self, recipe_id, fields):
        pass


class Drafts:
    """The project collection as the drafts routes use it, over `Projects`."""

    def __init__(self, projects):
        self.projects = projects

    async def find(self, query):
        return self.projects.projects.get(query['_id'])

    async def has_words(self, project_id):
        return bool(self.projects.projects[project_id].get('words'))

    async def claim(self, project_id, job, stale_before):
        current = self.projects.projects[project_id].get('drafts_job') or {}
        if current.get('state') in ('queued', 'running'):
            return False
        self.projects.projects[project_id]['drafts_job'] = job
        return True

    async def set(self, project_id, fields):
        self.projects.projects[project_id].update(fields)

    async def drafts_of(self, query):
        return []

    async def delete(self, query):
        return 0


class BrokerDown:
    def __call__(self, **kwargs):
        raise ConnectionError('[Errno 111] Connection refused')


class World:
    """The app with nothing behind it: the caller is OWNER, projects and
    renders are in memory, the queues record, and the library and the
    render directory are empty folders."""

    def __init__(self, monkeypatch, tmp_path):
        self.monkeypatch = monkeypatch
        library = tmp_path / 'videos'
        self.renders_dir = library / 'renders'
        self.renders_dir.mkdir(parents=True)
        (library / 'talk.wav').write_bytes(b'RIFF not really')
        monkeypatch.setattr(config, 'VIDEO_DIR', str(library))
        monkeypatch.setattr(config, 'RENDER_DIR', str(self.renders_dir))
        monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', None)
        offline_documents(monkeypatch, Render)
        self.renders = FakeRenderStore()
        self.projects = Projects()
        self.transcriptions = FakeQueue()
        self.overrides = as_user(app, OWNER) + use_fakes(app, self.renders, FakeQueue())
        app.dependency_overrides[caption_routes.get_captions_store] = (
            lambda: self.projects
        )
        app.dependency_overrides[caption_routes.get_captions_queue] = (
            lambda: self.transcriptions
        )
        app.dependency_overrides[cue_routes.get_cues_store] = lambda: self.projects
        self.recipes = Recipes()
        app.dependency_overrides[recipe_routes.get_recipe_store] = lambda: self.recipes
        self.drafts = Drafts(self.projects)
        app.dependency_overrides[draft_routes.get_drafts_store] = lambda: self.drafts
        app.dependency_overrides[draft_routes.get_drafts_queue] = lambda: FakeQueue()
        self.overrides += [
            caption_routes.get_captions_store,
            caption_routes.get_captions_queue,
            cue_routes.get_cues_store,
            recipe_routes.get_recipe_store,
            draft_routes.get_drafts_store,
            draft_routes.get_drafts_queue,
        ]
        self.client = TestClient(app)

    def close(self):
        for dependency in self.overrides:
            app.dependency_overrides.pop(dependency, None)

    def an_engine(self):
        self.monkeypatch.setattr(config, 'AUDIO_ENGINE_URL', 'http://engine.test:1059')
        self.monkeypatch.setattr(audio_engine, 'problem', lambda: None)

    def transcribe(self, project_id):
        return self.client.post(f'/project/{project_id}/captions/transcribe')

    def finished_render(self):
        render = make_render(status='RENDERED')
        render.filename = f'{render.id}.mp4'
        self.renders.renders[render.id] = render
        (self.renders_dir / render.filename).write_bytes(b'a render')
        return render

    def deliver(self, render, destination):
        return self.client.post(
            f'/render/{render.id}/deliver?destination={destination}'
        )

    def no_signing(self):
        def refuse(*args, **kwargs):
            raise OSError('no signing key')

        self.monkeypatch.setattr(render_routes, 'signed_url', refuse)

    def uploads_accepted(self):
        self.monkeypatch.setattr(bucket, 'upload', lambda *args, **kwargs: None)

    def broker_down(self):
        """Renders and mail are sent to a broker that is not there."""
        app.dependency_overrides[render_routes.get_render_queue] = lambda: BrokerDown()
        app.dependency_overrides[support_mail.get_mail_queue] = lambda: BrokerDown()
        self.overrides.append(support_mail.get_mail_queue)

    def mail(self, configured=True):
        self.monkeypatch.setattr(
            support_mail, 'support_mail_configured', lambda: configured
        )

    def report(self):
        """An issue reported with one of the caller's renders."""
        render = make_render()
        self.renders.renders[render.id] = render
        return self.client.post(f'/render/{render.id}/report', json='It stutters.')

    def sound_of(self, name, features=None):
        query = f'?features={features}' if features else ''
        return self.client.get(f'/media/videos/{name}/audio{query}')

    def engine_says(self, failure):
        """An engine that answers every analysis with `failure`."""
        self.an_engine()

        def analyze(*args):
            raise failure

        self.monkeypatch.setattr(audio_engine, 'analyze', analyze)


@pytest.fixture
def world(monkeypatch, tmp_path):
    made = World(monkeypatch, tmp_path)
    yield made
    made.close()


def refused_edl(edl):
    """What check_edl says of `edl`."""
    with pytest.raises(RefusedEdl) as refused:
        check_edl(Edl.model_validate(edl), TEMPLATE_NAMES)
    return str(refused.value)


def invalid_id(world):
    return world.client.get('/render/undefined/status'), 'Not a valid identifier'


def not_found(world):
    return world.client.get(f'/project/{ObjectId()}/captions'), 'Item not found'


def too_many_cues(world):
    project = world.projects.add()
    many = [{'start': n, 'label': 'here'} for n in range(MAX_CUES + 1)]
    res = world.client.put(f'/project/{project}/cues', json={'cues': many})
    return res, f'{MAX_CUES + 1} cues is more than the {MAX_CUES} a project may carry'


def media_name_refused(world):
    res = world.client.post('/media', files={'file': ('notes.txt', b'hello')})
    from alfred.core.utils.media import MEDIA_EXTENSIONS

    return res, (
        "'notes.txt' is not a name the library can hold: one file name, not "
        f'hidden, ending in one of {", ".join(sorted(MEDIA_EXTENSIONS))}'
    )


def media_exists(world):
    res = world.client.post('/media', files={'file': ('talk.wav', b'RIFF again')})
    return (
        res,
        'videos/talk.wav is in the library already; send replace=true to replace it',
    )


def media_too_large(world):
    world.monkeypatch.setattr(media_routes, 'UPLOAD_LIMIT', 8)
    res = world.client.post('/media', files={'file': ('big.wav', b'0123456789')})
    return res, 'big.wav is larger than an upload may be, 8 bytes'


def caption_file_unreadable(world):
    project = world.projects.add()
    text = '1\n00:00:61,000 --> 00:01:02,000\nSixty-one seconds\n'
    with pytest.raises(CaptionFormatError) as unreadable:
        parse('srt', text)
    res = world.client.post(
        f'/project/{project}/captions/import', json={'format': 'srt', 'text': text}
    )
    return res, str(unreadable.value)


TALK = {'clips': [{'type': 'audio', 'name': 'videos/talk.wav', 'duration': 4.0}]}


def audio_engine_missing(world):
    project = world.projects.add(edl=TALK)
    return world.transcribe(project), audio_engine.problem()


def timeline_empty(world):
    world.an_engine()
    project = world.projects.add(edl=None)
    return (
        world.transcribe(project),
        'The project has no saved timeline to transcribe; save one first.',
    )


def timeline_unplayable(world):
    world.an_engine()
    edl = {'clips': [{'type': 'audio', 'name': 'videos/gone.wav', 'duration': 1.0}]}
    project = world.projects.add(edl=edl)
    return (
        world.transcribe(project),
        f'The saved timeline cannot be played: {refused_edl(edl)}',
    )


def timeline_silent(world):
    world.an_engine()
    project = world.projects.add(edl=TEMPLATE_EDL)
    return world.transcribe(project), (
        'The timeline has no video or audio clips, so there is nothing to transcribe.'
    )


def transcription_running(world):
    world.an_engine()
    project = world.projects.add(edl=TALK)
    world.projects.claims = False
    return world.transcribe(project), (
        "This project's timeline is already being transcribed; wait for that to "
        'finish.'
    )


def transcription_not_queued(world):
    world.an_engine()
    world.transcriptions = BrokerDown()
    project = world.projects.add(edl=TALK)
    res = world.transcribe(project)
    assert world.projects.projects[project]['captions_job']['state'] == 'failed'
    return res, 'The transcription could not be queued: [Errno 111] Connection refused'


def encoder_options_refused(world):
    res = world.client.post('/render', json=render_request(bitrate=['5000k']))
    return res, (
        f'bitrate cannot be set by a client; choose a quality instead: '
        f'{", ".join(QUALITIES)}'
    )


def frame_size_out_of_range(world):
    res = world.client.post('/render', json=render_request(width=9000))
    return res, 'width must be between 16 and 7680 pixels'


def fps_out_of_range(world):
    res = world.client.post('/render', json=render_request(fps=500))
    return res, 'fps must be between 1 and 120 frames per second'


def unknown_quality(world):
    res = world.client.post('/render', json=render_request(quality='ultra'))
    return res, f"quality must be one of {', '.join(QUALITIES)}, not 'ultra'"


def edl_refused(world):
    edl = {'clips': [{'type': 'template', 'name': 'rgbToDec', 'duration': 1.0}]}
    res = world.client.post('/render', json=render_request(edl=edl))
    return res, refused_edl(edl)


def render_not_queued(world):
    world.broker_down()
    res = world.client.post('/render', json=render_request())
    (render,) = world.renders.renders.values()
    reason = 'ConnectionError: [Errno 111] Connection refused'
    assert (render.status, render.error) == ('failed', f'could not be queued: {reason}')
    return res, f'The render could not be queued: {reason}'


def render_not_finished(world):
    render = make_render()
    world.renders.renders[render.id] = render
    return world.deliver(render, 'local'), 'That render has no output file yet'


def destination_unknown(world):
    render = world.finished_render()
    return (
        world.deliver(render, 'nowhere'),
        "unknown destination 'nowhere'; known: ['bucket', 'local']",
    )


def delivery_failed(world):
    def refuse(*args, **kwargs):
        raise OSError('no credentials')

    world.monkeypatch.setattr(bucket, 'upload', refuse)
    render = world.finished_render()
    return world.deliver(render, 'bucket'), 'upload failed: no credentials'


def delivered_without_link(world):
    world.uploads_accepted()
    world.no_signing()
    render = world.finished_render()
    return (
        world.deliver(render, 'bucket'),
        'The render was uploaded, but no link to it could be signed',
    )


def cloud_link_unavailable(world):
    world.no_signing()
    render = world.finished_render()
    return (
        world.client.get(f'/render/{render.id}'),
        'No cloud link is available for this render',
    )


def unknown_feature(world):
    return world.sound_of('talk.wav', features='tempo,key'), (
        f'key: not a feature; ask for any of {", ".join(audio_engine.FEATURES)}'
    )


def media_silent(world):
    (Path(config.VIDEO_DIR) / 'still.png').write_bytes(b'not really a picture')
    return world.sound_of('still.png'), 'videos/still.png is an image: it has no sound'


def unknown_operation(world):
    res = world.client.post(
        '/recipes', json={'name': 'mine', 'steps': [{'op': 'shuffle'}]}
    )
    return res, (
        "step 1: 'shuffle' is not an operation; the operations are "
        + ', '.join(OPERATIONS)
    )


def recipe_refused(world):
    res = world.client.post(
        '/recipes', json={'name': 'mine', 'steps': [{'op': 'top', 'count': 0}]}
    )
    return res, 'step 1 (top): count: 0 is below 1'


def unknown_recipe(world):
    res = world.client.get('/recipes/nowhere')
    return res, (
        "No recipe is named 'nowhere': the built-in ones are "
        + ', '.join(BY_NAME)
        + ', and yours are listed by GET /recipes.'
    )


def no_words(world):
    project = world.projects.add(edl={'clips': []})
    res = world.client.post(
        f'/project/{project}/drafts', json={'recipes': [{'recipe': 'highlights'}]}
    )
    return res, 'The project has no words to cut by: transcribe its timeline first.'


def drafts_running(world):
    project = world.projects.add(
        words=[{'start': 0, 'end': 1, 'text': 'hi'}], drafts_job={'state': 'running'}
    )
    res = world.client.post(
        f'/project/{project}/drafts', json={'recipes': [{'recipe': 'highlights'}]}
    )
    return (
        res,
        'Recipes are already running over this project; wait for them to finish.',
    )


def drafts_not_queued(world):
    project = world.projects.add(words=[{'start': 0, 'end': 1, 'text': 'hi'}])
    app.dependency_overrides[draft_routes.get_drafts_queue] = lambda: BrokerDown()
    res = world.client.post(
        f'/project/{project}/drafts', json={'recipes': [{'recipe': 'highlights'}]}
    )
    return res, 'The run could not be queued: [Errno 111] Connection refused'


def not_a_draft(world):
    project = world.projects.add()
    res = world.client.request(
        'DELETE', f'/project/{project}/drafts', json={'drafts': ['not-an-id']}
    )
    return res, "'not-an-id' is not the id of a draft."


def no_picture(world):
    (Path(config.VIDEO_DIR) / 'still.png').write_bytes(b'not really a picture')
    return world.client.get('/media/videos/still.png/motion'), (
        'videos/still.png is an image: it has no moving picture'
    )


def picture_unreadable(world):
    why = 'ffmpeg could not read the picture of talk.mp4: moov atom not found'

    def fail(path):
        raise FFmpegException(why)

    world.monkeypatch.setattr(measures, 'measure', fail)
    (Path(config.VIDEO_DIR) / 'talk.mp4').write_bytes(b'not really a video')
    return world.client.get('/media/videos/talk.mp4/motion'), why


def audio_engine_refused(world):
    why = 'the audio engine at http://engine.test:1059: it refused this (415): no'
    world.engine_says(audio_engine.AudioEngineRefused(why))
    return world.sound_of('talk.wav'), why


def audio_engine_failed(world):
    why = 'the audio engine at http://engine.test:1059: it failed (500): broke'
    world.engine_says(audio_engine.AudioEngineFailed(why))
    return world.sound_of('talk.wav'), why


def previews_busy(world):
    """Every slot taken -- the one there is, by the test -- so the preview
    waits its turn, which does not come, and is turned away."""
    world.monkeypatch.setattr(config, 'PREVIEW_CONCURRENCY', 1)
    world.monkeypatch.setattr(config, 'PREVIEW_WAIT', 0.05)
    asyncio.run(concurrency.previews.acquire())
    try:
        res = preview_requests()['a template frame'](world.client)
    finally:
        concurrency.previews.release()
    assert concurrency.previews.use() == concurrency.Use(0, 0, 1)
    assert res.headers['retry-after'] == str(RETRY_AFTER)
    return res, (
        'The server is already drawing as many previews as it will (1 at once); '
        f'ask again in {RETRY_AFTER} seconds.'
    )


def mail_not_configured(world):
    world.mail(configured=False)
    return world.report(), support_mail.NOT_CONFIGURED


def mail_not_queued(world):
    world.mail()
    world.broker_down()
    return world.report(), 'The mail could not be queued; try again later.'


REQUESTS = {
    Code.INVALID_ID: invalid_id,
    Code.NOT_FOUND: not_found,
    Code.CAPTION_FILE_UNREADABLE: caption_file_unreadable,
    Code.AUDIO_ENGINE_MISSING: audio_engine_missing,
    Code.TIMELINE_EMPTY: timeline_empty,
    Code.TIMELINE_UNPLAYABLE: timeline_unplayable,
    Code.TIMELINE_SILENT: timeline_silent,
    Code.TRANSCRIPTION_RUNNING: transcription_running,
    Code.TRANSCRIPTION_NOT_QUEUED: transcription_not_queued,
    Code.TOO_MANY_CUES: too_many_cues,
    Code.ENCODER_OPTIONS_REFUSED: encoder_options_refused,
    Code.FRAME_SIZE_OUT_OF_RANGE: frame_size_out_of_range,
    Code.FPS_OUT_OF_RANGE: fps_out_of_range,
    Code.UNKNOWN_QUALITY: unknown_quality,
    Code.EDL_REFUSED: edl_refused,
    Code.RENDER_NOT_QUEUED: render_not_queued,
    Code.RENDER_NOT_FINISHED: render_not_finished,
    Code.DESTINATION_UNKNOWN: destination_unknown,
    Code.DELIVERY_FAILED: delivery_failed,
    Code.DELIVERED_WITHOUT_LINK: delivered_without_link,
    Code.CLOUD_LINK_UNAVAILABLE: cloud_link_unavailable,
    Code.UNKNOWN_FEATURE: unknown_feature,
    Code.MEDIA_NAME_REFUSED: media_name_refused,
    Code.MEDIA_EXISTS: media_exists,
    Code.MEDIA_TOO_LARGE: media_too_large,
    Code.MEDIA_SILENT: media_silent,
    Code.UNKNOWN_OPERATION: unknown_operation,
    Code.RECIPE_REFUSED: recipe_refused,
    Code.UNKNOWN_RECIPE: unknown_recipe,
    Code.NO_WORDS: no_words,
    Code.DRAFTS_RUNNING: drafts_running,
    Code.DRAFTS_NOT_QUEUED: drafts_not_queued,
    Code.NOT_A_DRAFT: not_a_draft,
    Code.NO_PICTURE: no_picture,
    Code.PICTURE_UNREADABLE: picture_unreadable,
    Code.AUDIO_ENGINE_REFUSED: audio_engine_refused,
    Code.AUDIO_ENGINE_FAILED: audio_engine_failed,
    Code.PREVIEWS_BUSY: previews_busy,
    Code.MAIL_NOT_CONFIGURED: mail_not_configured,
    Code.MAIL_NOT_QUEUED: mail_not_queued,
}


def test_every_code_has_a_request_that_is_answered_with_it():
    """A code nothing answers is a promise nobody keeps; a code with no
    request here is one nothing checks."""
    assert set(REQUESTS) == set(Code)


@pytest.mark.parametrize('code', list(Code), ids=[code.value for code in Code])
def test_the_request_is_answered_with_the_code_and_the_sentence(world, code):
    """Mutation: answer any of them with another code, another status, or a
    detail that is not the sentence -- red."""
    res, sentence = REQUESTS[code](world)
    assert res.status_code == REFUSALS[code].status, res.text
    assert res.json() == {'detail': sentence, 'code': code.value}


def test_a_request_fastapi_refuses_carries_no_code(world):
    """A body its model refuses is FastAPI's 422, whose `detail` list says
    where and what; alfred adds nothing to it."""
    res = world.client.post('/render', json={'width': 'wide'})
    assert res.status_code == 422
    assert set(res.json()) == {'detail'} and isinstance(res.json()['detail'], list)


def test_a_route_alfred_does_not_have_carries_no_code(world):
    """FastAPI's own 404, which a client tells from alfred's `not_found` by
    the code that is not there."""
    res = world.client.get('/render/a/b/c/d')
    assert (res.status_code, res.json()) == (404, {'detail': 'Not Found'})
