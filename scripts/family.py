#!/usr/bin/env python3
"""alfred and the repositories it works with, on one machine.

`./al family` runs this. alfred is a control plane over two engines it
vendors -- otto (the picture) at alfred/otto and vox (the sound) at
alfred/vox -- and an audio engine it reaches over HTTP, joe. qmcp drives
alfred as tools and flows; codecartographer shares its workspace shell; the
org's .github repository holds the CI workflows alfred's CI calls. A change
usually touches more than one of them, so the loop is: see where each one is,
run each one's quick suite, bring alfred up with joe as its audio engine, and
check the whole path live.

    ./al family [status]          where every repository is, and what is off
    ./al family test [NAME...]    each one's quick suite (--full: the whole)
    ./al family up [--build]      joe, then the dev stack pointed at it
    ./al family smoke             a live check of the running stack
    ./al family down              the dev stack, and the joe `up` started
    ./al family loop              test, up, smoke, down (--keep: stay up)

Where each repository is: ALFRED_FAMILY_<NAME> (ALFRED_FAMILY_JOE=~/src/joe),
else the first <ancestor>/<name> holding a git checkout, up to three levels
above this one; otto and vox fall back to the copies vendored here.
docs/family.md says the rest.

The standard library only, so it runs with any Python 3.8 or newer, with no
environment to make first. It prints no secret: nothing it runs is handed a
value it echoes, and the lines it shows from a log or an answer go through
`redact` first (AGENTS.md, "Logging and secrets").
"""

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.family'
LOGS = STATE / 'logs'
JOE_PID = STATE / 'joe.json'

# 127.0.0.1, not localhost: the stacks publish on IPv4 loopback, and on Windows
# a client that tries ::1 first waits about two seconds for each refusal.
LOOPBACK = '127.0.0.1'


class Repo:
    def __init__(self, name, role, vendored=None, aliases=()):
        self.name = name
        self.role = role
        self.vendored = vendored
        self.aliases = aliases

    @property
    def setting(self):
        """The variable that says where this repository is."""
        return 'ALFRED_FAMILY_' + re.sub(r'[^A-Z0-9]', '_', self.name.upper())


REPOS = (
    Repo('alfred', 'the control plane: this checkout'),
    Repo('otto', 'the picture engine, vendored at alfred/otto', 'alfred/otto'),
    Repo('vox', 'the sound seam, vendored at alfred/vox', 'alfred/vox'),
    Repo('joe', 'the audio engine alfred reaches over HTTP'),
    Repo('qmcp', 'drives alfred as tools and flows'),
    Repo('codecartographer', "shares the workspace's Golden Layout shell"),
    Repo(
        'org-dotgithub',
        "the org's CI workflows alfred's CI calls",
        aliases=('.github',),
    ),
)
BY_NAME = {repo.name: repo for repo in REPOS}


# --- what is said ------------------------------------------------------------

_SECRETS = (
    (re.compile(r'(sig=)[A-Za-z0-9_\-]+'), r'\1...'),
    (re.compile(r'(Bearer\s+)[A-Za-z0-9._\-]+'), r'\1...'),
    (re.compile(r'("access_token"\s*:\s*")[^"]+'), r'\1...'),
    (
        re.compile(r'((?:SECRET|PASSWORD|TOKEN|KEY)[A-Z_]*\s*[=:]\s*)\S+', re.I),
        r'\1...',
    ),
)


def redact(text):
    """`text` with the signatures, tokens and secret values in it hidden."""
    for pattern, replacement in _SECRETS:
        text = pattern.sub(replacement, text)
    return text


def say(line=''):
    print(redact(line), flush=True)


def tail(path, lines=15):
    try:
        content = path.read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return []
    return [redact(line) for line in content[-lines:]]


# --- where everything is -----------------------------------------------------


def is_checkout(path):
    return (Path(path) / '.git').exists()


