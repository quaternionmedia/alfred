"""Which templates actually produce a clip.

The editor's template bin and the preview endpoint both offer the templates on
alfred's allowlist. Offering one that cannot render is worse than not offering
it. otto's templates raise when they cannot be built, and generateEdl re-raises
that as an EdlException naming the clip, the template and the cause -- so a
failure here reads as its reason. They used to catch their own exceptions and
return None, and the engine said only that a clip "did not get made properly".

Rendering text needs ImageMagick with a font ImageMagick can find, which is a
property of the environment rather than of this code. The `needs_imagemagick`
marker covers that, and `conftest.py` skips rather than errors when it is
absent. Everything above the marked class is environment-free.
"""

import pytest
from otto import templates
from otto.exceptions import EdlException
from otto.models import Clip, Edl, TemplateData
from otto.render import generateEdl

from alfred.core.routes.templates import TEMPLATE_NAMES

SIZE = (320, 180)


def _frame(name, **kwargs):
    """Build a template from otto's registry the way generateEdl does, and
    draw a frame of it: building one does not run every drawing call.

    Three seconds, because `bullets` gives a one-word bullet three and leaves
    out a bullet that does not fit -- shorter, there would be nothing to draw.
    """
    clip = templates.TEMPLATES[name](clipsize=SIZE, duration=3.0, **kwargs)
    return clip.get_frame(1.5)


class TestTheContractWithoutRendering:
    def test_a_template_that_cannot_be_built_is_refused_with_its_reason(self):
        """The refusal names the clip, the template and what went wrong.

        `title` with no `text` fails before anything is drawn, so this needs
        no ImageMagick.
        """
        clip = Clip(type='template', name='title', duration=1, data=TemplateData())
        with pytest.raises(EdlException, match=r"clip 1 \('title'\)") as refused:
            generateEdl(Edl(clips=[clip]), moviesize=(64, 48))

        assert "template 'title' could not be built" in str(refused.value)
        assert "'text'" in str(refused.value), 'the missing argument is not named'

    def test_final_is_not_advertised_because_a_clip_cannot_fill_it_in(self):
        """The template whose details a clip cannot carry.

        `final` draws a headline, an address, a website and a phone number.
        The engine renders it without the last three -- the address and
        website fall back to otto's defaults, and the phone is left out -- but
        TemplateData, the only shape a clip's `data` can take, models none of
        them, and pydantic drops unknown keys silently. So through an EDL or
        the preview endpoint, `final` could only ever show otto's placeholder
        address and website.
        """
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
        assert _frame(name, text='Alfred').shape[:2] == SIZE[::-1]

    def test_makecolor_renders(self):
        assert _frame('makeColor', color='#f2aa4c').shape[:2] == SIZE[::-1]

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
        assert _frame('title', text='Alfred').shape[:2] == SIZE[::-1]

    def test_every_advertised_template_renders(self):
        """The bin should not offer what cannot be drawn.

        Kept separate from the parametrized cases so that a newly added
        template is covered without anyone remembering to list it. Every
        failure is collected, with its reason, rather than stopping at the
        first.
        """
        broken = {}
        for name in TEMPLATE_NAMES:
            kwargs = {'color': '#f2aa4c'} if name == 'makeColor' else {'text': 'x'}
            try:
                _frame(name, **kwargs)
            except Exception as exc:
                broken[name] = f'{type(exc).__name__}: {exc}'
        assert not broken, (
            f'advertised by /templates but cannot be drawn: {broken}. '
            'Either fix them or stop offering them in the bin.'
        )
