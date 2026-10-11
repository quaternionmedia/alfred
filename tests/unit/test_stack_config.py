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


def strip_comments(text):
    """Drop whole-line comments.

    Without this every assertion here can be satisfied by prose. The volume
    these tests exist to protect sits under eight lines of commentary that
    explain it, and `'- /app/node_modules' in text` is true of
    `# - /app/node_modules` -- so commenting the line out, the single most
    likely way to break it, left the suite green. A test that its own
    explanatory comment can satisfy is worse than no test.
    """
    return '\n'.join(
        line for line in text.split('\n') if not line.strip().startswith('#')
    )


def service_block(compose_text, service):
    """The lines of one service, by indentation. Valid for these files.

    Raises rather than returning empty when the service is absent: an empty
    block silently satisfies every `not in` assertion and fails `in` ones with
    a misleading message about the wrong thing.
    """
    lines = strip_comments(compose_text).split('\n')
    out, inside = [], False
    for line in lines:
        if re.match(rf'^  {re.escape(service)}:\s*(#.*)?$', line):
            inside = True
            continue
        if inside:
            if line.strip() and not line.startswith('   '):
                break
            out.append(line)
    if not inside:
        raise AssertionError(
            f'no service named {service!r} at two-space indentation. '
            'If it was renamed, these tests need renaming with it.'
        )
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
        assert re.search(r'^\s*-\s*/app/node_modules\s*$', website, re.M), (
            'The website service must mask /app/node_modules with its own '
            'volume. Without it the ./website:/app bind mount hands the '
            "container the host's node_modules, whose native bindings are "
            "for the host's platform, not the container's."
        )

    def test_the_bind_mount_the_volume_masks_is_still_there(self):
        """The masking volume is only meaningful against the mount it masks.

        Asserting the mask alone would keep passing if someone removed
        ./website:/app -- at which point src/ edits stop reaching parcel and
        the api serves a stale dist/, with the suite green.
        """
        website = service_block(read('docker-compose.yml'), 'website')
        assert re.search(r'^\s*-\s*\./website/?:/app/?\s*$', website, re.M), (
            'The website service must still bind-mount ./website to /app; '
            'that mount is how src/ reaches parcel and dist/ reaches the api.'
        )

    def test_the_website_image_installs_its_own_dependencies(self):
        dockerfile = strip_comments(read('website/Dockerfile'))
        copy = re.search(r'^COPY\s+.*package\.json.*yarn\.lock.*$', dockerfile, re.M)
        install = re.search(r'^RUN\s+yarn\s+install\b.*$', dockerfile, re.M)
        assert install, (
            'The website image must install dependencies at build time. An '
            'anonymous volume is seeded from the image, so if the image has '
            'no node_modules the volume is empty and parcel is simply absent.'
        )
        assert copy, 'Copy package.json and yarn.lock before installing.'
        assert copy.start() < install.start(), (
            'COPY of the manifests must precede RUN yarn install -- otherwise '
            'the build fails outright, with nothing to install from.'
        )

    def test_the_website_install_includes_dev_dependencies(self):
        """parcel is a devDependency. An install that skips it builds nothing.

        `yarn install --production` is the plausible edit here -- it looks like
        an image-size win -- and it leaves the anonymous volume populated but
        parcel absent, so the container exits at startup with the same shape of
        error this file was written for. --ignore-scripts is the other one: it
        skips the postinstall that puts the native binding in place.
        """
        dockerfile = strip_comments(read('website/Dockerfile'))
        install = re.search(r'^RUN\s+yarn\s+install\b.*$', dockerfile, re.M)
        assert install, 'no `RUN yarn install` line'
        for flag in ('--production', '--prod', '--ignore-scripts'):
            assert flag not in install.group(0), (
                f'{flag} on the website install drops what the build needs: '
                'parcel is a devDependency, and its native binding is placed '
                'by a postinstall script.'
            )

    def test_the_e2e_container_does_not_use_the_host_node_modules(self):
        """The same rule, for the container that actually runs the tests.

        test_e2e.yml bind-mounts ./website into the runner and installs inside
        it. Without a mask that install lands in the host's node_modules --
        Linux binaries and POSIX symlinks -- so `./al test` breaks the host
        Playwright setup that website/e2e/README.md asks for. This is the same
        defect as the website service's, in the opposite direction.
        """
        e2e = service_block(read('test_e2e.yml'), 'e2e')
        assert re.search(r'^\s*-\s*/e2e/node_modules\s*$', e2e, re.M), (
            'The e2e service must mask /e2e/node_modules, or its npm install '
            "writes the container's dependencies into the host's checkout."
        )

    def test_the_website_image_installs_from_the_committed_lockfile(self):
        assert '--frozen-lockfile' in strip_comments(read('website/Dockerfile')), (
            'Install with --frozen-lockfile. yarn.lock is committed precisely '
            'so the image cannot silently resolve something else; parcel and '
            '@parcel/transformer-sass must agree on a version or the build '
            'fails.'
        )

    def test_the_lockfile_the_image_installs_from_is_committed(self):
        """--frozen-lockfile is a promise about a file that has to exist.

        website/yarn.lock is committed against a .gitignore that would
        otherwise exclude it. Lose that negation and the flag turns from a
        guarantee into a build failure: "Your lockfile needs to be updated".
        """
        lockfile = REPO / 'website' / 'yarn.lock'
        assert lockfile.is_file(), 'website/yarn.lock is missing'
        tracked = subprocess.run(
            ['git', 'ls-files', '--error-unmatch', 'website/yarn.lock'],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        assert tracked.returncode == 0, (
            'website/yarn.lock exists but is not tracked by git, so a fresh '
            'clone cannot honour --frozen-lockfile.'
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
        # Any top-level line, not just the first: a leading comment or blank
        # line was enough to hide the key from a `split('\n')[0]` check.
        offenders = [
            line
            for line in strip_comments(read(compose)).split('\n')
            if re.match(r'^version:', line)
        ]
        assert not offenders, (
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
