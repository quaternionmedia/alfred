from os.path import join

import nox

# What `./al pytest` runs. Checks formatting, changes nothing: never blacken.
nox.options.sessions = ['formatting', 'lint', 'coverage']


# Tool ranges are pinned: the gate fails on a change here, not on a release.
# CI's shared format job installs black's newest release: keep its major here.
# Every session runs from the repository root, as CI does.
BLACK = 'black>=26,<27'
RUFF = 'ruff>=0.5,<1'


@nox.session
def blacken(session):
    session.install(BLACK)
    session.chdir('..')
    session.run('black', '-S', '-v', '.')


@nox.session
def formatting(session):
    """Black's check, as CI's format job runs it: fails, with the diff, on any
    file black would change, and changes none."""
    session.install(BLACK)
    session.chdir('..')
    session.run('black', '-S', '--check', '--diff', '.')


@nox.session
def lint(session):
    session.install(RUFF)
    # From the root, so `extend-exclude` matches; not `..` with --config.
    session.chdir('..')
    session.run('ruff', 'check', '.')


@nox.session(tags=['test'])
def coverage(session):
    # The locks as the image installs them, --no-deps; render's extra included,
    # which the boxed text templates import. See docs/dependencies.md#lockfiles.
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
    # The engines from their submodules, as the image has them.
    session.install('--no-deps', '-e', '../alfred/otto')
    session.install('--no-deps', '-e', '../alfred/vox')
    session.run('mkdir', '-p', 'dist')
    session.run('mkdir', '-p', 'site')
    session.run('touch', join('dist', 'index.html'))
    session.env['STATIC_DIR'] = './dist'
    # `./al nox -s coverage -- unit`: the unit tier alone.
    session.run(
        'pytest',
        '-vv',
        '--timeout=600',
        '-n',
        'auto',
        *session.posargs,
    )
