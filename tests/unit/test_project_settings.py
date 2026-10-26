"""A project remembers how it renders and where its output goes.

This is what makes the four-stage flow reusable rather than a wizard re-run
from scratch: the settings live on the project, so picking the project again is
picking the pipeline.

The route exists separately from the project's own PUT for a reason found the
hard way, pinned in TestWhyThisIsNotAPut below.
"""

import pytest
from pydantic import ValidationError

from alfred.core.models import Project, RenderSettings
from alfred.core.routes.project import ProjectSettings


class TestTheSettingsShape:
    def test_a_project_can_carry_render_settings(self):
        assert 'render_settings' in Project.model_fields

    def test_a_project_can_carry_a_destination(self):
        assert 'destination' in Project.model_fields

    def test_both_are_optional(self):
        """A project that has never been rendered has no opinion yet.

        Requiring them would invalidate every existing project and force the
        stages to invent values before anyone had chosen any.
        """
        assert not Project.model_fields['render_settings'].is_required()
        assert not Project.model_fields['destination'].is_required()

    def test_render_settings_default_to_something_renderable(self):
        settings = RenderSettings()
        assert settings.width and settings.height and settings.fps

    def test_render_settings_are_not_a_render(self):
        """A standing preference, not a job with a result.

        Conflating them would mean a project could not describe how it should
        be rendered until it had been rendered once.
        """
        assert 'filename' not in RenderSettings.model_fields
        assert 'progress' not in RenderSettings.model_fields
        assert 'link' not in RenderSettings.model_fields


class TestTheWritableSubset:
    """The settings route must not become an arbitrary write to the document."""

    def test_it_accepts_only_the_two_flow_fields(self):
        assert set(ProjectSettings.model_fields) == {'render_settings', 'destination'}

    @pytest.mark.parametrize('protected', ['logic', 'fields', 'edl', 'name'])
    def test_it_cannot_write_the_rest_of_the_project(self, protected):
        """Named individually so a regression says which field opened up.

        `edl` is the one that matters most: the timeline is edited through its
        own path, and letting "remember my render size" also replace the clips
        would make a settings save a way to lose work.
        """
        assert protected not in ProjectSettings.model_fields

    def test_unset_fields_are_dropped_rather_than_written_as_null(self):
        """`exclude_none` is what makes a partial save partial.

        Without it, saving only a destination would write
        `render_settings: null` over whatever was there.
        """
        patch = ProjectSettings(destination='local').model_dump(exclude_none=True)
        assert patch == {'destination': 'local'}


class TestWhyThisIsNotAPut:
    """The crud router's update replaces the whole document.

    Found by doing it: a partial `PUT /project/{id}` carrying only
    render_settings and destination wrote null over `name` and `logic`. The
    write succeeded, because writes are not validated -- and every subsequent
    `GET` of that project answered 500, because reads are. One request turned a
    readable project into an unreadable one, and nothing reported an error until
    the next reader arrived.
    """

    def test_logic_is_required_so_a_null_write_makes_the_project_unreadable(self):
        assert Project.model_fields['logic'].is_required()

        with pytest.raises(ValidationError) as excinfo:
            Project(logic=None, name='x')
        assert 'logic' in str(excinfo.value)

    def test_a_settings_patch_alone_would_not_satisfy_the_project_model(self):
        """Which is exactly why the full-replace PUT corrupted the document.

        The body a settings save sends is not a whole project, and the update
        route treated it as one.
        """
        patch = ProjectSettings(
            render_settings=RenderSettings(width=1280, height=720),
            destination='local',
        ).model_dump(exclude_none=True)

        with pytest.raises(ValidationError):
            Project(**patch)
