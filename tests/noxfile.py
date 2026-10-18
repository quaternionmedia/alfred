from os.path import join

import nox


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
    session.install('-e', '..[test]')
    # The vendored engine, over any published `al-otto` the extras dragged in:
    # otherwise the suite imports otto from site-packages and tests a different
    # copy than the image runs, which test_stack_config.py asserts against.
    #
    # With `[render]`, because the engine's optional dependencies are not
    # optional to the templates that use them. Installed bare, `gizeh` was
    # missing and every text template raised ImportError -- which the templates
    # then caught and turned into a `None` clip, so the suite reported "title
    # renders to nothing" rather than "a dependency is absent". The API image
    # has these, so the tests were failing on a gap that existed only in the
    # tests.
    session.install('-e', '../alfred/otto[render]')
    session.run('mkdir', '-p', 'dist')
    session.run('mkdir', '-p', 'site')
    session.run('touch', join('dist', 'index.html'))
    session.env['STATIC_DIR'] = './dist'
    session.run(
        'pytest',
        '-vv',
        '--timeout=600',
        '-n',
        'auto',
    )
