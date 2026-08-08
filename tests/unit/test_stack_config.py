"""Invariants of the dev stack's own configuration.

Everything else in this suite tests Python. These test the compose files and
Dockerfiles, because that is where the failures actually were: for most of this
project's recent history the stack did not start, and not one of those failures
was a bug in the application code.

Deliberately no YAML parser. The repository locks only `default` and `render`,
so adding PyYAML for a handful of assertions means re-resolving the whole
lockfile to read five lines. These read the files as text and look for specific,
distinctive lines. That is narrower than parsing -- reordering a compose file
freely could fool them -- and it is the right trade here: the point is to fail
when someone deletes a line that has already cost a day, not to model YAML.

`test_the_website_container_resolves_its_parcel_binding` is the one that would
actually have caught the bug these were written for. It needs Docker.
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

COMPOSE_FILES = [
    'docker-compose.yml',
    'dev.yml',
    'production.yml',
    'pytest.yml',
    'flower.yml',
    'test_e2e.yml',
]


def read(relative):
    return (REPO / relative).read_text(encoding='utf-8')


def service_block(compose_text, service):
    """The lines of one service, by indentation. Valid for these files."""
    lines = compose_text.split('\n')
    out, inside = [], False
    for line in lines:
        if re.match(rf'^  {re.escape(service)}:\s*$', line):
            inside = True
            continue
        if inside:
            if line.strip() and not line.startswith('    '):
                break
            out.append(line)
    return '\n'.join(out)


class TestNodeModulesIsolation:
    """The container's dependencies must not come from the host.

    docker-compose.yml mounts ./website over /app so that src/ edits reach
    parcel and dist/ reaches the api. That mount also covers /app/node_modules,
    and for a long time the image shipped none of its own -- so every
    dependency the container used was whatever the host had installed.

    parcel resolves a native binding per platform. An Alpine container needs
    @parcel/rust-linux-x64-musl; a Windows host installs
    @parcel/rust-win32-x64-msvc and nothing else. So a host `npm install` --
    which the README asks for, to get Playwright -- made the website container
    exit 1 on startup with `Cannot find module '@parcel/rust-linux-x64-musl'`.
    Following the documented setup broke the documented dev command.
    """

    def test_the_website_container_does_not_use_the_host_node_modules(self):
        website = service_block(read('docker-compose.yml'), 'website')
        assert '- /app/node_modules' in website, (
            'The website service must mask /app/node_modules with its own '
            'volume. Without it the ./website:/app bind mount hands the '
            "container the host's node_modules, whose native bindings are "
            "for the host's platform, not the container's."
        )

    def test_the_website_image_installs_its_own_dependencies(self):
        dockerfile = read('website/Dockerfile')
        assert 'yarn install' in dockerfile, (
            'The website image must install dependencies at build time. An '
            'anonymous volume is seeded from the image, so if the image has '
            'no node_modules the volume is empty and parcel is simply absent.'
        )
        assert re.search(r'COPY\s+package\.json\s+yarn\.lock', dockerfile), (
            'Copy the manifests before installing, so the dependency layer '
            'stays cached across source edits.'
        )

    def test_the_website_image_installs_from_the_committed_lockfile(self):
        assert '--frozen-lockfile' in read('website/Dockerfile'), (
            'Install with --frozen-lockfile. yarn.lock is committed precisely '
            'so the image cannot silently resolve something else; parcel and '
            '@parcel/transformer-sass must agree on a version or the build '
            'fails.'
        )


class TestImagePinning:
    """Bases are pinned by digest.

    Unpinned, the API image tracked `FROM python` into 3.14 -- which does not
    ship setuptools -- and stopped building. The website image tracked
    `node:current` into Node 26, which no longer bundles yarn, and `./al init`
    stopped working. Both were pinned; this fails if either drifts back.
    """

    @pytest.mark.parametrize('dockerfile', ['Dockerfile', 'website/Dockerfile'])
    def test_base_image_is_pinned_by_digest(self, dockerfile):
        froms = [
            line
            for line in read(dockerfile).split('\n')
            if line.strip().upper().startswith('FROM ')
        ]
        assert froms, f'{dockerfile} has no FROM line'
        for line in froms:
            assert '@sha256:' in line, (
                f'{dockerfile} must pin its base by digest, got: {line.strip()}. '
                'An unpinned base makes the build depend on the day it runs.'
            )


class TestComposeHygiene:
    @pytest.mark.parametrize('compose', COMPOSE_FILES)
    def test_no_obsolete_version_key(self, compose):
        first = read(compose).split('\n')[0]
        assert not first.startswith('version:'), (
            f'{compose} declares the obsolete top-level `version:` key, which '
            'makes every compose invocation emit a deprecation warning.'
        )

    @pytest.mark.parametrize('compose', COMPOSE_FILES)
    def test_compose_file_is_referenced_by_something(self, compose):
        """A compose file nothing invokes is a trap.

        `./al bats` invoked test_bats.yml, which has never existed in this
        repository -- nothing caught it because nothing checked. This is the
        reverse direction: every compose file present should be reachable.
        """
        haystack = read('al') + read('README.md') + read('AGENTS.md')
        for workflow in (REPO / '.github' / 'workflows').glob('*.yml'):
            haystack += workflow.read_text(encoding='utf-8')
        assert compose in haystack, (
            f'{compose} is not named by ./al, the docs, or any workflow. '
            'Either wire it up or delete it.'
        )


@pytest.mark.needs_docker
class TestStackActuallyStarts:
    """The behavioral version of the above. This is the test that bites."""

    def test_the_website_container_resolves_its_parcel_binding(self):
        """parcel must load inside the container, on the container's platform.

        The config tests above assert the arrangement that makes this true.
        This asserts the outcome, which is what actually matters and what the
        config tests are only a proxy for.
        """
        built = subprocess.run(
            ['docker', 'compose', 'build', 'website'],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        assert built.returncode == 0, f'website image failed to build:\n{built.stderr}'

        result = subprocess.run(
            [
                'docker',
                'compose',
                'run',
                '--rm',
                '--no-deps',
                '--entrypoint',
                'node',
                'website',
                '-e',
                "require('@parcel/rust'); console.log('binding-ok')",
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        assert 'binding-ok' in result.stdout, (
            'parcel\'s native binding did not load inside the container.\n'
            f'stdout: {result.stdout}\nstderr: {result.stderr}'
        )
