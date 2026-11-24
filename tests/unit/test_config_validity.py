"""IS-1 — config validity.

Pins the contract between configs the editor can emit and configs the backend
accepts, and makes the gap between them visible.

The editor enforces invariants in JS while the user drags (`website/src/
Clip.js`): `outpoint > inpoint`, and `inpoint >= 0`. The pydantic models
enforce none of them. Each gap below is pinned twice: a plain test asserting
what the code does today, so a silent change is caught, and a strict-xfail
asserting what it should do, so a fix turns the suite red.

No validators are added here. Rejecting configs the API currently accepts is
an API-visible behavior change and therefore a decision, recorded in
`governance/qm/adr/` rather than settled inside a test.
"""

import pytest
from beanie.exceptions import CollectionWasNotInitialized
from otto.exceptions import EdlException, EmptyClipsException
from otto.models import Clip, Edl
from otto.models import Render as OttoRender
from otto.render import generateEdl
from pydantic import ValidationError

from alfred.core.models.render import Render as RenderDoc
from tests.conftest import clip_dict, edl_dict, render_dict

# --- a realistic editing session ------------------------------------------
#
# Each entry is the EDL as it stands after one editor action. Built as dicts,
# which is the shape that actually arrives over HTTP.

SESSION = [
    (
        'add a clip',
        edl_dict([clip_dict()]),
    ),
    (
        'trim the in point',
        edl_dict([clip_dict(inpoint=1.5, duration=3.5)]),
    ),
    (
        'trim the out point',
        edl_dict([clip_dict(inpoint=1.5, outpoint=4.0, duration=2.5)]),
    ),
    (
        'move the clip later',
        edl_dict([clip_dict(inpoint=1.5, outpoint=4.0, duration=2.5, start=2.0)]),
    ),
    (
        'add a second clip',
        edl_dict(
            [
                clip_dict(inpoint=1.5, outpoint=4.0, duration=2.5, start=2.0),
                clip_dict(name='https://example.test/b.mp4', start=4.5),
            ]
        ),
    ),
    (
        'cut the second clip in two',
        edl_dict(
            [
                clip_dict(inpoint=1.5, outpoint=4.0, duration=2.5, start=2.0),
                clip_dict(
                    name='https://example.test/b.mp4',
                    start=4.5,
                    inpoint=0.0,
                    outpoint=2.0,
                    duration=2.0,
                ),
                clip_dict(
                    name='https://example.test/b.mp4',
                    start=6.5,
                    inpoint=2.0,
                    outpoint=5.0,
                    duration=3.0,
                ),
            ]
        ),
    ),
]

SESSION_IDS = [name for name, _ in SESSION]


@pytest.mark.parametrize('payload', [p for _, p in SESSION], ids=SESSION_IDS)
def test_every_editor_state_is_a_valid_edl(payload):
    """Each state the editor passes through validates as an Edl."""
    edl = Edl.model_validate(payload)
    assert len(edl.clips) == len(payload['clips'])


@pytest.mark.parametrize('payload', [p for _, p in SESSION], ids=SESSION_IDS)
def test_every_editor_state_round_trips(payload):
    """Serialising and reparsing an Edl is lossless."""
    edl = Edl.model_validate(payload)
    assert Edl.model_validate(edl.model_dump()) == edl


def test_final_state_is_a_valid_render_request():
    """The end of the session validates as a full render request."""
    _, final = SESSION[-1]
    render = OttoRender.model_validate({'edl': final})

    assert len(render.edl.clips) == 3
    assert render.width == 1920 and render.height == 1080
    assert render.fps == 30.0


def test_clips_stay_in_start_order_through_the_session():
    """A property of the session itself: cuts and moves never reorder starts."""
    _, final = SESSION[-1]
    starts = [c['start'] for c in final['clips']]
    assert starts == sorted(starts)


# --- documented defaults --------------------------------------------------


def test_clip_defaults_are_what_the_api_promises():
    clip = Clip()
    assert clip.duration == 5
    assert clip.fadeIn == 1
    assert clip.fadeOut == 1
    assert clip.relative is True


def test_render_defaults_are_what_the_api_promises():
    render = OttoRender.model_validate({'edl': edl_dict()})
    assert (render.width, render.height, render.fps) == (1920, 1080, 30.0)


def test_render_document_declares_the_same_defaults():
    """The persisted document agrees with the engine model on defaults.

    Read off the schema rather than an instance, because the document cannot
    be instantiated without a database — see below.
    """
    fields = RenderDoc.model_fields
    assert fields['width'].default == 1920
    assert fields['height'].default == 1080
    assert fields['fps'].default == 30.0


def test_nested_edl_is_validated_not_passed_through():
    """A malformed nested edl is rejected, not stored as an opaque blob."""
    with pytest.raises(ValidationError):
        OttoRender.model_validate({'edl': {'clips': 'not-a-list'}})


# --- validation is coupled to the database --------------------------------


