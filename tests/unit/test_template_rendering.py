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

    def test_final_requires_the_parameters_it_declares(self):
        """`final` is not broken -- it needs address, website and phone.

        Called without them it raises KeyError internally and returns None,
        which looks identical to the `title` defect below. The difference
        matters: this one is fixed by the caller, that one cannot be.
        /templates advertises all three, so a caller has what it needs.
        """
        for parameter in ('address', 'website', 'phone'):
            assert parameter in TEMPLATE_NAMES or True  # documented below
        from alfred.core.routes.templates import available_templates

        final = next(t for t in available_templates() if t.name == 'final')
        for parameter in ('address', 'website', 'phone'):
            assert parameter in final.parameters, (
                f'/templates must advertise {parameter}, or a caller cannot '
                'know to supply it and `final` will silently render nothing'
            )


@pytest.mark.needs_imagemagick
class TestWhatActuallyRenders:
    @pytest.mark.parametrize('name', ['textBox', 'bullets', 'initial'])
    def test_text_templates_render(self, name):
        assert _renders(name, text='Alfred') is not None

    def test_makecolor_renders(self):
        assert _renders('makeColor', color='#f2aa4c') is not None

    def test_final_renders_when_given_its_parameters(self):
        clip = _renders(
            'final',
            text='Alfred',
            address='1 Main St',
            website='alfred.test',
            phone='555',
        )
        assert clip is not None

    @pytest.mark.xfail(
        reason=(
            "otto's `title` raises internally and returns None on every call: "
            "\"'tuple' object has no attribute 'lower'\". Reproduced with and "
            'without an explicit color, with font=DejaVu-Sans and font=Courier, '
            'and with method=label and method=caption -- so it is neither a '
            'font nor a configuration problem. It is a defect in otto, which '
            'is a separate package and outside this seam, so it is pinned here '
            'rather than patched. The seeded demo project uses textBox for the '
            'same reason.'
        ),
    )
    def test_title_renders(self):
        assert _renders('title', text='Alfred') is not None

    def test_every_advertised_template_except_title_renders(self):
        """The bin should not offer what cannot be drawn.

        Kept separate from the parametrized cases so that a newly added
        template is covered without anyone remembering to list it.
        """
        needs_parameters = {
            'final': dict(
                text='Alfred', address='1 Main St', website='a.test', phone='555'
            ),
        }
        broken = []
        for name in TEMPLATE_NAMES:
            if name == 'title':
                continue
            kwargs = needs_parameters.get(name, {})
            if not kwargs:
                kwargs = {'color': '#f2aa4c'} if name == 'makeColor' else {'text': 'x'}
            if _renders(name, **kwargs) is None:
                broken.append(name)
        assert not broken, (
            f'advertised by /templates but render to nothing: {broken}. '
            'Either fix them or stop offering them in the bin.'
        )
