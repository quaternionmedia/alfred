"""Invariants of the dev stack's own configuration.

Everything else in this suite tests Python. These test the compose files and
Dockerfiles, because that is where the failures actually were: for most of this
project's recent history the stack did not start, and not one of those failures
was a bug in the application code.

Deliberately no YAML parser. These read the files as text and look for
specific, distinctive lines, which is narrower than parsing -- reordering a
compose file freely could fool them -- and it is the right trade here: the
point is to fail when someone deletes a line that has already cost a day, not
to model YAML. Comments are stripped first, because otherwise the prose
explaining a line satisfies the assertion about it.

`test_the_website_container_resolves_its_parcel_binding` is the one that would
actually have caught the bug these were written for. It needs Docker.
"""

import re
import subprocess
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name

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


# The lockfiles pip installs, both exported from pdm.lock: what the image runs,
# and the test tools from the same resolution.
EXPORTS = ['requirements.lock', 'requirements-test.lock']


def exported_pins(relative):
    """name -> version for every `==` pin in an exported requirements file."""
    pins = {}
    for line in read(relative).split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        name, _, rest = line.partition('==')
        if rest:
            name = canonicalize_name(name.split('[')[0])
            pins[name] = rest.split(';')[0].strip()
    return pins


def pyproject():
    return tomllib.loads(read('pyproject.toml'))


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


