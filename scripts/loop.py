#!/usr/bin/env python3
"""alfred's suites side by side, as one named run; start as many runs as you like.

`./al loop` runs this. Each run has a name (`main` unless one is given), and
everything it starts is named after it: its compose projects, its stack's
ports and database, its logs and its browser results. So two runs never meet,
and the suites inside one run go at the same time:

    ./al loop                          quick, pytest, e2e and docs, at once
    ./al loop --stack --keep           ... then joe and the dev stack, left up
    ./al loop fast --only quick,docs   the seconds-long ones
    ./al loop slow --only e2e --grep @slow
    ./al loop b --stack --port 8100    a second stack beside the first
    ./al loop shots --only stack --recipes
                                       the docs' screenshots and recordings
    ./al loop main --down              take a run's stack down
    ./al loop --list                   the runs this checkout has made

The suites:

    quick    the host's own tests of the tooling and the docs (uv; seconds)
    pytest   the API suite in Docker, formatting and lint included (./al pytest)
    e2e      the browser suite in Docker (./al test)
    docs     the docs site, built --strict
    family   the quick suites of otto, vox, joe, qmcp and the rest (--family)
    stack    joe, then the dev stack pointed at it, checked live (--stack)
    recipes  the docs' screenshots and the recipes' recordings (--recipes)

`main`'s stack is the ordinary dev stack: this checkout's compose project, on
8000, with ./database, so `./al stop` and `./al family down` still work on
it. Any other run's stack is `<checkout>-<name>`, on ports of its own (`--port`,
or the first free block of 8100, 8200 and so on) with a database under
.loop/<name>/. Every stack shares the joe on ALFRED_JOE_PORT (8010): `up`
uses a joe that already answers, and `--down` stops only a joe its own run
started.

The standard library only, as scripts/family.py, whose stack commands this
drives. Nothing it prints carries a secret: the environment it hands a step
is ports, names and paths, and a log's lines go through family's `redact`
before they are shown (AGENTS.md, "Logging and secrets").
"""

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import family  # noqa: E402

ROOT = family.ROOT
LOOPBACK = family.LOOPBACK

SUITES = ('quick', 'pytest', 'e2e', 'docs', 'family', 'stack', 'recipes')
DEFAULT = ('quick', 'pytest', 'e2e', 'docs')

# The host-side tests: the standard library, pytest and PyYAML, nothing of the
# app's. They check the scripts and the docs, so they answer in seconds.
QUICK = (
    'tests/unit/test_loop.py',
    'tests/unit/test_family.py',
    'tests/unit/test_task_runner.py',
    'tests/unit/test_docs_site.py',
    'tests/unit/test_docs_images.py',
    'tests/unit/test_docs_accounted.py',
    'tests/unit/test_docs_recordings.py',
    'tests/unit/test_cookbook.py',
    'tests/unit/test_recipe_gifs.py',
)

# The same ranges as pyproject's docs group and .github/workflows/docs.yml.
MKDOCS = ['--with', 'mkdocs-material>=9.7,<10', '--from', 'mkdocs>=1.6,<2']

# The other repositories `--family` runs; alfred's own are pytest and e2e.
KIN = ('otto', 'vox', 'joe', 'qmcp', 'codecartographer', 'org-dotgithub')

NAME = re.compile(r'^[a-z0-9][a-z0-9_-]{0,30}$')


# --- what a run is -----------------------------------------------------------


class Step:
    """One command of a suite. After a step fails the rest are passed over,
    except one that is `always` run, or that runs `after` a step that
    succeeded: taking down a stack its own `up` started."""

    def __init__(self, label, argv, env=None, always=False, after=None):
        self.label = label
        self.argv = argv
        self.env = env or {}
        self.always = always
        self.after = after


