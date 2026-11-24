"""The cookbook is generated, so it cannot disagree with the suite.

`website/e2e/cookbook.js` renders `docs/cookbook.md` from the end-to-end specs:
one line per spec, from its opening comment, and each walkthrough with the page
that plays it. The specs are the source and the page a build artefact, so it
cannot claim what the suite does not check.

That only holds if the committed artefact matches its source, which is what
these check. Without them the file is a snapshot of whatever the last person
happened to run.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
E2E = REPO / 'website' / 'e2e'
COOKBOOK = REPO / 'docs' / 'cookbook.md'
GENERATOR = E2E / 'cookbook.js'


def spec_files():
    return sorted(E2E.glob('*.spec.js'))


def titles_in(path):
    """Every test.describe/test title in a spec, as written."""
    source = path.read_text(encoding='utf-8')
    pattern = (
        r"""(?:test\.describe|test)\s*(?:\.\w+)?\s*"""
        r"""\(\s*(['"`])((?:\\.|(?!\1)[^\\])*?)\1"""
    )
    return [m.group(2) for m in re.finditer(pattern, source)]


def tracked_recipe_files():
    """What git tracks in docs/recipes, or None where git cannot say.

    A test image with the checkout mounted, or a worktree whose git directory
    lives outside the mount, has no repository to ask; existence is all that
    is checked there.
    """
    try:
        listed = subprocess.run(
            ['git', 'ls-files', '-z', '--', 'docs/recipes'],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return {Path(path).name for path in listed.split('\0') if path}


class TestTheCookbookExists:
    def test_the_generator_is_present(self):
        assert GENERATOR.is_file(), 'the cookbook generator is missing'

    def test_the_cookbook_is_committed(self):
        """A generated file still has to be in the repository.

        mkdocs builds from the checkout, so a cookbook that only exists after
        someone runs a node script is a cookbook the docs site does not have.
        """
        assert COOKBOOK.is_file(), (
            'docs/cookbook.md is missing. Regenerate with '
            '`node website/e2e/cookbook.js`.'
        )

    def test_it_says_it_is_generated(self):
        text = COOKBOOK.read_text(encoding='utf-8')
        assert 'cookbook.js' in text, (
            'the cookbook must name its generator, or someone will edit it by '
            'hand and lose the change on the next build'
        )


class TestTheCookbookMatchesTheSuite:
    def test_every_spec_appears(self):
        text = COOKBOOK.read_text(encoding='utf-8')
        missing = [spec.name for spec in spec_files() if f'`{spec.name}`' not in text]
        assert not missing, f'specs absent from the cookbook: {missing}. Regenerate it.'

    def test_every_spec_says_what_it_holds(self):
        """A spec's line is its opening comment's first sentence."""
        text = COOKBOOK.read_text(encoding='utf-8')
        bare = [
            spec.name
            for spec in spec_files()
            if re.search(rf'^\| `{re.escape(spec.name)}` \|\s*\|', text, re.M)
        ]
        assert not bare, (
            f'{bare} open with no comment saying what they hold: give each a '
            '/** ... */ above its first test, and regenerate'
        )

    def test_every_walkthrough_says_where_it_plays(self):
        text = COOKBOOK.read_text(encoding='utf-8')
        walkthroughs = [
            title
            for spec in spec_files()
            for title in titles_in(spec)
            if title.startswith('recipe: ')
        ]
        assert walkthroughs, 'the suite has no walkthrough'
        for title in walkthroughs:
            assert f'| {title[len("recipe: "):]} | [' in text, (
                f'the cookbook does not say where "{title}" plays: a page '
                'places it with <!-- recipe: ... -->; regenerate'
            )

    @pytest.mark.skipif(shutil.which('node') is None, reason='no node available')
    def test_regenerating_changes_nothing(self):
        """The committed file is exactly what the generator produces.

        The strongest form of the claim: not "it looks current" but "running
        the generator right now produces this byte for byte". Anything else
        and the cookbook is a snapshot of whatever the last person ran.
        """
        before = COOKBOOK.read_bytes()
        result = subprocess.run(
            ['node', str(GENERATOR)],
            cwd=str(REPO / 'website'),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f'generator failed: {result.stderr[-400:]}'

        after = COOKBOOK.read_bytes()
        if before != after:
            # Bytes: write_text would restore it with CRLF on Windows.
            COOKBOOK.write_bytes(before)
            pytest.fail(
                'docs/cookbook.md is out of date with the e2e specs. '
                'Regenerate with `node website/e2e/cookbook.js` and commit it.'
            )


class TestTheDocsSiteCarriesIt:
    def test_mkdocs_lists_the_cookbook(self):
        """Generating it is not enough; the docs site has to show it.

        A cookbook nobody navigates to is a file, not documentation.
        """
        mkdocs = (REPO / 'mkdocs.yml').read_text(encoding='utf-8')
        assert 'cookbook.md' in mkdocs, (
            'cookbook.md is not in the mkdocs nav, so the docs site does not '
            'include it'
        )


class TestTheRecipesMediaStaysOutOfGit:
    """`./al recipes` writes each recipe's recording and GIF to docs/recipes,
    for watching, and the docs served locally play the recordings; git ignores
    them. A GIF does not compress against its last version, so committing them
    added megabytes to history on every refresh."""

    def test_no_page_links_recipe_media(self):
        """The hook makes a player only where the file is; a page never names it."""
        linked = [
            (page.relative_to(REPO).as_posix(), found)
            for page in sorted((REPO / 'docs').rglob('*.md'))
            for found in re.findall(
                r'(?:\]\(|src=")((?:\.\./)*recipes/[^)"\s]+)',
                page.read_text(encoding='utf-8'),
            )
        ]
        assert not linked, (
            f'{linked}: a clean checkout lacks these. Place a walkthrough '
            'with <!-- recipe: TITLE --> instead.'
        )

    def test_git_tracks_nothing_in_docs_recipes(self):
        tracked = tracked_recipe_files()
        if tracked is None:
            pytest.skip('git cannot say what docs/recipes tracks here')
        assert not tracked, f'docs/recipes tracks {sorted(tracked)}; it commits nothing'
