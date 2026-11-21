#!/usr/bin/env python3
"""alfred as processes on this machine, without Docker.

`./al host` runs this. The api, a render worker and the site's watcher start
from this checkout's own environment, against a MongoDB the machine can
reach, with joe beside them as `./al family up` starts it: the code the dev
stack runs, for a machine whose Docker is down or absent. docs/host-run.md
says what the run lacks beside the stack.

    ./al host [status]      what answers on each port, and what `up` started
    ./al host up            joe, then the api, the worker and the site
    ./al host down          what `up` started

ALFRED_HOST_DB names the database, mongodb://127.0.0.1:27018 unless set: one
answering on a port the dev stack does not publish, so both can be started
without moving either. ALFRED_PORT and ALFRED_HMR_PORT are the api's and the
site's, as for the stack; ALFRED_JOE_HOST and ALFRED_JOE_PORT are joe's, as
for the family; ALFRED_HOST_STATE is where the logs and the record of what
started are kept, .host/ unless set. The environment passes through to the
api and the worker, so `ALFRED_DEV_SKIP_AUTH=1 ./al host up` serves without
a login, as the stack does under the same setting.

The standard library only, as family.py, which this imports for joe, the
probes and what is printed; nothing it prints carries a secret.
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

# family.py beside this file, however this file was started.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import family  # noqa: E402
from family import LOOPBACK, ROOT, fetch, kill_tree, say, shown, tail, title_at, tool

STATE = Path(os.environ.get('ALFRED_HOST_STATE') or ROOT / '.host')
LOGS = STATE / 'logs'
RECORD = STATE / 'processes.json'
JOE_RECORD = STATE / 'joe.json'
DEFAULT_DB = 'mongodb://127.0.0.1:27018'
PARCEL = ROOT / 'website' / 'node_modules' / 'parcel' / 'lib' / 'bin.js'
# Seconds the api's reloader gives open connections before it restarts.
RELOAD_GRACE = 3
KEY_FILE = ROOT / '.secret_key.local'
# How long each process is given to say it is up, in seconds.
API_WAIT = 120
SITE_WAIT = 120
WORKER_WAIT = 60


# --- what is asked for -------------------------------------------------------


def settings(env=None):
    """The database, the api's port and the site's, from the environment."""
    env = os.environ if env is None else env
    return {
        'db': env.get('ALFRED_HOST_DB') or DEFAULT_DB,
        'port': int(env.get('ALFRED_PORT') or 1732),
        'hmr': int(env.get('ALFRED_HMR_PORT') or 1733),
    }


def interpreter(root=None):
    """The checkout's own Python: what `.pdm-python` names, else the
    in-project virtualenv; None where pdm has made neither."""
    root = ROOT if root is None else root
    noted = root / '.pdm-python'
    if noted.is_file():
        path = Path(noted.read_text(encoding='utf-8').strip())
        if path.is_file():
            return path
    for candidate in (
        root / '.venv' / 'Scripts' / 'python.exe',
        root / '.venv' / 'bin' / 'python',
    ):
        if candidate.is_file():
            return candidate
    return None


def key_from(path):
    """ALFRED_SECRET_KEY as `.secret_key.local` holds it, or None."""
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except OSError:
        return None
    for line in lines:
        name, sep, value = line.partition('=')
        if sep and name.strip() == 'ALFRED_SECRET_KEY' and value.strip():
            return value.strip()
    return None


def environment(env=None, engine_port=None, key_file=None):
    """What the stacks wire for the api and the worker (docker-compose.yml,
    dev.yml), pointed at this machine, over the environment, which passes
    through: the database, the broker, where the site and the media are, and
    the audio engine unless one is already named."""
    env = dict(os.environ if env is None else env)
    chosen = settings(env)
    key = key_from(KEY_FILE if key_file is None else key_file)
    if key and not env.get('ALFRED_SECRET_KEY'):
        env['ALFRED_SECRET_KEY'] = key
    env.update(
        {
            'DB_URL': chosen['db'],
            'DB_NAME': 'alfred',
            'CELERY_BROKER': chosen['db'] + '/celery',
            'CELERY_BACKEND': chosen['db'] + '/celery',
            'STATIC_DIR': 'website/dist',
            'VIDEO_DIR': 'videos',
        }
    )
    if engine_port is not None:
        env.setdefault('ALFRED_AUDIO_ENGINE_URL', f'http://{LOOPBACK}:{engine_port}')
    return env


def commands(python, node, chosen, broker):
    """The three processes as dev.yml's services run them, each (name, argv,
    cwd): the api with its reloader on alfred/, the worker on celery's solo
    pool, the site's watcher with its reload server on loopback."""
    return [
        (
            'api',
            [
                str(python),
                '-m',
                'uvicorn',
                'alfred.main:app',
                '--host',
                LOOPBACK,
                '--port',
                str(chosen['port']),
                '--reload',
                '--reload-dir',
                'alfred',
                # A reload waits for open connections to close, and a
                # browser streaming a video keeps one open for as long as
                # it plays: bounded, so a code change reaches the api.
                '--timeout-graceful-shutdown',
                str(RELOAD_GRACE),
            ],
            ROOT,
        ),
        (
            'worker',
            [
                str(python),
                '-m',
                'celery',
                '-A',
                'alfred.core.utils.tasks:renderer',
                '-b',
                broker,
                '--result-backend',
                broker,
                'worker',
                '--loglevel=info',
                '--pool=solo',
            ],
            ROOT,
        ),
        (
            'site',
            [
                str(node),
                str(PARCEL),
                'watch',
                'src/index.html',
                '--hmr-host',
                LOOPBACK,
                '--hmr-port',
                str(chosen['hmr']),
            ],
            ROOT / 'website',
        ),
    ]