class Run:
    """One named run: its directories, its compose projects and its ports."""

    def __init__(self, name, port=None, root=None, env=None):
        env = os.environ if env is None else env
        root = root or ROOT
        self.name = name
        self.root = root
        self.dir = root / '.loop' / name
        self.checkout = family.compose_project(root, {})
        # pytest and e2e add their own -pytest and -e2e to this.
        self.project = f'{self.checkout}-{name}'
        self.main = name == 'main'
        self.stack_project = self.checkout if self.main else self.project
        self.port = port or int(env.get('ALFRED_PORT') or 8000)

    @property
    def ports(self):
        """The stack's api, live-reload and database ports: 8000, 8001 and
        27017 for main, and the same offsets from any other api port."""
        return {
            'ALFRED_PORT': self.port,
            'ALFRED_HMR_PORT': self.port + 1,
            'ALFRED_DB_PORT': self.port + 19017,
        }

    @property
    def base(self):
        return f'http://{LOOPBACK}:{self.port}'

    def stack_env(self):
        env = {name: str(value) for name, value in self.ports.items()}
        env['COMPOSE_PROJECT_NAME'] = self.stack_project
        env['ALFRED_FAMILY_STATE'] = str(
            self.root / '.family' if self.main else self.dir / 'family'
        )
        if not self.main:
            env['ALFRED_DB_DIR'] = f'./.loop/{self.name}/database'
        return env


def steps_for(suite, run, args, which=family.tool):
    """`suite`'s steps for `run`, or the reason it cannot run here."""
    sh = which('sh') or which('bash')
    python = sys.executable
    if suite == 'quick':
        uv = which('uv')
        if not uv:
            return [], 'needs uv on PATH'
        return [
            Step(
                'host tests',
                [
                    uv,
                    'run',
                    '--no-project',
                    '--with',
                    'pytest',
                    '--with',
                    'pyyaml',
                    'python',
                    '-m',
                    'pytest',
                    '--noconftest',
                    '-p',
                    'no:cacheprovider',
                    '-q',
                    *QUICK,
                ],
            )
        ], None
    if suite == 'docs':
        uvx = which('uvx')
        if not uvx:
            return [], 'needs uvx on PATH'
        site = str(run.dir / 'site')
        return [
            Step(
                'mkdocs build --strict',
                [uvx, *MKDOCS, 'mkdocs', 'build', '--strict', '-d', site],
                {'NO_MKDOCS_2_WARNING': '1'},
            )
        ], None
    if not sh:
        return [], 'needs a POSIX shell (Git Bash on Windows)'
    docker = which('docker')
    if suite in ('pytest', 'e2e', 'stack', 'recipes') and not docker:
        return [], 'needs docker'
    project = {'COMPOSE_PROJECT_NAME': run.project}
    if suite == 'pytest':
        return [
            Step('./al pytest', [sh, 'al', 'pytest'], project),
            Step(
                'down',
                [
                    docker,
                    'compose',
                    '-p',
                    f'{run.project}-pytest',
                    '-f',
                    'pytest.yml',
                    'down',
                ],
                always=True,
            ),
        ], None
    if suite == 'e2e':
        env = dict(project, E2E_OUTPUT=f'.loop/{run.name}')
        if args.grep:
            env['E2E_ARGS'] = f'--grep {args.grep}'
        if args.projects:
            env['E2E_PROJECTS'] = ' '.join(
                f'--project={name}' for name in args.projects.split(',')
            )
        return [Step('./al test', [sh, 'al', 'test'], env)], None
    if suite == 'family':
        return [
            Step(
                'family test',
                [python, 'scripts/family.py', 'test', *KIN],
                {'ALFRED_FAMILY_STATE': str(run.dir / 'family')},
            )
        ], None
    if suite == 'stack':
        env = run.stack_env()
        if args.joe:
            env['ALFRED_FAMILY_JOE'] = args.joe
        # Down first: a stack this run's name left up (--keep) is replaced by
        # this checkout's code as it is now, and main's is the dev stack, which
        # `./al dev` refuses to start over.
        steps = [
            Step('replace', [python, 'scripts/family.py', 'down'], env),
            Step('up', [python, 'scripts/family.py', 'up', '--build'], env),
            Step('smoke', [python, 'scripts/family.py', 'smoke'], env),
        ]
        if args.recipes:
            steps.append(
                Step(
                    './al recipes',
                    [sh, 'al', 'recipes'],
                    dict(env, E2E_BASE_URL=run.base),
                )
            )
        if not args.keep:
            steps.append(
                Step('down', [python, 'scripts/family.py', 'down'], env, after='up')
            )
        return steps, None
    return [], f'no suite called {suite}'


