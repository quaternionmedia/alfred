"""Making a source's drafts in the worker (`alfred/core/utils/drafts.py`,
`sculptDrafts` in `alfred/core/utils/tasks.py`), without a database or an
engine: the collections are in memory, and the measures are given.
"""

from datetime import datetime
from pathlib import Path

import pytest
from bson import ObjectId

from alfred import config
from alfred.core.models.drafts import CUE_SOURCE
from alfred.core.utils import (
    analyses,
    drafts,
    labeller,
    language_engine,
    measures,
    tasks,
)
from alfred.core.utils.measures import Measures
from tests.unit.test_sculpt import TOPICS, make_captions, make_words, series


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
def measured(monkeypatch, tmp_path):
    """The timeline's measures, as the worker would read them: a spike at 40 s;
    no language engine, and a library of its own for what is kept beside it."""
    monkeypatch.setattr(config, 'LANGUAGE_ENGINE_URL', None)
    monkeypatch.setattr(config, 'LABELLER_URL', None)
    monkeypatch.setattr(config, 'VIDEO_DIR', str(tmp_path))

    def timeline_measures(clips):
        return Measures(
            duration=60,
            levels=series(1, {10, 40, 41}),
            motion=series(1, {40, 41, 50}),
            silences=[{'start': 25, 'end': 34}],
            notes=['videos/other.mp4: its motion was not measured: gone'],
        )

    monkeypatch.setattr(measures, 'timeline_measures', timeline_measures)


@pytest.fixture
def engine(monkeypatch):
    """A language engine that reads the test's topics, counting what it is asked."""
    asked = []

    def read(lines, title=None, transport=None):
        asked.append((len(lines), title))
        return language_engine.Reading(topics=TOPICS)

    monkeypatch.setattr(config, 'LANGUAGE_ENGINE_URL', 'http://words.test:8000')
    monkeypatch.setattr(language_engine, 'read', read)
    return asked


@pytest.fixture
def sorter(monkeypatch):
    """A labeller that sorts everything as the last category and scores it
    0.7, counting what it is asked."""
    asked = []

    class Sorting:
        def category(self, text, categories):
            asked.append(('category', tuple(categories)))
            return categories[-1]

        def alone(self, text):
            asked.append(('alone',))
            return 0.7

    monkeypatch.setattr(config, 'LABELLER_URL', 'http://labels.test:11434/v1')
    monkeypatch.setattr(config, 'LABELLER_MODEL', 'small-model')
    monkeypatch.setattr(labeller, 'Labeller', Sorting)
    return asked


def sorting_recipe(owner='owner@example.com'):
    """A stored recipe whose `label` step asks a category and a score."""
    return {
        '_id': ObjectId(),
        'owner': owner,
        'name': 'sorted',
        'label': 'Sorted',
        'description': '',
        'fields': [],
        'steps': [
            {'op': 'chapters', 'pause': 4},
            {'op': 'label', 'categories': 'rules, play', 'score': True},
            {'op': 'compose', 'how': 'each'},
        ],
    }


def untitled(recipe):
    return f'{recipe}: label: nothing was titled: {language_engine.problem()}'


