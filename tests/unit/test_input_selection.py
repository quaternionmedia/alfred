"""IS-2 — input selection.

How a clip resolves to a source, and what happens when it cannot.

No network and no filesystem: `otto.getdata.head`, `download_url` and
`path.isfile` are all substituted.
"""

import numpy as np
import pytest
from otto import getdata
from otto.exceptions import EdlException
from otto.models import Clip, Edl, TemplateData
from otto.render import generateEdl

# --- download: the happy paths --------------------------------------------


def test_local_path_is_returned_unchanged():
    """Anything not starting with http is treated as already local."""
    assert getdata.download('data/clip.mp4') == 'data/clip.mp4'
    assert getdata.download('/abs/clip.mp4') == '/abs/clip.mp4'


@pytest.mark.parametrize(
    'content_type,extension',
    [
        ('image/jpeg', 'jpg'),
        ('video/mp4', 'mp4'),
        ('image/png', 'png'),
        ('audio/mpeg', 'mp3'),
    ],
)
def test_allowed_content_types_map_to_extensions(
    content_type, extension, fake_head, recorded_downloads, monkeypatch
):
    monkeypatch.setattr(getdata.path, 'isfile', lambda _: False)
    fake_head(content_type=content_type)

    result = getdata.download('https://example.test/media')

    assert result.endswith(f'.{extension}')
    assert len(recorded_downloads) == 1


def test_downloads_are_content_addressed(fake_head, recorded_downloads, monkeypatch):
    """Same URL gives the same name; different URLs do not collide."""
    monkeypatch.setattr(getdata.path, 'isfile', lambda _: False)

    first = getdata.download('https://example.test/a.mp4')
    again = getdata.download('https://example.test/a.mp4')
    other = getdata.download('https://example.test/b.mp4')

    assert first == again
    assert first != other


def test_an_existing_file_is_not_downloaded_again(
    fake_head, recorded_downloads, monkeypatch
):
    monkeypatch.setattr(getdata.path, 'isfile', lambda _: True)

    result = getdata.download('https://example.test/a.mp4')

    assert result.endswith('.mp4')
    assert recorded_downloads == [], 'already-present file was fetched again'


# --- download: the rejections ---------------------------------------------
#
# Every rejection path ends in the same bare `except Exception` that prints
# and returns None, so a caller cannot tell "refused" from "succeeded with
# nothing". The pinning tests record that; the xfails record what it should be.

REJECTIONS = [
    pytest.param({'content_type': 'text/html'}, id='html'),
    pytest.param({'content_type': 'text/plain'}, id='text'),
    pytest.param({'content_type': 'application/zip'}, id='not-on-allowlist'),
    pytest.param({'content_length': str(int(2e10))}, id='too-large'),
    pytest.param({'content_type': None}, id='no-content-type'),
]


@pytest.mark.parametrize('response', REJECTIONS)
def test_rejected_downloads_return_none_today(
    response, fake_head, recorded_downloads, monkeypatch
):
    monkeypatch.setattr(getdata.path, 'isfile', lambda _: False)
    fake_head(**response)

    assert getdata.download('https://example.test/bad') is None
    assert recorded_downloads == []


@pytest.mark.parametrize('response', REJECTIONS)
@pytest.mark.xfail(reason='a refused download should raise, not return None')
def test_rejected_downloads_should_raise(
    response, fake_head, recorded_downloads, monkeypatch
):
    monkeypatch.setattr(getdata.path, 'isfile', lambda _: False)
    fake_head(**response)

    # `match`, not a bare `Exception`. otto raises undifferentiated
    # `Exception` for every refusal, so there is no type to name here -- but
    # matching the message still distinguishes "the download was refused" from
    # "this test called something that does not exist", which bare Exception
    # does not. Narrowing the type is otto's change to make, not this one's.
    with pytest.raises(Exception, match='not allowed|too large|no content_type'):
        getdata.download('https://example.test/bad')


