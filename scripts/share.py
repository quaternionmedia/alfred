#!/usr/bin/env python3
"""alfred's family, shared from this machine to devices invited onto a private network.

`./al share` runs this. A share is one standing copy of the family, kept
apart from every development stack: alfred in containers and joe beside it,
each built from a commit the share's manifest names, never from a working
tree; a database and a media library of its own; alfred's own login, with
registration closed and no bypass; and snapshots taken by name.
docs/share.md says how to run one and what it cannot do.

    ./al share                         what each member is meant to serve, serves, and answers as
    ./al share init ADDRESS [MEMBER=REF ...]   the state directory, its key and its manifest
    ./al share move MEMBER=REF ...     members pointed at new commits, and brought up there
    ./al share env MEMBER NAME=VALUE   a setting one member is started with, kept in the manifest
    ./al share bind ADDRESS ...        the private-network addresses alfred is published on
    ./al share network [create | authorize NODE --name WHO | revoke NODE]
                                       the share's own private network, on this host's controller
    ./al share up                      every member at its commit
    ./al share down                    every member stopped; the state stays
    ./al share snapshot NAME           the database, the media and the manifest, kept as NAME
    ./al share snapshots               every snapshot, and the space each takes
    ./al share restore NAME --yes      the share's database and media replaced by NAME's
    ./al share account EMAIL --name FIRST [--superuser]   an account; the password is asked for

ADDRESS is this host's address on the private network. alfred is published
there and on loopback, and nowhere else. `network create` makes that network
on this host's own ZeroTier controller and puts this host on it; it and
`network authorize` read ZeroTier One's token, which an administrator can
read, so they run from a shell started as administrator. joe and the other members alfred
drives ask no login, so they are bound to loopback (docker0 on a Linux host)
and reached only through alfred.

ALFRED_SHARE_STATE is the share's directory, ~/.alfred/share unless set. The
manifest in it is a claim about this machine and is never committed.

The standard library only, as family.py, which this imports for where each
repository is, the probes and what is printed; nothing it prints carries a
secret.
"""

import argparse
import getpass
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# family.py and host.py beside this file, however this file was started.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import family  # noqa: E402
from family import LOOPBACK, fetch, kill_tree, say, tail, title_at, tool  # noqa: E402
from host import alive  # noqa: E402

PROJECT = 'alfred-share'
SCHEMA = 1
NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')
# Seconds each member is given to answer after it starts.
STACK_WAIT = 600
PROCESS_WAIT = 300


def state_dir(env=None):
    env = os.environ if env is None else env
    given = (env.get('ALFRED_SHARE_STATE') or '').strip()
    return Path(given).expanduser() if given else Path.home() / '.alfred' / 'share'


class Member:
    """One repository the share runs: alfred as a stack of containers, or a
    member alfred drives as a process on loopback, which `gives` alfred the
    setting naming its address."""

    def __init__(
        self,
        name,
        port,
        answers_as,
        kind,
        command=(),
        setup=(),
        gives=None,
        vendored=(),
    ):
        self.name = name
        self.port = port
        self.answers_as = answers_as
        self.kind = kind
        self.command = tuple(command)
        self.setup = tuple(setup)
        self.gives = gives
        self.vendored = tuple(vendored)

    def repo(self):
        return family.BY_NAME.get(self.name) or family.Repo(self.name, 'a share member')

    def answered(self, title):
        """Whether an OpenAPI title is this member's own."""
        return bool(title) and self.answers_as.lower() in title.lower()


# Each port is its constant's first five digits, one more than the
# development port's four, so a share and a developer's servers never meet.
MEMBERS = (
    Member(
        'alfred',
        17320,
        'Alfred API',
        'stack',
        vendored=('alfred/otto', 'alfred/vox'),
    ),
    Member(
        'joe',
        10594,
        'joe',
        'process',
        command=(
            'uv',
            'run',
            '--frozen',
            'uvicorn',
            'api:app',
            '--host',
            '{host}',
            '--port',
            '{port}',
        ),
        setup=('uv', 'sync', '--frozen'),
        gives='ALFRED_AUDIO_ENGINE_URL',
    ),
    Member(
        'looksatwords',
        14142,
        'Conversation Thread Visualizer',
        'process',
        command=(
            'uv',
            'run',
            '--frozen',
            'looksatwords',
            'serve',
            '--host',
            '{host}',
            '--port',
            '{port}',
            '--no-open',
        ),
        setup=('uv', 'sync', '--frozen'),
        gives='ALFRED_LANGUAGE_ENGINE_URL',
    ),
)
BY_NAME = {member.name: member for member in MEMBERS}


# --- the manifest ------------------------------------------------------------


class Refused(Exception):
    """A reason this command stops, said as the reason."""


def manifest_path(state):
    return Path(state) / 'manifest.json'


def load(state):
    path = manifest_path(state)
    if not path.exists():
        raise Refused(
            f'no share at {state}: ./al share init ADDRESS alfred=REF joe=REF '
            'makes one (docs/share.md)'
        )
    return json.loads(path.read_text(encoding='utf-8'))


