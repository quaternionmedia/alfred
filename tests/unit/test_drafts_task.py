"""Making a source's drafts in the worker (`alfred/core/utils/drafts.py`,
`sculptDrafts` in `alfred/core/utils/tasks.py`), without a database or an
engine: the collections are in memory, and the measures are given.
"""

from datetime import datetime

import pytest
from bson import ObjectId

from alfred.core.models.drafts import CUE_SOURCE
from alfred.core.utils import drafts, measures, tasks
from alfred.core.utils.measures import Measures
from tests.unit.test_sculpt import make_captions, make_words, series


class FakeCollection:
    def __init__(self, *documents):
        self.documents = {d['_id']: dict(d) for d in documents}
        self.updates = []
        self.inserted = []

    def find_one(self, query, projection=None):
        for document in self.documents.values():
            if all(document.get(key) == value for key, value in query.items()):
                return dict(document)
        return None

    def update_one(self, query, update):
        self.updates.append(update['$set'])
        if query['_id'] in self.documents:
            self.documents[query['_id']].update(update['$set'])

    def insert_many(self, documents):
        ids = []
        for document in documents:
            made = ObjectId()
            self.documents[made] = {**document, '_id': made}
            self.inserted.append(self.documents[made])
            ids.append(made)
        return type('Inserted', (), {'inserted_ids': ids})()


def source(**fields):
    document = {
        '_id': ObjectId(),
        'owner': 'owner@example.com',
        'name': 'the show',
        'logic': {},
        'edl': {
            'clips': [
                {
                    'type': 'video',
                    'name': 'videos/show.mp4',
                    'duration': 60,
                    'start': 0,
                    'inpoint': 0,
                }
            ]
        },
        'captions': make_captions(),
        'words': make_words(),
        'caption_style': {'enabled': False, 'color': '#ffcc00'},
        'render_settings': {'width': 1280, 'height': 720},
        'cues': [
            {'start': 0, 'end': 5, 'label': 'Chapter 1', 'source': 'alfred-excerpts'}
        ],
    }
    document.update(fields)
    return document


@pytest.fixture
def measured(monkeypatch):
    """The timeline's measures, as the worker would read them: a spike at 40 s."""

    def timeline_measures(clips):
        return Measures(
            duration=60,
            levels=series(1, {10, 40, 41}),
            motion=series(1, {40, 41, 50}),
            silences=[{'start': 25, 'end': 34}],
            scenes=[0, 10.3, 34.2, 60],
            notes=['videos/other.mp4: its motion was not measured: gone'],
        )

    monkeypatch.setattr(measures, 'timeline_measures', timeline_measures)


