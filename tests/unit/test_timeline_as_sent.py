"""A saved timeline holds what the editor sent, and nothing otto filled in.

Contract M4. `PUT /project/{id}/timeline` validated the clips through otto's
models and stored the result, defaults and all: every clip came back with
`fadeIn: 1` and `fadeOut: 1` (and `duration: 5`, `relative: true`, a null for
each other field), indistinguishable from a fade somebody chose, and rendered
with it. A project now stores each EDL with `exclude_unset`, and answers with
it the same way.

These pin the two halves without a database: how an EDL is encoded for
storage, and how a project is serialised for a response.
`integration/test_project_timeline_api.py` round-trips one through the routes.
"""

import pytest
from beanie.odm.utils.encoder import Encoder
from otto.models import Edl

from alfred.core.models import Project, ProjectUpdate
from alfred.core.models.project import as_sent

SENT = {
    'clips': [
        {
            'type': 'template',
            'name': 'makeColor',
            'duration': 2.0,
            'start': 0.0,
            'data': {'color': '#f2aa4c'},
            # The editor's view index, written onto each clip as it is drawn.
            'i': 0,
        },
        {
            'type': 'video',
            'name': 'videos/demo-bars.mp4',
            'duration': 3.0,
            'start': 2.0,
            'inpoint': 0.0,
            'fadeIn': 0,
            'fadeOut': 0.5,
            'i': 1,
        },
    ],
    'duration': 5.0,
}


def clip(edl, n):
    return edl['clips'][n]


@pytest.fixture
def offline(monkeypatch):
    """Projects constructed with no database behind them."""
    for document in (Project, ProjectUpdate):
        monkeypatch.setattr(
            document, 'get_motor_collection', classmethod(lambda cls: None)
        )


class TestAsSent:
    def test_a_default_nobody_sent_is_not_written_in(self):
        stored = as_sent(Edl(**SENT))
        for absent in ('fadeIn', 'fadeOut', 'relative', 'opacity', 'inpoint'):
            assert absent not in clip(stored, 0), absent

    def test_template_data_keeps_only_what_was_sent(self):
        """`method: 'label'` is TemplateData's default, not the editor's."""
        assert clip(as_sent(Edl(**SENT)), 0)['data'] == {'color': '#f2aa4c'}

    def test_an_explicit_zero_stays_zero(self):
        """Excluding *defaults* would drop it; excluding *unset* keeps it."""
        stored = as_sent(Edl(**SENT))
        assert clip(stored, 1)['fadeIn'] == 0
        assert clip(stored, 1)['inpoint'] == 0.0
        assert clip(stored, 0)['start'] == 0.0

    def test_what_was_sent_is_kept_exactly(self):
        stored = as_sent(Edl(**SENT))
        assert clip(stored, 1) == {
            'type': 'video',
            'name': 'videos/demo-bars.mp4',
            'duration': 3.0,
            'start': 2.0,
            'inpoint': 0.0,
            'fadeIn': 0,
            'fadeOut': 0.5,
        }
        assert stored['duration'] == 5.0

    def test_the_editor_s_view_index_is_dropped(self):
        stored = as_sent(Edl(**SENT))
        assert all('i' not in c for c in stored['clips'])

    def test_a_clip_with_defaults_written_in_keeps_them(self):
        """Clips stored before this carry `fadeIn: 1`; they stay as they are."""
        legacy = {'clips': [{'type': 'template', 'name': 'title', 'fadeIn': 1}]}
        assert clip(as_sent(Edl(**legacy)), 0)['fadeIn'] == 1


class TestStoring:
    """beanie encodes a project's fields through its Settings' encoders."""

    def test_a_project_encodes_its_edl_as_sent(self):
        assert Project.Settings.bson_encoders[Edl] is as_sent

    def test_so_does_the_update_body(self):
        """`PUT /project/{id}` writes a ProjectUpdate, encoded the same way."""
        assert ProjectUpdate.Settings.bson_encoders[Edl] is as_sent

    def test_a_set_of_the_edl_writes_it_as_sent(self):
        """What `project.set({'edl': edl})` sends to MongoDB."""
        encoder = Encoder(custom_encoders=Project.Settings.bson_encoders)
        written = encoder.encode({'$set': {'edl': Edl(**SENT)}})['$set']['edl']
        assert written == as_sent(Edl(**SENT))
        assert 'fadeIn' not in clip(written, 0)


class TestServing:
    def test_a_project_answers_with_its_edl_as_stored(self, offline):
        """Read back, otto's models fill the defaults in again; the answer
        must not, or a client rendering what it read gets the fades anyway."""
        project = Project(logic={}, edl=as_sent(Edl(**SENT)))
        served = project.model_dump()['edl']
        assert 'fadeIn' not in clip(served, 0)
        assert clip(served, 1)['fadeIn'] == 0

    def test_the_rest_of_the_project_is_served_as_before(self, offline):
        project = Project(logic={}, name='kept', edl=SENT)
        served = project.model_dump()
        assert served['name'] == 'kept'
        assert served['render_settings'] is None

    def test_a_project_without_a_timeline_is_unaffected(self, offline):
        assert Project(logic={}).model_dump()['edl'] is None

    def test_an_excluded_edl_stays_excluded(self, offline):
        project = Project(logic={}, edl=SENT)
        assert 'edl' not in project.model_dump(exclude={'edl'})
