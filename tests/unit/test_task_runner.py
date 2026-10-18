"""`./al`, the task runner everything routes through.

Two promises are held here. The help is the full command list -- README and
AGENTS.md both say `./al` with no arguments prints it -- and it was not: it
offered `s`, which did nothing, and left out six commands that worked and
names others answer to. And `./al dev` refuses to start on a port somebody
else holds, for each of the three ports the dev stack publishes rather than
only the api's.

The guard is run for real: `al` is copied into a scratch directory and run
with stand-ins for `curl` and `docker` first on PATH, so a test decides what
each port answers and which container publishes it, and sees whether the
stack would have been started.
"""

import os
import re
import shutil
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
        result.started = ' up' in calls and 'compose' in calls
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
