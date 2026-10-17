"""IS-2 — input selection.

How a clip resolves to a source, and what happens when it cannot.

No network and no filesystem: `otto.getdata.head`, `download_url` and
`path.isfile` are all substituted.
"""

import pytest
from otto import getdata
from otto.exceptions import DownloadException, EdlException
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
        # Judged by its media type: a parameter does not make it another type.
        ('video/mp4; charset=binary', 'mp4'),
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


# --- download: the refusals -----------------------------------------------
#
# Each refusal raises DownloadException, an EdlException, naming the URL and
# the reason. They used to end in a bare `except Exception` that printed and
# returned None, so a caller could not tell "refused" from "succeeded with
# nothing".

REJECTIONS = [
    pytest.param({'content_type': 'text/html'}, 'not allowed', id='html'),
    pytest.param({'content_type': 'text/plain'}, 'not allowed', id='text'),
    pytest.param(
        {'content_type': 'application/zip'}, 'not allowed', id='not-on-allowlist'
    ),
    pytest.param({'content_length': str(int(2e10))}, 'too large', id='too-large'),
    pytest.param({'content_type': None}, 'no content_type', id='no-content-type'),
    pytest.param(
        {'content_length': None}, 'size must be known', id='no-content-length'
    ),
]


@pytest.mark.parametrize('response,reason', REJECTIONS)
def test_a_refused_download_raises_naming_the_url_and_the_reason(
    response, reason, fake_head, recorded_downloads, monkeypatch
):
    monkeypatch.setattr(getdata.path, 'isfile', lambda _: False)
    fake_head(**response)

    with pytest.raises(DownloadException, match=reason) as refused:
        getdata.download('https://example.test/bad')

    assert 'https://example.test/bad' in str(refused.value)
    assert recorded_downloads == [], 'a refused file was fetched anyway'


def test_a_refused_download_stops_the_render_at_its_clip(
    fake_head, recorded_downloads, monkeypatch
):
    """The render stops at the clip, saying which clip, which URL and why.

    A refused download used to become the clip's file name -- None -- and the
    render failed later in the clip constructor, naming neither the URL nor
    the reason. The clip's `name` is also left as the caller wrote it; the
    engine used to overwrite it with the downloaded path.
    """
    monkeypatch.setattr(getdata.path, 'isfile', lambda _: False)
    fake_head(content_type='text/html')

    clip = Clip(type='video', name='https://example.test/bad', duration=1)
    with pytest.raises(EdlException, match='not allowed') as refused:
        generateEdl(Edl(clips=[clip]), moviesize=(64, 48))

    assert "clip 0 ('https://example.test/bad')" in str(refused.value)
    assert clip.name == 'https://example.test/bad'


# --- clip type dispatch ---------------------------------------------------
#
# `generateEdl` dispatched on clip.type through if/elif with no else, so an
# unknown type crashed the first clip with UnboundLocalError and, on any later
# clip, silently became a copy of the previous clip's picture. Both are
# refused now, naming the clip.


def _template_clip(duration=1.0, color='#ff0000'):
    return Clip(
        type='template',
        name='makeColor',
        duration=duration,
        data=TemplateData(color=color),
    )


def test_an_unknown_clip_type_is_refused_naming_the_clip():
    with pytest.raises(EdlException, match=r"clip 0 \('x'\): unknown clip type"):
        generateEdl(Edl(clips=[Clip(type='bogus', name='x', duration=1)]))


def test_an_unknown_clip_type_after_a_valid_clip_is_refused_not_duplicated():
    """This was the most damaging case, because it was silent.

    The bad clip became a second layer carrying the previous clip's picture,
    retimed to its own duration: no exception, no log line, and a rendered
    video with a frame nobody asked for.
    """
    edl = Edl(
        clips=[
            _template_clip(duration=1.0),
            Clip(type='bogus', name='x', duration=4.0),
        ]
    )
    with pytest.raises(EdlException, match=r"clip 1 \('x'\): unknown clip type"):
        generateEdl(edl, moviesize=(64, 48))


def test_a_missing_clip_type_is_refused_like_an_unknown_one():
    """`type` is Optional, so omitting it reaches the same check."""
    with pytest.raises(EdlException, match='unknown clip type None'):
        generateEdl(Edl(clips=[Clip(name='x', duration=1)]))


# --- template resolution --------------------------------------------------
#
# A template clip's name is looked up in otto's registry,
# `otto.templates.TEMPLATES`, and nowhere else. It was
# `getattr(templates, clip.name)`: AttributeError for an unknown name, and for
# a known one, anything the module happens to hold.


def test_an_unknown_template_name_is_refused_naming_the_clip():
    clip = Clip(
        type='template', name='no_such_template', duration=1, data=TemplateData()
    )
    with pytest.raises(
        EdlException, match=r"clip 0 \('no_such_template'\): no template is named"
    ):
        generateEdl(Edl(clips=[clip]), moviesize=(64, 48))


@pytest.mark.parametrize(
    'name', ['concatenate_videoclips', 'rgbToDec', 'ColorClip', 'TextClip']
)
def test_what_the_template_module_imports_is_not_a_template(name):
    """Still in `otto.templates`' namespace; no longer reachable from a clip."""
    from otto import templates

    assert callable(getattr(templates, name, None)), (
        f'{name} has left otto.templates, so this case no longer shows '
        'anything -- pick a helper the module still imports'
    )
    clip = Clip(type='template', name=name, duration=1, data=TemplateData())
    with pytest.raises(EdlException, match='no template is named'):
        generateEdl(Edl(clips=[clip]), moviesize=(64, 48))
