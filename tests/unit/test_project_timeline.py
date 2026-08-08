"""A project can carry a timeline, and one seeded project does.

`OttoTimeline` has always opened a project with `Edl.edl = e.edl`, and the
Project model has never had an `edl` field, so the value was always undefined
and the timeline always empty. There was nothing wrong with the editor: it was
asking for something the API could not return.

Two things had to be true before the timeline could show anything, and both are
pinned here -- the field exists, and something seeded uses it.
"""

from otto.models import Edl

from alfred.core.models import Project
from alfred.seed import seed

DEMO = 'Timeline demo'


class TestTheModelCanHoldATimeline:
    def test_project_declares_an_edl_field(self):
        assert 'edl' in Project.__fields__, (
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
        assert not Project.__fields__['edl'].required

    def test_the_edl_field_uses_the_same_type_as_render(self):
        """One shape for an EDL across the API, not two.

        Render already models its edl with otto's type. A project using a
        different shape for the same document would mean converting between
        them on the way to a render, which is where the frontend's own
        `Edl.edl`-is-a-clips-array confusion came from.
        """
        from alfred.core.models.render import Render

        assert Project.__fields__['edl'].type_ is Render.__fields__['edl'].type_


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

    def test_the_seeded_timeline_only_uses_templates_that_render(self):
        """Specifically: not `title`, which raises inside otto on every call.

        A demo project whose first clip cannot render is a worse demo than no
        demo at all -- it looks like the editor is broken.
        """
        from alfred.core.routes.templates import TEMPLATE_NAMES

        demo = next(p for p in seed if p.get('name') == DEMO)
        names = [c['name'] for c in demo['edl']['clips']]
        for name in names:
            assert name in TEMPLATE_NAMES, (
                f'{name} is not on the template allowlist, so the preview '
                'endpoint would refuse it'
            )
        assert 'title' not in names, (
            'the demo timeline uses `title`, which returns None on every call '
            '-- see the xfail in test_template_rendering.py'
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