class TestMakingDrafts:
    def test_the_picture_s_cuts_reach_a_recipe_s_scenes_step(self, measured):
        """Mutation: leave the cuts out of the recipe's source -- red, the step
        says none was measured."""
        mine = source()
        projects, recipes = FakeCollection(mine), FakeCollection(
            {
                '_id': ObjectId(),
                'owner': 'owner@example.com',
                'name': 'cut',
                'label': 'Cut',
                'fields': [],
                'steps': [
                    {'op': 'chapters', 'pause': 4},
                    {'op': 'scenes', 'within': 1.5},
                    {'op': 'compose', 'how': 'each'},
                ],
            }
        )
        recipe_id = next(iter(recipes.documents))
        made, notes = drafts.make_drafts(
            mine, [{'recipe': str(recipe_id)}], projects, recipes
        )
        assert made == 2
        assert not [n for n in notes if 'scenes' in n]
        assert [d['source']['spans'] for d in projects.inserted] == [
            [[1, 24.4]],
            [[34.2, 51.9]],
        ]

    def test_each_draft_is_a_project_of_the_owner_carrying_its_source(self, measured):
        mine = source()
        projects, recipes = FakeCollection(mine), FakeCollection()
        made, notes = drafts.make_drafts(
            mine,
            [
                {
                    'recipe': 'highlights',
                    'values': {'shortest': '4', 'longest': '8', 'count': '2'},
                }
            ],
            projects,
            recipes,
        )
        assert made == 2
        assert notes == ['videos/other.mp4: its motion was not measured: gone']
        first, second = projects.inserted
        assert first['owner'] == 'owner@example.com'
        assert first['name'] == 'the show – Highlights 1'
        assert second['name'] == 'the show – Highlights 2'
        assert first['logic'] == {} and first['fields'] == []
        assert 4 <= first['edl']['duration'] <= 8
        assert first['edl']['clips'][0]['start'] == 0
        assert first['words'] and first['captions']
        assert first['caption_style'] == {'enabled': False, 'color': '#ffcc00'}
        assert first['render_settings'] == {'width': 1280, 'height': 720}
        source_of = first['source']
        assert source_of['project'] == str(mine['_id'])
        assert source_of['recipe'] == 'highlights'
        assert source_of['values'] == {'shortest': '4', 'longest': '8', 'count': '2'}
        assert len(source_of['spans']) == 1
        assert set(source_of['scores']) == {'dialogue', 'spikes'}
        assert isinstance(source_of['made_at'], datetime)
        assert 'of the source' in first['description']

    def test_the_source_gets_a_cue_per_draft_and_keeps_other_writers(self, measured):
        mine = source()
        projects, recipes = FakeCollection(mine), FakeCollection()
        drafts.make_drafts(mine, [{'recipe': 'chapters'}], projects, recipes)
        cues = projects.documents[mine['_id']]['cues']
        labels = [(c['label'], c.get('source'), c.get('kind')) for c in cues]
        assert ('Chapter 1', 'alfred-excerpts', None) in labels
        ours = [c for c in cues if c['source'] == CUE_SOURCE]
        assert [c['label'] for c in ours] == ['Chapters 1', 'Chapters 2']
        assert all(c['kind'] == 'draft' and ObjectId.is_valid(c['ref']) for c in ours)
        assert {c['ref'] for c in ours} == {str(d['_id']) for d in projects.inserted}

    def test_a_second_run_replaces_the_drafts_cues_and_leaves_the_old_drafts(
        self, measured
    ):
        mine = source()
        projects, recipes = FakeCollection(mine), FakeCollection()
        drafts.make_drafts(mine, [{'recipe': 'chapters'}], projects, recipes)
        again = projects.documents[mine['_id']]
        drafts.make_drafts(again, [{'recipe': 'chapters'}], projects, recipes)
        ours = [
            c
            for c in projects.documents[mine['_id']]['cues']
            if c['source'] == CUE_SOURCE
        ]
        assert len(ours) == 2
        assert len(projects.inserted) == 4

    def test_a_recipe_of_the_owner_s_by_its_id(self, measured):
        mine = source()
        recipe = {
            '_id': ObjectId(),
            'owner': 'owner@example.com',
            'name': 'mine',
            'label': 'Mine',
            'fields': [],
            'steps': [{'op': 'chapters'}, {'op': 'compose', 'how': 'each'}],
        }
        projects, recipes = FakeCollection(mine), FakeCollection(recipe)
        made, _ = drafts.make_drafts(
            mine, [{'recipe': str(recipe['_id'])}], projects, recipes
        )
        assert made == 2
        assert projects.inserted[0]['source']['recipe'] == str(recipe['_id'])
        assert projects.inserted[0]['name'] == 'the show – Mine 1'

    def test_another_s_recipe_or_none_is_unknown(self, measured):
        mine = source()
        theirs = {
            '_id': ObjectId(),
            'owner': 'other@example.com',
            'name': 'x',
            'steps': [],
        }
        with pytest.raises(drafts.UnknownRecipe):
            drafts.make_drafts(
                mine,
                [{'recipe': str(theirs['_id'])}],
                FakeCollection(mine),
                FakeCollection(theirs),
            )
        with pytest.raises(drafts.UnknownRecipe):
            drafts.make_drafts(
                mine, [{'recipe': 'nowhere'}], FakeCollection(mine), FakeCollection()
            )

    def test_a_run_that_finds_nothing_leaves_a_note_and_no_project(self, measured):
        mine = source(words=[], captions=[])
        projects = FakeCollection(mine)
        made, notes = drafts.make_drafts(
            mine, [{'recipe': 'highlights'}], projects, FakeCollection()
        )
        assert made == 0
        assert 'highlights: no stretch of the source was found to keep' in notes
        assert projects.inserted == []


class TestTheTask:
    @pytest.fixture
    def db(self, monkeypatch, measured):
        collections = {}

        def make(*documents):
            collections[tasks.PROJECTS] = FakeCollection(*documents)
            collections[drafts.RECIPES] = FakeCollection()
            monkeypatch.setattr(tasks, 'get_sync_db', lambda: collections)
            return collections[tasks.PROJECTS]

        return make

    def test_running_then_done_with_the_count_and_the_notes(self, db):
        mine = source()
        projects = db(mine)
        tasks.sculptDrafts(
            projectId=str(mine['_id']), recipes=[{'recipe': 'chapters', 'values': {}}]
        )
        states = [
            u['drafts_job']['state'] for u in projects.updates if 'drafts_job' in u
        ]
        assert states == ['running', 'done']
        job = projects.documents[mine['_id']]['drafts_job']
        assert job['made'] == 2
        assert job['recipes'] == ['chapters']
        assert job['notes'] == ['videos/other.mp4: its motion was not measured: gone']
        assert job['error'] is None
        assert len(projects.inserted) == 2

    def test_a_failure_is_recorded_plainly(self, db):
        mine = source()
        projects = db(mine)
        tasks.sculptDrafts(projectId=str(mine['_id']), recipes=[{'recipe': 'nowhere'}])
        job = projects.documents[mine['_id']]['drafts_job']
        assert job['state'] == 'failed'
        assert job['error'] == "no recipe is named 'nowhere'"
        assert projects.inserted == []

    def test_a_source_deleted_meanwhile_is_left_deleted(self, db):
        projects = db()
        tasks.sculptDrafts(projectId=str(ObjectId()), recipes=[{'recipe': 'chapters'}])
        assert projects.updates == []
