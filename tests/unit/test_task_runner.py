"""`./al`, the task runner everything routes through.

Five promises are held here. The help is the full command list -- README and
AGENTS.md both say `./al` with no arguments prints it -- and it was not: it
offered `s`, which did nothing, and left out six commands that worked and
names others answer to. `./al dev` refuses to start on a port somebody else
holds, for each of the three ports the dev stack publishes rather than only
the api's. The checkout's development signing key is made once, random, and
readable by its owner alone. `./al dev` says so when it is about to
serve the network with its authentication switched off. And `./al pytest`
checks formatting, as CI does, rather than rewriting the files it tests.

Each is run for real: `al` is copied into a scratch directory and run with
stand-ins for `curl` and `docker` first on PATH, so a test decides what each
port answers and which container publishes it, and sees whether the stack
would have been started. Nothing here prints the key a run makes: it is
checked for its shape and compared, and a failing check names neither value.
"""

import ast
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def al_source():
    return (REPO / 'al').read_text(encoding='utf-8')


def dispatched():
    """The names each branch of `al`'s dispatch answers to."""
    groups = []
    for line in al_source().splitlines():
        stripped = line.strip()
        if stripped.startswith(('if ', 'elif ')):
            names = re.findall(r'\$1 = "([^"]+)"', stripped)
            if names:
                groups.append(frozenset(names))
    return groups


def listed():
    """The names each line of the help's command list gives."""
    block = al_source().split('COMMANDS:', 1)[1].split('"', 1)[0]
    groups = []
    for line in block.splitlines():
        if line.strip():
            names = re.split(r'\s{2,}', line.strip(), maxsplit=1)[0]
            groups.append(frozenset(name.strip() for name in names.split('|')))
    return groups


class TestTheHelp:
    def test_the_parsers_find_the_commands(self):
        """A parse that found nothing would make the next test pass."""
        assert len(dispatched()) > 20 and len(listed()) > 20

    def test_the_help_lists_exactly_the_commands_that_exist(self):
        """Every command under every name it answers to, and nothing else."""
        missing = [sorted(group) for group in dispatched() if group not in listed()]
        phantom = [sorted(group) for group in listed() if group not in dispatched()]
        assert not missing and not phantom, (
            f'./al runs {missing} but its help does not list them that way, and '
            f'lists {phantom}, which it does not run that way. The help is the '
            'command list README and AGENTS.md send people to; keep it whole.'
        )

    def test_no_name_is_dispatched_twice(self):
        names = [name for group in dispatched() for name in group]
        repeated = sorted({name for name in names if names.count(name) > 1})
        assert not repeated, f'{repeated} each start more than one branch of ./al'


# --- the port guard ---------------------------------------------------------

FAKE_CURL = r"""#!/bin/sh
# Answers as $FAKE_PORTS says, e.g. "8001=52 27017=0": the exit status curl
# gives for a connection to that port. A port not listed refuses (7).
for arg in "$@"; do
  case "$arg" in
    http://localhost:*) rest=${arg#http://localhost:}; port=${rest%%/*} ;;
  esac
done
for entry in $FAKE_PORTS; do
  if [ "${entry%%=*}" = "$port" ]; then
    status=${entry#*=}
    [ "$status" = 0 ] && printf '%s' "$FAKE_OPENAPI"
    exit "$status"
  fi
done
exit 7
"""

FAKE_DOCKER = r"""#!/bin/sh
# Records every call. `docker ps --filter publish=PORT` prints the publisher
# $FAKE_PUBLISHERS names, e.g. "27017=alfred-y2-db-1:alfred-y2".
echo "docker $*" >> "$FAKE_LOG"
if [ "$1" = ps ]; then
  for arg in "$@"; do
    case "$arg" in publish=*) port=${arg#publish=} ;; esac
  done
  for entry in $FAKE_PUBLISHERS; do
    if [ "${entry%%=*}" = "$port" ]; then
      holder=${entry#*=}
      echo "${holder%%:*} ${holder#*:}"
    fi
  done
fi
exit 0
"""