def chosen(args):
    """The suites a run's flags name, in the order they are listed."""
    names = set(DEFAULT)
    if args.only:
        names = set(args.only.split(','))
    names -= set(args.skip.split(',')) if args.skip else set()
    if 'recipes' in names:
        # A step of the stack, not a suite of its own.
        args.recipes = True
        names.discard('recipes')
    if args.stack or args.recipes or args.keep:
        names.add('stack')
    if args.family:
        names.add('family')
    unknown = names - set(SUITES)
    if unknown:
        raise SystemExit(
            f'./al loop: no suite called {", ".join(sorted(unknown))}; '
            f'the suites are {", ".join(SUITES)}'
        )
    return [suite for suite in SUITES if suite in names]


# --- ports -------------------------------------------------------------------


def taken(port, host=LOOPBACK):
    """Whether anything accepts a connection on `port`."""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def free_port(is_taken=taken, start=8100, step=100, tries=9):
    """The first api port from `start` whose api, live-reload and database
    ports are all free, or None."""
    for port in range(start, start + step * tries, step):
        if not any(is_taken(p) for p in (port, port + 1, port + 19017)):
            return port
    return None


# --- what a log says ---------------------------------------------------------

COMPOSE_PREFIX = re.compile(r'^[\w.-]+-\d+\s*\|\s?')
PYTEST_SUMMARY = re.compile(r'^=+ (.+?) in [\d.]+s(?: \([^)]*\))? =+$')
PLAYWRIGHT_COUNT = re.compile(
    r'^\s*(\d+) (passed|failed|flaky|skipped|did not run|interrupted)\b'
)
NOX_SESSION = re.compile(r'^nox > \* (\S+?): (success|failed|skipped)')
QUICK_SUMMARY = re.compile(r'^(\d+ passed.*?) in [\d.]+s$')
SMOKE_SUMMARY = re.compile(r'^\d+ (pass|fail|skip)\b.*$')


def plain(line):
    """A log line without the `service-1  | ` compose puts in front of it."""
    return COMPOSE_PREFIX.sub('', line.rstrip('\n'))


def summary(suite, text):
    """What a finished suite's log says it counted, in one line, or ''."""
    lines = [plain(line) for line in text.splitlines()]
    if suite == 'pytest':
        counts = [m.group(1) for line in lines if (m := PYTEST_SUMMARY.match(line))]
        sessions = [
            f'{m.group(1)} {m.group(2)}'
            for line in lines
            if (m := NOX_SESSION.match(line)) and m.group(2) != 'success'
        ]
        return '; '.join(([counts[-1]] if counts else []) + sessions)
    if suite == 'e2e':
        found = {}
        for line in lines:
            m = PLAYWRIGHT_COUNT.match(line)
            if m:
                found[m.group(2)] = m.group(1)
        order = ('passed', 'failed', 'flaky', 'skipped', 'did not run', 'interrupted')
        return ', '.join(f'{found[k]} {k}' for k in order if k in found)
    if suite == 'quick':
        counts = [m.group(1) for line in lines if (m := QUICK_SUMMARY.match(line))]
        return counts[-1] if counts else ''
    if suite == 'docs':
        return (
            'built, strict'
            if any('Documentation built' in line for line in lines)
            else ''
        )
    if suite == 'stack':
        counts = [line for line in lines if SMOKE_SUMMARY.match(line)]
        return counts[-1] if counts else ''
    if suite == 'family':
        last = [line for line in lines if ': ok' in line or ': failed' in line]
        return last[-1].strip() if last else ''
    return ''