def save(state, manifest):
    path = manifest_path(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    scratch = path.with_suffix('.json.new')
    scratch.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    scratch.replace(path)


def new_manifest(addresses):
    """A manifest serving nothing yet, published on loopback and `addresses`."""
    bind = [LOOPBACK]
    for address in addresses:
        if address not in bind:
            bind.append(address)
    return {
        'schema': SCHEMA,
        'project': PROJECT,
        'bind': bind,
        'ports': {member.name: member.port for member in MEMBERS},
        'members': {},
    }


def assignments(pairs, separator='='):
    """`MEMBER=VALUE` pairs as a dict, refusing a member the share does not run."""
    found = {}
    for pair in pairs:
        name, sep, value = pair.partition(separator)
        name, value = name.strip(), value.strip()
        if not sep or not name or not value:
            raise Refused(f'{pair!r} is not MEMBER{separator}VALUE')
        if name not in BY_NAME:
            raise Refused(
                f'{name!r} is not a member a share runs: '
                + ', '.join(member.name for member in MEMBERS)
            )
        found[name] = value
    return found


def private_addresses(manifest):
    return [address for address in manifest['bind'] if address != LOOPBACK]


def process_host():
    """Where a member alfred drives listens: loopback, which Docker Desktop
    forwards to, or docker0 on a Linux host. Never the private network."""
    return family.docker0_address() or LOOPBACK


def engine_url(member, manifest):
    """The address alfred's containers reach a process member at."""
    return f'http://host.docker.internal:{manifest["ports"][member.name]}'


# --- the trees the share serves from ------------------------------------------


def run(argv, cwd=None, env=None, stdin=None, capture=True):
    """(returncode, output) of a command, its output folded into one string."""
    done = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        input=stdin,
        capture_output=capture,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    if not capture:
        return done.returncode, ''
    return done.returncode, (done.stdout or '') + (done.stderr or '')


def git(path, *args):
    """git in `path`, raising with git's own words when it fails."""
    code, output = run(['git', '-C', str(path), *args])
    if code != 0:
        raise Refused(f'git {" ".join(args)} in {path}: {output.strip()}')
    return output.strip()


def tree(state, name):
    return Path(state) / 'src' / name


def head(path):
    try:
        return git(path, 'rev-parse', 'HEAD')
    except Refused:
        return ''


def source_clone(member):
    """The checkout this machine works on `member` in: where its objects are
    borrowed from, and whose origin the share's own clone fetches from."""
    found, how = family.locate(member.repo())
    if found is None:
        raise Refused(f'{member.name}: {how}')
    return Path(found)


def ensure_clone(state, member):
    """The share's own clone of `member`, made from the developer's checkout's
    origin with its objects borrowed and then copied, so the share keeps
    working whatever happens to that checkout."""
    path = tree(state, member.name)
    if (path / '.git').exists():
        return path
    source = source_clone(member)
    origin = git(source, 'remote', 'get-url', 'origin')
    objects = Path(git(source, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    path.parent.mkdir(parents=True, exist_ok=True)
    say(f'{member.name}: cloning {origin} into {path}')
    code, output = run(
        [
            'git',
            'clone',
            '--quiet',
            '--no-checkout',
            '--reference-if-able',
            str(objects),
            '--dissociate',
            origin,
            str(path),
        ]
    )
    if code != 0:
        raise Refused(f'{member.name}: git clone failed: {output.strip()}')
    return path


def resolve(path, ref):
    """The commit `ref` names in the share's clone: a branch of origin first,
    then a commit. A commit no branch of origin holds is refused, because
    nobody else could fetch what a finding against it names."""
    git(path, 'fetch', '--quiet', '--prune', 'origin')
    for candidate in (f'refs/remotes/origin/{ref}', ref):
        code, output = run(
            ['git', '-C', str(path), 'rev-parse', '--verify', '--quiet', candidate + '^{commit}']
        )
        if code == 0 and output.strip():
            commit = output.strip()
            break
    else:
        raise Refused(f'{ref!r} names no branch of origin and no commit in {path}')
    holders = git(path, 'branch', '-r', '--contains', commit)
    if not any(line.strip().startswith('origin/') for line in holders.splitlines()):
        raise Refused(f'{ref} ({commit[:12]}) is on no branch of origin: push it first')
    return commit


def check_out(path, member, commit):
    """`path` at `commit`, its vendored engines at the commit's pins."""
    if head(path) != commit:
        git(path, 'checkout', '--quiet', '--detach', commit)
    if member.vendored:
        git(path, 'submodule', 'update', '--init', '--quiet', '--', *member.vendored)


# --- alfred, in containers ----------------------------------------------------


def posix(path):
    return Path(path).resolve().as_posix()


def compose_document(manifest, state, env=None):
    """The share's compose file, as a dict compose reads as JSON.

    alfred's api and render worker run the image built from the share's own
    clone, so the code is the commit's and nothing is mounted over it; the
    site is built once from the same commit. The database and the media
    library are the share's. ALFRED_PRODUCTION closes registration and makes
    alfred refuse to start with the login bypass; the bypass is never passed.
    Only the api is published, on the manifest's addresses.
    """
    env = os.environ if env is None else env
    state = Path(state)
    source = tree(state, 'alfred')
    commit = manifest['members']['alfred']['commit']
    port = manifest['ports']['alfred']
    public = (private_addresses(manifest) or [LOOPBACK])[0]
    settings = {
        'ALFRED_PRODUCTION': 'true',
        'ALFRED_ALLOW_REGISTRATION': 'false',
        'ALFRED_PUBLIC_URL': f'http://{public}:{port}',
        'DB_URL': 'mongodb://db:27017',
        'DB_NAME': 'alfred',
        'CELERY_BROKER': 'mongodb://db:27017/celery',
        'CELERY_BACKEND': 'mongodb://db:27017/celery',
        'VIDEO_DIR': '/app/videos',
        'OTTO_DOWNLOAD_DIR': '/app/videos/.remote-cache',
    }
    for name in manifest['members']:
        member = BY_NAME[name]
        if member.gives:
            settings[member.gives] = engine_url(member, manifest)
    settings.update(manifest['members']['alfred'].get('env') or {})
    for refused in ('ALFRED_DEV_SKIP_AUTH', 'ALFRED_SECRET_KEY'):
        settings.pop(refused, None)

    image = f'{PROJECT}-api:{commit[:12]}'
    labels = {'qm.share.member': 'alfred', 'qm.share.commit': commit}
    videos = f'{posix(state / "videos")}:/app/videos'
    fonts = f'{posix(source / "alfred" / "otto" / "fonts")}:/usr/share/fonts/truetype/otto'
    env_files = [posix(source / '.email'), posix(state / 'secret_key')]
    return {
        'name': PROJECT,
        'services': {
            'site': {
                'build': {'context': posix(source / 'website')},
                'image': f'{PROJECT}-site:{commit[:12]}',
                'volumes': [f'{posix(source / "website")}:/app', '/app/node_modules'],
                'labels': labels,
                'restart': 'no',
            },
            'api': {
                'build': {
                    'context': posix(source),
                    'target': 'api',
                    'labels': {'org.opencontainers.image.revision': commit},
                },
                'image': image,
                'command': ['uvicorn', 'alfred.main:app', '--host', '0.0.0.0', '--port', '80'],
                'depends_on': {
                    'db': {'condition': 'service_started'},
                    'site': {'condition': 'service_completed_successfully'},
                },
                'ports': [f'{address}:{port}:80' for address in manifest['bind']],
                'volumes': [
                    videos,
                    f'{posix(source / "website" / "dist")}:/app/dist',
                    fonts,
                ],
                'env_file': env_files,
                'environment': settings,
                'extra_hosts': ['host.docker.internal:host-gateway'],
                'labels': labels,
                'healthcheck': {
                    'test': [
                        'CMD',
                        'python',
                        '-c',
                        "import urllib.request; urllib.request.urlopen('http://127.0.0.1/healthz', timeout=5)",
                    ],
                    'interval': '30s',
                    'timeout': '10s',
                    'retries': 3,
                    'start_period': '60s',
                },
                'networks': ['isolated', 'outgoing'],
                'restart': 'unless-stopped',
            },
            'renderer': {
                'image': image,
                'pull_policy': 'never',
                'entrypoint': [
                    'celery',
                    '-A',
                    'alfred.core.utils.tasks:renderer',
                    '-b',
                    'mongodb://db:27017/celery',
                    '--result-backend',
                    'mongodb://db:27017/celery',
                    'worker',
                    '--loglevel=info',
                ],
                'depends_on': {'api': {'condition': 'service_started'}},
                'volumes': [videos, fonts],
                'env_file': env_files,
                'environment': settings,
                'extra_hosts': ['host.docker.internal:host-gateway'],
                'labels': labels,
                'networks': ['isolated', 'outgoing'],
                'restart': 'unless-stopped',
            },
            'db': {
                'image': (env.get('ALFRED_SHARE_DB_IMAGE') or 'mongo:bionic'),
                'volumes': [f'{posix(state / "db")}:/data/db'],
                'labels': {'qm.share.member': 'alfred'},
                'networks': ['isolated'],
                'restart': 'unless-stopped',
            },
        },
        'networks': {'isolated': {'internal': True}, 'outgoing': {}},
    }


def compose_file(state):
    return Path(state) / 'compose.json'


def compose(state, *args, capture=False, stdin=None):
    """docker compose on the share's project and file."""
    argv = ['docker', 'compose', '-p', PROJECT, '-f', str(compose_file(state)), *args]
    return run(argv, capture=capture, stdin=stdin)


def docker_up():
    code, _ = run(['docker', 'info', '--format', '{{.ServerVersion}}'])
    return code == 0


def ensure_key(state):
    """The share's own signing key, made once, readable by its owner alone."""
    path = Path(state) / 'secret_key'
    if path.exists() and path.stat().st_size:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    old = os.umask(0o077)
    try:
        path.write_text(f'ALFRED_SECRET_KEY={secrets.token_hex(32)}\n', encoding='utf-8')
    finally:
        os.umask(old)
    say(f'alfred: made {path}, the share\'s own signing key')
    return path


def served_commit(container):
    """The commit a running container was started from, '' if none runs."""
    code, output = run(
        ['docker', 'inspect', '--format', '{{index .Config.Labels "qm.share.commit"}}', container]
    )
    return output.strip() if code == 0 else ''


def api_container():
    code, output = run(
        [
            'docker',
            'ps',
            '--filter',
            f'label=com.docker.compose.project={PROJECT}',
            '--filter',
            'label=com.docker.compose.service=api',
            '--format',
            '{{.Names}}',
        ]
    )
    return output.strip().splitlines()[0] if code == 0 and output.strip() else ''


def port_holder(address, port):
    """What answers at address:port: its OpenAPI title, '' for nothing, None
    for something that is not an OpenAPI server."""
    return title_at(f'http://{address}:{port}')


def stack_up(state, manifest, rebuilt):
    """alfred's containers up at the manifest's commit."""
    member = BY_NAME['alfred']
    port = manifest['ports']['alfred']
    if not api_container():
        for address in manifest['bind']:
            title = port_holder(address, port)
            if title != '':
                what = f'"{title}"' if title else 'something that is not an OpenAPI server'
                raise Refused(
                    f'alfred: {address}:{port} is held by {what}; the share leaves it alone'
                )
    for directory in ('db', 'videos'):
        (Path(state) / directory).mkdir(parents=True, exist_ok=True)
    ensure_key(state)
    document = compose_document(manifest, state)
    compose_file(state).write_text(json.dumps(document, indent=2) + '\n', encoding='utf-8')
    args = ['up', '-d', '--build']
    if rebuilt:
        args.append('--renew-anon-volumes')
    say(f'alfred: docker compose -p {PROJECT} {" ".join(args)}')
    code, _ = compose(state, *args)
    if code != 0:
        raise Refused(f'alfred: docker compose up failed; ./al share says what runs')
    base = f'http://{manifest["bind"][0]}:{port}'
    if not family.wait_for(lambda: fetch(base + '/healthz')[0] == 200, STACK_WAIT, every=3):
        raise Refused(f'alfred: {base}/healthz did not answer; docker compose -p {PROJECT} logs api says why')
    title = port_holder(manifest['bind'][0], port)
    if not member.answered(title):
        raise Refused(f'alfred: {base} answers as {title!r}, not as alfred')


# --- members alfred drives, as processes --------------------------------------


def record_path(state, name):
    return Path(state) / 'run' / f'{name}.json'


def recorded(state, name):
    path = record_path(state, name)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except ValueError:
        return None


def process_argv(member, host, port):
    uv = tool('uv') or 'uv'
    argv = [part.format(host=host, port=port) for part in member.command]
    return [uv if part == 'uv' else part for part in argv]


def stop_process(state, name):
    started = recorded(state, name)
    if started and alive(started['pid']):
        kill_tree(started['pid'])
        say(f'{name}: stopped (pid {started["pid"]})')
    record_path(state, name).unlink(missing_ok=True)


def process_up(state, manifest, member, rebuilt):
    """`member` answering on its port from the share's clone, at the manifest's
    commit: the process already there when it is that one, else a new one."""
    entry = manifest['members'][member.name]
    port = manifest['ports'][member.name]
    host = process_host()
    path = tree(state, member.name)
    started = recorded(state, member.name)
    running = bool(started and alive(started['pid']))
    title = port_holder(host, port)
    if running and started.get('commit') == entry['commit'] and member.answered(title):
        say(f'{member.name}: serving {entry["commit"][:12]} on {host}:{port}')
        return
    if running:
        stop_process(state, member.name)
        family.wait_for(lambda: port_holder(host, port) == '', 30)
        title = port_holder(host, port)
    if title != '':
        what = f'"{title}"' if title else 'something that is not an OpenAPI server'
        raise Refused(f'{member.name}: {host}:{port} is held by {what}; the share leaves it alone')
    if not tool('uv'):
        raise Refused(f'{member.name}: runs with uv, which is not on PATH')
    env = dict(os.environ)
    env.update(entry.get('env') or {})
    logs = Path(state) / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    log_path = logs / f'{member.name}.log'
    if rebuilt or not (path / '.venv').exists():
        say(f'{member.name}: {" ".join(member.setup)} in {path}')
        code, output = run([tool('uv'), *member.setup[1:]], cwd=path, env=env)
        if code != 0:
            log_path.write_text(output, encoding='utf-8')
            raise Refused(f'{member.name}: {" ".join(member.setup)} failed; {log_path} has its output')
    options = {}
    if os.name == 'nt':
        options['creationflags'] = 0x00000008 | 0x00000200  # DETACHED, NEW_GROUP
    else:
        options['start_new_session'] = True
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen(
            process_argv(member, host, port),
            cwd=path,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            **options,
        )
    record_path(state, member.name).parent.mkdir(parents=True, exist_ok=True)
    record_path(state, member.name).write_text(
        json.dumps({'pid': process.pid, 'port': port, 'host': host, 'commit': entry['commit']}),
        encoding='utf-8',
    )
    say(f'{member.name}: starting {entry["commit"][:12]} on {host}:{port} (log: {log_path})')
    answered = family.wait_for(
        lambda: process.poll() is not None or member.answered(port_holder(host, port)),
        PROCESS_WAIT,
    )
    if process.poll() is not None or not answered:
        say(f'{member.name}: did not come up; {log_path} ends:')
        for line in tail(log_path):
            say(f'     {line}')
        raise Refused(f'{member.name}: not serving')


# --- what the share serves ----------------------------------------------------


def verdict(meant, checked_out, running, answers):
    """One member's state, from the four facts the share can read."""
    if not meant:
        return 'not in the manifest'
    if not running:
        return 'not running'
    if answers is None:
        return 'unknown: its port does not say what it is'
    if not answers:
        return 'not answering as itself'
    if running != meant or checked_out != meant:
        return 'moved, not restarted: ./al share up'
    return 'serving'


def size(path):
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                pass
    return total


def shown_size(count):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if count < 1024 or unit == 'GB':
            return f'{count:.0f} {unit}' if unit == 'B' else f'{count:.1f} {unit}'
        count /= 1024
    return f'{count:.1f} GB'


def status(args, state):
    manifest = load(state)
    port_of = manifest['ports']
    worst = 0
    say(f'share  {state}')
    say(f'bind   {", ".join(manifest["bind"])}')
    for name, entry in manifest['members'].items():
        member = BY_NAME[name]
        meant = entry.get('commit', '')
        checked_out = head(tree(state, name))
        if member.kind == 'stack':
            container = api_container() if docker_up() else ''
            running = served_commit(container) if container else ''
            answers = [
                (address, port_holder(address, port_of[name])) for address in manifest['bind']
            ]
        else:
            started = recorded(state, name)
            running = started['commit'] if started and alive(started['pid']) else ''
            answers = [(process_host(), port_holder(process_host(), port_of[name]))]
        for address, title in answers:
            answered = None if title is None else member.answered(title)
            said = verdict(meant, checked_out, running, answered)
            if said != 'serving':
                worst = 1
            say(
                f'  {name:<13} {entry.get("ref", "?")} @ {meant[:12]}  '
                f'http://{address}:{port_of[name]}  {said}'
            )
    say(f'state  database {shown_size(size(Path(state) / "db"))}, '
        f'media {shown_size(size(Path(state) / "videos"))}, '
        f'snapshots {shown_size(size(Path(state) / "snapshots"))}')
    return worst


# --- commands -----------------------------------------------------------------


def init(args, state):
    if manifest_path(state).exists():
        raise Refused(f'a share is already kept at {state}; ./al share move changes what it serves')
    refuse_every_interface(args.address)
    manifest = new_manifest(args.address)
    save(state, manifest)
    ensure_key(state)
    say(f'share: kept at {state}, published on {", ".join(manifest["bind"])}')
    if args.members:
        return move(argparse.Namespace(members=args.members, no_up=True), state)
    return 0


def move(args, state):
    manifest = load(state)
    wanted = assignments(args.members)
    for name, ref in wanted.items():
        member = BY_NAME[name]
        path = ensure_clone(state, member)
        commit = resolve(path, ref)
        entry = manifest['members'].setdefault(name, {})
        before = entry.get('commit')
        entry.update(
            {
                'ref': ref,
                'commit': commit,
                'moved_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            }
        )
        say(
            f'{name}: {ref} @ {commit[:12]}'
            + ('' if before in (None, commit) else f' (was {before[:12]})')
        )
    save(state, manifest)
    if getattr(args, 'no_up', False):
        return 0
    return up(argparse.Namespace(), state)


def set_env(args, state):
    manifest = load(state)
    if args.member not in manifest['members']:
        raise Refused(f'{args.member} is not in the manifest: ./al share move {args.member}=REF first')
    name, sep, value = args.setting.partition('=')
    if not sep or not name:
        raise Refused(f'{args.setting!r} is not NAME=VALUE')
    if name in ('ALFRED_DEV_SKIP_AUTH', 'ALFRED_SECRET_KEY', 'ALFRED_PRODUCTION'):
        raise Refused(f'{name} is the share\'s own, and is not set per member')
    settings = manifest['members'][args.member].setdefault('env', {})
    if value:
        settings[name] = value
    else:
        settings.pop(name, None)
    save(state, manifest)
    say(f'{args.member}: {name} {"set" if value else "unset"}; ./al share up starts it so')
    return 0


def up(args, state):
    manifest = load(state)
    if 'alfred' not in manifest['members']:
        raise Refused('the manifest names no alfred: ./al share move alfred=REF')
    if not docker_up():
        raise Refused('Docker is not running; the share\'s alfred runs in containers')
    ordered = [name for name in manifest['members'] if name != 'alfred'] + ['alfred']
    for name in ordered:
        member = BY_NAME[name]
        entry = manifest['members'][name]
        path = ensure_clone(state, member)
        rebuilt = head(path) != entry['commit']
        check_out(path, member, entry['commit'])
        if member.kind == 'process':
            process_up(state, manifest, member, rebuilt)
        else:
            stack_up(state, manifest, rebuilt)
    port = manifest['ports']['alfred']
    say()
    for address in manifest['bind']:
        say(f'alfred  http://{address}:{port}')
    say('accounts: ./al share account EMAIL --name FIRST')
    return 0


def down(args, state):
    load(state)
    if compose_file(state).exists() and docker_up():
        compose(state, 'down')
    for member in MEMBERS:
        if member.kind == 'process':
            stop_process(state, member.name)
    say('share: stopped; its state stays in ' + str(state))
    return 0


def snapshot_dir(state, name):
    if not NAME.match(name):
        raise Refused(f'{name!r} is not a snapshot name: letters, digits, dot, dash, underscore')
    return Path(state) / 'snapshots' / name


def copy_state(source, destination):
    """`source`'s database and media into `destination`, which must not exist,
    leaving out the cache of fetched remote media, which is fetched again."""
    destination.mkdir(parents=True)
    for directory in ('db', 'videos'):
        found = Path(source) / directory
        if found.exists():
            shutil.copytree(
                found, destination / directory, ignore=shutil.ignore_patterns('.remote-cache')
            )
        else:
            (destination / directory).mkdir()


LONG_RUNNING = ('db', 'api', 'renderer')


def quiesce(state):
    """Every container stopped, so the database's files are at rest."""
    code, _ = compose(state, 'stop')
    if code != 0:
        raise Refused('docker compose stop failed; nothing was copied')


def resume(state):
    """The services that serve, started again; the site's build is not rerun."""
    compose(state, 'start', *LONG_RUNNING)


def snapshot(args, state):
    manifest = load(state)
    target = snapshot_dir(state, args.name)
    if target.exists():
        raise Refused(f'a snapshot named {args.name} exists: {target}')
    running = bool(api_container()) if docker_up() else False
    if running:
        say('share: stopping alfred while its files are copied')
        quiesce(state)
    try:
        staging = target.with_name(target.name + '.partial')
        if staging.exists():
            shutil.rmtree(staging)
        copy_state(state, staging)
        (staging / 'manifest.json').write_text(
            json.dumps(
                {
                    'snapshot': args.name,
                    'taken_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'manifest': manifest,
                },
                indent=2,
            )
            + '\n',
            encoding='utf-8',
        )
        staging.rename(target)
    finally:
        if running:
            resume(state)
    say(f'snapshot {args.name}: {shown_size(size(target))} at {target}')
    return 0


def snapshots(args, state):
    root = Path(state) / 'snapshots'
    found = sorted(p for p in root.iterdir() if p.is_dir()) if root.exists() else []
    if not found:
        say('no snapshots: ./al share snapshot NAME takes one')
        return 0
    for path in found:
        try:
            taken = json.loads((path / 'manifest.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            say(f'  {path.name:<24} unreadable: no manifest.json')
            continue
        members = ', '.join(
            f'{name} {entry.get("commit", "")[:12]}'
            for name, entry in taken['manifest']['members'].items()
        )
        say(f'  {path.name:<24} {taken["taken_at"]}  {shown_size(size(path)):>9}  {members}')
    return 0


def restore(args, state):
    load(state)
    source = snapshot_dir(state, args.name)
    if not (source / 'manifest.json').exists():
        raise Refused(f'no snapshot named {args.name} in {Path(state) / "snapshots"}')
    if not args.yes:
        say(
            f'restore replaces the share\'s database and media with snapshot {args.name}\'s; '
            'what is there now is gone unless a snapshot holds it. '
            f'./al share snapshot NAME first, then ./al share restore {args.name} --yes'
        )
        return 1
    running = bool(api_container()) if docker_up() else False
    if running:
        say('share: stopping alfred while its files are replaced')
        quiesce(state)
    try:
        for directory in ('db', 'videos'):
            current = Path(state) / directory
            if current.exists():
                shutil.rmtree(current)
            shutil.copytree(source / directory, current)
    finally:
        if running:
            resume(state)
    say(f'share: database and media are snapshot {args.name}\'s')
    return 0


def bind(args, state):
    manifest = load(state)
    refuse_every_interface(args.address)
    manifest['bind'] = new_manifest(args.address)['bind']
    save(state, manifest)
    say(f'share: published on {", ".join(manifest["bind"])}')
    if docker_up() and api_container():
        return up(argparse.Namespace(), state)
    return 0


def refuse_every_interface(addresses):
    for address in addresses:
        if address in ('0.0.0.0', '::'):
            raise Refused(
                f'{address} is every interface; a share is published on its private '
                'network\'s address alone (docs/share.md)'
            )


# --- the private network, on this host's own ZeroTier controller ---------------

ZEROTIER = 'http://127.0.0.1:9993'
# This host's address on the share's network, and the addresses invited
# devices are given, in 10.173.20.0/24: root three again, as the ports are.
NETWORK_HOST = '10.173.20.1'
NETWORK_ROUTE = '10.173.20.0/24'
NETWORK_POOL = ('10.173.20.10', '10.173.20.250')
NODE = re.compile(r'^[0-9a-f]{10}$')


def zerotier_tokens(env=None):
    """Where ZeroTier One keeps the token its local API asks for: the
    service's own, which an administrator can read, then the copy its tray
    app keeps for the user."""
    env = os.environ if env is None else env
    if os.name == 'nt':
        bases = [env.get('ProgramData'), env.get('LOCALAPPDATA')]
        return [Path(base) / 'ZeroTier' / 'One' / 'authtoken.secret' for base in bases if base]
    if sys.platform == 'darwin':
        system = Path('/Library/Application Support/ZeroTier/One/authtoken.secret')
    else:
        system = Path('/var/lib/zerotier-one/authtoken.secret')
    return [system, Path.home() / '.zeroTierOneAuthToken']


def zerotier(path, body=None):
    """(status, answer) from ZeroTier One's local API: a POST of `body` when
    one is given. The token is read for each call and never printed."""
    data = None if body is None else json.dumps(body).encode('utf-8')
    for candidate in zerotier_tokens():
        try:
            token = candidate.read_text(encoding='utf-8').strip()
        except OSError:
            continue
        if not token:
            continue
        headers = {'X-ZT1-Auth': token}
        if data is not None:
            headers['Content-Type'] = 'application/json'
        status, answer, _ = fetch(ZEROTIER + path, data=data, headers=headers)
        if status == 401:
            continue
        if status == 0:
            raise Refused('ZeroTier One does not answer on 127.0.0.1:9993; is its service running?')
        try:
            return status, json.loads(answer) if answer else {}
        except ValueError:
            return status, {}
    raise Refused(
        "ZeroTier One's token could not be read, or was refused: run this from a "
        'shell started as administrator, where the service\'s own token is readable'
    )


def answered(status, answer, what):
    if status != 200:
        raise Refused(f'ZeroTier One answered {status} to {what}')
    return answer


def network_of(manifest):
    network = manifest.get('network')
    if not network:
        raise Refused('this share has no network of its own: ./al share network create')
    return network


def network_create(args, state):
    try:
        manifest = load(state)
    except Refused:
        manifest = None
    if manifest and manifest.get('network'):
        raise Refused(f'this share already has its network, {manifest["network"]["id"]}')
    node = answered(*zerotier('/status'), 'its status')['address']
    config = {
        'name': args.name,
        'private': True,
        'v4AssignMode': {'zt': True},
        'ipAssignmentPools': [{'ipRangeStart': NETWORK_POOL[0], 'ipRangeEnd': NETWORK_POOL[1]}],
        'routes': [{'target': NETWORK_ROUTE, 'via': None}],
    }
    made = answered(*zerotier(f'/controller/network/{node}______', config), 'making a network')
    network = made.get('id') or made.get('nwid')
    if not network:
        raise Refused('ZeroTier One made a network and did not say its id')
    say(f'network {network}: made on this host\'s controller ({args.name}, private)')
    answered(
        *zerotier(
            f'/controller/network/{network}/member/{node}',
            {'authorized': True, 'ipAssignments': [NETWORK_HOST]},
        ),
        'authorizing this host',
    )
    answered(*zerotier(f'/network/{network}', {}), 'joining it')
    joined = family.wait_for(
        lambda: any(
            address.split('/')[0] == NETWORK_HOST
            for address in zerotier(f'/network/{network}')[1].get('assignedAddresses') or []
        ),
        60,
        every=2,
    )
    if not joined:
        raise Refused(
            f'this host joined {network} and has not been given {NETWORK_HOST} yet; '
            './al share network says where it stands'
        )
    if manifest is None:
        manifest = new_manifest([NETWORK_HOST])
        ensure_key(state)
    elif NETWORK_HOST not in manifest['bind']:
        manifest['bind'].append(NETWORK_HOST)
    manifest['network'] = {'id': network, 'controller': node, 'address': NETWORK_HOST, 'names': {}}
    save(state, manifest)
    say(f'this host is {NETWORK_HOST} on it, and the share is published there')
    say(f'an invited device joins {network}, then: ./al share network authorize NODE --name WHO')
    return 0


def network_status(args, state):
    network = network_of(load(state))
    say(f'network {network["id"]}, controlled by this host ({network["controller"]})')
    listed = answered(*zerotier(f'/controller/network/{network["id"]}/member'), 'listing members')
    for node in sorted(listed):
        member = answered(
            *zerotier(f'/controller/network/{network["id"]}/member/{node}'), f'member {node}'
        )
        who = 'this host' if node == network['controller'] else network['names'].get(node, '?')
        state_said = 'authorized' if member.get('authorized') else 'asking to join'
        addresses = ', '.join(member.get('ipAssignments') or []) or 'no address'
        say(f'  {node}  {state_said:<14} {addresses:<16} {who}')
    return 0


def network_authorize(args, state, authorized=True):
    manifest = load(state)
    network = network_of(manifest)
    node = args.node.strip().lower()
    if not NODE.match(node):
        raise Refused(f'{args.node!r} is not a ZeroTier node id: ten hex digits')
    if node == network['controller'] and not authorized:
        raise Refused('this host is the share; it stays on its own network')
    answered(
        *zerotier(
            f'/controller/network/{network["id"]}/member/{node}', {'authorized': authorized}
        ),
        f'{"authorizing" if authorized else "revoking"} {node}',
    )
    if authorized:
        network['names'][node] = args.name
    say(f'{node} ({network["names"].get(node, "?")}): {"authorized" if authorized else "revoked"}')
    save(state, manifest)
    return 0


def network(args, state):
    actions = {
        None: network_status,
        'create': network_create,
        'authorize': network_authorize,
        'revoke': lambda args, state: network_authorize(args, state, authorized=False),
    }
    return actions[args.action](args, state)


ACCOUNT = r'''
import asyncio, sys
from beanie import init_beanie
from fastapi_users import exceptions
from fastapi_users.db import BeanieUserDatabase
from alfred.core.models.users import UserCreate
from alfred.core.routes.users import UserManager
from alfred.core.utils.db import User, get_db


async def main(email, first_name, superuser):
    password = sys.stdin.readline().rstrip('\r\n')
    await init_beanie(database=get_db(), document_models=[User])
    manager = UserManager(BeanieUserDatabase(User, get_db()['users']))
    account = UserCreate(
        email=email,
        password=password,
        first_name=first_name,
        is_verified=True,
        is_superuser=superuser,
    )
    try:
        user = await manager.create(account, safe=False)
    except exceptions.UserAlreadyExists:
        print(f'{email} already has an account on this share; nothing changed')
        return 1
    except exceptions.InvalidPasswordException as refused:
        print(f'the password was refused: {refused.reason}')
        return 1
    print(f'made {user.email}' + (', a superuser' if superuser else ''))
    return 0


sys.exit(asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3] == '1')))
'''


def account(args, state):
    load(state)
    if not api_container():
        raise Refused('alfred is not running: ./al share up')
    if sys.stdin.isatty():
        password = getpass.getpass(f'password for {args.email}: ')
        if password != getpass.getpass('again: '):
            raise Refused('the two passwords differ; nothing changed')
    else:
        password = sys.stdin.readline().rstrip('\r\n')
    if not password:
        raise Refused('no password given; nothing changed')
    code, output = compose(
        state,
        'exec',
        '-T',
        'api',
        'python',
        '-c',
        ACCOUNT,
        args.email,
        args.name,
        '1' if args.superuser else '0',
        capture=True,
        stdin=password + '\n',
    )
    for line in output.strip().splitlines()[-3:]:
        say(line)
    return 0 if code == 0 else 1


def main(argv=None):
    parser = argparse.ArgumentParser(prog='./al share', description=__doc__.split('\n\n')[0])
    commands = parser.add_subparsers(dest='command')
    commands.add_parser('status', help='what each member serves, and whether it answers as itself')
    made = commands.add_parser('init', help='the state directory, its key and its manifest')
    made.add_argument('address', nargs='+', help="this host's address on the private network")
    made.add_argument('members', nargs='*', default=[], help='MEMBER=REF')
    moved = commands.add_parser('move', help='members pointed at new commits, and brought up there')
    moved.add_argument('members', nargs='+', help='MEMBER=REF')
    setting = commands.add_parser('env', help='a setting one member is started with')
    setting.add_argument('member')
    setting.add_argument('setting', help='NAME=VALUE; NAME= removes it')
    published = commands.add_parser('bind', help='the private-network addresses alfred is published on')
    published.add_argument('address', nargs='+')
    private = commands.add_parser('network', help="the share's own private network, on this host's controller")
    actions = private.add_subparsers(dest='action')
    created = actions.add_parser('create', help='a private network, with this host on it')
    created.add_argument('--name', default='alfred-share')
    allowed = actions.add_parser('authorize', help='an invited device let in')
    allowed.add_argument('node', help="the device's ZeroTier node id")
    allowed.add_argument('--name', required=True, help='who the device is')
    revoked = actions.add_parser('revoke', help='a device shut out')
    revoked.add_argument('node')
    commands.add_parser('up', help='every member at its commit')
    commands.add_parser('down', help='every member stopped; the state stays')
    taken = commands.add_parser('snapshot', help='the database, the media and the manifest, kept by name')
    taken.add_argument('name')
    commands.add_parser('snapshots', help='every snapshot, and the space each takes')
    back = commands.add_parser('restore', help="the share's database and media replaced by a snapshot's")
    back.add_argument('name')
    back.add_argument('--yes', action='store_true')
    made_account = commands.add_parser('account', help='an account on the share; the password is asked for')
    made_account.add_argument('email')
    made_account.add_argument('--name', required=True, help='the first name alfred greets')
    made_account.add_argument('--superuser', action='store_true')
    args = parser.parse_args(argv)
    if args.command == 'init':
        # argparse cannot split two positional lists: an address has no '='.
        given = args.address + args.members
        args.address = [item for item in given if '=' not in item]
        args.members = [item for item in given if '=' in item]
        if not args.address:
            parser.error('init needs the address of this host on the private network')
    handlers = {
        None: status,
        'status': status,
        'init': init,
        'move': move,
        'env': set_env,
        'bind': bind,
        'network': network,
        'up': up,
        'down': down,
        'snapshot': snapshot,
        'snapshots': snapshots,
        'restore': restore,
        'account': account,
    }
    state = state_dir()
    try:
        return handlers[args.command](args, state)
    except Refused as reason:
        say(f'./al share: {reason}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