@pytest.fixture
def run_al(tmp_path):
    """Run `./al ARGS` from a scratch copy, with stand-in curl and docker.

    A copy, because `al` writes `.secret_key.local` beside itself and reads
    quotes.csv and alfred/_version.py from there. The scratch directory is
    named `checkout`, so the stack's compose project is `checkout`.
    """
    if sys.platform == 'win32' or not shutil.which('sh'):
        pytest.skip('./al and the stand-ins for curl and docker need a POSIX shell')
    checkout = tmp_path / 'checkout'
    (checkout / 'alfred').mkdir(parents=True)
    shutil.copy(REPO / 'al', checkout / 'al')
    shutil.copy(REPO / 'quotes.csv', checkout / 'quotes.csv')
    shutil.copy(REPO / 'alfred' / '_version.py', checkout / 'alfred' / '_version.py')
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    for name, script in (('curl', FAKE_CURL), ('docker', FAKE_DOCKER)):
        path = bin_dir / name
        path.write_text(script, encoding='utf-8', newline='\n')
        path.chmod(0o755)
    log = tmp_path / 'docker.log'

    def run(*args, ports='', publishers='', openapi='', **env):
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(('ALFRED_', 'COMPOSE_'))
        }
        environment.update(
            PATH=f'{bin_dir}{os.pathsep}{environment.get("PATH", "")}',
            FAKE_PORTS=ports,
            FAKE_PUBLISHERS=publishers,
            FAKE_OPENAPI=openapi,
            FAKE_LOG=str(log),
            **env,
        )
        result = subprocess.run(
            ['sh', 'al', *args],
            cwd=checkout,
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
        )
        calls = log.read_text(encoding='utf-8') if log.exists() else ''
        result.calls = calls.splitlines()
        result.started = any(
            'compose' in call and ' up' in call for call in result.calls
        )
        return result

    return run


ALFRED = '{"openapi":"3.1.0","info":{"title":"Alfred API","version":"0.3.0"}}'
OTHER = '{"openapi":"3.1.0","info":{"title":"Apothecary API","version":"1"}}'


class TestThePortGuard:
    def test_free_ports_start_the_stack(self, run_al):
        result = run_al('dev')
        assert result.returncode == 0, result.stderr
        assert result.started

    @pytest.mark.parametrize(
        'port, setting, moved',
        [
            ('8001', 'ALFRED_HMR_PORT', 'ALFRED_HMR_PORT=8101'),
            ('27017', 'ALFRED_DB_PORT', 'ALFRED_DB_PORT=27117'),
        ],
    )
    def test_a_held_port_is_refused_and_named_by_its_setting(
        self, run_al, port, setting, moved
    ):
        """Neither port speaks HTTP to curl the way the api does: any listener
        counts, here one that closes without a reply (curl's 52)."""
        result = run_al('dev', ports=f'{port}=52')
        assert result.returncode == 1
        assert not result.started, 'the stack was started on a held port'
        assert setting in result.stderr
        assert f'{moved} ./al dev' in result.stderr

    def test_the_container_holding_a_port_is_named(self, run_al):
        result = run_al(
            'dev', ports='27017=0', publishers='27017=alfred-y2-db-1:alfred-y2'
        )
        assert result.returncode == 1 and not result.started
        assert 'the container alfred-y2-db-1' in result.stderr

    def test_every_held_port_is_reported_with_one_command_that_moves_them(self, run_al):
        result = run_al('thin', ports='8000=0 8001=56 27017=0', openapi=OTHER)
        assert result.returncode == 1 and not result.started
        assert 'Apothecary API' in result.stderr
        assert (
            'ALFRED_PORT=8100 ALFRED_HMR_PORT=8101 ALFRED_DB_PORT=27117 ./al thin'
            in result.stderr
        )

    def test_the_ports_are_the_ones_the_settings_say(self, run_al):
        result = run_al(
            'dev', ports='9301=52', ALFRED_HMR_PORT='9301', ALFRED_DB_PORT='9302'
        )
        assert result.returncode == 1 and not result.started
        assert 'ALFRED_HMR_PORT=9401 ./al dev' in result.stderr

    def test_ports_this_checkouts_own_stack_holds_are_left_to_compose(self, run_al):
        """Compose keeps or recreates its own containers rather than colliding
        with them, so moving only the api beside a running stack is allowed."""
        result = run_al(
            'dev',
            ports='8001=52 27017=0',
            publishers='8001=checkout-website-1:checkout 27017=checkout-db-1:checkout',
            ALFRED_PORT='8100',
        )
        assert result.returncode == 0, result.stderr
        assert result.started

    def test_alfred_already_running_here_is_told_to_stop(self, run_al):
        result = run_al(
            'dev',
            ports='8000=0',
            publishers='8000=checkout-api-1:checkout',
            openapi=ALFRED,
        )
        assert result.returncode == 1 and not result.started
        assert 'already running from this checkout' in result.stderr
        assert './al stop' in result.stderr

    def test_another_alfred_on_the_port_is_named(self, run_al):
        result = run_al(
            'dev',
            ports='8000=0',
            publishers='8000=alfred-api-1:alfred',
            openapi=ALFRED,
        )
        assert result.returncode == 1 and not result.started
        assert 'another Alfred stack, the container alfred-api-1' in result.stderr
        assert 'ALFRED_PORT=8100 ./al dev' in result.stderr


