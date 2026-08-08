"""Which templates actually produce a clip, and which only claim to.

The editor's template bin and the preview endpoint both offer six templates.
Offering one that cannot render is worse than not offering it, because the
failure surfaces as otto's `EdlException('A clip did not get made properly')`
-- a message that names neither the template nor the reason.

Rendering text needs ImageMagick with a font ImageMagick can find, which is a
property of the environment rather than of this code. The `needs_imagemagick`
marker covers that, and `conftest.py` skips rather than errors when it is
absent. Everything above the marked class is environment-free.
"""

import pytest

from otto import templates

from alfred.core.routes.templates import TEMPLATE_NAMES


def _renders(name, **kwargs):
    """Call a template the way generateEdl does, and report the outcome.

    otto catches its own exceptions and returns None, so a caller cannot tell
    a failure from a success without checking the return value -- which is
    exactly how `title` failing went unnoticed.
    """
    fn = getattr(templates, name)
    return fn(clipsize=(320, 180), duration=1.0, **kwargs)


class TestTheContractWithoutRendering:
    def test_templates_swallow_their_own_errors(self):
        """Why every check here is `is not None` rather than `pytest.raises`.

        otto's template functions catch internally and return None. A caller
        gets no exception and no clip, and generateEdl only notices one frame
        later, when it reports that some clip "did not get made properly".
        This test states that contract so the assertions below read as
        deliberate rather than lazy.
        """
        result = _renders('title', text='anything')
        assert result is None or hasattr(result, 'size')

    def test_final_is_not_advertised_because_it_cannot_be_driven(self):
        """The template that needs parameters a clip cannot carry.

        `final` raises KeyError without address, website and phone, and
        TemplateData -- the only shape a clip's `data` can take -- models none
        of them. Pydantic drops unknown keys silently, so no caller can supply
        them through an EDL or the preview endpoint. Advertising it would mean
        every attempt failing as "A clip did not get made properly", which
        reads as a bug in the caller's data rather than a gap in the model.
        """
        from otto.models import TemplateData

        from alfred.core.routes.templates import UNDRIVABLE_TEMPLATES

        assert 'final' in UNDRIVABLE_TEMPLATES
        assert 'final' not in TEMPLATE_NAMES

        carried = TemplateData(
            text='x', address='1 Main', website='a.test', phone='555'
        ).dict(exclude_none=True)
        for parameter in ('address', 'website', 'phone'):
            assert parameter not in carried, (
                f'TemplateData now carries {parameter}, so `final` may be '
                'drivable -- re-check whether it belongs on the allowlist'
            )


@pytest.mark.needs_imagemagick
class TestWhatActuallyRenders:
    @pytest.mark.parametrize('name', ['textBox', 'bullets', 'initial'])
    def test_text_templates_render(self, name):
        assert _renders(name, text='Alfred') is not None

    def test_makecolor_renders(self):
        assert _renders('makeColor', color='#f2aa4c') is not None

    def test_title_renders(self):
        """Was a strict xfail: `title` returned None on every call.

        makeColor accepted only a '#rrggbb' string and passed it to PIL's
        getcolor, which calls .lower() on it -- while `title` passed the tuple
        (0, 0, 0) with no background colour and rgbToDec's list of 0-1 floats
        with one. Both branches raised, so there was no argument for which
        `title` worked. otto swallowed the traceback in its own `except` and
        returned None, and generateEdl reported that one frame later as "A clip
        did not get made properly".

        Fixed in otto by normalising the colour in makeColor rather than
        patching the one caller that was noticed.
        """
        assert _renders('title', text='Alfred') is not None

    def test_every_advertised_template_renders(self):
        """The bin should not offer what cannot be drawn.

        Kept separate from the parametrized cases so that a newly added
        template is covered without anyone remembering to list it. `title` used
        to be excepted here; it no longer is, which is the whole point.
        """
        broken = []
        for name in TEMPLATE_NAMES:
            kwargs = {'color': '#f2aa4c'} if name == 'makeColor' else {'text': 'x'}
            if _renders(name, **kwargs) is None:
                broken.append(name)
        assert not broken, (
            f'advertised by /templates but render to nothing: {broken}. '
            'Either fix them or stop offering them in the bin.'
        )
