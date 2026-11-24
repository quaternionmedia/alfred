"""What the docs site's build checks, and what its pages load.

mkdocs can report a page left out of the nav, a link to no page or file, an
anchor no heading makes, and an absolute link -- each at the level mkdocs.yml
gives it, and most of them at `info` by default, which nobody reads. Two
pages sat outside the nav for years that way. These hold every check at
`warn`, and the docs workflow's build at `--strict`, which makes a warning
fatal before mike deploys anything.

Separately, the site loaded Google Fonts on every page view and an emoji from
a CDN; the open-license record asks that frontend assets come from the site's
own origin.

And the tools that build it are declared and pinned. `./al docs` runs mkdocs
on the host, which nothing named, so a fresh clone could not know what to
install; `./al prod` built the site with `squidfunk/mkdocs-material` at
whatever `latest` meant that day.
"""

import re
import tomllib
from pathlib import Path

import yaml
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

REPO = Path(__file__).resolve().parents[2]


class _Loader(yaml.SafeLoader):
    """mkdocs.yml may carry mkdocs' own tags (`!ENV`, `!!python/name:`).

    Read as nothing, so a tag added later fails the assertion it affects
    rather than every test here with a ConstructorError.
    """


_Loader.add_multi_constructor('!', lambda loader, suffix, node: None)
_Loader.add_multi_constructor(
    'tag:yaml.org,2002:python/', lambda loader, suffix, node: None
)


def load(relative):
    return yaml.load((REPO / relative).read_text(encoding='utf-8'), Loader=_Loader)


class TestTheBuildChecksEverything:
    CHECKS = [
        'omitted_files',
        'not_found',
        'absolute_links',
        'unrecognized_links',
        'anchors',
    ]

    def test_every_check_mkdocs_makes_is_a_warning(self):
        validation = load('mkdocs.yml').get('validation') or {}
        weaker = {
            check: validation.get(check, 'the default')
            for check in self.CHECKS
            if validation.get(check) != 'warn'
        }
        assert not weaker, (
            f'mkdocs.yml leaves {weaker}; set each to `warn` under '
            '`validation:`, so the strict build in CI fails on it'
        )

    def test_ci_builds_strictly_before_it_deploys(self):
        workflow = load('.github/workflows/docs.yml')
        # PyYAML reads the bare key `on` as the boolean true.
        triggers = workflow.get('on', workflow.get(True)) or {}
        jobs = workflow['jobs']
        commands = [
            line.strip()
            for step in jobs['build']['steps']
            for line in step.get('run', '').split('\n')
        ]
        assert 'mkdocs build --strict' in commands, (
            'the docs workflow must build with --strict: a warning is otherwise '
            'printed and the site deployed anyway'
        )
        assert 'pull_request' in triggers, (
            'build the docs on pull requests, so a broken link is found before '
            'it is merged rather than by the deploy'
        )
        needs = jobs['deploy'].get('needs')
        assert needs == 'build', 'the deploy must need the strict build'
        condition = jobs['deploy'].get('if')
        assert (
            condition == "github.event_name == 'push'"
        ), 'deploy from pushes only: a pull request builds, and never publishes'


class TestThePagesLoadNothingFromAnotherHost:
    def test_the_theme_uses_the_readers_fonts(self):
        """Material's default fonts are fetched from Google Fonts per view."""
        assert (
            load('mkdocs.yml')['theme'].get('font') is False
        ), 'set `theme: font: false`; the default loads Google Fonts'

    def test_no_emoji_extension_turns_a_shortcode_into_a_cdn_image(self):
        """`:wink:` became an <img> from cdn.jsdelivr.net."""
        extensions = [
            next(iter(entry)) if isinstance(entry, dict) else entry
            for entry in load('mkdocs.yml').get('markdown_extensions', [])
        ]
        assert 'pymdownx.emoji' not in extensions, (
            'pymdownx.emoji draws emoji as images from a CDN; write the '
            'character itself'
        )


def docs_group():
    """pyproject.toml's docs group, as {name: requirement}."""
    groups = tomllib.loads((REPO / 'pyproject.toml').read_text(encoding='utf-8'))
    declared = groups['tool']['pdm']['dev-dependencies'].get('docs', [])
    return {
        canonicalize_name(Requirement(line).name): Requirement(line)
        for line in declared
    }


def locked(name):
    lock = tomllib.loads((REPO / 'pdm.lock').read_text(encoding='utf-8'))
    for package in lock['package']:
        if canonicalize_name(package['name']) == name:
            return package
    return None


class TestTheToolsThatBuildItAreDeclared:
    def test_the_docs_group_names_what_ci_builds_with(self):
        """`./al docs` runs mkdocs on the host; the group says what to install,
        in the ranges the docs workflow installs."""
        workflow = load('.github/workflows/docs.yml')
        installs = [
            step['run']
            for step in workflow['jobs']['build']['steps']
            if 'pip install' in step.get('run', '')
        ]
        assert installs, 'the docs workflow installs nothing to build with'
        ci = {
            canonicalize_name(Requirement(spec).name): str(Requirement(spec))
            for spec in re.findall(r"'([^']+)'", installs[0])
        }
        group = {name: str(requirement) for name, requirement in docs_group().items()}
        assert group == ci, (
            f"pyproject.toml's docs group is {group}; the docs workflow builds "
            f'with {ci}. Keep the two in step.'
        )

    def test_the_docs_group_is_locked(self):
        lock = tomllib.loads((REPO / 'pdm.lock').read_text(encoding='utf-8'))
        assert 'docs' in lock['metadata']['groups'], 'pdm.lock has no docs group'
        for name, requirement in docs_group().items():
            package = locked(name)
            assert package and 'docs' in package['groups'], f'{name} is not locked'
            assert Version(package['version']) in requirement.specifier

    def test_prod_builds_the_docs_with_the_release_the_lock_holds(self):
        """An image tag is a moving target unless it names a release."""
        al = (REPO / 'al').read_text(encoding='utf-8')
        images = re.findall(r'squidfunk/mkdocs-material(?::(\S+))?', al)
        assert images, './al no longer builds the docs with the Material image'
        material = locked('mkdocs-material')
        for tag in images:
            assert re.fullmatch(r'\d+\.\d+\.\d+', tag or ''), (
                f'./al prod runs squidfunk/mkdocs-material:{tag or "latest"}; '
                'pin it to a release'
            )
            assert material and tag == material['version'], (
                f'./al prod builds with Material {tag}, and pdm.lock holds '
                f"{material and material['version']} for ./al docs"
            )
