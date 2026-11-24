"""The projects an empty database starts with render on any install.

Each is the first thing a new user opens, so each must render as seeded: no
media to fetch, no address to reach, and a form whose logic reads only what
the form collects.
"""

import json
import re
from pathlib import Path

import pytest

from alfred.core.routes.templates import TEMPLATE_NAMES
from alfred.seed import seed

COMPONENTS = Path(__file__).resolve().parents[2] / 'website' / 'src' / 'Components.js'
# What the form adds to a project's own fields (`ProjectForm.js`).
THE_FRAME = {'width', 'height'}

FORMS = [p for p in seed if p.get('fields')]


def clips(project):
    """Each clip a project makes: its timeline's, or its logic's layers."""
    for clip in (project.get('edl') or {}).get('clips', []):
        yield clip
    for layer in (project.get('logic') or {}).get('merge', []):
        yield layer['eachKey']


def reads(logic):
    """Every name a piece of json-logic reads with `var`."""
    if isinstance(logic, dict):
        for op, args in logic.items():
            if op == 'var':
                yield args
            else:
                yield from reads(args)
    elif isinstance(logic, list):
        for item in logic:
            yield from reads(item)


def test_there_is_a_form_project_and_a_timeline_project():
    assert FORMS
    assert any((p.get('edl') or {}).get('clips') for p in seed)


@pytest.mark.parametrize('project', seed, ids=lambda p: p['name'])
def test_every_clip_is_a_template_the_server_offers(project):
    """A template draws its picture, so it needs no file."""
    made = list(clips(project))
    assert made
    for clip in made:
        assert clip['type'] == 'template'
        assert clip['name'] in TEMPLATE_NAMES


def test_the_seed_names_no_media_and_no_address():
    text = json.dumps(seed)
    assert 'http' not in text
    assert 'videos/' not in text


@pytest.mark.parametrize('project', FORMS, ids=lambda p: p['name'])
def test_the_logic_reads_only_the_form_and_the_frame(project):
    """A name the form does not collect evaluates to nothing."""
    fields = {f['attrs']['name'] for f in project['fields']}
    assert set(reads(project['logic'])) <= fields | THE_FRAME


@pytest.mark.parametrize('project', FORMS, ids=lambda p: p['name'])
def test_every_field_is_drawn_and_starts_filled(project):
    """A component the form lacks draws nothing. A field fills with
    `defaultValue` once; a `value` is written back over what was typed at
    every redraw. A select starts on its first choice."""
    drawn = set(re.findall(r'^export function (\w+)', COMPONENTS.read_text(), re.M))
    for field in project['fields']:
        assert field['type'] in drawn
        assert 'value' not in field['attrs']
        if field['type'] == 'Selector':
            assert field['children']
        else:
            assert field['attrs'].get('defaultValue')