class TestDependencyPinning:
    """The image and the test suite must run the same versions.

    They did not. The image installed with `pip install -e .`, re-resolving
    the loose ranges in pyproject.toml on every build, so it ran beanie 1.30,
    fastapi 0.125 and motor 3.7 while the suite ran 1.20, 0.100 and 3.2. Every
    test was evidence about versions the application did not use -- and one
    test in this repository already failed for exactly that reason, pinning an
    import path that had moved between the two beanie versions.
    """

    def test_the_image_installs_from_the_lockfile(self):
        dockerfile = strip_comments(read('Dockerfile'))
        assert re.search(r'pip3?\s+install[^\n]*-r\s+requirements\.lock', dockerfile), (
            'the API image must install pinned dependencies from '
            'requirements.lock, or its versions are whatever pip resolved on '
            'the day of the build'
        )

    def test_the_pins_are_installed_before_the_project(self):
        """Order decides whether the pins bind.

        `pip install -e .` after the pins finds every version already
        satisfied. Before them, it resolves the ranges first and the pins
        become a no-op that looks like it is working.
        """
        dockerfile = strip_comments(read('Dockerfile'))
        pins = re.search(
            r'^RUN\s+pip3?\s+install[^\n]*requirements\.lock', dockerfile, re.M
        )
        project = re.search(
            r'^RUN\s+pip3?\s+install\s+(?:--?[\w-]+\s+)*-e\s+\.', dockerfile, re.M
        )
        assert pins and project
        assert pins.start() < project.start(), (
            'requirements.lock must be installed before `pip install -e .`, '
            'or the loose ranges resolve first and the pins do nothing'
        )

    def test_the_suite_installs_the_lockfiles_before_the_project(self):
        """The suite is evidence about the image only if it runs its versions.

        The coverage session installed `-e ..[test]` and nothing else, which
        resolves pyproject.toml's ranges on the day: the suite ran numpy 2.4
        and starlette 0.50 while the image ran the lockfile's 1.24 and 0.44.
        It installs both exports now, with --no-deps (see TestExactInstall),
        and no later than the project.
        """
        noxfile = strip_comments(read('tests/noxfile.py'))
        assert 'def coverage(' in noxfile, 'no coverage session in tests/noxfile.py'
        session = noxfile[noxfile.index('def coverage(') :]
        calls = re.findall(r'session\.install\(([^)]*)\)', session)
        project = next(
            (i for i, call in enumerate(calls) if re.search(r"'-e',\s*'\.\.'", call)),
            None,
        )
        assert project is not None, 'no `-e ..` install in the coverage session'
        assert "'--no-deps'" in calls[project], (
            'install the project with --no-deps: resolving it refuses the '
            'override the lock carries'
        )
        for export in EXPORTS:
            lock = next(
                (i for i, call in enumerate(calls) if f"'../{export}'" in call), None
            )
            assert lock is not None and lock <= project, (
                f'the coverage session must install ../{export} no later than '
                'the project, or the suite tests what pip resolves instead of '
                'what the image runs'
            )
            assert "'--no-deps'" in calls[lock], f'install ../{export} with --no-deps'

    @pytest.mark.parametrize('export', EXPORTS)
    def test_each_export_agrees_with_pdm_lock(self, export):
        """The exported files are copies, and copies drift.

        Rather than shell out to pdm -- which is not in the test image -- this
        checks that every package an export pins is in pdm.lock at the same
        version. By name: the search this replaces looked for the bare
        `version = "..."` line, which any package sharing the version
        satisfied. Regenerate with the command in the file's own header.
        """
        exported = exported_pins(export)
        assert exported, f'{export} pins nothing'
        locked = {}
        for package in tomllib.loads(read('pdm.lock'))['package']:
            name = canonicalize_name(package['name'])
            locked.setdefault(name, set()).add(package['version'])
        mismatched = [
            f'{name}=={version}'
            for name, version in exported.items()
            if version not in locked.get(name, set())
        ]
        assert not mismatched, (
            f'{export} pins versions pdm.lock does not: {mismatched[:5]}. '
            'Regenerate it -- see the header of the file.'
        )

    def test_every_dependency_is_exported_at_a_version_it_accepts(self):
        """The check a resolving `pip install -e .` used to make, made here.

        The image installs the project with --no-deps, so a dependency added
        to pyproject.toml and never relocked would not fail the build -- it
        would just be missing from the image.
        """
        exported = exported_pins('requirements.lock')
        text = read('requirements.lock')
        problems = []
        for spec in pyproject()['project']['dependencies']:
            requirement = Requirement(spec)
            name = canonicalize_name(requirement.name)
            if name == 'al-otto':
                continue  # the vendored submodule, installed editable
            if requirement.url:
                if not re.search(rf'^{re.escape(requirement.name)} @ ', text, re.M):
                    problems.append(f'{requirement.name} is not exported')
            elif name not in exported:
                problems.append(f'{requirement.name} is not exported')
            elif not requirement.specifier.contains(exported[name], prereleases=True):
                problems.append(
                    f'{requirement.name}=={exported[name]} is outside '
                    f'{requirement.specifier}'
                )
        assert not problems, (
            f'requirements.lock does not satisfy pyproject.toml: {problems}. '
            'Relock and regenerate it.'
        )

    def test_the_overrides_hold_in_the_export(self):
        """An override the lock does not honour protects nothing.

        When python-multipart's override was added, `pdm lock --update-reuse`
        kept it at 0.0.6 and recorded the lock as current; `pdm update
        python-multipart` was what moved it.
        """
        overrides = pyproject()['tool']['pdm']['resolution']['overrides']
        exported = exported_pins('requirements.lock')
        for name, spec in overrides.items():
            version = exported.get(canonicalize_name(name))
            assert version and SpecifierSet(spec).contains(version), (
                f'{name} is exported at {version}, outside its override {spec}. '
                f'Relock with `pdm update {name}` and regenerate the export.'
            )

    def test_the_installed_otto_is_the_vendored_one(self):
        """Tests must import the same engine the application runs.

        The image installs `alfred/otto` editable; a developer environment
        that installed the published al-otto instead would import a different
        copy of the same package. That is not hypothetical -- it was the state
        of this checkout, so a fix made in the submodule was invisible to the
        local suite while the container had it. Every otto assertion in this
        repository was evidence about the wrong code.

        Fix with: pip install -e alfred/otto --no-deps
        """
        import otto

        installed = Path(otto.__file__).resolve()
        vendored = (REPO / 'alfred' / 'otto' / 'otto').resolve()
        assert vendored in installed.parents or installed.parent == vendored, (
            f'otto is imported from {installed.parent}, not the vendored '
            f'submodule at {vendored}. The suite is testing a different copy '
            'of the engine than the image runs. '
            'Fix with: pip install -e alfred/otto --no-deps'
        )

    def test_al_otto_is_not_pinned_in_the_export(self):
        """The vendored submodule must win.

        The image installs alfred/otto editable. If requirements.lock also
        pinned the published al-otto, pip would install that too and the
        editable checkout would be shadowed -- so a fix made in the submodule
        would appear to have no effect.
        """
        for line in read('requirements.lock').split('\n'):
            assert not line.strip().lower().startswith('al-otto=='), (
                'al-otto is pinned in requirements.lock; it would shadow the '
                'vendored submodule the image installs editable'
            )

    def test_the_installed_vox_is_the_vendored_one(self):
        """The sound engine's client is vendored the way otto is, for the
        same reason: the suite must import the copy the image runs.

        vox is not on an index alfred installs from, so the likelier mistake
        is the other one -- a checkout whose environment never installed it,
        or installed some other clone of it. Either way every audio-engine
        assertion here would be evidence about the wrong code.

        Fix with: pip install -e alfred/vox --no-deps
        """
        import vox

        installed = Path(vox.__file__).resolve()
        vendored = (REPO / 'alfred' / 'vox' / 'vox').resolve()
        assert vendored in installed.parents or installed.parent == vendored, (
            f'vox is imported from {installed.parent}, not the vendored '
            f'submodule at {vendored}. '
            'Fix with: pip install -e alfred/vox --no-deps'
        )

    def test_vox_is_not_pinned_in_the_export(self):
        """Nothing may install a second vox over the vendored one."""
        for line in read('requirements.lock').split('\n'):
            assert not line.strip().lower().startswith('vox=='), (
                'vox is pinned in requirements.lock; it would shadow the '
                'vendored submodule the image installs editable'
            )

    def test_what_the_vox_core_imports_is_locked(self):
        """vox is installed with --no-deps, so its core's one dependency has
        to come from this project's own lock.

        Read from vox's own pyproject rather than restated, so a dependency
        its core gains shows up here as one alfred does not install.
        `pyttsx3` (a synthesizer adapter) and `typer` (its CLI) serve parts of
        vox alfred never imports; the import test below holds that.
        """
        declared = tomllib.loads(read('alfred/vox/pyproject.toml'))['project'][
            'dependencies'
        ]
        exported = exported_pins('requirements.lock')
        unused_here = {'pyttsx3', 'typer'}
        missing = [
            spec
            for spec in declared
            if canonicalize_name(Requirement(spec).name) not in exported
            and canonicalize_name(Requirement(spec).name) not in unused_here
        ]
        assert not missing, (
            f'vox needs {missing}, which requirements.lock does not install. '
            'Add it to pyproject.toml, relock and regenerate the exports.'
        )
        for spec in declared:
            requirement = Requirement(spec)
            name = canonicalize_name(requirement.name)
            if name in exported:
                assert requirement.specifier.contains(
                    exported[name], prereleases=True
                ), f'vox needs {spec}; the lock has {name}=={exported[name]}'

    def test_importing_vox_needs_nothing_alfred_leaves_out(self):
        """The core imports neither its synthesizer adapter nor its CLI.

        Run in a fresh interpreter, so modules this suite imported earlier
        cannot make it pass: what loading `vox` pulls in is the question.
        """
        import sys

        probe = (
            'import sys, vox; '
            'print(",".join(sorted(m for m in ("pyttsx3", "typer", "vox.cli") '
            'if m in sys.modules)))'
        )
        loaded = subprocess.run(
            [sys.executable, '-c', probe],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert loaded == '', f'importing vox loaded {loaded}'

    @pytest.mark.parametrize('path', ['alfred/otto', 'alfred/vox'])
    def test_each_engine_is_a_submodule_on_its_own_remote(self, path):
        """Both engines are vendored the same way: a submodule tracking its
        repository's `main`, at a URL the submodule check can fetch from.

        `.github/workflows/submodule-check.yml` walks every submodule `git
        submodule status` lists, and errors on a filesystem URL -- one that
        resolves only on the machine that added it. This holds the two engines
        to that from the test suite too, where a slip shows before a push.
        """
        text = read('.gitmodules')
        block = re.search(
            rf'^\[submodule "{re.escape(path)}"\]\n((?:[ \t]+.*\n?)+)', text, re.M
        )
        assert block, f'{path} is not declared in .gitmodules'
        fields = dict(
            line.strip().split(' = ', 1)
            for line in block.group(1).splitlines()
            if ' = ' in line
        )
        assert fields.get('path') == path
        assert fields.get('url', '').startswith('https://github.com/quaternionmedia/')
        assert fields.get('branch') == 'main'


class TestExactInstall:
    """Every install path installs pdm's resolution exactly.

    pyproject.toml overrides fastapi-users' exact pin on python-multipart. pdm
    honours an override; pip has no such thing, so a resolving install of the
    lockfile or of the project fails with ResolutionImpossible. The image, the
    suite and CI all install with --no-deps instead, and TestDependencyPinning
    makes the check the resolver used to.
    """

    def test_the_image_installs_the_lock_and_the_project_with_no_deps(self):
        dockerfile = strip_comments(read('Dockerfile'))
        lock = re.search(
            r'^RUN\s+pip3?\s+install\b.*requirements\.lock.*$', dockerfile, re.M
        )
        project = re.search(
            r'^RUN\s+pip3?\s+install\b.*\s-e\s+\.\s*$', dockerfile, re.M
        )
        assert lock and '--no-deps' in lock.group(0).split(), (
            'install requirements.lock with --no-deps: resolving it refuses the '
            'override'
        )
        assert (
            project and '--no-deps' in project.group(0).split()
        ), 'install the project with --no-deps: resolving it refuses the override'

    @pytest.mark.parametrize('workflow', ['CI.yml', 'publish.yml'])
    def test_ci_installs_both_exports_with_no_deps(self, workflow):
        """CI runs the suite as the image and nox do, or it tests other versions."""
        text = strip_comments(read(f'.github/workflows/{workflow}'))
        args = re.findall(r"^\s*pip_args:\s*'([^']*)'", text, re.M)
        assert args, f'{workflow} passes no pip_args'
        for line in args:
            assert '--no-deps' in line.split(), f'{workflow}: pip_args lack --no-deps'
            for export in EXPORTS:
                assert f'-r {export}' in line, f'{workflow}: does not install {export}'
        # The org workflow's `requirements` input installs with the resolver.
        assert not re.search(
            r'^\s*requirements:', text, re.M
        ), f'{workflow} hands a lockfile to the resolving install step'


class TestBothEnginesAreInstalledAlike:
    """otto draws the picture and vox carries the sound, and both are vendored
    submodules installed editable from the checkout -- in the image, in the
    suite and in CI. An install path that has one and not the other tests a
    stack nobody runs.
    """

    def test_the_image_installs_vox_from_the_submodule_with_no_deps(self):
        dockerfile = strip_comments(read('Dockerfile'))
        line = re.search(
            r'^RUN\s+pip3?\s+install\b.*-e\s+alfred/vox\b.*$', dockerfile, re.M
        )
        assert line, 'the image does not install alfred/vox'
        assert '--no-deps' in line.group(0).split(), (
            'install alfred/vox with --no-deps: its core needs only httpx, '
            'which the lockfile carries'
        )

    def test_the_image_installs_vox_before_the_project(self):
        dockerfile = strip_comments(read('Dockerfile'))
        vox = re.search(r'^RUN\s+pip3?\s+install\b.*alfred/vox', dockerfile, re.M)
        project = re.search(
            r'^RUN\s+pip3?\s+install\b.*\s-e\s+\.\s*$', dockerfile, re.M
        )
        assert vox and project and vox.start() < project.start()

    def test_the_suite_installs_vox_from_the_submodule_with_no_deps(self):
        calls = [
            call
            for call in re.findall(
                r'session\.install\(([^)]*)\)', read('tests/noxfile.py')
            )
            if 'alfred/vox' in call
        ]
        assert calls, 'tests/noxfile.py does not install ../alfred/vox'
        assert "'--no-deps'" in calls[0] and "'../alfred/vox'" in calls[0]

    @pytest.mark.parametrize('workflow', ['CI.yml', 'publish.yml'])
    def test_ci_installs_both_engines(self, workflow):
        text = strip_comments(read(f'.github/workflows/{workflow}'))
        for line in re.findall(r"^\s*pip_args:\s*'([^']*)'", text, re.M):
            assert '-e alfred/otto' in line, f'{workflow}: does not install otto'
            assert '-e alfred/vox' in line, f'{workflow}: does not install vox'


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
            line.split()
            for line in read(dockerfile).split('\n')
            if line.strip().upper().startswith('FROM ')
        ]
        assert froms, f'{dockerfile} has no FROM line'
        stages = set()
        for words in froms:
            image = next(word for word in words[1:] if not word.startswith('--'))
            # `FROM api` names a stage built earlier in this file, not a base:
            # it is as pinned as the line that stage started from.
            if image not in stages:
                assert '@sha256:' in image, (
                    f'{dockerfile} must pin its base by digest, got: '
                    f'{" ".join(words)}. An unpinned base makes the build '
                    'depend on the day it runs.'
                )
            if len(words) >= 2 and words[-2].upper() == 'AS':
                stages.add(words[-1])

    def test_the_test_image_is_built_from_this_checkout(self):
        """Not from a tag left behind by whatever ran last.

        tests/Dockerfile was `FROM alfred_api`, which resolves to whichever
        image last carried that tag on the machine. Every test image built for
        the 0.3.x review sat on one two months older than the checkout, and a
        machine that had never built the dev stack had none, so the build went
        to Docker Hub for it. The suite runs on a stage of the root Dockerfile
        instead, built from the commit under test.
        """
        pytest_service = service_block(read('pytest.yml'), 'pytest')
        assert re.search(r'^\s*context:\s*\.\s*$', pytest_service, re.M), (
            'pytest.yml must build from the repository root, where the '
            'Dockerfile with the test stage is'
        )
        assert re.search(
            r'^\s*target:\s*test\s*$', pytest_service, re.M
        ), "pytest.yml must build the root Dockerfile's `test` stage"
        froms = [
            line
            for line in strip_comments(read('Dockerfile')).split('\n')
            if line.upper().startswith('FROM ')
        ]
        assert any(
            re.search(r'(?i)\sAS\s+test\s*$', line) for line in froms
        ), 'the root Dockerfile has no `test` stage'
        assert not re.search(r'(?i)\sAS\s+test\s*$', froms[-1]), (
            'the test stage must not be the last: a build that names no target '
            '-- the api and renderer in every compose file -- gets the last '
            'stage, and would get the test runner'
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