def took(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    return f'{minutes}m{seconds:02d}s' if minutes else f'{seconds}s'


# --- running -----------------------------------------------------------------


class Children:
    """Every process the run started, so an interrupt can stop them all."""

    def __init__(self):
        self.lock = threading.Lock()
        self.pids = set()
        self.stopping = False

    def start(self, argv, env, out):
        options = {}
        if os.name == 'nt':
            options['creationflags'] = 0x00000200  # CREATE_NEW_PROCESS_GROUP
        else:
            options['start_new_session'] = True
        with self.lock:
            if self.stopping:
                return None
            process = subprocess.Popen(
                argv,
                cwd=ROOT,
                env=env,
                stdout=out,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                **options,
            )
            self.pids.add(process.pid)
        return process

    def done(self, process):
        with self.lock:
            self.pids.discard(process.pid)

    def stop_all(self):
        with self.lock:
            self.stopping = True
            pids = list(self.pids)
        for pid in pids:
            family.kill_tree(pid)


def run_suite(suite, steps, log, children, results):
    """Run `steps` into `log`; after the first that fails, only the `always`
    steps run. Puts (suite, ok, seconds, failed label) on `results`."""
    started = time.monotonic()
    failed = None
    succeeded = set()
    with log.open('w', encoding='utf-8') as out:
        for step in steps:
            if step.after and step.after not in succeeded:
                continue
            if failed and not (step.always or step.after):
                continue
            shown = [Path(step.argv[0]).name, *step.argv[1:]]
            named = ' '.join(f'{k}={v}' for k, v in sorted(step.env.items()))
            out.write(f'$ {named + " " if named else ""}{" ".join(shown)}\n')
            out.flush()
            process = children.start(step.argv, dict(os.environ, **step.env), out)
            if process is None:
                failed = failed or step
                break
            code = process.wait()
            children.done(process)
            if code == 0:
                succeeded.add(step.label)
            elif failed is None:
                failed = step
    results.append((suite, failed is None, time.monotonic() - started, failed))


def describe(run, suites, plans):
    say = family.say
    say(f'loop {run.name}: {", ".join(suites)}   (logs: .loop/{run.name}/)')
    for suite in suites:
        steps, reason = plans[suite]
        if not steps:
            say(f'-  {suite:<8} skipped: {reason}')
            continue
        labels = ', '.join(step.label for step in steps)
        say(f'.. {suite:<8} {labels}')
    if 'stack' in suites:
        say(f'   stack    {run.stack_project} at {run.base}')
    say()


def record(run, suites, args):
    run.dir.mkdir(parents=True, exist_ok=True)
    (run.dir / 'run.json').write_text(
        json.dumps(
            {
                'name': run.name,
                'suites': suites,
                'started': time.strftime('%Y-%m-%d %H:%M:%S'),
                'stack': 'stack' in suites,
                'kept': bool(args.keep),
                'port': run.port,
                'project': run.stack_project,
            },
            indent=2,
        ),
        encoding='utf-8',
    )


def loop(args):
    say = family.say
    name = args.name
    if not NAME.match(name):
        say(f'./al loop: a run is named in lower case, digits, - and _; not {name!r}')
        return 2
    suites = chosen(args)
    port = args.port
    if 'stack' in suites and name != 'main' and port is None:
        port = free_port()
        if port is None:
            say(
                './al loop: no free block of ports from 8100 to 8900; name one with --port'
            )
            return 1
    run = Run(name, port)
    plans = {suite: steps_for(suite, run, args) for suite in suites}
    describe(run, suites, plans)
    if args.dry_run:
        for suite in suites:
            for step in plans[suite][0]:
                named = ' '.join(f'{k}={v}' for k, v in sorted(step.env.items()))
                shown = [Path(step.argv[0]).name, *step.argv[1:]]
                say(f'{suite:<8} $ {named + " " if named else ""}{" ".join(shown)}')
        return 0

    run.dir.mkdir(parents=True, exist_ok=True)
    claim = run.dir / 'running'
    try:
        claim.mkdir()
    except FileExistsError:
        say(
            f'./al loop: a run named {name} is going already, or one died; pick '
            f'another name, or remove .loop/{name}/running if none is'
        )
        return 1
    record(run, suites, args)
    children = Children()
    results = []
    threads = []
    try:
        for suite in suites:
            steps, _ = plans[suite]
            if not steps:
                continue
            thread = threading.Thread(
                target=run_suite,
                args=(suite, steps, run.dir / f'{suite}.log', children, results),
                daemon=True,
            )
            thread.start()
            threads.append(thread)
        shown = 0
        while shown < len(threads):
            time.sleep(0.5)
            while shown < len(results):
                report(run, *results[shown])
                shown += 1
    except KeyboardInterrupt:
        say()
        say('./al loop: interrupted; stopping what this run started')
        children.stop_all()
        for thread in threads:
            thread.join(timeout=30)
        say(
            f'Its containers may still be up: ./al loop {name} --down takes the stack down.'
        )
        return 130
    finally:
        try:
            claim.rmdir()
        except OSError:
            pass

    say()
    states = {suite: ok for suite, ok, _, _ in results}
    for suite in suites:
        if suite not in states:
            states[suite] = None
    say(
        '  '.join(
            f'{suite}: {"ok" if ok else "skipped" if ok is None else "failed"}'
            for suite, ok in states.items()
        )
    )
    if 'stack' in suites and args.keep and states.get('stack'):
        say(
            f'Left up: alfred at {run.base}. Take it down with ./al loop {name} --down.'
        )
    return 0 if all(ok is not False for ok in states.values()) else 1


def report(run, suite, ok, seconds, failed):
    say = family.say
    log = run.dir / f'{suite}.log'
    text = log.read_text(encoding='utf-8', errors='replace') if log.exists() else ''
    counted = summary(suite, text)
    if ok:
        say(f'ok {suite:<8} {took(seconds):>7}  {counted}')
        return
    say(
        f'XX {suite:<8} {took(seconds):>7}  {failed.label} failed'
        f'{"; " + counted if counted else ""}; {family.shown(log)} ends:'
    )
    for line in text.splitlines()[-15:]:
        say(f'     {family.redact(plain(line))}')


# --- the other commands ------------------------------------------------------


def down(args):
    say = family.say
    recorded = ROOT / '.loop' / args.name / 'run.json'
    if not recorded.exists():
        say(f'./al loop: no run named {args.name} here (.loop/{args.name}/run.json)')
        return 1
    state = json.loads(recorded.read_text(encoding='utf-8'))
    run = Run(args.name, state.get('port'))
    say(f'loop {run.name}: taking {run.stack_project} down')
    return subprocess.run(
        [sys.executable, 'scripts/family.py', 'down'],
        cwd=ROOT,
        env=dict(os.environ, **run.stack_env()),
    ).returncode


def listing(args):
    say = family.say
    runs = ROOT / '.loop'
    found = sorted(runs.glob('*/run.json')) if runs.exists() else []
    if not found:
        say('./al loop: no runs yet')
        return 0
    for path in found:
        state = json.loads(path.read_text(encoding='utf-8'))
        going = (path.parent / 'running').exists()
        line = f'{state["name"]:<10} {state["started"]}  {", ".join(state["suites"])}'
        if state.get('stack'):
            base = f'http://{LOOPBACK}:{state["port"]}'
            up = family.fetch(base + '/healthz', timeout=3)[0] == 200
            line += f'   stack {base} {"up" if up else "down"}'
        say(line + ('   (going)' if going else ''))
    return 0


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='replace')
    parser = argparse.ArgumentParser(
        prog='./al loop',
        description=__doc__.split('\n\n')[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split('\n\n', 1)[1].split('\n\n`main`')[0],
    )
    parser.add_argument('name', nargs='?', default='main', help='this run (main)')
    parser.add_argument('--only', help='these suites, comma-separated')
    parser.add_argument('--skip', help='all but these, comma-separated')
    parser.add_argument('--stack', action='store_true', help='joe and the dev stack')
    parser.add_argument('--keep', action='store_true', help='leave the stack up')
    parser.add_argument(
        '--recipes', action='store_true', help="the docs' screenshots and recordings"
    )
    parser.add_argument(
        '--family', action='store_true', help="the other repositories' suites"
    )
    parser.add_argument('--port', type=int, help="the stack's api port")
    parser.add_argument('--joe', help="joe's checkout (ALFRED_FAMILY_JOE)")
    parser.add_argument('--grep', help='only the browser tests matching this')
    parser.add_argument(
        '--projects', help='browser projects, comma-separated (chromium,phone)'
    )
    parser.add_argument(
        '--down', action='store_true', help="take this run's stack down"
    )
    parser.add_argument('--list', action='store_true', help='the runs made here')
    parser.add_argument(
        '--dry-run', action='store_true', help='say what would run, and stop'
    )
    args = parser.parse_args(argv)
    if args.list:
        return listing(args)
    if args.down:
        return down(args)
    return loop(args)


if __name__ == '__main__':
    sys.exit(main())
