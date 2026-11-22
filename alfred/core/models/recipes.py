"""Recipes: chains of algorithms that turn a long source into drafts.

A recipe is data a person chooses and sets, not code a person writes: a
`name` a program reads, a `label` and a `description` a person reads,
`fields` as a form project declares them (`docs/about/project.md`), each a
knob the editor draws, and `steps`, a list of operations from the fixed set
`OPERATIONS`, each with its parameters. A parameter is a value, or
`{"var": <field name>}`, which reads the field as `logic` does in a form
project. The operations fall into five kinds, run in the order the steps
give them (`utils.sculpt`):

- *segment* finds candidate stretches of the source: `windows`, `chapters`,
  `sentences`, `spans`, `silences`;
- *score* gives each candidate a score: `dialogue`, `spikes`, `label`;
- *filter* keeps some candidates: `top`, `keep`, `fillers`;
- *edit* changes the timeline: `tighten`, `excerpt`;
- *compose* makes the drafts: `compose`, `render`.

What holds for a recipe is checked here, wherever one arrives: a step names
an operation and gives it parameters it has, each in its range or reading a
field the recipe declares. A recipe is owned as a project is; the built-in
ones (`utils.recipes_builtin`) belong to nobody and every account reads
them.
"""

import math
import re
from typing import Any, Dict, List, NamedTuple, Optional

from beanie import Document
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

MAX_NAME_CHARS = 60
MAX_LABEL_CHARS = 100
MAX_DESCRIPTION_CHARS = 1000
MAX_STEPS = 40
MAX_FIELDS = 20

# A recipe's name: a word a program reads, as a cue's kind is.
_NAME = re.compile(r'[a-z][a-z0-9_-]{0,59}')

# The field types the editor draws (website/src/Components.js).
FIELD_TYPES = ('Text', 'Textarea', 'Selector', 'Color', 'Image')


class Parameter(NamedTuple):
    """One parameter of an operation: its `kind` (`number`, `integer`,
    `boolean`, `text` or `choice`), its bounds for a number, its choices
    for a choice, and what it is when not given."""

    kind: str
    default: Any
    low: Optional[float] = None
    high: Optional[float] = None
    choices: tuple = ()


def number(default, low, high):
    return Parameter('number', default, low, high)


def integer(default, low, high):
    return Parameter('integer', default, low, high)


def boolean(default):
    return Parameter('boolean', default)


def text(default):
    return Parameter('text', default)


def choice(default, *choices):
    return Parameter('choice', default, choices=(default, *choices))


# The longest a timeline the recipes cut: a day of seconds.
A_DAY = 86400.0