class TestTitles:
    def test_drafts_are_named_by_the_topic_live_over_them(self, measured, engine):
        mine = source()
        projects, recipes = FakeCollection(mine), FakeCollection()
        made, notes = drafts.make_drafts(
            mine, [{'recipe': 'chapters'}], projects, recipes
        )
        assert made == 2
        assert [d['name'] for d in projects.inserted] == [
            'the show – Rules 1',
            'the show – Tower 2',
        ]
        ours = [
            c
            for c in projects.documents[mine['_id']]['cues']
            if c['source'] == CUE_SOURCE
        ]
        assert [c['label'] for c in ours] == ['Rules 1', 'Tower 2']
        assert not [n for n in notes if 'label' in n]
        assert engine == [(len(make_captions()), str(mine['_id']))]

    def test_the_reading_is_kept_beside_the_library(self, measured, engine):
        mine = source()
        projects, recipes = FakeCollection(mine), FakeCollection()
        drafts.make_drafts(mine, [{'recipe': 'chapters'}], projects, recipes)
        drafts.make_drafts(
            projects.documents[mine['_id']], [{'recipe': 'excerpts'}], projects, recipes
        )
        assert len(engine) == 1
        kept = list((Path(config.VIDEO_DIR) / analyses.FOLDER).iterdir())
        assert [p.suffix for p in kept] == ['.json']
        assert all(
            'Rules' in d['name'] or 'Tower' in d['name'] for d in projects.inserted
        )

    def test_a_recipe_without_a_label_step_asks_the_engine_nothing(
        self, measured, engine
    ):
        mine = source()
        drafts.make_drafts(
            mine, [{'recipe': 'tight-cut'}], FakeCollection(mine), FakeCollection()
        )
        assert engine == []

    def test_without_an_engine_the_recipe_names_the_draft_and_the_job_says_why(
        self, measured
    ):
        mine = source()
        projects = FakeCollection(mine)
        _, notes = drafts.make_drafts(
            mine, [{'recipe': 'chapters'}], projects, FakeCollection()
        )
        assert [d['name'] for d in projects.inserted] == [
            'the show – Chapters 1',
            'the show – Chapters 2',
        ]
        assert untitled('chapters') in notes
        assert 'ALFRED_LANGUAGE_ENGINE_URL' in untitled('chapters')

    def test_an_engine_that_fails_is_a_note_and_not_the_run_s_failure(
        self, measured, monkeypatch
    ):
        monkeypatch.setattr(config, 'LANGUAGE_ENGINE_URL', 'http://words.test:8000')

        def read(lines, title=None, transport=None):
            raise language_engine.LanguageEngineFailed(
                'the language engine at words.test:8000: it answered 500'
            )

        monkeypatch.setattr(language_engine, 'read', read)
        mine = source()
        projects = FakeCollection(mine)
        made, notes = drafts.make_drafts(
            mine, [{'recipe': 'chapters'}], projects, FakeCollection()
        )
        assert made == 2
        assert projects.inserted[0]['name'] == 'the show – Chapters 1'
        assert (
            'chapters: label: nothing was titled: the language engine at '
            'words.test:8000: it answered 500'
        ) in notes


class TestLabels:
    def test_drafts_carry_the_category_and_the_score_the_labeller_gave(
        self, measured, sorter
    ):
        mine, recipe = source(), sorting_recipe()
        projects, recipes = FakeCollection(mine), FakeCollection(recipe)
        made, notes = drafts.make_drafts(
            mine, [{'recipe': str(recipe['_id'])}], projects, recipes
        )
        assert made == 2
        assert [d['source']['category'] for d in projects.inserted] == ['play', 'play']
        assert [d['source']['scores']['label'] for d in projects.inserted] == [0.7, 0.7]
        assert sorter == [('category', ('rules', 'play')), ('alone',)] * 2
        assert [n for n in notes if 'categorised' in n] == []

    def test_without_a_labeller_the_job_says_why(self, measured):
        mine, recipe = source(), sorting_recipe()
        projects, recipes = FakeCollection(mine), FakeCollection(recipe)
        made, notes = drafts.make_drafts(
            mine, [{'recipe': str(recipe['_id'])}], projects, recipes
        )
        assert made == 2
        assert [d['source']['category'] for d in projects.inserted] == ['', '']
        [note] = [n for n in notes if 'categorised' in n]
        assert note.startswith('sorted: label: nothing was categorised or scored: ')
        assert 'ALFRED_LABELLER_URL' in note

    def test_a_recipe_asking_no_category_asks_the_labeller_nothing(
        self, measured, sorter
    ):
        mine = source()
        drafts.make_drafts(
            mine, [{'recipe': 'chapters'}], FakeCollection(mine), FakeCollection()
        )
        assert sorter == []


class TestMakingDrafts:
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
        assert notes == [
            'videos/other.mp4: its motion was not measured: gone',
            untitled('highlights'),
        ]
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
        assert job['notes'] == [
            'videos/other.mp4: its motion was not measured: gone',
            untitled('chapters'),
        ]
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
