"""The tour: the editor's journeys a stage at a time, and the words kept on them.

The journeys are docs/journeys.md's, over the flow's stages, so these hold the
tour to both: a journey is a section of the page by its anchor and heading, a
stage is one of the rail's with the rail's words, and what there is to try on
a stage is the page's own steps. Taking the editor to a stage is drawn from a
closed list, none of which makes, renders, sends or deletes anything. The words
are reached through `TourWords`, which a list stands in for here.
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alfred import config, tour
from alfred.core.routes import tour as routes
from alfred.main import app

REPO = Path(__file__).resolve().parents[2]
STAGES_JS = REPO / 'website' / 'src' / 'Stages.js'
REGISTRY_JS = REPO / 'website' / 'src' / 'layout' / 'registry.js'


class ListWords:
    """Words kept in a list, oldest first, as the database keeps them."""

    def __init__(self):
        self.kept = []

    async def add(self, record):
        self.kept.append(dict(record))

    async def all(self):
        return [dict(r) for r in self.kept]


@pytest.fixture
def words():
    return ListWords()


@pytest.fixture
def client(words):
    app.dependency_overrides[routes.tour_words] = lambda: words
    yield TestClient(app)
    app.dependency_overrides.pop(routes.tour_words, None)


@pytest.fixture
def no_words():
    app.dependency_overrides[routes.tour_words] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.pop(routes.tour_words, None)


# --- the journeys ----------------------------------------------------------


def test_the_stages_are_the_rails_with_the_rails_words():
    """A stage's line is the one the rail shows for it, so the tour has none of its own."""
    rail = re.findall(
        r"\{ id: '([a-z]+)', label: '([^']+)', hint: '([^']+)' \}",
        STAGES_JS.read_text(),
    )
    assert rail, 'no stage found in Stages.js'
    assert {i: (label, hint) for i, label, hint in rail} == tour.FLOW


def test_each_journey_is_a_section_of_the_journeys_page():
    page = tour.JOURNEYS_PAGE.read_text(encoding='utf-8')
    for journey in tour.JOURNEYS:
        heading = f"## {journey['name']} {{ #{journey['id']} }}"
        assert heading in page, f'docs/journeys.md has no {heading!r}'


def test_each_stage_names_steps_the_page_has():
    on_page = tour.steps()
    for journey in tour.JOURNEYS:
        for stage in journey['stages']:
            missing = set(stage['steps']) - set(on_page.get(journey['id'], {}))
            assert not missing, f"{journey['id']}/{stage['stage']}: no step {missing}"


def test_a_step_is_read_as_a_person_reads_it():
    """No emphasis marks or link targets: the step's words, as the page shows them."""
    first = tour.steps()['first-video'][1]
    assert first.startswith('Open the editor. The line under the rail says Start here.')
    assert '**' not in first and '](' not in first


def test_stage_ids_are_unique_and_a_roadmap_can_name_each_journey():
    ids = tour.stage_ids()
    assert len(ids) == len(set(ids))
    for journey in tour.JOURNEYS:
        assert re.fullmatch(r'[a-z0-9-]+', journey['id'])


def test_taking_the_editor_to_a_stage_is_drawn_from_the_closed_list():
    panels = set(re.findall(r"\{ id: '([a-z]+)', title:", REGISTRY_JS.read_text()))
    for journey in tour.JOURNEYS:
        for stage in journey['stages']:
            for put in stage['puts']:
                assert put['do'] in tour.PUTS, put
                if put['do'] == 'panel':
                    assert put['panel'] in panels, put
            assert stage['puts'][-1] == {'do': 'stage', 'stage': stage['stage']}


def test_the_document_is_the_journeys_in_order_with_their_stages(client):
    document = client.get('/tour').json()
    assert [j['id'] for j in document['journeys']] == [j['id'] for j in tour.JOURNEYS]
    stage = document['journeys'][0]['stages'][0]
    assert stage['id'] == 'first-video/source'
    assert (stage['title'], stage['words']) == tour.FLOW['source']
    assert stage['tries'][0]['href'] == '/docs/journeys/#first-video'
    assert stage['feedback'] is None
    assert document['words'] is True
    assert set(document) >= {'commit', 'changed', 'journeys'}