def test_render_document_cannot_be_validated_without_a_database():
    """alfred's request schema cannot be validated in isolation.

    `Render` is a beanie `Document`, and `Document.__init__` calls
    `get_motor_collection()`, which needs settings that only `init_beanie`
    provides. So validating an incoming render request — deciding whether a
    payload is well-formed at all — requires a live MongoDB connection.

    That couples the API's input contract to its storage engine: the schema
    cannot be exercised, fuzzed, or checked in a unit test without standing up
    a database, and a validation-only code path pays a connection's cost.
    """
    with pytest.raises(CollectionWasNotInitialized):
        RenderDoc.model_validate(render_dict())


@pytest.mark.xfail(reason='request validation should not require a database connection')
def test_render_document_should_validate_standalone():
    render = RenderDoc.model_validate(render_dict())
    assert render.width == 1920


# --- invariants the editor enforces and the models do not -----------------
#
# Each pair: what happens today, then what should happen.


def test_inverted_in_out_point_is_accepted_today():
    clip = Clip.model_validate(clip_dict(inpoint=5.0, outpoint=1.0))
    assert clip.inpoint == 5.0 and clip.outpoint == 1.0


@pytest.mark.xfail(reason='model does not enforce outpoint > inpoint')
def test_inverted_in_out_point_should_be_rejected():
    with pytest.raises(ValidationError):
        Clip.model_validate(clip_dict(inpoint=5.0, outpoint=1.0))


def test_negative_inpoint_is_accepted_today():
    assert Clip.model_validate(clip_dict(inpoint=-3.0)).inpoint == -3.0


@pytest.mark.xfail(reason='model does not enforce inpoint >= 0')
def test_negative_inpoint_should_be_rejected():
    with pytest.raises(ValidationError):
        Clip.model_validate(clip_dict(inpoint=-3.0))


def test_non_positive_duration_is_accepted_today():
    assert Clip.model_validate(clip_dict(duration=-5.0)).duration == -5.0
    assert Clip.model_validate(clip_dict(duration=0.0)).duration == 0.0


@pytest.mark.xfail(reason='model does not enforce duration > 0')
def test_non_positive_duration_should_be_rejected():
    with pytest.raises(ValidationError):
        Clip.model_validate(clip_dict(duration=-5.0))


def test_out_of_range_opacity_is_accepted_today():
    assert Clip.model_validate(clip_dict(opacity=4.2)).opacity == 4.2


@pytest.mark.xfail(reason='model does not constrain opacity to 0..1')
def test_out_of_range_opacity_should_be_rejected():
    with pytest.raises(ValidationError):
        Clip.model_validate(clip_dict(opacity=4.2))


def test_non_positive_resize_is_accepted_today():
    assert Clip.model_validate(clip_dict(resize=0.0)).resize == 0.0


@pytest.mark.xfail(reason='model does not enforce resize > 0')
def test_non_positive_resize_should_be_rejected():
    with pytest.raises(ValidationError):
        Clip.model_validate(clip_dict(resize=0.0))


# --- the empty-EDL case, which fails late ---------------------------------


def test_empty_edl_is_accepted_by_the_model():
    """Accepted at the API boundary..."""
    assert Edl.model_validate(edl_dict(clips=[])).clips == []
    assert OttoRender.model_validate({'edl': edl_dict(clips=[])}).edl.clips == []


def test_empty_edl_is_only_rejected_at_render_time():
    """...and rejected only once a worker picks the job up.

    This is the sharpest case in this file: the config is refused after it has
    been persisted and dispatched, not when it was submitted.
    """
    with pytest.raises(EmptyClipsException):
        generateEdl(Edl(clips=[]))


@pytest.mark.parametrize(
    'overrides,field',
    [
        (dict(inpoint=5.0, outpoint=1.0), 'outpoint'),
        (dict(inpoint=-3.0), 'inpoint'),
        (dict(duration=-5.0, outpoint=None), 'duration'),
        (dict(opacity=4.2), 'opacity'),
        (dict(resize=0.0), 'resize'),
    ],
    ids=['inverted-in-out', 'negative-inpoint', 'duration', 'opacity', 'resize'],
)
def test_what_the_model_accepts_the_engine_refuses_at_render_time(overrides, field):
    """The invariants above have the empty EDL's shape now.

    Accepted at the API boundary, then refused by the engine, which names the
    clip and the field -- where it used to render nonsense or crash somewhere
    unrelated. A template clip, so nothing is fetched whatever order the
    engine checks things in.
    """
    template = dict(type='template', name='makeColor', data={'color': '#000000'})
    clip = Clip.model_validate(clip_dict(**template, **overrides))
    with pytest.raises(EdlException, match=rf"clip 1 \('makeColor'\): .*{field}"):
        generateEdl(Edl(clips=[clip]), moviesize=(64, 48))


@pytest.mark.xfail(reason='an empty clip list should be rejected at validation')
def test_empty_edl_should_be_rejected_at_validation():
    with pytest.raises(ValidationError):
        Edl.model_validate(edl_dict(clips=[]))
