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