# --- the development signing key --------------------------------------------

KEY_LINE = re.compile(r'ALFRED_SECRET_KEY=[0-9a-f]{64}\n')


@pytest.fixture
def key_file(tmp_path):
    """Where `al` in run_al's scratch checkout writes the key."""
    return tmp_path / 'checkout' / '.secret_key.local'


def printed(key, result):
    """Whether a run wrote the key's value anywhere it shows."""
    value = key.split('=', 1)[-1].strip()
    return bool(value) and value in result.stdout + result.stderr


class TestTheDevKey:
    """`./al init`, `dev` and `thin` give the checkout a key of its own.

    docker-compose.yml loads `.secret_key`, a committed stub that leaves
    ALFRED_SECRET_KEY empty, and PyJWT signs with an empty key: anyone could
    mint a development session for any account. dev.yml loads
    `.secret_key.local` over it, and `ensureDevKey` makes that file.

    The key is compared and its shape matched, never shown: every assertion
    on it is a boolean with a message of its own, so a failure prints neither
    value (AGENTS.md, "Logging and secrets").
    """

    @pytest.mark.parametrize('command', ['init', 'dev', 'thin'])
    def test_it_is_made_once_as_64_hex_characters(self, run_al, key_file, command):
        first = run_al(command)
        assert first.returncode == 0, first.stderr
        assert key_file.exists(), f'./al {command} made no .secret_key.local'
        key = key_file.read_text(encoding='utf-8')
        shaped = KEY_LINE.fullmatch(key) is not None
        assert shaped, '.secret_key.local is not one ALFRED_SECRET_KEY= line of 64 hex'
        assert 'Created .secret_key.local' in first.stderr
        leaked = printed(key, first)
        assert not leaked, f'./al {command} printed the key it made'

        again = run_al(command)
        assert again.returncode == 0, again.stderr
        kept = key_file.read_text(encoding='utf-8') == key
        assert kept, f'a second ./al {command} replaced the key'
        assert 'Created' not in again.stderr

    def test_each_checkout_gets_a_key_of_its_own(self, run_al, key_file):
        """Random, not derived from anything: a key made again differs."""
        run_al('init')
        first = key_file.read_text(encoding='utf-8')
        key_file.unlink()
        run_al('init')
        differs = key_file.read_text(encoding='utf-8') != first
        assert differs, 'deleting .secret_key.local and running again gave the same key'

    def test_only_its_owner_can_read_it(self, run_al, key_file):
        if os.name != 'posix':
            pytest.skip('this filesystem has no POSIX modes to check')
        run_al('init')
        mode = stat.S_IMODE(key_file.stat().st_mode)
        assert mode == 0o600, f'.secret_key.local is {oct(mode)}, not 0o600'

    def test_an_empty_file_is_given_a_key(self, run_al, key_file):
        """Emptied by hand, it would hand the api the stub's empty key again."""
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_text('', encoding='utf-8')
        result = run_al('init')
        assert result.returncode == 0, result.stderr
        shaped = KEY_LINE.fullmatch(key_file.read_text(encoding='utf-8')) is not None
        assert shaped, 'an empty .secret_key.local was left empty'

    def test_no_key_is_written_when_none_could_be_made(
        self, run_al, key_file, tmp_path
    ):
        """Without random bytes, a short key would be a guessable one: say so,
        and leave the file for a later run to make."""
        od = tmp_path / 'bin' / 'od'
        od.write_text('#!/bin/sh\nexit 0\n', encoding='utf-8', newline='\n')
        od.chmod(0o755)
        result = run_al('init')
        assert 'Could not generate a development signing key' in result.stderr
        assert not key_file.exists(), 'a key that is not 64 hex characters was written'


# --- the network warning ----------------------------------------------------

EXPOSED = 'anyone who can reach it is served'


