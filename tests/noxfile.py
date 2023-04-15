import nox
from os.path import join


@nox.session
def blacken(session):
    session.install('black')
    session.run('black', '-S', '-v', '.')


@nox.session
def lint(session):
    session.install('ruff')
    session.run('ruff', '-v', '.')


@nox.session(tags=['test'])
def coverage(session):
    session.install('-e', '..[test]')
    session.run('mkdir', '-p', 'dist')
    session.run('mkdir', '-p', 'site')
    session.run('touch', join('dist', 'index.html'))
    session.env['DATA_DIR'] = '../data'
    session.env['STATIC_DIR'] = './dist'
    session.run(
        'pytest',
        '-vv',
        '--timeout=600',
        '-n',
        'auto',
    )