# --- what answers ------------------------------------------------------------


def taken(port, host=LOOPBACK):
    """Whether anything accepts a connection on `port`."""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def database_answers(url):
    """Whether anything accepts a connection where `url` points."""
    parts = urlsplit(url)
    return taken(parts.port or 27017, parts.hostname or LOOPBACK)


def alive(pid):
    if os.name == 'nt':
        found = subprocess.run(
            ['tasklist', '/FI', f'PID eq {pid}', '/NH'], capture_output=True, text=True
        )
        return str(pid) in found.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def recorded():
    try:
        return json.loads(RECORD.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


# --- the processes -----------------------------------------------------------


def start(name, argv, cwd, env):
    """`argv` detached, its output in the log named for it; the process."""
    LOGS.mkdir(parents=True, exist_ok=True)
    log = (LOGS / f'{name}.log').open('w', encoding='utf-8')
    options = {}
    if os.name == 'nt':
        options['creationflags'] = 0x00000008 | 0x00000200  # DETACHED, NEW_GROUP
    else:
        options['start_new_session'] = True
    return subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        **options,
    )


def log_says(name, text):
    try:
        return text in (LOGS / f'{name}.log').read_text(
            encoding='utf-8', errors='replace'
        )
    except OSError:
        return False


def wait(check, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(1)
    return False


def ends_of(name):
    for line in tail(LOGS / f'{name}.log'):
        say(f'     {line}')


def up(args):
    chosen = settings()
    base = f'http://{LOOPBACK}:{chosen["port"]}'
    python = interpreter()
    if python is None:
        say(
            './al host up: this checkout has no environment of its own; '
            '`pdm install -G dev -G test -G render` makes it (docs/host-run.md)'
        )
        return 1
    node = tool('node')
    if node is None or not PARCEL.is_file():
        say(
            './al host up: the site needs node and website/node_modules; '
            '`yarn install --frozen-lockfile` in website/ makes the second'
        )
        return 1
    title = title_at(base)
    if title != '':
        held = f'as "{title}"' if title else 'not as an API'
        say(
            f'./al host up: port {chosen["port"]} (ALFRED_PORT) is already '
            f'answering, {held}; `./al host` says what is up and `./al host down` '
            'stops what it started'
        )
        return 1
    if taken(chosen['hmr']):
        say(f'./al host up: port {chosen["hmr"]} (ALFRED_HMR_PORT) is already in use')
        return 1
    if not database_answers(chosen['db']):
        say(
            f'./al host up: nothing answers at {chosen["db"]} (ALFRED_HOST_DB); '
            'start a MongoDB there, or name one (docs/host-run.md)'
        )
        return 1
    joe = family.ensure_joe('./al host up', JOE_RECORD, LOGS / 'joe.log')
    if joe is None:
        return 1
    probe, engine_port = joe
    env = environment(engine_port=engine_port)
    say(
        f'alfred: the api, the worker and the site from {shown(python)}, database {chosen["db"]}'
    )
    record = {}
    for name, argv, cwd in commands(python, node, chosen, env['CELERY_BROKER']):
        process = start(name, argv, cwd, env)
        record[name] = {'pid': process.pid, 'log': shown(LOGS / f'{name}.log')}
    STATE.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(record, indent=2), encoding='utf-8')
    if not wait(lambda: fetch(base + '/healthz')[0] == 200, API_WAIT):
        say(
            f'./al host up: the api did not answer {base}/healthz; {shown(LOGS / "api.log")} ends:'
        )
        ends_of('api')
        say('`./al host down` stops what started')
        return 1
    if not wait(lambda: log_says('site', 'Built in'), SITE_WAIT):
        say(f'! the site has not built; {shown(LOGS / "site.log")} ends:')
        ends_of('site')
    if not wait(lambda: log_says('worker', 'ready.'), WORKER_WAIT):
        say(
            f'! the worker has not said it is ready; {shown(LOGS / "worker.log")} ends:'
        )
        ends_of('worker')
    say()
    say(
        f'alfred  {base}   (status: ./al host; stop: ./al host down; logs: {shown(LOGS)})'
    )
    say(f'joe     {probe}')
    say(f'qmcp    QMCP_ALFRED_URL={base} for its alfred tools')
    return 0