class TestTheExposureWarning:
    """`./al dev` and `thin` warn when they are about to publish beyond this
    machine with the auth bypass on: every request is then served as a
    superuser, to anyone on the network. A warning, not a refusal, so the
    stack still starts."""

    @pytest.mark.parametrize('command', ['dev', 'thin'])
    @pytest.mark.parametrize('skip', ['1', 'true', 'YES', 'on'])
    def test_the_network_and_the_bypass_together_are_warned_of(
        self, run_al, command, skip
    ):
        result = run_al(command, ALFRED_BIND='0.0.0.0', ALFRED_DEV_SKIP_AUTH=skip)
        assert result.returncode == 0, result.stderr
        assert result.started
        assert EXPOSED in result.stderr
        assert 'ALFRED_BIND=0.0.0.0' in result.stderr

    @pytest.mark.parametrize(
        'settings',
        [
            pytest.param({'ALFRED_DEV_SKIP_AUTH': '1'}, id='bypass on loopback'),
            pytest.param(
                {'ALFRED_BIND': '127.0.0.1', 'ALFRED_DEV_SKIP_AUTH': '1'},
                id='bypass on loopback, said',
            ),
            pytest.param({'ALFRED_BIND': '0.0.0.0'}, id='network without bypass'),
            pytest.param(
                {'ALFRED_BIND': '0.0.0.0', 'ALFRED_DEV_SKIP_AUTH': '0'},
                id='network, bypass off',
            ),
        ],
    )
    def test_either_alone_is_not(self, run_al, settings):
        result = run_al('dev', **settings)
        assert result.returncode == 0, result.stderr
        assert result.started
        assert EXPOSED not in result.stderr


class TestTheBrowserSuite:
    def test_a_run_starts_from_nothing_under_a_project_of_its_own(self, run_al):
        """`./al test` removes what its last run left, then runs.

        Under <project>-e2e: test_e2e.yml's api, renderer and db share their
        names with the dev stack's, so under the checkout's own project a run
        took over a running dev stack's containers -- and `down --volumes`
        would remove them. The scratch checkout's project is `checkout`.
        """
        result = run_al('test')
        assert result.returncode == 0, result.stderr
        compose = [call for call in result.calls if 'compose' in call]
        assert compose[0].startswith(
            'docker compose -p checkout-e2e -f test_e2e.yml down --volumes'
        ), compose
        assert compose[1].startswith(
            'docker compose -p checkout-e2e -f test_e2e.yml up --build'
        ), compose
        assert '--exit-code-from e2e' in compose[1]


class TestTheApiSuite:
    @pytest.mark.parametrize(
        'args, expected',
        [
            (('pytest',), 'docker compose -p checkout-pytest -f pytest.yml up'),
            (
                ('nox', '-s', 'lint'),
                'docker compose -p checkout-pytest -f pytest.yml run',
            ),
        ],
    )
    def test_it_runs_under_a_project_of_its_own(self, run_al, args, expected):
        """pytest.yml's throwaway database is a service named `db`, as the dev
        stack's is: under the checkout's own project a run recreated a running
        dev stack's database container with the test's."""
        result = run_al(*args)
        assert result.returncode == 0, result.stderr
        compose = [call for call in result.calls if 'compose' in call]
        assert compose and compose[0].startswith(expected), compose


def noxfile():
    return ast.parse((REPO / 'tests' / 'noxfile.py').read_text(encoding='utf-8'))


def default_sessions():
    """`nox.options.sessions`: what nox runs when no session is named."""
    for node in ast.walk(noxfile()):
        if isinstance(node, ast.Assign) and any(
            ast.unparse(target) == 'nox.options.sessions' for target in node.targets
        ):
            return ast.literal_eval(node.value)
    return None


def black_runs(session):
    """The arguments of each `session.run('black', ...)` in a session."""
    for node in ast.walk(noxfile()):
        if isinstance(node, ast.FunctionDef) and node.name == session:
            return [
                [ast.literal_eval(arg) for arg in call.args]
                for call in ast.walk(node)
                if isinstance(call, ast.Call)
                and ast.unparse(call.func) == 'session.run'
                and call.args
                and ast.literal_eval(call.args[0]) == 'black'
            ]
    return []


class TestTheApiSuiteChecksFormatting:
    """`./al pytest` checks formatting as CI does, and rewrites nothing.

    pytest.yml names no session, so nox ran every session in the file,
    `blacken` first: the suite formatted the checkout in place, and code CI's
    `black --check` fails passed here. `./al nox -s blacken` formats.
    """

    def test_al_pytest_runs_the_default_sessions(self):
        text = (REPO / 'pytest.yml').read_text(encoding='utf-8')
        command = re.search(r'^\s+command:\s*(.+)$', text, re.MULTILINE).group(1)
        assert command.split() == ['-f', 'tests/noxfile.py'], command

    def test_the_default_sessions_check_formatting_and_run_the_suite(self):
        sessions = default_sessions()
        assert sessions, 'no nox.options.sessions: nox runs every session'
        assert 'blacken' not in sessions, './al pytest would format in place'
        assert {'lint', 'coverage'} <= set(sessions)
        runs = [run for session in sessions for run in black_runs(session)]
        assert runs, 'no default session runs black: formatting goes unchecked'
        assert all('--check' in run and '-S' in run for run in runs), runs

    def test_blacken_still_formats(self):
        runs = black_runs('blacken')
        assert runs and all('--check' not in run for run in runs), runs
