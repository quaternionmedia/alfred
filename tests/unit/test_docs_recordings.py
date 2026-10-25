"""The cookbook plays a walkthrough's recording where one is on disk, only there.

`scripts/docs_recordings.py` is the mkdocs hook. Recordings are git-ignored,
so the published docs must come out exactly as generated, and docs served
after `./al recipes` must play each one from its recipe's start.
"""

import importlib.util
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COOKBOOK = REPO / 'docs' / 'cookbook.md'


def load():
    spec = importlib.util.spec_from_file_location(
        'docs_recordings', REPO / 'scripts' / 'docs_recordings.py'
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


recordings = load()

PAGE = (
    '### @recipe walkthroughs\n\n'
    '- **recipe: open the editor and look around**\n'
    '- **recipe: generate a demo from an empty install**\n\n'
    '  A first run needs no downloads.\n'
)


def test_no_recording_leaves_the_page_as_generated():
    # Mutation: insert a player whatever url_of answers -- this fails.
    assert recordings.with_recordings(PAGE, lambda path: None, {}) == PAGE


def test_a_recording_is_played_from_its_recipe_start():
    present = {
        'recipes/generate-a-demo-from-an-empty-install.webm': '../recipes/g.webm'
    }
    out = recordings.with_recordings(
        PAGE, present.get, {'generate-a-demo-from-an-empty-install': 1.16}
    )
    players = re.findall(r'<video [^>]*src="([^"]+)"', out)
    assert players == ['../recipes/g.webm#t=1.16']
    # Under its own recipe, inside the list item, before the recipe's prose.
    lines = out.split('\n')
    title = lines.index('- **recipe: generate a demo from an empty install**')
    assert lines[title + 2].startswith('  <video ')
    assert out.index('<video ') < out.index('A first run needs no downloads.')


def test_a_recording_with_no_start_plays_from_the_beginning():
    present = {'recipes/open-the-editor-and-look-around.webm': 'o.webm'}
    out = recordings.with_recordings(PAGE, present.get, {})
    assert 'src="o.webm"' in out


def test_the_slug_is_the_collector_s(tmp_path):
    """Every walkthrough the cookbook lists names the file the collector writes."""
    titles = re.findall(r'^- \*\*recipe: (.+)\*\*$', COOKBOOK.read_text('utf-8'), re.M)
    assert titles, 'the cookbook lists no recorded walkthrough'
    # collect-recipe-videos.js: drop "recipe:", runs of non-alphanumerics to -,
    # trim the ends, lowercase.
    for title in titles:
        expected = re.sub(r'[^a-z0-9]+', '-', title, flags=re.I).strip('-').lower()
        assert recordings.slug_for(title) == expected


def test_starts_reads_the_collector_s_manifest(tmp_path):
    manifest = tmp_path / 'recipe-videos.json'
    manifest.write_text(json.dumps({'recipes': [{'slug': 'a', 'start': 2.5}]}))
    assert recordings.starts(manifest) == {'a': 2.5}
    assert recordings.starts(tmp_path / 'absent.json') == {}


def test_mkdocs_runs_the_hook():
    config = (REPO / 'mkdocs.yml').read_text(encoding='utf-8')
    assert re.search(r'^hooks:\n  - scripts/docs_recordings\.py$', config, re.M)
