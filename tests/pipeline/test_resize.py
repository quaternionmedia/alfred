"""The resize path, on the Pillow the lockfile installs.

moviepy 1.0.3 resizes with `Image.ANTIALIAS`, which Pillow 10 removed, so this
project pinned Pillow 9.5 -- and with it every advisory filed against Pillow
since. The engine gives the name back when Pillow lacks it
(alfred/otto/otto/__init__.py). These run that path for real: a clip's
`resize`, drawn and then encoded. On a Pillow without the name and without the
engine's shim, both fail with AttributeError.

The text templates resize too (`bullets` scales its text into place), and
test_template_rendering.py draws those wherever ImageMagick can.
"""

import PIL
import pytest
from otto.models import Clip, Edl, TemplateData
from otto.render import generateEdl, renderMultitrack
from PIL import Image


def red(**overrides):
    attrs = dict(
        type='template',
        name='makeColor',
        duration=1.0,
        fadeIn=0,
        fadeOut=0,
        data=TemplateData(color='#ff0000'),
    )
    attrs.update(overrides)
    return Clip(**attrs)


def test_antialias_names_lanczos():
    """Pillow 10 and later have no ANTIALIAS; there, this is the engine's doing."""
    assert Image.ANTIALIAS == Image.LANCZOS, f'Pillow {PIL.__version__}'


def test_a_resized_clip_is_drawn_at_its_new_size():
    video = generateEdl(Edl(clips=[red(resize=0.5)]), moviesize=(64, 48))

    layer = video.clips[0]

    assert layer.get_frame(0).shape[:2] == (24, 32)


@pytest.mark.needs_ffmpeg
def test_a_resized_clip_encodes_where_its_size_says(tmp_path):
    """Half the frame red, at the top left, and the rest of it black.

    A template clip has no position unless it is given one, so the resized
    layer sits at the origin: the encode shows the resize happened, not only
    that a file came out.
    """
    from moviepy.video.io.VideoFileClip import VideoFileClip

    out = tmp_path / 'resized.mp4'
    renderMultitrack(
        Edl(clips=[red(resize=0.5)], duration=1.0),
        filename=str(out),
        moviesize=(320, 240),
        logger=None,
        ffmpeg_params=['-preset', 'ultrafast'],
    )

    with VideoFileClip(str(out)) as produced:
        assert tuple(produced.size) == (320, 240)
        frame = produced.get_frame(0.5)
    inside, outside = frame[60, 80], frame[180, 240]
    assert inside[0] > 150 and inside[1] < 80, f'not red inside: {inside}'
    assert max(outside) < 60, f'not black outside: {outside}'