def locate(repo, env=None, root=ROOT, depth=3):
    """Where `repo` is checked out, and how that was decided: (path, how).

    The setting wins, and a setting that names no checkout is an answer, not
    a reason to look elsewhere -- someone asked for that one. Then the
    ancestors, nearest first, so a worktree beside its repository finds the
    same siblings the repository does. Then the vendored copy.
    """
    env = os.environ if env is None else env
    if repo.name == 'alfred':
        return root, 'this checkout'
    given = (env.get(repo.setting) or '').strip()
    if given:
        path = Path(given).expanduser()
        if not path.is_absolute():
            path = root / path
        if is_checkout(path):
            return path.resolve(), repo.setting
        return None, f'{repo.setting}={given} is not a git checkout'
    for ancestor in list(root.resolve().parents)[:depth]:
        for name in (repo.name, *repo.aliases):
            candidate = ancestor / name
            if candidate.resolve() != root.resolve() and is_checkout(candidate):
                return candidate, 'beside this checkout'
    if repo.vendored and is_checkout(root / repo.vendored):
        return root / repo.vendored, 'vendored here'
    return None, f'not found: set {repo.setting} to its checkout'


def git(path, *args):
    result = subprocess.run(
        ['git', '-C', str(path), *args], capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else ''


def pinned(vendored, root=ROOT):
    """The commit this checkout pins a submodule at, from HEAD's tree."""
    line = git(root, 'ls-tree', 'HEAD', vendored)
    parts = line.split()
    return parts[2] if len(parts) >= 3 else ''


def on_origin(module, commit):
    """Whether `commit` is on a branch of the module's origin, as far as this
    machine's remote-tracking refs know (they are as fresh as the last fetch)."""
    refs = git(module, 'branch', '-r', '--contains', commit)
    return any(ref.strip().startswith('origin/') for ref in refs.splitlines())


def pin_notes(pin, head, pushed, sibling):
    """What to say about a vendored engine's pin."""
    notes = []
    if not pin:
        return ['! no pin found in HEAD']
    if sibling and head and head != pin:
        notes.append(
            f'! alfred pins {pin[:7]}; this checkout is at {head[:7]}: alfred runs the pin'
        )
    if not pushed:
        notes.append(
            f'! {pin[:7]} is on no origin branch this machine knows of: push it '
            'before alfred, or a clone cannot check it out'
        )
    return notes


def describe(repo, path, how, root=ROOT):
    """One repository's status: its headline and its notes."""
    if path is None:
        return f'{repo.name:<17} -- {how}', []
    branch = git(path, 'rev-parse', '--abbrev-ref', 'HEAD') or '?'
    if branch == 'HEAD':
        branch = 'detached'
    head = git(path, 'rev-parse', 'HEAD')
    changes = git(path, 'status', '--porcelain', '--untracked-files=no')
    changed = len(changes.splitlines()) if changes else 0
    counts = git(path, 'rev-list', '--left-right', '--count', '@{upstream}...HEAD')
    if counts:
        behind, ahead = counts.split()
        upstream = f'{ahead} ahead, {behind} behind upstream'
    else:
        upstream = 'no upstream'
    state = f'{changed} changed' if changed else 'clean'
    headline = f'{repo.name:<17} {branch}@{head[:7]:<8} {state}; {upstream}'
    notes = [f'  {path}  ({how})']
    if repo.vendored:
        pin = pinned(repo.vendored, root)
        module = root / repo.vendored
        sibling = path.resolve() != module.resolve()
        notes += pin_notes(pin, head, on_origin(module, pin), sibling)
    if repo.name == 'joe' and not has_media_api(path):
        notes.append(
            '! no media API (/api/media) on this branch: captions and audio '
            f'analysis need one that has it ({repo.setting})'
        )
    if repo.name == 'qmcp' and not (path / 'qmcp' / 'tools' / 'alfred.py').exists():
        notes.append(f'! no alfred tools on this branch ({repo.setting})')
    if repo.name == 'codecartographer' and not (path / 'web' / 'node_modules').exists():
        notes.append('! web/node_modules missing: npm ci in web/ before its suite')
    return headline, notes


def has_media_api(joe):
    files = [joe / 'api.py', *sorted((joe / 'Modules').glob('*.py'))]
    for file in files:
        try:
            if '/api/media' in file.read_text(encoding='utf-8', errors='ignore'):
                return True
        except OSError:
            continue
    return False


def status(args):
    say(f'alfred and family, from {ROOT}')
    say()
    for repo in REPOS:
        path, how = locate(repo)
        headline, notes = describe(repo, path, how)
        say(headline)
        for note in notes:
            say(f'  {note}' if note.startswith('!') else note)
    return 0


# --- each one's suite --------------------------------------------------------


class Step:
    def __init__(self, label, argv, cwd):
        self.label = label
        self.argv = argv
        self.cwd = cwd


def tool(name):
    """The full path of a command, so Windows runs its .cmd and .exe shims."""
    return shutil.which(name)


def plan(repo, path, full=False, which=tool):
    """`repo`'s suite as steps to run, or the reason there are none."""
    if path is None:
        return [], 'not found'
    name = repo.name
    if name == 'alfred':
        sh = which('sh') or which('bash')
        docker = which('docker')
        if not sh or not docker:
            return [], './al needs a POSIX shell (Git Bash on Windows) and docker'
        # The test image first: `./al nox` and `./al pytest` run whichever
        # alfred_test image is there, however old. A build that changes nothing
        # is a few seconds of cache.
        image = Step(
            'test image',
            [docker, 'compose', '-f', 'pytest.yml', 'build', 'pytest'],
            path,
        )
        if full:
            return [
                image,
                Step('pytest', [sh, 'al', 'pytest'], path),
                Step('browser suite', [sh, 'al', 'test'], path),
            ], None
        # -r: nox keeps its environments in tests/.nox, on the bind mount, so
        # a reused one only checks what the lockfiles ask for instead of
        # installing all of it again -- minutes saved on every run after the
        # first. --full starts from fresh environments.
        return [
            image,
            Step('lint', [sh, 'al', 'nox', '-r', '-s', 'lint'], path),
            Step(
                'unit tier',
                [sh, 'al', 'nox', '-r', '-s', 'coverage', '--', 'unit'],
                path,
            ),
        ], None
    if name == 'otto':
        docker = which('docker')
        if not docker:
            return [], 'needs docker: its suite runs in its test image'
        return [
            Step(
                'test image',
                [docker, 'build', '--target', 'test', '-t', 'alfred-family-otto', '.'],
                path,
            ),
            Step('suite', [docker, 'run', '--rm', 'alfred-family-otto'], path),
        ], None
    if name in ('vox', 'joe', 'qmcp'):
        uv = which('uv')
        if not uv:
            return [], 'needs uv'
        if name == 'vox':
            return [Step('pytest', [uv, 'run', 'pytest', '-q'], path)], None
        if name == 'joe':
            return [Step('pytest', [uv, 'run', '--frozen', 'pytest', '-q'], path)], None
        if full:
            argv = [uv, 'run', '--locked', 'pytest', '-q', 'tests', 'walkthrough']
            return [Step('pytest', argv, path)], None
        tests = sorted(p.name for p in (path / 'tests').glob('test_alfred*.py'))
        if not tests:
            return [], 'no alfred tests on this branch (--full runs everything)'
        argv = [uv, 'run', '--locked', 'pytest', '-q', *(f'tests/{t}' for t in tests)]
        return [Step('alfred tests', argv, path)], None
    if name == 'codecartographer':
        npm = which('npm')
        web = path / 'web'
        if not npm:
            return [], 'needs npm'
        if not (web / 'node_modules').exists():
            return [], 'web/node_modules missing: npm ci in web/'
        steps = [
            Step('typecheck', [npm, 'run', 'typecheck'], web),
            Step('unit', [npm, 'run', 'test:pure'], web),
        ]
        if full:
            steps += [
                Step('state', [npm, 'run', 'test:state'], web),
                Step('build', [npm, 'run', 'build'], web),
            ]
        return steps, None
    return [], 'no suite of its own here: its workflows run in the CI that calls them'


def run_steps(name, steps, log_dir=LOGS):
    """Run `steps` one after another into `<log_dir>/<name>.log`, stopping at
    the first that fails. Returns (ok, seconds, failed step or None)."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / f'{name}.log'
    started = time.monotonic()
    with log.open('w', encoding='utf-8') as out:
        for step in steps:
            shown = [Path(step.argv[0]).name, *step.argv[1:]]
            out.write(f'$ {" ".join(shown)}\n')
            out.flush()
            result = subprocess.run(
                step.argv,
                cwd=step.cwd,
                stdout=out,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
            )
            if result.returncode != 0:
                return False, time.monotonic() - started, step
    return True, time.monotonic() - started, None


def test(args):
    names = args.names or [repo.name for repo in REPOS]
    unknown = [name for name in names if name not in BY_NAME]
    if unknown:
        say(f'unknown: {", ".join(unknown)}; the family is {", ".join(BY_NAME)}')
        return 2
    results = []
    for name in names:
        repo = BY_NAME[name]
        path, how = locate(repo)
        steps, reason = plan(repo, path, full=args.full)
        if not steps:
            say(f'-  {name:<17} skipped: {reason}')
            results.append((name, 'skipped'))
            continue
        labels = ', '.join(step.label for step in steps)
        say(f'.. {name:<17} {labels}  ({path})')
        ok, seconds, failed = run_steps(name, steps)
        if ok:
            say(f'ok {name:<17} {seconds:.0f}s')
            results.append((name, 'ok'))
        else:
            say(
                f'XX {name:<17} {failed.label} failed after {seconds:.0f}s; .family/logs/{name}.log ends:'
            )
            for line in tail(LOGS / f'{name}.log'):
                say(f'     {line}')
            results.append((name, 'failed'))
    say()
    say('  '.join(f'{name}: {state}' for name, state in results))
    return 1 if any(state == 'failed' for _, state in results) else 0


# --- the stack ---------------------------------------------------------------


def fetch(url, data=None, headers=None, method=None, timeout=10):
    """(status, body bytes, headers) for a request; status 0 when nothing answers."""
    request = urllib.request.Request(
        url, data=data, headers=headers or {}, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers or {})
    except (urllib.error.URLError, OSError, ValueError):
        return 0, b'', {}


def title_at(base):
    """The OpenAPI title of what answers at `base`, '' when nothing does, and
    None when something answers that is not an OpenAPI server."""
    status, body, _ = fetch(base + '/openapi.json', timeout=4)
    if status == 0:
        return ''
    try:
        return json.loads(body)['info']['title']
    except (ValueError, KeyError, TypeError):
        return None


def joe_port(env=None):
    env = os.environ if env is None else env
    return int(env.get('ALFRED_JOE_PORT') or 8010)


def docker0_address():
    """docker0's IPv4 address on a Linux host, where containers reach it."""
    if not sys.platform.startswith('linux') or not shutil.which('ip'):
        return None
    shown = subprocess.run(
        ['ip', '-4', '-o', 'addr', 'show', 'docker0'], capture_output=True, text=True
    ).stdout
    match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', shown)
    return match.group(1) if match else None


def joe_host(env=None):
    """Where joe listens: ALFRED_JOE_HOST, else loopback, which Docker Desktop
    forwards to -- and on a Linux host docker0's address, since a bridge cannot
    reach loopback (docs/configuration.md, "Docker hosts and joe")."""
    env = os.environ if env is None else env
    return env.get('ALFRED_JOE_HOST') or docker0_address() or LOOPBACK


def joe_problem(title, port):
    """Why what answers on joe's port cannot be used as joe, or None."""
    if title == '' or (title and 'joe' in title.lower()):
        return None
    what = f'"{title}"' if title else 'something that is not an OpenAPI server'
    return f'port {port} is held by {what}: move joe with ALFRED_JOE_PORT'


def start_joe(path, host, port):
    STATE.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    uv = tool('uv')
    if not uv:
        raise SystemExit('./al family up: joe runs with uv, which is not on PATH')
    log = (LOGS / 'joe.log').open('w', encoding='utf-8')
    argv = [
        uv,
        'run',
        '--frozen',
        'uvicorn',
        'api:app',
        '--host',
        host,
        '--port',
        str(port),
    ]
    options = {}
    if os.name == 'nt':
        options['creationflags'] = 0x00000008 | 0x00000200  # DETACHED, NEW_GROUP
    else:
        options['start_new_session'] = True
    process = subprocess.Popen(
        argv,
        cwd=path,
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        **options,
    )
    JOE_PID.write_text(
        json.dumps({'pid': process.pid, 'port': port, 'host': host, 'path': str(path)}),
        encoding='utf-8',
    )
    return process


def wait_for(check, seconds, every=1.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(every)
    return None


def up(args):
    port = joe_port()
    host = joe_host()
    probe = f'http://{LOOPBACK if host in ("0.0.0.0", "::") else host}:{port}'
    title = title_at(probe)
    problem = joe_problem(title, port)
    if problem:
        say(f'./al family up: {problem}')
        return 1
    if title:
        say(f'joe: "{title}" already answers on {probe}; using it')
    else:
        joe, how = locate(BY_NAME['joe'])
        if joe is None:
            say(f'./al family up: joe {how}')
            return 1
        if not has_media_api(joe):
            say(
                f'! joe at {joe} has no media API: captions and audio analysis will refuse'
            )
        say(f'joe: starting from {joe} on {host}:{port} (log: .family/logs/joe.log)')
        process = start_joe(joe, host, port)
        answered = wait_for(lambda: process.poll() is not None or title_at(probe), 120)
        if process.poll() is not None or not answered:
            say('./al family up: joe did not come up; .family/logs/joe.log ends:')
            for line in tail(LOGS / 'joe.log'):
                say(f'     {line}')
            return 1
    status, _, _ = fetch(probe + '/api/media/capabilities')
    if status != 200:
        say(
            f'! joe answered {status} for /api/media/capabilities: no media engine there'
        )

    env = dict(os.environ)
    env.setdefault('ALFRED_AUDIO_ENGINE_URL', f'http://host.docker.internal:{port}')
    command = [shell(), 'al', 'dev', '-d', *(['--build'] if args.build else [])]
    say(
        f'alfred: ./al dev -d{" --build" if args.build else ""}, audio engine '
        f'{env["ALFRED_AUDIO_ENGINE_URL"]}'
    )
    if subprocess.run(command, cwd=ROOT, env=env).returncode != 0:
        return 1
    base = alfred_base()
    if not wait_for(lambda: fetch(base + '/healthz')[0] == 200, 300, every=2):
        say(f'./al family up: alfred did not answer {base}/healthz; ./al logs says why')
        return 1
    say()
    say(f'alfred  {base}   (docs: ./al docs; smoke: ./al family smoke)')
    say(f'joe     {probe}')
    say(f'qmcp    QMCP_ALFRED_URL={base} for its alfred tools')
    return 0


def kill_tree(pid):
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True)
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    for _ in range(20):
        try:
            os.killpg(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.25)
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def shell():
    found = tool('sh') or tool('bash')
    if not found:
        raise SystemExit('./al family: ./al needs a POSIX shell (Git Bash on Windows)')
    return found


def down(args):
    subprocess.run([shell(), 'al', 'stop'], cwd=ROOT)
    if JOE_PID.exists():
        started = json.loads(JOE_PID.read_text(encoding='utf-8'))
        kill_tree(started['pid'])
        JOE_PID.unlink()
        say(f'joe: stopped (pid {started["pid"]}, port {started["port"]})')
    else:
        say(
            'joe: not started by ./al family up; whatever answers on its port is left alone'
        )
    return 0


# --- the live check ----------------------------------------------------------


def alfred_base(env=None):
    env = os.environ if env is None else env
    return f'http://{LOOPBACK}:{env.get("ALFRED_PORT") or 8000}'


class Checks:
    """PASS, FAIL and SKIP lines, and whether any failed."""

    def __init__(self):
        self.results = []

    def record(self, state, name, detail=''):
        self.results.append((state, name))
        say(f'{state:<4}  {name}' + (f' -- {detail}' if detail else ''))

    @property
    def failed(self):
        return any(state == 'FAIL' for state, _ in self.results)

    def summary(self):
        counts = {}
        for state, _ in self.results:
            counts[state] = counts.get(state, 0) + 1
        return ', '.join(
            f'{counts[s]} {s.lower()}' for s in ('PASS', 'FAIL', 'SKIP') if s in counts
        )


def session_headers(base, env=None):
    """Headers that get past /health's session check, or None when there are none.

    The auth bypass needs none. Otherwise ALFRED_SMOKE_EMAIL and
    ALFRED_SMOKE_PASSWORD name an account to log in as -- names only ever:
    neither value is printed.
    """
    env = os.environ if env is None else env
    status, _, _ = fetch(base + '/health')
    if status == 200:
        return {}
    email, password = env.get('ALFRED_SMOKE_EMAIL'), env.get('ALFRED_SMOKE_PASSWORD')
    if status != 401 or not (email and password):
        return None
    form = urllib.parse.urlencode({'username': email, 'password': password}).encode()
    status, body, _ = fetch(
        base + '/auth/jwt/login',
        data=form,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    if status != 200:
        return None
    return {'Authorization': f'Bearer {json.loads(body)["access_token"]}'}


def as_json(body):
    try:
        return json.loads(body)
    except ValueError:
        return None


def smoke(args, env=None):
    env = os.environ if env is None else env
    base = alfred_base(env)
    checks = Checks()
    status, body, _ = fetch(base + '/healthz')
    if status != 200:
        checks.record(
            'FAIL',
            'alfred answers',
            f'{base}/healthz: {status or "nothing"}; ./al family up',
        )
        return 1
    title = title_at(base)
    checks.record(
        'PASS' if title == 'Alfred API' else 'FAIL',
        'alfred answers',
        f'"{title}" at {base}',
    )

    auth = session_headers(base, env)
    if auth is None:
        checks.record(
            'SKIP',
            'everything behind a session',
            'start with ALFRED_DEV_SKIP_AUTH=1, or set ALFRED_SMOKE_EMAIL and ALFRED_SMOKE_PASSWORD',
        )
        say(checks.summary())
        return 1 if checks.failed else 0
    json_headers = {**auth, 'Content-Type': 'application/json'}

    status, body, _ = fetch(base + '/health', headers=auth)
    health = as_json(body) or {}
    engine = health.get('audio_engine') or {}
    renderer = health.get('renderer') or {}
    ok = (
        status == 200
        and health.get('db') == 'ok'
        and (renderer.get('workers') or 0) >= 1
    )
    checks.record(
        'PASS' if ok else 'FAIL',
        'database and a render worker',
        f'db {health.get("db")}, {renderer.get("workers")} worker(s)',
    )
    if not engine.get('configured'):
        checks.record(
            'FAIL',
            'audio engine',
            'not configured: ./al family up sets ALFRED_AUDIO_ENGINE_URL',
        )
    else:
        checks.record(
            'PASS' if engine.get('ok') else 'FAIL',
            'audio engine',
            'answers' if engine.get('ok') else str(engine.get('detail')),
        )

    status, body, _ = fetch(base + '/media', headers=auth, timeout=60)
    media = as_json(body) if status == 200 else None
    checks.record(
        'PASS' if isinstance(media, list) else 'FAIL',
        'media library',
        f'{len(media)} files' if isinstance(media, list) else f'{status}',
    )
    if engine.get('ok') and isinstance(media, list):
        candidates = [m for m in media if m.get('kind') == 'audio'] + [
            m for m in media if m.get('kind') == 'video'
        ]
        heard = None
        for item in candidates[:6]:
            name = urllib.parse.quote(item['name'].split('/', 1)[-1])
            status, body, _ = fetch(
                f'{base}/media/{name}/audio', headers=auth, timeout=180
            )
            if status == 200:
                heard = (item['name'], as_json(body) or {})
                break
        if heard:
            checks.record(
                'PASS',
                'sound analysed by the audio engine',
                f'{heard[0]}: {heard[1].get("duration")} s',
            )
        else:
            checks.record(
                'SKIP',
                'sound analysed by the audio engine',
                'no library file with sound among the first few',
            )

    status, body, headers = fetch(
        f'{base}/preview/template/title?text=Smoke&width=320&height=180&t=0.5',
        headers=auth,
        timeout=60,
    )
    checks.record(
        (
            'PASS'
            if status == 200 and headers.get('content-type', '').startswith('image/')
            else 'FAIL'
        ),
        'template preview',
        f'{status}',
    )

    edl = {
        'clips': [
            {
                'type': 'template',
                'name': 'title',
                'start': 0,
                'duration': 1,
                'data': {'text': 'Family smoke'},
            }
        ],
        'duration': 1,
    }
    request = {'edl': edl, 'project': 'family smoke', 'width': 320, 'height': 180}
    status, body, _ = fetch(
        base + '/preview/?t=0.5',
        data=json.dumps(request).encode(),
        headers=json_headers,
        method='POST',
        timeout=60,
    )
    frame = as_json(body) if status == 200 else None
    if isinstance(frame, str):
        status, _, headers = fetch(base + frame, headers=auth)
        checks.record(
            'PASS' if status == 200 else 'FAIL',
            'timeline preview',
            'a signed frame, fetched',
        )
    else:
        checks.record('FAIL', 'timeline preview', f'{status}')

    status, body, _ = fetch(
        base + '/render',
        data=json.dumps({**request, 'quality': 'draft'}).encode(),
        headers=json_headers,
        method='POST',
        timeout=60,
    )
    render_id = as_json(body) if status == 200 else None
    if not isinstance(render_id, str):
        checks.record('FAIL', 'render', f'not queued: {status}')
    else:

        def settled():
            got = (
                as_json(fetch(f'{base}/render/{render_id}/status', headers=auth)[1])
                or {}
            )
            return got if got.get('state') in ('rendered', 'failed') else None

        started = time.monotonic()
        state = wait_for(settled, 180, every=2) or {}
        seconds = time.monotonic() - started
        if state.get('state') == 'rendered' and state.get('download_url'):
            # A path on alfred, signed: its `exp` and `sig` admit it without
            # a session, which is how an <a> or a player fetches it.
            url = state['download_url']
            url = base + url if url.startswith('/') else url
            status, part, _ = fetch(url, headers={'Range': 'bytes=0-99'})
            checks.record(
                'PASS' if status == 206 and len(part) == 100 else 'FAIL',
                'render',
                f'rendered in {seconds:.0f} s, downloaded through a signed URL',
            )
        else:
            checks.record(
                'FAIL', 'render', f'{state.get("state")}: {state.get("error")}'
            )
        fetch(f'{base}/render/{render_id}', headers=auth, method='DELETE')

    qmcp, _ = locate(BY_NAME['qmcp'], env)
    uv = tool('uv')
    if qmcp and uv and (qmcp / 'qmcp' / 'tools' / 'alfred.py').exists():
        code = (
            'import json, qmcp.tools.alfred\n'
            'from qmcp.tools import tool_registry\n'
            "print(json.dumps(tool_registry.get('alfred_health').handler({})))\n"
        )
        token = (auth.get('Authorization') or 'Bearer dev').split(' ', 1)[1]
        run = subprocess.run(
            [uv, 'run', '--locked', 'python', '-c', code],
            cwd=qmcp,
            capture_output=True,
            text=True,
            timeout=600,
            env={**env, 'QMCP_ALFRED_URL': base, 'QMCP_ALFRED_TOKEN': token},
        )
        answer = run.stdout.strip().splitlines()[-1:] or ['']
        checks.record(
            'PASS' if run.returncode == 0 and 'audio_engine' in answer[0] else 'FAIL',
            "qmcp's alfred tools reach it",
            (
                'alfred_health answered'
                if run.returncode == 0
                else redact(
                    run.stderr.strip().splitlines()[-1:][0]
                    if run.stderr.strip()
                    else ''
                )
            ),
        )
    else:
        checks.record(
            'SKIP',
            "qmcp's alfred tools reach it",
            'no qmcp with alfred tools, or no uv',
        )

    say(checks.summary())
    return 1 if checks.failed else 0


def loop(args):
    failed = test(argparse.Namespace(names=[], full=False)) != 0
    if up(argparse.Namespace(build=args.build)) != 0:
        return 1
    try:
        failed = smoke(args) != 0 or failed
    finally:
        if not args.keep:
            down(args)
    return 1 if failed else 0


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='replace')
    parser = argparse.ArgumentParser(
        prog='./al family', description=__doc__.split('\n\n')[0]
    )
    commands = parser.add_subparsers(dest='command')
    commands.add_parser('status', help='where every repository is, and what is off')
    tests = commands.add_parser('test', help="each repository's quick suite")
    tests.add_argument('names', nargs='*', help=f'some of: {", ".join(BY_NAME)}')
    tests.add_argument('--full', action='store_true', help='the whole suites')
    starting = commands.add_parser('up', help='joe, then the dev stack pointed at it')
    starting.add_argument(
        '--build', action='store_true', help='rebuild the images first'
    )
    commands.add_parser('smoke', help='a live check of the running stack')
    commands.add_parser('down', help='the dev stack, and the joe `up` started')
    looping = commands.add_parser('loop', help='test, up, smoke, down')
    looping.add_argument('--build', action='store_true')
    looping.add_argument('--keep', action='store_true', help='leave the stack up')
    args = parser.parse_args(argv)
    handlers = {
        'status': status,
        'test': test,
        'up': up,
        'smoke': smoke,
        'down': down,
        'loop': loop,
    }
    return handlers.get(args.command or 'status')(args)


if __name__ == '__main__':
    sys.exit(main())
