"""`./al host`: alfred as processes on this machine, without Docker.

scripts/host.py starts the api, a render worker and the site's watcher from
the checkout's own environment, against a MongoDB it checks for, with joe as
the family starts it. What is tested here is what decides: which Python and
which settings, what the api and the worker are handed, what each process is
run as, when `up` refuses before starting anything, and that `down` stops
what `up` recorded and nothing else. The processes are stand-ins that record
what they were started as; the run against real ones is by hand
(docs/host-run.md).
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]


def load():
    sys.path.insert(0, str(REPO / 'scripts'))
    spec = importlib.util.spec_from_file_location('host', REPO / 'scripts' / 'host.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


host = load()
KEY = 'k' * 64


class TestWhatIsAskedFor:
    def test_the_defaults_are_the_stacks_ports_and_a_database_beside_them(self):
        assert host.settings({}) == {
            'db': 'mongodb://127.0.0.1:27018',
            'port': 1732,
            'hmr': 1733,
        }

    def test_the_settings_move_each(self):
        chosen = host.settings(
            {
                'ALFRED_HOST_DB': 'mongodb://db.local:27017',
                'ALFRED_PORT': '1832',
                'ALFRED_HMR_PORT': '1833',
            }
        )
        assert chosen == {'db': 'mongodb://db.local:27017', 'port': 1832, 'hmr': 1833}

    def test_pdms_note_names_the_interpreter(self, tmp_path):
        python = tmp_path / 'elsewhere' / 'python'
        python.parent.mkdir()
        python.write_text('', encoding='utf-8')
        (tmp_path / '.pdm-python').write_text(f'{python}\n', encoding='utf-8')
        assert host.interpreter(tmp_path) == python

    def test_the_in_project_virtualenv_is_the_fallback(self, tmp_path):
        """A note naming a Python that is gone is passed over."""
        (tmp_path / '.pdm-python').write_text(
            str(tmp_path / 'gone' / 'python'), encoding='utf-8'
        )
        venv = tmp_path / '.venv' / 'bin'
        venv.mkdir(parents=True)
        (venv / 'python').write_text('', encoding='utf-8')
        assert host.interpreter(tmp_path) == venv / 'python'

    def test_no_environment_is_none(self, tmp_path):
        assert host.interpreter(tmp_path) is None


class TestWhatTheApiIsHanded:
    def test_the_stacks_plumbing_pointed_at_this_machine(self, tmp_path):
        key = tmp_path / '.secret_key.local'
        key.write_text(f'ALFRED_SECRET_KEY={KEY}\n', encoding='utf-8')
        env = host.environment({'PATH': 'kept'}, engine_port=1059, key_file=key)
        assert env['PATH'] == 'kept'
        assert env['DB_URL'] == 'mongodb://127.0.0.1:27018'
        assert env['DB_NAME'] == 'alfred'
        assert env['CELERY_BROKER'] == 'mongodb://127.0.0.1:27018/celery'
        assert env['CELERY_BACKEND'] == env['CELERY_BROKER']
        assert env['STATIC_DIR'] == 'website/dist'
        assert env['VIDEO_DIR'] == 'videos'
        assert env['ALFRED_AUDIO_ENGINE_URL'] == 'http://127.0.0.1:1059'
        assert env['ALFRED_SECRET_KEY'] == KEY

    def test_an_audio_engine_already_named_is_kept(self, tmp_path):
        env = host.environment(
            {'ALFRED_AUDIO_ENGINE_URL': 'http://joe.local:1059'},
            engine_port=1059,
            key_file=tmp_path / 'none',
        )
        assert env['ALFRED_AUDIO_ENGINE_URL'] == 'http://joe.local:1059'

    def test_a_key_in_the_environment_wins_over_the_file(self, tmp_path):
        key = tmp_path / '.secret_key.local'
        key.write_text('ALFRED_SECRET_KEY=from-the-file\n', encoding='utf-8')
        env = host.environment({'ALFRED_SECRET_KEY': 'from-the-shell'}, key_file=key)
        assert env['ALFRED_SECRET_KEY'] == 'from-the-shell'

    def test_without_the_file_no_key_is_invented(self, tmp_path):
        env = host.environment({}, key_file=tmp_path / 'none')
        assert 'ALFRED_SECRET_KEY' not in env


class TestWhatRuns:
    def test_the_three_processes_as_the_stack_runs_them(self):
        chosen = host.settings({'ALFRED_PORT': '1832', 'ALFRED_HMR_PORT': '1833'})
        named = {
            name: (argv, cwd)
            for name, argv, cwd in host.commands(
                'py', 'node', chosen, 'mongodb://x/celery'
            )
        }
        assert list(named) == ['api', 'worker', 'site']

        api, cwd = named['api']
        assert api[:3] == ['py', '-m', 'uvicorn'] and 'alfred.main:app' in api
        assert api[api.index('--host') + 1] == '127.0.0.1'
        assert api[api.index('--port') + 1] == '1832'
        assert '--reload' in api and api[api.index('--reload-dir') + 1] == 'alfred'
        assert cwd == host.ROOT

        worker, cwd = named['worker']
        assert worker[:3] == ['py', '-m', 'celery']
        assert worker[worker.index('-b') + 1] == 'mongodb://x/celery'
        assert worker[worker.index('--result-backend') + 1] == 'mongodb://x/celery'
        assert '--pool=solo' in worker and cwd == host.ROOT

        site, cwd = named['site']
        assert site[:3] == ['node', str(host.PARCEL), 'watch']
        assert site[site.index('--hmr-host') + 1] == '127.0.0.1'
        assert site[site.index('--hmr-port') + 1] == '1833'
        assert cwd == host.ROOT / 'website'


@pytest.fixture
def machine(tmp_path, monkeypatch):
    """A checkout with an environment and the site's parcel, the api's and
    the site's ports free, a database and joe answering: `up` would start
    everything. The stand-ins record what was started and what was killed,
    and each answer can be turned."""
    root = tmp_path / 'checkout'
    python = root / '.venv' / 'bin' / 'python'
    python.parent.mkdir(parents=True)
    python.write_text('', encoding='utf-8')
    parcel = root / 'website' / 'node_modules' / 'parcel' / 'lib' / 'bin.js'
    parcel.parent.mkdir(parents=True)
    parcel.write_text('', encoding='utf-8')
    key_file = root / '.secret_key.local'
    key_file.write_text(f'ALFRED_SECRET_KEY={KEY}\n', encoding='utf-8')
    state = root / '.host'
    patched = {
        'ROOT': root,
        'STATE': state,
        'LOGS': state / 'logs',
        'RECORD': state / 'processes.json',
        'JOE_RECORD': state / 'joe.json',
        'PARCEL': parcel,
        'KEY_FILE': key_file,
        'API_WAIT': 1,
        'SITE_WAIT': 1,
        'WORKER_WAIT': 1,
    }
    for name, value in patched.items():
        monkeypatch.setattr(host, name, value)
    answers = {'api': '', 'hmr': False, 'db': True}
    monkeypatch.setattr(host, 'title_at', lambda base: answers['api'])
    monkeypatch.setattr(host, 'taken', lambda port, host_=None: answers['hmr'])
    monkeypatch.setattr(host, 'database_answers', lambda url: answers['db'])
    monkeypatch.setattr(host, 'tool', lambda name: 'node' if name == 'node' else None)
    monkeypatch.setattr(
        host.family,
        'ensure_joe',
        lambda command, record, log_path: ('http://127.0.0.1:1059', 1059),
    )
    monkeypatch.setattr(host, 'fetch', lambda url, *args, **kwargs: (200, b'{}', {}))
    started = []

    def starting(name, argv, cwd, env):
        started.append((name, argv, cwd, env))
        host.LOGS.mkdir(parents=True, exist_ok=True)
        said = {'site': 'Built in 1s\n', 'worker': 'celery ready.\n'}
        (host.LOGS / f'{name}.log').write_text(said.get(name, ''), encoding='utf-8')
        return SimpleNamespace(pid=100 + len(started))

    monkeypatch.setattr(host, 'start', starting)
    killed = []
    monkeypatch.setattr(host, 'kill_tree', killed.append)
    for name in (
        'ALFRED_HOST_DB',
        'ALFRED_PORT',
        'ALFRED_HMR_PORT',
        'ALFRED_AUDIO_ENGINE_URL',
        'ALFRED_SECRET_KEY',
    ):
        monkeypatch.delenv(name, raising=False)
    return SimpleNamespace(
        root=root,
        answers=answers,
        started=started,
        killed=killed,
        record=state / 'processes.json',
    )


class TestUp:
    def test_everything_free_starts_the_three_and_records_them(self, machine, capsys):
        """Mutation: print the environment -- red: the key is in the output."""
        assert host.up(SimpleNamespace()) == 0
        out = capsys.readouterr().out
        assert [name for name, *_ in machine.started] == ['api', 'worker', 'site']
        env = machine.started[0][3]
        assert env['DB_URL'] == 'mongodb://127.0.0.1:27018'
        assert env['ALFRED_AUDIO_ENGINE_URL'] == 'http://127.0.0.1:1059'
        assert env['ALFRED_SECRET_KEY'] == KEY and KEY not in out
        record = json.loads(machine.record.read_text(encoding='utf-8'))
        assert {name: entry['pid'] for name, entry in record.items()} == {
            'api': 101,
            'worker': 102,
            'site': 103,
        }
        assert 'alfred  http://127.0.0.1:1732' in out
        assert 'joe     http://127.0.0.1:1059' in out

    def test_the_api_already_answering_stops_up_before_anything_starts(
        self, machine, capsys
    ):
        """Mutation: start before the port checks -- red: something started."""
        machine.answers['api'] = 'Alfred API'
        assert host.up(SimpleNamespace()) == 1
        out = capsys.readouterr().out
        assert 'port 1732 (ALFRED_PORT) is already answering, as "Alfred API"' in out
        assert machine.started == [] and not machine.record.exists()

    def test_the_sites_port_in_use_stops_up(self, machine, capsys):
        machine.answers['hmr'] = True
        assert host.up(SimpleNamespace()) == 1
        assert '(ALFRED_HMR_PORT) is already in use' in capsys.readouterr().out
        assert machine.started == []

    def test_no_database_stops_up_and_names_the_setting(self, machine, capsys):
        machine.answers['db'] = False
        assert host.up(SimpleNamespace()) == 1
        out = capsys.readouterr().out
        assert 'nothing answers at mongodb://127.0.0.1:27018 (ALFRED_HOST_DB)' in out
        assert machine.started == []

    def test_no_environment_stops_up_and_says_what_makes_one(self, machine, capsys):
        (machine.root / '.venv' / 'bin' / 'python').unlink()
        assert host.up(SimpleNamespace()) == 1
        assert 'pdm install -G dev -G test -G render' in capsys.readouterr().out
        assert machine.started == []

    def test_an_api_that_does_not_answer_fails_up_and_keeps_the_record(
        self, machine, monkeypatch, capsys
    ):
        monkeypatch.setattr(host, 'fetch', lambda url, *args, **kwargs: (0, b'', {}))
        assert host.up(SimpleNamespace()) == 1
        out = capsys.readouterr().out
        assert 'the api did not answer' in out and './al host down' in out
        assert machine.record.exists(), 'down stops what started from the record'


class TestStatusAndDown:
    def test_status_says_what_answers_and_what_started(self, machine, capsys):
        machine.answers['api'] = 'Alfred API'
        assert host.status(SimpleNamespace()) == 0
        out = capsys.readouterr().out
        assert 'answers as "Alfred API"' in out
        assert 'started  nothing by ./al host up' in out

    def test_down_stops_what_up_recorded_and_nothing_else(self, machine, capsys):
        assert host.up(SimpleNamespace()) == 0
        capsys.readouterr()
        assert host.down(SimpleNamespace()) == 0
        out = capsys.readouterr().out
        assert machine.killed == [101, 102, 103]
        assert not machine.record.exists()
        assert 'joe: not started by ./al host up' in out

    def test_down_with_nothing_recorded_leaves_everything_alone(self, machine, capsys):
        assert host.down(SimpleNamespace()) == 0
        assert machine.killed == []
        assert 'nothing started by ./al host up' in capsys.readouterr().out

    def test_down_stops_a_joe_up_started(self, machine, capsys):
        host.STATE.mkdir(parents=True)
        host.JOE_RECORD.write_text(
            json.dumps({'pid': 7, 'port': 1059, 'host': '127.0.0.1', 'path': 'x'}),
            encoding='utf-8',
        )
        assert host.down(SimpleNamespace()) == 0
        assert machine.killed == [7] and not host.JOE_RECORD.exists()
        assert 'joe: stopped (pid 7, port 1059)' in capsys.readouterr().out


class TestTheCommand:
    def test_help_runs_with_nothing_but_the_standard_library(self):
        done = subprocess.run(
            [sys.executable, '-I', str(REPO / 'scripts' / 'host.py'), '--help'],
            capture_output=True,
            text=True,
        )
        assert done.returncode == 0, done.stderr
        assert 'up' in done.stdout and 'down' in done.stdout
