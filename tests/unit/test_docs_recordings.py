"""A walkthrough's recording plays on the page it walks, where one is on disk, only there.

`scripts/docs_recordings.py` is the mkdocs hook. Recordings are git-ignored,
so the published docs must come out exactly as committed, and docs served
after `./al recipes` must play each one from its recipe's start, at the marker
the page places it with.
"""

import importlib.util
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / 'docs'
RECIPES = REPO / 'website' / 'e2e' / 'recipes.spec.js'


def load():
    spec = importlib.util.spec_from_file_location(
        'docs_recordings', REPO / 'scripts' / 'docs_recordings.py'
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


recordings = load()

PAGE = (
    '## A first video { #first-video }\n\n'
    '<!-- recipe: generate a demo from an empty install -->\n\n'
    'Nothing to bring.\n'
)


def markers():
    """Each marker in the docs, as (page, title)."""
    return [
        (page.relative_to(DOCS).as_posix(), found['title'])
        for page in sorted(DOCS.rglob('*.md'))
        for line in page.read_text(encoding='utf-8').splitlines()
        if (found := recordings.MARKER.match(line))
    ]


def recipe_titles():
    source = RECIPES.read_text(encoding='utf-8')
    return re.findall(r"test\(\s*'recipe: ([^']+)'", source)


def test_no_recording_leaves_the_page_as_committed():
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
    # In the marker's place, under its heading, before the prose.
    assert '<!-- recipe:' not in out
    assert out.index('{ #first-video }') < out.index('<video ')
    assert out.index('<video ') < out.index('Nothing to bring.')


def test_a_recording_with_no_start_plays_from_the_beginning():
    present = {'recipes/generate-a-demo-from-an-empty-install.webm': 'g.webm'}
    out = recordings.with_recordings(PAGE, present.get, {})
    assert 'src="g.webm"' in out


def test_every_walkthrough_is_placed_once_by_a_page():
    placed = [title for _, title in markers()]
    titles = recipe_titles()
    assert titles, 'recipes.spec.js has no walkthrough'
    unplaced = [t for t in titles if t not in placed]
    assert not unplaced, f'no page places {unplaced}: add <!-- recipe: TITLE -->'
    twice = sorted({t for t in placed if placed.count(t) > 1})
    assert not twice, f'placed more than once: {twice}'


def test_every_marker_names_a_walkthrough():
    titles = set(recipe_titles())
    stray = [(page, title) for page, title in markers() if title not in titles]
    assert not stray, f'markers naming no recipe in recipes.spec.js: {stray}'


def test_the_slug_is_the_collector_s():
    """Every walkthrough names the file the collector writes."""
    # collect-recipe-videos.js: drop "recipe:", runs of non-alphanumerics to -,
    # trim the ends, lowercase.
    for title in recipe_titles():
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