def status(args):
    chosen = settings()
    base = f'http://{LOOPBACK}:{chosen["port"]}'
    title = title_at(base)
    if title == '':
        say(f'api      nothing answers on {base} (ALFRED_PORT)')
    else:
        say(f'api      {base} answers as "{title or "not an API"}"')
    say(
        f'site     port {chosen["hmr"]} (ALFRED_HMR_PORT) {"in use" if taken(chosen["hmr"]) else "free"}'
    )
    say(
        f'database {chosen["db"]} (ALFRED_HOST_DB) '
        f'{"answers" if database_answers(chosen["db"]) else "does not answer"}'
    )
    joe_probe = f'http://{LOOPBACK}:{family.joe_port()}'
    joe_title = title_at(joe_probe)
    say(
        f'joe      {joe_probe} {"answers as " + repr(joe_title) if joe_title else "nothing answers"}'
    )
    started = recorded()
    if not started and not JOE_RECORD.exists():
        say('started  nothing by ./al host up')
        return 0
    for name, entry in started.items():
        state = 'running' if alive(entry['pid']) else 'gone'
        say(f'started  {name} pid {entry["pid"]} {state} (log: {entry["log"]})')
    if JOE_RECORD.exists():
        joe = json.loads(JOE_RECORD.read_text(encoding='utf-8'))
        state = 'running' if alive(joe['pid']) else 'gone'
        say(f'started  joe pid {joe["pid"]} {state}')
    return 0


def down(args):
    started = recorded()
    for name, entry in started.items():
        kill_tree(entry['pid'])
        say(f'{name}: stopped (pid {entry["pid"]})')
    if started:
        RECORD.unlink()
    else:
        say('alfred: nothing started by ./al host up; whatever answers is left alone')
    if JOE_RECORD.exists():
        joe = json.loads(JOE_RECORD.read_text(encoding='utf-8'))
        kill_tree(joe['pid'])
        JOE_RECORD.unlink()
        say(f'joe: stopped (pid {joe["pid"]}, port {joe["port"]})')
    else:
        say(
            'joe: not started by ./al host up; whatever answers on its port is left alone'
        )
    return 0


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='replace')
    parser = argparse.ArgumentParser(
        prog='./al host', description=__doc__.split('\n\n')[0]
    )
    commands_ = parser.add_subparsers(dest='command')
    commands_.add_parser(
        'status', help='what answers on each port, and what `up` started'
    )
    commands_.add_parser('up', help='joe, then the api, the worker and the site')
    commands_.add_parser('down', help='what `up` started')
    args = parser.parse_args(argv)
    handlers = {'status': status, 'up': up, 'down': down}
    return handlers.get(args.command or 'status')(args)


if __name__ == '__main__':
    sys.exit(main())