# Every operation, its kind, and its parameters. The values here are the
# first ones, held until they are measured against kept and dropped drafts.
OPERATIONS: Dict[str, Dict[str, Any]] = {
    # --- segment ---
    'windows': {
        'kind': 'segment',
        'about': (
            'candidate windows of a length between shortest and longest, laid '
            'every so often along the source, each beginning at a word and '
            'ending at a word, a sentence\'s end preferred'
        ),
        'parameters': {
            'shortest': number(8.0, 1.0, A_DAY),
            'longest': number(12.0, 1.0, A_DAY),
            'every': number(2.0, 0.1, A_DAY),
        },
    },
    'chapters': {
        'kind': 'segment',
        'about': 'the stretches between pauses of at least `pause` seconds',
        'parameters': {'pause': number(4.0, 0.1, 3600.0)},
    },
    'sentences': {
        'kind': 'segment',
        'about': 'each sentence of the transcript, from caption to caption',
        'parameters': {},
    },
    'spans': {
        'kind': 'segment',
        'about': (
            'stretches cut at pauses and at the ends of sentences, between '
            'shortest and longest seconds, as the excerpt flow proposes them'
        ),
        'parameters': {
            'pause': number(1.0, 0.1, 3600.0),
            'chapter_pause': number(4.0, 0.1, 3600.0),
            'shortest': number(10.0, 1.0, A_DAY),
            'longest': number(90.0, 1.0, A_DAY),
        },
    },
    'silences': {
        'kind': 'segment',
        'about': 'the stretches the audio engine heard as silence, longer than `longer_than`',
        'parameters': {'longer_than': number(2.0, 0.1, 3600.0)},
    },
    'speakers': {
        'kind': 'segment',
        'about': (
            'each turn a speaker takes, from the speaker the words carry: every '
            'speaker, or `who` alone, between shortest and longest seconds'
        ),
        'parameters': {
            'who': text(''),
            'shortest': number(3.0, 0.1, A_DAY),
            'longest': number(60.0, 0.1, A_DAY),
        },
    },
    # --- score ---
    'dialogue': {
        'kind': 'score',
        'about': 'how much is said in a candidate: words a second over its whole length',
        'parameters': {'weight': number(1.0, 0.0, 10.0)},
    },
    'spikes': {
        'kind': 'score',
        'about': (
            'moments where the level rises above its usual and the picture moves '
            'more than usual at the same time, as a share of the candidate'
        ),
        'parameters': {
            'weight': number(1.0, 0.0, 10.0),
            'level_above': number(1.5, 1.0, 10.0),
            'motion_above': number(1.5, 1.0, 10.0),
            'where_words': boolean(True),
        },
    },
    'label': {
        'kind': 'score',
        'about': 'a title and a category from the labeller; skipped where there is none',
        'parameters': {'title': boolean(True), 'categories': text('')},
    },
    # --- filter ---
    'top': {
        'kind': 'filter',
        'about': (
            'the highest-scored candidates that do not overlap: `count` of them, '
            'or `per_hour` for each hour of the source when that is set'
        ),
        'parameters': {
            'count': integer(25, 1, 500),
            'per_hour': number(0.0, 0.0, 500.0),
        },
    },
    'keep': {
        'kind': 'filter',
        'about': 'the candidates between shortest and longest seconds',
        'parameters': {
            'shortest': number(0.0, 0.0, A_DAY),
            'longest': number(A_DAY, 0.1, A_DAY),
        },
    },
    'scenes': {
        'kind': 'filter',
        'about': (
            "each candidate's edges moved to a scene change within `within` seconds "
            'of them, where the picture cuts from one shot to another, so a cut does '
            'not land inside a shot'
        ),
        'parameters': {'within': number(1.0, 0.0, 60.0)},
    },
    'fillers': {
        'kind': 'filter',
        'about': 'the filler words to cut out, separated by commas',
        'parameters': {'words': text('um, uh, er, ah, erm, hmm')},
    },
    # --- edit ---
    'tighten': {
        'kind': 'edit',
        'about': 'every pause longer than `longer_than` seconds cut down to `to`',
        'parameters': {
            'longer_than': number(1.5, 0.1, 3600.0),
            'to': number(0.5, 0.0, 3600.0),
        },
    },
    'excerpt': {
        'kind': 'edit',
        'about': 'each candidate as a draft of its own',
        'parameters': {},
    },
    # --- compose ---
    'compose': {
        'kind': 'compose',
        'about': (
            'how the drafts are made: `each` candidate its own; the candidates '
            '`together` in order, up to `target` seconds when that is set; or '
            'the `whole` source with the edits applied'
        ),
        'parameters': {
            'how': choice('each', 'together', 'whole'),
            'target': number(0.0, 0.0, A_DAY),
        },
    },
    'render': {
        'kind': 'compose',
        'about': "each draft's render size, and whether its captions are drawn",
        'parameters': {
            'width': integer(1920, 16, 7680),
            'height': integer(1080, 16, 7680),
            'captions': boolean(False),
        },
    },
}

KINDS = ('segment', 'score', 'filter', 'edit', 'compose')


class RecipeError(ValueError):
    """A recipe that cannot run. The message says which step and why."""


def is_reference(value) -> bool:
    """Whether `value` reads a field: `{"var": name}`."""
    return (
        isinstance(value, dict)
        and set(value) == {'var'}
        and isinstance(value['var'], str)
    )


def coerce(parameter: Parameter, value, where: str):
    """`value` as `parameter` takes it: a number in its range, a whole number,
    a boolean, a line of text or one of the choices. RecipeError otherwise."""
    kind = parameter.kind
    if kind in ('number', 'integer'):
        if isinstance(value, bool):
            raise RecipeError(f'{where}: expected a number, not {value!r}')
        try:
            found = float(value)
        except (TypeError, ValueError):
            raise RecipeError(f'{where}: expected a number, not {value!r}') from None
        if not math.isfinite(found):
            raise RecipeError(f'{where}: expected a number, not {value!r}')
        if kind == 'integer':
            if found != int(found):
                raise RecipeError(f'{where}: expected a whole number, not {value!r}')
            found = int(found)
        if parameter.low is not None and found < parameter.low:
            raise RecipeError(f'{where}: {found} is below {parameter.low:g}')
        if parameter.high is not None and found > parameter.high:
            raise RecipeError(f'{where}: {found} is above {parameter.high:g}')
        return found
    if kind == 'boolean':
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in (
            'true',
            'yes',
            'on',
            '1',
        ):
            return True
        if isinstance(value, str) and value.strip().lower() in (
            'false',
            'no',
            'off',
            '0',
            '',
        ):
            return False
        raise RecipeError(f'{where}: expected true or false, not {value!r}')
    if kind == 'choice':
        if value in parameter.choices:
            return value
        raise RecipeError(
            f'{where}: expected one of {", ".join(parameter.choices)}, not {value!r}'
        )
    if kind == 'text':
        if value is None:
            return ''
        if not isinstance(value, (str, int, float)):
            raise RecipeError(f'{where}: expected text, not {value!r}')
        line = ' '.join(str(value).split())
        if len(line) > MAX_DESCRIPTION_CHARS:
            raise RecipeError(
                f'{where}: text is at most {MAX_DESCRIPTION_CHARS} characters'
            )
        return line
    raise RecipeError(f'{where}: no such kind of parameter, {kind}')