def test_a_failed_download_hands_none_to_the_engine(
    fake_head, recorded_downloads, monkeypatch
):
    """The consequence: `clip.name` becomes None and the engine gets it.

    `generateEdl` assigns `clip.name = download(clip.name)` before constructing
    the source, so a refused download does not stop the render -- it feeds
    None into the clip constructor and fails there instead, with an error that
    names neither the URL nor the reason it was refused.
    """
    monkeypatch.setattr(getdata.path, 'isfile', lambda _: False)
    fake_head(content_type='text/html')

    clip = Clip(type='video', name='https://example.test/bad', duration=1)
    with pytest.raises(Exception) as excinfo:
        generateEdl(Edl(clips=[clip]), moviesize=(64, 48))

    assert 'example.test' not in str(excinfo.value)


# --- clip type dispatch ---------------------------------------------------
#
# `generateEdl` dispatches on clip.type through if/elif with no else, so when
# nothing matches `c` is never assigned. The `if not c:` guard below the chain
# was meant to catch this and cannot: the name is either unbound or left over
# from the previous iteration.


def _template_clip(duration=1.0, color='#ff0000'):
    return Clip(
        type='template',
        name='makeColor',
        duration=duration,
        data=TemplateData(color=color),
    )


def test_unknown_clip_type_alone_raises_unbound_local():
    """First clip: `c` is unbound, so the failure is an interpreter error."""
    with pytest.raises(UnboundLocalError):
        generateEdl(Edl(clips=[Clip(type='bogus', name='x', duration=1)]))


@pytest.mark.xfail(reason='an unknown clip type should raise EdlException')
def test_unknown_clip_type_alone_should_raise_edl_exception():
    with pytest.raises(EdlException):
        generateEdl(Edl(clips=[Clip(type='bogus', name='x', duration=1)]))


def test_unknown_clip_type_after_a_valid_clip_silently_duplicates_it():
    """Later clip: `c` still holds the previous clip, so nothing raises.

    The bad clip becomes a second layer carrying the *previous* clip's
    picture, re-timed to the bad clip's own duration. No exception, no log
    line, and the rendered video contains a frame nobody asked for.

    This is the most damaging behavior covered in this file, because unlike
    the unbound case it is completely silent.
    """
    edl = Edl(
        clips=[
            _template_clip(duration=1.0),
            Clip(type='bogus', name='x', duration=4.0),
        ]
    )

    video = generateEdl(edl, moviesize=(64, 48))

    assert len(video.clips) == 2, 'the unknown clip still produced a layer'
    first, second = video.clips
    assert np.array_equal(
        first.get_frame(0), second.get_frame(0)
    ), 'expected the stale clip to be reused'
    assert second.duration == 4.0, 'stale picture, bad clip timing'


@pytest.mark.xfail(reason='an unknown clip type should raise, not duplicate')
def test_unknown_clip_type_after_a_valid_clip_should_raise():
    edl = Edl(
        clips=[
            _template_clip(duration=1.0),
            Clip(type='bogus', name='x', duration=4.0),
        ]
    )
    with pytest.raises(EdlException):
        generateEdl(edl, moviesize=(64, 48))


def test_missing_clip_type_behaves_the_same_as_an_unknown_one():
    """`type` is Optional, so omitting it reaches the same dead end."""
    with pytest.raises(UnboundLocalError):
        generateEdl(Edl(clips=[Clip(name='x', duration=1)]))


# --- template resolution --------------------------------------------------


def test_unknown_template_name_raises_attribute_error():
    clip = Clip(type='template', name='no_such_template', duration=1)
    with pytest.raises(AttributeError):
        generateEdl(Edl(clips=[clip]), moviesize=(64, 48))


def test_template_lookup_reaches_any_module_attribute():
    """`getattr(templates, clip.name)` is not restricted to templates.

    `otto.templates` imports helpers into its namespace, so a caller-supplied
    name resolves to things that were never meant to be reachable as
    templates. Pinned here so that narrowing the lookup to a registry is a
    visible change rather than a silent one.
    """
    from otto import templates

    for name in ('concatenate_videoclips', 'rgbToDec'):
        assert callable(
            getattr(templates, name, None)
        ), f'{name} is reachable via the template lookup'
