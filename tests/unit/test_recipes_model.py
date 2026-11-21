"""What holds for a recipe (`alfred/core/models/recipes.py`), and that the
page lists what the code offers.

A recipe is checked wherever it arrives: a step names an operation, gives it
parameters it has, each in its range or reading a field the recipe declares.
The built-in recipes pass the same check, and every operation the registry
names is one the engine runs and the page describes.
"""

from pathlib import Path

import pytest

from alfred.core.models import recipes
from alfred.core.models.recipes import OPERATIONS, RecipeError, check_recipe, coerce
from alfred.core.utils import sculpt
from alfred.core.utils.recipes_builtin import BUILTIN, BY_NAME

PAGE = Path(__file__).resolve().parents[2] / 'docs' / 'drafts.md'


def recipe(**changes):
    base = {
        'name': 'mine',
        'label': 'Mine',
        'description': 'what it does',
        'fields': [
            {
                'type': 'Text',
                'attrs': {'name': 'count', 'text': 'How many', 'defaultValue': '5'},
            }
        ],
        'steps': [
            {'op': 'windows'},
            {'op': 'dialogue'},
            {'op': 'top', 'count': {'var': 'count'}},
        ],
    }
    base.update(changes)
    return base


class TestARecipe:
    def test_a_good_one_is_tidied_and_kept(self):
        checked = check_recipe(recipe(label='  Mine  ', description=' said \n'))
        assert checked['label'] == 'Mine'
        assert checked['description'] == 'said'
        assert checked['steps'][2] == {'op': 'top', 'count': {'var': 'count'}}

    def test_the_label_falls_back_to_the_name(self):
        assert check_recipe(recipe(label=None))['label'] == 'mine'

    @pytest.mark.parametrize('name', ['', 'Mine', '1st', 'a b', 'x' * 61, None])
    def test_a_name_is_a_word(self, name):
        with pytest.raises(RecipeError, match='name must be a word'):
            check_recipe(recipe(name=name))

    def test_an_unknown_operation_is_named_with_the_step(self):
        with pytest.raises(RecipeError, match="step 2: 'shuffle' is not an operation"):
            check_recipe(recipe(steps=[{'op': 'windows'}, {'op': 'shuffle'}]))

    def test_a_parameter_the_operation_lacks(self):
        with pytest.raises(
            RecipeError, match=r"step 1 \(top\): 'speed' is not a parameter of top"
        ):
            check_recipe(recipe(steps=[{'op': 'top', 'speed': 3}]))

    @pytest.mark.parametrize(
        'step, rule',
        [
            ({'op': 'top', 'count': 0}, 'count: 0 is below 1'),
            ({'op': 'top', 'count': 2.5}, 'expected a whole number'),
            ({'op': 'windows', 'shortest': 'soon'}, 'expected a number'),
            ({'op': 'windows', 'shortest': 1e9}, 'is above'),
            ({'op': 'spikes', 'where_words': 'maybe'}, 'expected true or false'),
            (
                {'op': 'compose', 'how': 'backwards'},
                'expected one of each, together, whole',
            ),
            ({'op': 'fillers', 'words': ['um']}, 'expected text'),
        ],
    )
    def test_a_parameter_out_of_its_kind_or_range(self, step, rule):
        with pytest.raises(RecipeError, match=rule):
            check_recipe(recipe(steps=[step]))

    def test_a_field_read_must_be_declared(self):
        with pytest.raises(
            RecipeError,
            match="reads the field 'speed', which the recipe does not declare",
        ):
            check_recipe(recipe(steps=[{'op': 'top', 'count': {'var': 'speed'}}]))

    def test_no_steps_is_no_recipe(self):
        with pytest.raises(RecipeError, match='at least one step'):
            check_recipe(recipe(steps=[]))

    @pytest.mark.parametrize(
        'fields, rule',
        [
            ([{'type': 'Dial', 'attrs': {'name': 'x'}}], 'expected a type among'),
            (
                [{'type': 'Text', 'attrs': {'name': 'Count'}}],
                'attrs.name must be a word',
            ),
            (
                [{'type': 'Text', 'attrs': {'name': 'x'}}] * 2,
                "a second field is named 'x'",
            ),
            ('count', 'fields must be a list'),
        ],
    )
    def test_fields_are_the_form_s(self, fields, rule):
        with pytest.raises(RecipeError, match=rule):
            check_recipe(recipe(fields=fields, steps=[{'op': 'windows'}]))


class TestCoercion:
    def test_text_is_one_line(self):
        assert coerce(recipes.text(''), ' um,  uh\nah ', 'x') == 'um, uh ah'

    def test_a_boolean_reads_the_words_a_form_sends(self):
        assert coerce(recipes.boolean(False), 'on', 'x') is True
        assert coerce(recipes.boolean(True), '', 'x') is False

    def test_a_number_from_a_form_s_string(self):
        assert coerce(recipes.number(1.0, 0.0, 10.0), '2.5', 'x') == 2.5
        assert coerce(recipes.integer(1, 0, 10), '3', 'x') == 3


class TestTheRegistry:
    @pytest.mark.parametrize('name', list(OPERATIONS))
    def test_every_operation_has_a_kind_and_runs_with_its_defaults(self, name):
        assert OPERATIONS[name]['kind'] in recipes.KINDS
        source = sculpt.Source(
            clips=[
                {'type': 'video', 'name': 'videos/a.mp4', 'duration': 30, 'start': 0}
            ],
            captions=[{'start': 1, 'end': 4, 'text': 'Hello there.'}],
            words=[
                {'start': 1, 'end': 1.5, 'text': 'Hello'},
                {'start': 2, 'end': 4, 'text': 'there.'},
            ],
            levels={'rate': 1, 'values': [0.1] * 30},
            motion={'rate': 1, 'values': [0.1] * 30},
            silences=[{'start': 10, 'end': 20}],
        )
        state = sculpt.State(candidates=[sculpt.Candidate(start=1, end=4)])
        p = sculpt.resolve({'op': name}, {}, [])
        sculpt.apply(
            name,
            p,
            state,
            source,
            sculpt.spoken(source.words),
            sculpt.spoken(source.captions),
        )

    @pytest.mark.parametrize('name', list(OPERATIONS))
    def test_every_operation_is_on_the_page(self, name):
        assert f'`{name}`' in PAGE.read_text(encoding='utf-8')

    @pytest.mark.parametrize('name', list(BY_NAME))
    def test_every_built_in_recipe_is_on_the_page_and_passes_the_check(self, name):
        assert f'`{name}`' in PAGE.read_text(encoding='utf-8')
        check_recipe(BY_NAME[name])

    def test_highlights_is_the_first_built_in(self):
        assert BUILTIN[0]['name'] == 'highlights'