# --- the words ---------------------------------------------------------------


def test_a_word_is_kept_and_is_the_stages_feedback(client, words):
    said = client.post(
        '/tour/feedback',
        json={'stage': 'first-video/edit', 'verdict': 'works', 'by': 'Ada'},
    )
    assert said.status_code == 201, said.text
    assert words.kept[0]['by'] == 'Ada'
    assert set(words.kept[0]) == {
        'stage',
        'verdict',
        'note',
        'by',
        'at',
        'commit',
        'changed',
    }
    stage = client.get('/tour').json()['journeys'][0]['stages'][1]
    assert stage['feedback']['verdict'] == 'works'
    assert stage['feedback']['current'] is True
    assert client.get('/tour/feedback').json() == {'feedback': words.kept}


def test_the_latest_word_is_the_stages_and_none_is_rewritten(client, words):
    for verdict, note in (('works', ''), ('off', 'the frame is black')):
        client.post(
            '/tour/feedback',
            json={
                'stage': 'first-video/edit',
                'verdict': verdict,
                'note': note,
                'by': 'Ada',
            },
        )
    assert [r['verdict'] for r in words.kept] == ['works', 'off']
    stage = client.get('/tour').json()['journeys'][0]['stages'][1]
    assert stage['feedback']['note'] == 'the frame is black'


def test_a_word_said_of_another_build_waits_again(client, words, monkeypatch):
    words.kept.append(
        {
            'stage': 'first-video/edit',
            'verdict': 'works',
            'note': '',
            'by': 'Ada',
            'at': '2026-11-15T00:00:00+00:00',
            'commit': 'abcdef12',
            'changed': False,
        }
    )
    monkeypatch.setattr(
        tour, 'running', lambda: {'commit': '12345678', 'changed': False}
    )
    stage = client.get('/tour').json()['journeys'][0]['stages'][1]
    assert stage['feedback']['current'] is False


@pytest.mark.parametrize(
    'body, status, why',
    [
        (
            {'stage': 'first-video/nowhere', 'verdict': 'works', 'by': 'Ada'},
            404,
            'no journey',
        ),
        (
            {'stage': 'first-video/edit', 'verdict': 'fine', 'by': 'Ada'},
            422,
            'one of works, off',
        ),
        (
            {'stage': 'first-video/edit', 'verdict': 'off', 'note': ' ', 'by': 'Ada'},
            422,
            'what is off',
        ),
        (
            {'stage': 'first-video/edit', 'verdict': 'works', 'by': '  '},
            422,
            'who is saying',
        ),
    ],
)
def test_a_word_the_tour_does_not_keep_is_refused_saying_why(
    client, words, body, status, why
):
    answer = client.post('/tour/feedback', json=body)
    assert answer.status_code == status
    assert why in answer.json()['detail']
    assert words.kept == []


def test_a_server_that_keeps_no_words_says_so_and_still_tours(no_words):
    assert (
        no_words.post(
            '/tour/feedback',
            json={'stage': 'first-video/edit', 'verdict': 'works', 'by': 'Ada'},
        ).status_code
        == 403
    )
    assert no_words.get('/tour/feedback').status_code == 403
    document = no_words.get('/tour').json()
    assert document['words'] is False
    assert document['journeys'][0]['stages'][0]['tries']


def test_words_are_off_unless_asked_for_and_refused_in_production():
    assert config.resolve_tour_words({}) is False
    assert config.resolve_tour_words({'ALFRED_TOUR_WORDS': 'false'}) is False
    assert config.resolve_tour_words({'ALFRED_TOUR_WORDS': '1'}) is True
    with pytest.raises(RuntimeError, match='ALFRED_PRODUCTION'):
        config.resolve_tour_words({'ALFRED_TOUR_WORDS': '1', 'ALFRED_PRODUCTION': '1'})
