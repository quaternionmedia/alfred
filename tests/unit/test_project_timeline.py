"""A project can carry a timeline, and one seeded project does.

`OttoTimeline` has always opened a project with `Edl.edl = e.edl`, and the
Project model has never had an `edl` field, so the value was always undefined
and the timeline always empty. There was nothing wrong with the editor: it was
asking for something the API could not return.

Two things had to be true before the timeline could show anything, and both are
pinned here -- the field exists, and something seeded uses it.
"""

from typing import Optional

import pytest
from otto.config import defaults
from otto.models import Edl

from alfred.core.models import Project
from alfred.core.routes.demo import _demo_project_document
from alfred.seed import seed

DEMO = 'Timeline demo'


def _contrast_on_black(colour):
    """The WCAG contrast ratio of a '#rrggbb' colour against black."""
    channels = [int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = (
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels
    )
    return (0.2126 * r + 0.7152 * g + 0.0722 * b + 0.05) / 0.05


@pytest.mark.parametrize(
    'timeline',
    [
        next(p for p in seed if p.get('name') == DEMO)['edl'],
        _demo_project_document(owner='someone@example.com')['edl'],
    ],
    ids=['seeded Timeline demo', 'generated Demo'],
)
def test_the_demo_text_shows_on_the_black_it_is_drawn_over(timeline):
    """Nothing is behind the demos' text but the frame, which is black.

    It was #101820, a contrast of about 1.2 to 1: the first thing a new user
    rendered was a video whose words could not be read. 4.5 is WCAG's AA.
    """
    for clip in timeline['clips']:
        data = clip.get('data') or {}
        if data.get('text'):
            colour = data.get('color') or defaults['fontcolor']
            assert _contrast_on_black(colour) >= 4.5, f'{clip["name"]}: {colour}'


class TestTheModelCanHoldATimeline:
    def test_project_declares_an_edl_field(self):
        assert 'edl' in Project.model_fields, (
            'Project has no edl field, so `project.edl` is undefined and the '
            'timeline editor has nothing to open'
        )

    def test_the_edl_field_is_optional(self):
        """Projects predating the timeline must stay valid.

        The three original seeded projects carry logic and fields and no
        timeline -- they drive the form flow, where clips are compiled from a
        filled-in form at render time. Requiring an edl would invalidate every
        one of them.
        """
        assert not Project.model_fields['edl'].is_required()

    def test_the_edl_field_uses_the_same_type_as_render(self):
        """One shape for an EDL across the API, not two.

        Render already models its edl with otto's type. A project using a
        different shape for the same document would mean converting between
        them on the way to a render, which is where the frontend's own
        `Edl.edl`-is-a-clips-array confusion came from.
        """
        from alfred.core.models.render import Render

        render_edl = Render.model_fields['edl'].annotation
        assert Project.model_fields['edl'].annotation == Optional[render_edl]


class TestTheSeedExercisesTheTimeline:
    def test_a_seeded_project_has_a_timeline(self):
        demo = [p for p in seed if p.get('name') == DEMO]
        assert demo, (
            f'no seeded project named {DEMO!r}. Without one, opening the '
            'timeline editor shows an empty timeline on every project and '
            'there is no way to tell a broken editor from an empty one.'
        )

    def test_the_seeded_timeline_validates_as_an_edl(self):
        demo = next(p for p in seed if p.get('name') == DEMO)
        edl = Edl(**demo['edl'])
        assert len(edl.clips) >= 2

    def test_the_seeded_timeline_needs_no_media_files(self):
        """`./al demo` must not be a prerequisite for opening the editor.

        Every clip is a template, so the demo renders from nothing on disk. A
        video clip here would make the project depend on downloaded media and
        fail confusingly on a fresh clone.
        """
        demo = next(p for p in seed if p.get('name') == DEMO)
        types = {c['type'] for c in demo['edl']['clips']}
        assert types == {'template'}, f'demo timeline uses non-template clips: {types}'

    def test_the_seeded_timeline_only_uses_allowlisted_templates(self):
        """A demo whose clips the preview endpoint would refuse is no demo.

        This previously also asserted the demo avoided `title`, which returned
        None on every call. That defect is fixed in otto, so the demo opens
        with `title` again -- whether each name renders is now
        test_template_rendering.py's job, and this only has to keep the demo
        inside what the API will serve.
        """
        from alfred.core.routes.templates import TEMPLATE_NAMES

        demo = next(p for p in seed if p.get('name') == DEMO)
        for clip in demo['edl']['clips']:
            assert clip['name'] in TEMPLATE_NAMES, (
                f'{clip["name"]} is not on the template allowlist, so the '
                'preview endpoint would refuse it'
            )

    def test_the_original_projects_still_have_no_timeline(self):
        """The form-driven projects are unchanged.

        Adding the field must not have quietly given them an empty timeline,
        which would make the editor offer a blank canvas for projects that are
        not edited that way.
        """
        others = [p for p in seed if p.get('name') != DEMO]
        assert others
        for project in others:
            assert project.get('edl') is None
