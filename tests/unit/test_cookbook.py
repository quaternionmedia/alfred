"""The cookbook is generated, so it cannot disagree with the suite.

The docs, tests and recipes are meant to be one object rather than three that
drift. `website/e2e/cookbook.js` renders `docs/cookbook.md` from the end-to-end
specs, which makes the tests the source and the prose a build artefact -- prose
describing behaviour goes stale silently, a test describing behaviour goes red.

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
RECIPES = REPO / 'docs' / 'recipes'


def spec_files():
    return sorted(E2E.glob('*.spec.js'))


def titles_in(path):
    """Every test.describe/test title in a spec, as written."""
    source = path.read_text(encoding='utf-8')
    pattern = (
        r"""(?:test\.describe|test)\s*(?:\.\w+)?\s*"""
        r"""\(\s*(['"`])((?:\\.|(?!\1)[\s\S])*?)\1"""
    )
    return [m.group(2) for m in re.finditer(pattern, source)]


def recipe_slug(title):
    """A recipe's file name, as the collector and the generator make it."""
    name = re.sub(r'^recipe:\s*', '', title, flags=re.I)
    return re.sub(r'[^a-z0-9]+', '-', name, flags=re.I).strip('-').lower()


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
        missing = []
        for spec in spec_files():
            heading = spec.name.replace('.spec.js', '').replace('-', ' ')
            if heading not in text:
                missing.append(spec.name)
        assert not missing, f'specs absent from the cookbook: {missing}. Regenerate it.'

    def test_every_test_title_appears(self):
        """The recipes are the tests, so all of them have to be there.

        Parameterised titles carry a `${...}` expression that the generator
        renders as a placeholder, so those are compared on their literal
        prefix rather than in full.
        """
        text = COOKBOOK.read_text(encoding='utf-8')
        missing = []
        for spec in spec_files():
            for title in titles_in(spec):
                literal = title.split('${')[0].strip()
                if len(literal) < 8:
                    # Too short to identify; the placeholder cases are covered
                    # by the spec-level check above.
                    continue
                if literal not in text:
                    missing.append(f'{spec.name}: {title}')
        assert not missing, (
            'recipes missing from the cookbook, so it is out of date:\n'
            + '\n'.join(missing[:10])
            + '\nRegenerate with `node website/e2e/cookbook.js`.'
        )

    @pytest.mark.skipif(shutil.which('node') is None, reason='no node available')
    def test_regenerating_changes_nothing(self):
        """The committed file is exactly what the generator produces.

        The strongest form of the claim: not "it looks current" but "running
        the generator right now produces this byte for byte". Anything else
        and the cookbook is a snapshot of whatever the last person ran.
        """
        before = COOKBOOK.read_text(encoding='utf-8')
        result = subprocess.run(
            ['node', str(GENERATOR)],
            cwd=str(REPO / 'website'),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f'generator failed: {result.stderr[-400:]}'

        after = COOKBOOK.read_text(encoding='utf-8')
        if before != after:
            COOKBOOK.write_text(before, encoding='utf-8')
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


class TestTheCookbookLinksOnlyWhatIsCommitted:
    def test_every_recipe_file_it_links_is_a_tracked_gif(self):
        """The committed cookbook cannot name a file a clean checkout lacks.

        It linked `recipes/<slug>.webm` whenever a recording existed locally,
        and recordings are git-ignored -- so a cookbook regenerated on a
        machine that had recorded the recipes linked files nobody else had.
        It links a recipe's GIF, and only once git tracks it.
        """
        linked = re.findall(
            r'\]\((recipes/[^)\s]+)\)', COOKBOOK.read_text(encoding='utf-8')
        )
        tracked = tracked_recipe_files()
        problems = []
        for link in linked:
            name = link.split('/', 1)[1]
            if not name.endswith('.gif'):
                problems.append(f'{link} is not a GIF')
            elif not (RECIPES / name).is_file():
                problems.append(f'{link} does not exist')
            elif tracked is not None and name not in tracked:
                problems.append(f'{link} is not tracked by git')
        assert not problems, (
            f'docs/cookbook.md links {problems}. Commit the GIF, or regenerate '
            'with `node website/e2e/cookbook.js`.'
        )


class TestTheRecipeGifs:
    """The GIFs are committed, so they are held to their recipes and a size.

    `./al recipes` makes one from each passing recipe's recording
    (scripts/recipe_gifs.py): 720 pixels wide, and at most MAX_BYTES, so the
    repository grows by what the docs need and no more.
    """

    MAX_BYTES = 1_500_000

    def gifs(self):
        return sorted(RECIPES.glob('*.gif'))

    def test_each_gif_is_for_a_recipe_the_suite_has(self):
        recipes = {
            recipe_slug(title)
            for title in titles_in(E2E / 'recipes.spec.js')
            if title.lower().startswith('recipe:')
        }
        orphans = [gif.name for gif in self.gifs() if gif.stem not in recipes]
        assert not orphans, (
            f'GIFs for recipes recipes.spec.js no longer has: {orphans}. '
            'Run ./al recipes, which clears them, or delete them.'
        )

    def test_each_gif_is_a_gif_of_the_width_and_size_the_docs_take(self):
        problems = []
        for gif in self.gifs():
            head = gif.read_bytes()[:10]
            width = int.from_bytes(head[6:8], 'little')
            size = gif.stat().st_size
            if head[:6] not in (b'GIF87a', b'GIF89a'):
                problems.append(f'{gif.name} is not a GIF')
            elif not 700 <= width <= 740:
                problems.append(f'{gif.name} is {width} pixels wide, not about 720')
            if size > self.MAX_BYTES:
                problems.append(f'{gif.name} is {size} bytes, over {self.MAX_BYTES}')
        assert not problems, problems

    def test_no_stub_or_recording_is_committed_in_their_place(self):
        """docs/recipes commits GIFs: no SVG stub, and no recording."""
        tracked = tracked_recipe_files()
        if tracked is None:
            pytest.skip('git cannot say what docs/recipes tracks here')
        others = sorted(name for name in tracked if not name.endswith('.gif'))
        assert not others, f'docs/recipes tracks {others}; it commits GIFs only'