def field_names(fields) -> set:
    names = set()
    for field in fields or []:
        attrs = field.get('attrs') if isinstance(field, dict) else None
        if isinstance(attrs, dict) and isinstance(attrs.get('name'), str):
            names.add(attrs['name'])
    return names


def check_step(step: dict, names: set, index: int) -> dict:
    """`step` as it runs: its operation known, each parameter one the
    operation has, each value in range or reading a declared field. The
    step's own words are kept; nothing is filled in here."""
    where = f'step {index + 1}'
    if not isinstance(step, dict):
        raise RecipeError(f'{where}: expected an object with an op')
    op = step.get('op')
    if not isinstance(op, str) or op not in OPERATIONS:
        raise RecipeError(
            f'{where}: {op!r} is not an operation; the operations are '
            f'{", ".join(OPERATIONS)}'
        )
    parameters = OPERATIONS[op]['parameters']
    for key, value in step.items():
        if key == 'op':
            continue
        if key not in parameters:
            raise RecipeError(
                f'{where} ({op}): {key!r} is not a parameter of {op}; '
                f'it takes {", ".join(parameters) or "none"}'
            )
        if is_reference(value):
            if value['var'] not in names:
                raise RecipeError(
                    f'{where} ({op}): {key} reads the field {value["var"]!r}, '
                    'which the recipe does not declare'
                )
            continue
        coerce(parameters[key], value, f'{where} ({op}): {key}')
    return step


def check_fields(fields) -> list:
    if fields is None:
        return []
    if not isinstance(fields, list):
        raise RecipeError('fields must be a list')
    if len(fields) > MAX_FIELDS:
        raise RecipeError(f'a recipe has at most {MAX_FIELDS} fields')
    seen = set()
    for n, field in enumerate(fields):
        where = f'field {n + 1}'
        if not isinstance(field, dict) or field.get('type') not in FIELD_TYPES:
            raise RecipeError(
                f'{where}: expected a type among {", ".join(FIELD_TYPES)}'
            )
        attrs = field.get('attrs')
        name = attrs.get('name') if isinstance(attrs, dict) else None
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise RecipeError(
                f'{where}: attrs.name must be a word of letters, digits, hyphens '
                'and underscores, starting with a letter'
            )
        if name in seen:
            raise RecipeError(f'{where}: a second field is named {name!r}')
        seen.add(name)
    return fields


def check_steps(steps, fields) -> list:
    if not isinstance(steps, list) or not steps:
        raise RecipeError('a recipe needs at least one step')
    if len(steps) > MAX_STEPS:
        raise RecipeError(f'a recipe has at most {MAX_STEPS} steps')
    names = field_names(fields)
    return [check_step(step, names, n) for n, step in enumerate(steps)]


def check_recipe(data: dict) -> dict:
    """`data` as a recipe, every rule applied; RecipeError naming the first
    one broken."""
    if not isinstance(data, dict):
        raise RecipeError('a recipe is an object')
    name = data.get('name')
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise RecipeError(
            'name must be a word of letters, digits, hyphens and underscores, '
            f'starting with a letter, at most {MAX_NAME_CHARS} long'
        )
    label = data.get('label') or name
    if not isinstance(label, str) or len(label) > MAX_LABEL_CHARS:
        raise RecipeError(f'label is a line of at most {MAX_LABEL_CHARS} characters')
    description = data.get('description') or ''
    if not isinstance(description, str) or len(description) > MAX_DESCRIPTION_CHARS:
        raise RecipeError(f'description is at most {MAX_DESCRIPTION_CHARS} characters')
    fields = check_fields(data.get('fields'))
    steps = check_steps(data.get('steps'), fields)
    return {
        'name': name,
        'label': ' '.join(label.split()),
        'description': description.strip(),
        'fields': fields,
        'steps': steps,
    }


class RecipeBody(BaseModel):
    """What `POST /recipes` and `PUT /recipes/{id}` take."""

    name: str
    label: Optional[str] = None
    description: Optional[str] = None
    fields: Optional[List[dict]] = None
    steps: List[dict]

    model_config = ConfigDict(extra='forbid')

    @model_validator(mode='after')
    def every_rule(self):
        checked = check_recipe(self.model_dump())
        self.label = checked['label']
        self.description = checked['description']
        self.fields = checked['fields']
        return self


class Recipe(Document):
    """A stored recipe, owned by an account."""

    name: str
    label: str
    description: str = ''
    fields: List[dict] = []
    steps: List[dict]
    # The owner key (`utils.ownership`); None for a built-in one.
    owner: Optional[str] = None

    model_config = ConfigDict(title='Alfred Recipe')

    @field_validator('steps')
    @classmethod
    def steps_that_run(cls, value, info):
        return check_steps(value, info.data.get('fields'))
