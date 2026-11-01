"""alfred's docs state what is true; its dated account lives in qm.

A page here says what alfred is and does at any commit. When each round
landed, its pull request, what it measured and what it taught are history,
and they live on qm's site, in alfred's subtree under its project page, with a
timeline qm generates from git. The changelog is release notes: what changed
in each version, and no dates or counts. These hold the line a reader can see;
`.github/workflows/timeless-check.yml` holds the prose of every line a pull
request adds.
"""

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / 'docs'
HISTORY = 'https://quaternionmedia.github.io/qm/projects/alfred/timeline/'
DATE = re.compile(r'\b20\d\d-\d\d-\d\d\b')
PAGES = ['README.md', 'AGENTS.md', 'CONTRIBUTING.md', 'tests/README.md']


class _Loader(yaml.SafeLoader):
    pass


# mkdocs.yml names Python objects for some extensions; their values do not
# matter here.
_Loader.add_multi_constructor('tag:yaml.org,2002:python/', lambda *_: None)


def nav():
    config = yaml.load((REPO / 'mkdocs.yml').read_text(encoding='utf-8'), _Loader)
    return config['nav']


def durable_pages():
    return [REPO / name for name in PAGES] + sorted(DOCS.rglob('*.md'))


def test_no_page_here_is_history():
    named = [
        page.relative_to(REPO).as_posix()
        for page in DOCS.rglob('*.md')
        if re.search(r'retrospective|history|timeline', page.stem, re.I)
    ]
    assert (
        not named
    ), f'{named}: dated history belongs in alfred\'s subtree on qm\'s site'


def test_history_on_the_site_is_qm_s_timeline():
    history = [
        entry for entry in nav() if isinstance(entry, dict) and 'History' in entry
    ]
    assert history == [{'History': HISTORY}], (
        'the nav\'s History links out to alfred\'s timeline on qm\'s site, and '
        'to nothing in this repository'
    )


def test_the_changelog_is_release_notes():
    text = (REPO / 'CHANGELOG.md').read_text(encoding='utf-8')
    found = [
        what
        for what, pattern in (
            ('a Measured section', r'^#+\s*Measured\b'),
            ('a table of rounds', r'^\|\s*Round\s*\|'),
            ('a date', DATE.pattern),
            ('a measured count', r'\b\d+ passed\b'),
        )
        if re.search(pattern, text, re.M)
    ]
    assert not found, (
        f'CHANGELOG.md carries {found}: what each round measured, and when, is '
        'alfred\'s timeline on qm\'s site'
    )


def test_the_pages_name_no_date():
    dated = [
        f'{page.relative_to(REPO).as_posix()}: {match.group(0)}'
        for page in durable_pages()
        for match in DATE.finditer(page.read_text(encoding='utf-8'))
    ]
    assert not dated, f'dates in durable pages: {dated}'
