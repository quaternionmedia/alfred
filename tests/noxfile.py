from os.path import join

import nox

# What `./al pytest` runs: pytest.yml names no session, so nox runs these.
# Formatting is checked, as CI checks it, and nothing is changed. Without a
# list nox ran every session, `blacken` first, so the suite rewrote the files
# it was about to test and passed code CI then failed. `./al nox -s blacken`
# formats.
nox.options.sessions = ['formatting', 'lint', 'coverage']


# The formatters and linters are pinned deliberately.
#
# These were installed unpinned, so a session resolved to whatever had been
# released that morning, and upstream changed under them: `ruff <path>` was
# removed in favour of `ruff check <path>` in 0.5, and the lint session failed
# with a usage message on code nobody had touched. A version range means the
# gate fails when someone changes the code, not when someone else ships.
@nox.session
def blacken(session):
    session.install('black>=24,<26')
    # From the root, for the same reason lint is: run from `tests/` this
    # formatted 18 test files and never touched the application, while
    # CONTRIBUTING.md tells contributors it is the formatting gate.
    session.chdir('..')
    session.run('black', '-S', '-v', '.')


@nox.session
def formatting(session):
    """Black's check, as CI's format job runs it: fails, with the diff, on any
    file black would change, and changes none."""
    session.install('black>=24,<26')
    session.chdir('..')
    session.run('black', '-S', '--check', '--diff', '.')


@nox.session
def lint(session):
    session.install('ruff>=0.5,<1')
    # `check` is required as of 0.5; the bare form was the deprecated spelling.
    #
    # Run from the repository root, not from here. The session's working
    # directory is `tests/`, so `ruff check .` linted the test suite and never
    # once looked at `alfred/` -- the gate covered everything except the
    # application. Configuration comes from the root pyproject.toml.
    # From the repository root, so ruff discovers pyproject.toml itself and
    # resolves `extend-exclude` against the same root it reports paths from.
    # Passing `..` with an explicit `--config` instead left the excludes
    # unmatched, and the run reported 26 findings inside `alfred/otto` -- a
    # submodule with its own repository, its own CI and its own linting.
    session.chdir('..')
    session.run('ruff', 'check', '.')


@nox.session(tags=['test'])
def coverage(session):
    # Exactly what pdm locked, the way the Dockerfile and CI install it: the
    # image's pins, the test tools from the same resolution, and the project,
    # all with --no-deps. So the suite tests the versions the image runs.
    #
    # It did not. `-e ..[test]` alone resolves pyproject.toml's ranges afresh
    # on every run, so on integrate/review-fixes the suite ran numpy 2.4,
    # fastapi 0.125, starlette 0.50 and beanie 1.30 while the image ran
    # requirements.lock's 1.24, 0.124, 0.44 and 1.29 -- the divergence the
    # lockfile was introduced to end, back again one layer down, and a green
    # suite was evidence about versions nothing deployed.
    #
    # --no-deps so pip resolves nothing: the lock carries overrides pip does
    # not read (see the Dockerfile). test_stack_config.py holds this in place.
    #
    # requirements-render.lock is the engine's `render` extra: optional to pip,
    # not to the templates that draw a box behind their text (title, bullets),
    # which import gizeh and fail without it. It was resolved here on the day,
    # as `alfred/otto[render]`; it is pdm's resolution now, as the image's and
    # CI's are.
    session.install(
        '--no-deps',
        '-r',
        '../requirements.lock',
        '-r',
        '../requirements-test.lock',
        '-r',
        '../requirements-render.lock',
        '-e',
        '..',
    )
    # The vendored engine: the project's `al-otto`, which the --no-deps install
    # above leaves out, from the submodule rather than PyPI -- otherwise the
    # suite imports otto from site-packages and tests a different copy than
    # the image runs, which test_stack_config.py asserts against. With
    # --no-deps, as the image installs it: what it depends on is in the
    # lockfiles above.
    session.install('--no-deps', '-e', '../alfred/otto')
    # The sound engine's client, vendored beside otto and installed the way
    # the image installs it: editable from the submodule, with --no-deps. Its
    # core needs only httpx, which the lockfiles above carry.
    session.install('--no-deps', '-e', '../alfred/vox')
    session.run('mkdir', '-p', 'dist')
    session.run('mkdir', '-p', 'site')
    session.run('touch', join('dist', 'index.html'))
    session.env['STATIC_DIR'] = './dist'
    # Arguments after `--` narrow the run: `./al nox -s coverage -- unit` is
    # the unit tier alone, alfred's quick suite in `./al family test`.
    session.run(
        'pytest',
        '-vv',
        '--timeout=600',
        '-n',
        'auto',
        *session.posargs,
    )
