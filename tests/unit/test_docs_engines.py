"""The docs link an engine's own pages at the commit alfred runs.

What otto and vox own is documented in their repositories, and alfred's pages
link there rather than restating it. A link names the commit the submodule is
pinned at, so it shows the engine alfred actually runs, and the page it names
is in the vendored copy at that commit. A pin bump that moves past a page, or
a link left on the old pin, fails here.
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ENGINES = {'otto': REPO / 'alfred' / 'otto', 'vox': REPO / 'alfred' / 'vox'}
LINK = re.compile(
    r'https://github\.com/quaternionmedia/(?P<engine>otto|vox)/blob/'
    r'(?P<ref>[^/\s)]+)/(?P<path>[^#\s)]+)(?:#(?P<anchor>[^\s)]+))?'
)


def pages():
    return [REPO / 'README.md'] + sorted((REPO / 'docs').rglob('*.md'))


def links():
    return [
        (page.relative_to(REPO).as_posix(), found)
        for page in pages()
        for found in LINK.finditer(page.read_text(encoding='utf-8'))
    ]


def pinned(engine):
    """The commit the index pins the submodule at, or None where git cannot say."""
    try:
        out = subprocess.run(
            ['git', 'ls-files', '-s', '--', f'alfred/{engine}'],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        return None
    return out[1] if len(out) > 1 and out[0] == '160000' else None


def github_slug(heading):
    """The anchor GitHub gives a heading: lower case, punctuation dropped."""
    text = re.sub(r'[`*_]', '', heading).strip().lower()
    return re.sub(r'\s', '-', re.sub(r'[^\w\s-]', '', text))


def test_the_docs_link_the_engines():
    assert links(), 'no page links otto or vox; the engines own their pages'


@pytest.mark.parametrize('engine', sorted(ENGINES))
def test_each_link_names_the_pinned_commit(engine):
    pin = pinned(engine)
    if pin is None:
        pytest.skip('git cannot say what the submodule is pinned at here')
    wrong = [
        f'{page}: {m["ref"]}'
        for page, m in links()
        if m['engine'] == engine and m['ref'] != pin
    ]
    assert not wrong, f'links to {engine} not at its pin, {pin}: {wrong}'


def test_each_linked_page_and_heading_is_in_the_vendored_copy():
    missing = []
    for page, m in links():
        target = ENGINES[m['engine']] / m['path']
        if not target.is_file():
            if any(ENGINES[m['engine']].iterdir()):
                missing.append(f'{page}: {m["engine"]}/{m["path"]}')
            continue
        if m['anchor']:
            headings = re.findall(
                r'^#{1,6}\s+(.+?)\s*$', target.read_text(encoding='utf-8'), re.M
            )
            if m['anchor'] not in {github_slug(h) for h in headings}:
                missing.append(f'{page}: {m["engine"]}/{m["path"]}#{m["anchor"]}')
    assert not missing, f'links to what the vendored engines lack: {missing}'
