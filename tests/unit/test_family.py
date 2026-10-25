"""`./al family`: alfred and the repositories it works with, on one machine.

scripts/family.py finds each repository, plans each one's quick suite, starts
joe and the dev stack together, and checks the whole path live. What is tested
here is what decides: where a repository is taken to be, which commands are
its suite (and why there are none), what is said about a vendored pin, whether
what holds joe's port can be used, and that nothing it prints carries a
secret.

`up`, `smoke` and `down` run too, against stand-ins: an HTTP server on
127.0.0.1 answering as alfred or joe, an `./al` that records what it was
asked, and a joe that `up` starts and `down` stops. The whole loop against a
real stack is still run by hand (docs/family.md), as the browser suite's
recipes are.
"""

import importlib.util
import json
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

REPO = Path(__file__).resolve().parents[2]


def load():
    spec = importlib.util.spec_from_file_location(
        'family', REPO / 'scripts' / 'family.py'
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


family = load()


def checkout(path):
    (path / '.git').mkdir(parents=True)
    return path


@pytest.fixture
def tree(tmp_path):
    """repos/qm/alfred, with siblings beside it and one level further up."""
    alfred = checkout(tmp_path / 'repos' / 'qm' / 'alfred')
    checkout(alfred / 'alfred' / 'otto')
    checkout(alfred / 'alfred' / 'vox')
    return SimpleNamespace(
        root=alfred, qm=tmp_path / 'repos' / 'qm', repos=tmp_path / 'repos'
    )


class TestWhereEachOneIs:
    def test_alfred_is_this_checkout(self, tree):
        path, how = family.locate(family.BY_NAME['alfred'], {}, tree.root)
        assert path == tree.root and how == 'this checkout'

    def test_a_sibling_is_found_beside_it_or_further_up(self, tree):
        checkout(tree.qm / 'qmcp')
        checkout(tree.repos / 'joe')
        qmcp, _ = family.locate(family.BY_NAME['qmcp'], {}, tree.root)
        joe, how = family.locate(family.BY_NAME['joe'], {}, tree.root)
        assert qmcp == tree.qm / 'qmcp'
        assert joe == tree.repos / 'joe' and how == 'beside this checkout'

    def test_the_setting_wins(self, tree, tmp_path):
        checkout(tree.qm / 'joe')
        elsewhere = checkout(tmp_path / 'worktrees' / 'joe-media')
        env = {'ALFRED_FAMILY_JOE': str(elsewhere)}
        path, how = family.locate(family.BY_NAME['joe'], env, tree.root)
        assert path == elsewhere.resolve() and how == 'ALFRED_FAMILY_JOE'

    def test_a_setting_naming_no_checkout_is_said_not_ignored(self, tree, tmp_path):
        """Someone asked for that one: falling back to a sibling would test the
        wrong code without saying so."""
        checkout(tree.qm / 'joe')
        env = {'ALFRED_FAMILY_JOE': str(tmp_path / 'nowhere')}
        path, how = family.locate(family.BY_NAME['joe'], env, tree.root)
        assert path is None and 'is not a git checkout' in how

    def test_the_engines_fall_back_to_their_vendored_copies(self, tree):
        path, how = family.locate(family.BY_NAME['otto'], {}, tree.root)
        assert path == tree.root / 'alfred' / 'otto' and how == 'vendored here'

    def test_a_sibling_engine_is_preferred_to_the_vendored_copy(self, tree):
        """Where it is worked on: the status view compares it with the pin."""
        sibling = checkout(tree.qm / 'vox')
        path, _ = family.locate(family.BY_NAME['vox'], {}, tree.root)
        assert path == sibling

    def test_the_org_workflows_answer_to_either_name(self, tree):
        dotgithub = checkout(tree.qm / '.github')
        path, _ = family.locate(family.BY_NAME['org-dotgithub'], {}, tree.root)
        assert path == dotgithub

    def test_a_directory_without_git_is_not_a_checkout(self, tree):
        (tree.qm / 'joe').mkdir()
        path, how = family.locate(family.BY_NAME['joe'], {}, tree.root)
        assert path is None and 'ALFRED_FAMILY_JOE' in how

    def test_every_setting_is_named_after_its_repository(self):
        assert family.BY_NAME['org-dotgithub'].setting == 'ALFRED_FAMILY_ORG_DOTGITHUB'
        assert family.BY_NAME['codecartographer'].setting == (
            'ALFRED_FAMILY_CODECARTOGRAPHER'
        )


def which_all(name):
    return f'/bin/{name}'


def which_none(name):
    return None


class TestEachSuite:
    def plan(self, name, path, **kwargs):
        return family.plan(family.BY_NAME[name], path, **kwargs)

    def test_alfreds_quick_suite_is_lint_and_the_unit_tier(self, tree):
        steps, reason = self.plan('alfred', tree.root, which=which_all)
        assert reason is None
        assert [step.argv[1:] for step in steps] == [
            ['compose', '-f', 'pytest.yml', 'build', 'pytest'],
            ['al', 'nox', '-r', '-s', 'lint'],
            ['al', 'nox', '-r', '-s', 'coverage', '--', 'unit'],
            ['compose', '-p', 'alfred-pytest', '-f', 'pytest.yml', 'down', '-v'],
        ]
        assert steps[-1].always and not any(step.always for step in steps[:-1])

    def test_alfreds_full_suite_is_both_suites(self, tree):
        steps, _ = self.plan('alfred', tree.root, full=True, which=which_all)
        assert [step.argv[1:] for step in steps][1:] == [
            ['al', 'pytest'],
            ['al', 'test'],
        ]

    def test_joe_runs_its_locked_environment(self, tree):
        joe = checkout(tree.qm / 'joe')
        steps, _ = self.plan('joe', joe, which=which_all)
        assert steps[0].argv == ['/bin/uv', 'run', '--frozen', 'pytest', '-q']

    def test_qmcps_quick_suite_is_its_alfred_tests(self, tree):
        qmcp = checkout(tree.qm / 'qmcp')
        (qmcp / 'tests').mkdir()
        for name in (
            'test_alfred_tools.py',
            'test_alfred_render_flow.py',
            'test_voice.py',
        ):
            (qmcp / 'tests' / name).write_text('', encoding='utf-8')
        steps, _ = self.plan('qmcp', qmcp, which=which_all)
        assert steps[0].argv[-2:] == [
            'tests/test_alfred_render_flow.py',
            'tests/test_alfred_tools.py',
        ]

    def test_a_qmcp_without_alfred_tests_says_so(self, tree):
        qmcp = checkout(tree.qm / 'qmcp')
        (qmcp / 'tests').mkdir()
        steps, reason = self.plan('qmcp', qmcp, which=which_all)
        assert steps == [] and 'no alfred tests' in reason

    def test_codecartographer_needs_its_node_modules(self, tree):
        cc = checkout(tree.qm / 'codecartographer')
        (cc / 'web').mkdir()
        steps, reason = self.plan('codecartographer', cc, which=which_all)
        assert steps == [] and 'npm ci' in reason
        (cc / 'web' / 'node_modules').mkdir()
        steps, _ = self.plan('codecartographer', cc, which=which_all)
        assert [step.label for step in steps] == ['typecheck', 'unit']
        assert all(step.cwd == cc / 'web' for step in steps)

    def test_a_missing_tool_is_a_reason_not_a_failure(self, tree):
        for name, tool_needed in (
            ('otto', 'docker'),
            ('vox', 'uv'),
            ('alfred', 'shell'),
        ):
            path, _ = family.locate(family.BY_NAME[name], {}, tree.root)
            steps, reason = self.plan(name, path, which=which_none)
            assert steps == [] and tool_needed.split()[0] in reason, (name, reason)

    def test_a_tidying_step_runs_after_a_failure(self, tmp_path):
        """`./al nox` leaves the test database running; the step that takes it
        down runs whatever the suite said."""
        steps = [
            family.Step(
                'suite', [sys.executable, '-c', 'raise SystemExit(1)'], tmp_path
            ),
            family.Step('next', [sys.executable, '-c', 'print("skipped")'], tmp_path),
            family.Step(
                'tidy', [sys.executable, '-c', 'print("tidied")'], tmp_path, always=True
            ),
        ]
        ok, _, failed = family.run_steps('demo', steps, log_dir=tmp_path / 'logs')
        log = (tmp_path / 'logs' / 'demo.log').read_text(encoding='utf-8')
        assert not ok and failed.label == 'suite'
        assert 'tidied' in log and 'skipped' not in log

    def test_the_project_is_the_one_al_uses(self, tmp_path):
        assert family.compose_project(tmp_path / 'My Alfred', {}) == 'myalfred'
        env = {'COMPOSE_PROJECT_NAME': 'lane-z1'}
        assert family.compose_project(tmp_path, env) == 'lane-z1'

    def test_steps_stop_at_the_first_failure_and_keep_a_log(self, tmp_path):
        steps = [
            family.Step('first', [sys.executable, '-c', 'print("one")'], tmp_path),
            family.Step(
                'second', [sys.executable, '-c', 'raise SystemExit(3)'], tmp_path
            ),
            family.Step('third', [sys.executable, '-c', 'print("three")'], tmp_path),
        ]
        ok, _, failed = family.run_steps('demo', steps, log_dir=tmp_path / 'logs')
        log = (tmp_path / 'logs' / 'demo.log').read_text(encoding='utf-8')
        assert not ok and failed.label == 'second'
        assert 'one' in log and 'three' not in log


class TestWhatIsSaid:
    def test_a_pin_that_differs_from_the_checkout_is_said(self):
        notes = family.pin_notes('a' * 40, 'b' * 40, True, sibling=True)
        assert notes == [
            '! alfred pins aaaaaaa; this checkout is at bbbbbbb: alfred runs the pin'
        ]

    def test_a_pin_on_no_origin_branch_is_said(self):
        notes = family.pin_notes('a' * 40, 'a' * 40, False, sibling=False)
        assert len(notes) == 1 and 'push it before alfred' in notes[0]

    def test_a_pin_that_matches_and_is_pushed_says_nothing(self):
        assert family.pin_notes('a' * 40, 'a' * 40, True, sibling=True) == []

    @pytest.mark.parametrize(
        'text, hidden',
        [
            ('/render/1/download?exp=1792&sig=7S5bNh2xZFz8', '7S5bNh2xZFz8'),
            ('Authorization: Bearer eyJhbGciOi.payload.sig', 'eyJhbGciOi'),
            ('{"access_token": "eyJhbGciOi", "token_type": "bearer"}', 'eyJhbGciOi'),
            ('ALFRED_SECRET_KEY=0123456789abcdef', '0123456789abcdef'),
            ('EMAIL_PASSWORD: hunter2', 'hunter2'),
        ],
    )
    def test_secrets_are_hidden_in_what_is_printed(self, text, hidden):
        assert hidden not in family.redact(text)

    def test_the_rest_of_a_line_is_left_alone(self):
        line = 'PASS  render -- rendered in 4 s, downloaded through a signed URL'
        assert family.redact(line) == line


class TestJoesPort:
    def test_nothing_there_or_joe_there_can_be_used(self):
        assert family.joe_problem('', 8010) is None
        assert family.joe_problem('Joe API', 8010) is None

    def test_another_server_on_the_port_is_named(self):
        problem = family.joe_problem('Apothecary API', 8010)
        assert 'Apothecary API' in problem and 'ALFRED_JOE_PORT' in problem

    def test_a_listener_that_is_not_an_api_is_refused(self):
        assert 'not an OpenAPI server' in family.joe_problem(None, 8010)

    def test_the_settings_move_joe(self):
        assert family.joe_port({}) == 8010
        assert family.joe_port({'ALFRED_JOE_PORT': '8020'}) == 8020
        assert family.joe_host({'ALFRED_JOE_HOST': '0.0.0.0'}) == '0.0.0.0'

    def test_alfred_is_reached_on_ipv4_loopback(self):
        """Not localhost: on Windows a client trying ::1 first waits about two
        seconds for each refusal, since the stacks publish on 127.0.0.1."""
        assert family.alfred_base({}) == 'http://127.0.0.1:8000'
        assert family.alfred_base({'ALFRED_PORT': '8100'}) == 'http://127.0.0.1:8100'


class TestTheCommand:
    def test_status_runs_with_nothing_but_the_standard_library(self):
        result = subprocess.run(
            [sys.executable, '-I', str(REPO / 'scripts' / 'family.py'), '--help'],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0
        for command in ('status', 'test', 'up', 'smoke', 'down', 'loop'):
            assert command in result.stdout


# --- the stack, against stand-ins -------------------------------------------


class Stub:
    """An HTTP server on 127.0.0.1 that answers as a test says, and keeps
    every request it was sent.

    `stub.answer('GET', '/healthz', {'status': 'ok'})` answers that path
    with JSON; a status, headers or bytes can be given instead, or a
    function of the request returning `(body, status)`. Anything not
    answered is a 404.
    """

    def __init__(self):
        self.answers = {}
        self.requests = []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def answer(self):
                url = urlsplit(self.path)
                length = int(self.headers.get('Content-Length') or 0)
                request = SimpleNamespace(
                    method=self.command,
                    path=url.path,
                    query=parse_qs(url.query),
                    headers=dict(self.headers),
                    body=self.rfile.read(length),
                )
                stub.requests.append(request)
                given = stub.answers.get((self.command, url.path))
                if callable(given):
                    given = stub.reply(*given(request))
                status, headers, body = given or (404, {}, b'{}')
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_GET = do_POST = do_DELETE = answer

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.port = self.server.server_address[1]
        self.base = f'http://127.0.0.1:{self.port}'
        threading.Thread(
            target=self.server.serve_forever, args=(0.05,), daemon=True
        ).start()

    def answer(self, method, path, body=None, status=200, headers=None):
        if callable(body):
            self.answers[(method, path)] = body
        else:
            self.answers[(method, path)] = self.reply(body, status, headers)

    @staticmethod
    def reply(body=None, status=200, headers=None):
        headers = dict(headers or {})
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
            headers.setdefault('Content-Type', 'application/json')
        return status, headers, body

    def asked(self, method, path):
        return [r for r in self.requests if (r.method, r.path) == (method, path)]

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def stub():
    server = Stub()
    yield server
    server.close()


def free_port():
    """A port nothing on 127.0.0.1 is listening on, as far as can be told."""
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


# Made up for these tests; each is checked to be absent from what is printed.
SIGNATURE = 'c2lnbmF0dXJlLW9mLXRoZS1zdHVi'
TOKEN = 'eyJzdHViIjoidG9rZW4ifQ.c3R1Yg'


def as_alfred(stub, session='bypass', render='rendered', engine=True):
    """Answer as a dev stack that passes every live check.

    `session` is how /health is reached: 'bypass', as under
    ALFRED_DEV_SKIP_AUTH, or 'login', with a bearer from /auth/jwt/login.
    """
    stub.answer('GET', '/healthz', {'status': 'ok'})
    stub.answer('GET', '/openapi.json', {'info': {'title': 'Alfred API'}})
    health = {
        'api': 'ok',
        'db': 'ok',
        'renderer': {'ok': True, 'workers': 1},
        'audio_engine': {'configured': engine, 'ok': engine},
    }
    if session == 'bypass':
        stub.answer('GET', '/health', health)
    else:
        stub.answer(
            'GET',
            '/health',
            lambda request: (
                (health, 200)
                if request.headers.get('Authorization') == f'Bearer {TOKEN}'
                else ({'detail': 'Unauthorized'}, 401)
            ),
        )
        stub.answer(
            'POST', '/auth/jwt/login', {'access_token': TOKEN, 'token_type': 'bearer'}
        )
    stub.answer(
        'GET',
        '/media',
        [
            {'name': 'videos/train.mp4', 'kind': 'video'},
            {'name': 'videos/e2e-speech.wav', 'kind': 'audio'},
        ],
    )
    stub.answer('GET', '/media/e2e-speech.wav/audio', {'duration': 4.0})
    # Named as uvicorn sends it.
    jpeg = {'content-type': 'image/jpeg'}
    stub.answer('GET', '/preview/template/title', b'\xff\xd8', headers=jpeg)
    stub.answer('POST', '/preview/', f'/preview/frame/f1.jpg?exp=9&sig={SIGNATURE}')
    stub.answer('GET', '/preview/frame/f1.jpg', b'\xff\xd8', headers=jpeg)
    stub.answer('POST', '/render', 'r1')
    rendered = render == 'rendered'
    stub.answer(
        'GET',
        '/render/r1/status',
        {
            'id': 'r1',
            'state': render,
            'error': None if rendered else 'the engine refused the clip',
            'download_url': (
                f'/render/r1/download?exp=9&sig={SIGNATURE}' if rendered else None
            ),
        },
    )
    stub.answer(
        'GET',
        '/render/r1/download',
        bytes(100),
        status=206,
        headers={'Content-Type': 'video/mp4', 'Content-Range': 'bytes 0-99/4096'},
    )
    stub.answer('DELETE', '/render/r1', None)


@pytest.fixture
def smoke(stub, tmp_path, capsys):
    """`./al family smoke` against the stub, with no qmcp to find."""

    def run(**env):
        settings = {
            'ALFRED_PORT': str(stub.port),
            # Named, and not a checkout: no qmcp on this machine is found.
            'ALFRED_FAMILY_QMCP': str(tmp_path / 'no-qmcp'),
            **env,
        }
        code = family.smoke(SimpleNamespace(), settings)
        out = capsys.readouterr().out
        return SimpleNamespace(code=code, out=out, lines=out.splitlines())

    return run


def line(result, name):
    """The line a check printed: `STATE  name -- detail`."""
    found = [
        text
        for text in result.lines
        if text[6:] == name or text[6:].startswith(f'{name} -- ')
    ]
    assert found, f'no line for {name!r} in:\n{result.out}'
    return found[0]


class TestTheLiveCheck:
    def test_a_stack_that_works_passes_every_check(self, stub, smoke):
        as_alfred(stub)
        result = smoke()
        assert result.code == 0, result.out
        for name in (
            'alfred answers',
            'database and a render worker',
            'audio engine',
            'media library',
            'sound analysed by the audio engine',
            'template preview',
            'timeline preview',
            'render',
        ):
            assert line(result, name).startswith('PASS'), result.out
        assert line(result, "qmcp's alfred tools reach it").startswith('SKIP')
        assert result.lines[-1] == '8 pass, 1 skip'

    def test_it_asks_what_the_docs_say_it_asks(self, stub, smoke):
        """The library's file with sound is analysed, the frame is fetched by
        its signed URL, the render downloaded with a range, then deleted."""
        as_alfred(stub)
        smoke()
        assert stub.asked('GET', '/media/e2e-speech.wav/audio')
        frame = stub.asked('GET', '/preview/frame/f1.jpg')
        assert frame and frame[0].query['sig'] == [SIGNATURE]
        download = stub.asked('GET', '/render/r1/download')[0]
        assert download.headers.get('Range') == 'bytes=0-99'
        assert 'Authorization' not in download.headers, 'its signature admits it'
        render = json.loads(stub.asked('POST', '/render')[0].body)
        assert render['quality'] == 'draft' and render['edl']['duration'] == 1
        assert stub.asked('DELETE', '/render/r1')

    def test_nothing_answering_fails_at_once_and_says_what_to_run(self, smoke):
        result = smoke(ALFRED_PORT=str(free_port()))
        assert result.code == 1
        assert len(result.lines) == 1
        assert line(result, 'alfred answers').startswith('FAIL')
        assert './al family up' in result.out

    def test_another_application_on_the_port_fails(self, stub, smoke):
        as_alfred(stub)
        stub.answer('GET', '/openapi.json', {'info': {'title': 'Apothecary API'}})
        result = smoke()
        assert result.code == 1
        assert line(result, 'alfred answers').startswith('FAIL')
        assert '"Apothecary API"' in line(result, 'alfred answers')

    def test_without_a_session_the_checks_behind_one_are_skipped(self, stub, smoke):
        as_alfred(stub, session='login')
        result = smoke()
        assert result.code == 0, result.out
        skipped = line(result, 'everything behind a session')
        assert skipped.startswith('SKIP')
        assert 'ALFRED_DEV_SKIP_AUTH=1' in skipped and 'ALFRED_SMOKE_EMAIL' in skipped
        assert not stub.asked('POST', '/auth/jwt/login')
        assert not stub.asked('GET', '/media')

    def test_an_account_logs_in_and_neither_its_password_nor_token_is_printed(
        self, stub, smoke
    ):
        as_alfred(stub, session='login')
        password = 'stub-password-for-this-test'
        result = smoke(
            ALFRED_SMOKE_EMAIL='smoke@example.com', ALFRED_SMOKE_PASSWORD=password
        )
        assert result.code == 0, result.out
        login = parse_qs(stub.asked('POST', '/auth/jwt/login')[0].body.decode())
        assert login == {'username': ['smoke@example.com'], 'password': [password]}
        behind = [r for r in stub.requests if r.path in ('/media', '/render')]
        assert behind and all(
            r.headers.get('Authorization') == f'Bearer {TOKEN}' for r in behind
        )
        shown = [
            secret for secret in (password, TOKEN, SIGNATURE) if secret in result.out
        ]
        assert not shown, 'smoke printed a password, a token or a signature'

    def test_a_render_that_fails_fails_the_check_and_is_deleted(self, stub, smoke):
        as_alfred(stub, render='failed')
        result = smoke()
        assert result.code == 1
        assert line(result, 'render') == (
            'FAIL  render -- failed: the engine refused the clip'
        )
        assert stub.asked('DELETE', '/render/r1')

    def test_no_audio_engine_fails_and_nothing_is_sent_to_one(self, stub, smoke):
        as_alfred(stub, engine=False)
        result = smoke()
        assert result.code == 1
        assert line(result, 'audio engine').startswith('FAIL')
        assert 'ALFRED_AUDIO_ENGINE_URL' in line(result, 'audio engine')
        assert not stub.asked('GET', '/media/e2e-speech.wav/audio')


FAKE_AL = r'''
"""./al, as far as scripts/family.py can tell: says what it was asked."""
import json
import os
import sys

with open(os.environ['FAKE_AL_LOG'], 'a', encoding='utf-8') as log:
    asked = {'args': sys.argv[1:], 'engine': os.environ.get('ALFRED_AUDIO_ENGINE_URL')}
    log.write(json.dumps(asked) + '\n')
sys.exit(int(os.environ.get('FAKE_AL_STATUS') or 0))
'''

FAKE_JOE = r'''
"""joe, as `uv run --frozen uvicorn api:app --host H --port P` starts it."""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

args = sys.argv[1:]
host, port = args[args.index('--host') + 1], int(args[args.index('--port') + 1])


class Joe(BaseHTTPRequestHandler):
    def do_GET(self):
        answer = {'info': {'title': 'joe'}} if self.path == '/openapi.json' else {}
        body = json.dumps(answer).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


HTTPServer((host, port), Joe).serve_forever()
'''


@pytest.fixture
def stack(stub, tmp_path, monkeypatch):
    """`up` and `down` from a scratch checkout, with stand-ins for what they run.

    The checkout holds a stand-in `./al`, run by this Python where family.py
    would run a shell, which records each command and the audio engine it was
    handed. The stub answers as alfred, on ALFRED_PORT. joe's port is free,
    and ALFRED_FAMILY_JOE names a checkout whose joe `uv` -- this Python,
    again -- starts there.
    """
    root = tmp_path / 'checkout'
    root.mkdir()
    (root / 'al').write_text(FAKE_AL, encoding='utf-8')
    joe = tmp_path / 'joe'
    (joe / '.git').mkdir(parents=True)
    (joe / 'api.py').write_text("ROUTES = ['/api/media']\n", encoding='utf-8')
    # `uv run --frozen ...` from joe's checkout, run by Python, runs `run`.
    (joe / 'run').write_text(FAKE_JOE, encoding='utf-8')
    log = tmp_path / 'al.log'
    state = root / '.family'
    monkeypatch.setattr(family, 'ROOT', root)
    monkeypatch.setattr(family, 'STATE', state)
    monkeypatch.setattr(family, 'LOGS', state / 'logs')
    monkeypatch.setattr(family, 'JOE_PID', state / 'joe.json')
    monkeypatch.setattr(family, 'shell', lambda: sys.executable)
    monkeypatch.setattr(
        family, 'tool', lambda name: sys.executable if name == 'uv' else None
    )
    port = free_port()
    for name, value in {
        'FAKE_AL_LOG': str(log),
        'ALFRED_PORT': str(stub.port),
        'ALFRED_JOE_HOST': '127.0.0.1',
        'ALFRED_JOE_PORT': str(port),
        'ALFRED_FAMILY_JOE': str(joe),
    }.items():
        monkeypatch.setenv(name, value)
    for name in ('ALFRED_AUDIO_ENGINE_URL', 'FAKE_AL_STATUS'):
        monkeypatch.delenv(name, raising=False)
    stub.answer('GET', '/healthz', {'status': 'ok'})

    # The joe `up` starts is reaped as it exits, as init reaps it once
    # `./al family up` has returned: `down` waits for it to be gone.
    started = []
    start_joe = family.start_joe

    def starting(*args):
        process = start_joe(*args)
        started.append(process)
        threading.Thread(target=process.wait, daemon=True).start()
        return process

    monkeypatch.setattr(family, 'start_joe', starting)

    def asked():
        lines = log.read_text(encoding='utf-8').splitlines() if log.exists() else []
        return [json.loads(entry) for entry in lines]

    yield SimpleNamespace(
        joe=joe,
        port=port,
        engine=f'http://host.docker.internal:{port}',
        asked=asked,
        started=started,
        pid_file=state / 'joe.json',
    )
    for process in started:
        if process.poll() is None:
            family.kill_tree(process.pid)


@pytest.fixture
def running_joe(stack, monkeypatch):
    """A joe that is already up: a stub answering as one, on joe's port."""
    joe = Stub()
    joe.answer('GET', '/openapi.json', {'info': {'title': 'joe'}})
    joe.answer('GET', '/api/media/capabilities', {})
    monkeypatch.setenv('ALFRED_JOE_PORT', str(joe.port))
    yield joe
    joe.close()


class TestUpAndDown:
    def test_up_uses_a_joe_already_answering_then_starts_the_dev_stack(
        self, stack, stub, running_joe, capsys
    ):
        code = family.up(SimpleNamespace(build=False))
        out = capsys.readouterr().out
        assert code == 0, out
        assert f'joe: "joe" already answers on {running_joe.base}; using it' in out
        assert stack.asked() == [
            {
                'args': ['dev', '-d'],
                'engine': f'http://host.docker.internal:{running_joe.port}',
            }
        ]
        assert stub.asked('GET', '/healthz')
        assert f'QMCP_ALFRED_URL={stub.base}' in out
        assert not stack.started and not stack.pid_file.exists()

    def test_up_starts_joe_from_its_checkout_and_down_stops_it(self, stack, capsys):
        code = family.up(SimpleNamespace(build=True))
        out = capsys.readouterr().out
        assert code == 0, out
        assert f'joe: starting from {stack.joe} on 127.0.0.1:{stack.port}' in out
        probe = f'http://127.0.0.1:{stack.port}'
        assert family.title_at(probe) == 'joe'
        assert stack.asked() == [
            {'args': ['dev', '-d', '--build'], 'engine': stack.engine}
        ]
        recorded = json.loads(stack.pid_file.read_text(encoding='utf-8'))
        assert recorded['pid'] == stack.started[0].pid
        assert recorded['port'] == stack.port

        assert family.down(SimpleNamespace()) == 0
        out = capsys.readouterr().out
        assert f'joe: stopped (pid {recorded["pid"]}, port {stack.port})' in out
        assert stack.asked()[-1]['args'] == ['stop']
        assert not stack.pid_file.exists()
        assert family.title_at(probe) == '', 'joe still answers after down'

    def test_an_audio_engine_already_set_is_kept(self, stack, running_joe, monkeypatch):
        engine = 'http://host.docker.internal:9999'
        monkeypatch.setenv('ALFRED_AUDIO_ENGINE_URL', engine)
        assert family.up(SimpleNamespace(build=False)) == 0
        assert stack.asked()[0]['engine'] == engine

    def test_another_application_on_joes_port_stops_up_before_the_stack(
        self, stack, monkeypatch, capsys
    ):
        other = Stub()
        try:
            other.answer('GET', '/openapi.json', {'info': {'title': 'Apothecary API'}})
            monkeypatch.setenv('ALFRED_JOE_PORT', str(other.port))
            code = family.up(SimpleNamespace(build=False))
        finally:
            other.close()
        assert code == 1
        assert (
            f'port {other.port} is held by "Apothecary API"' in capsys.readouterr().out
        )
        assert stack.asked() == [] and not stack.started

    def test_a_dev_stack_that_does_not_start_fails_up(
        self, stack, running_joe, monkeypatch
    ):
        monkeypatch.setenv('FAKE_AL_STATUS', '1')
        assert family.up(SimpleNamespace(build=False)) == 1
        assert [entry['args'] for entry in stack.asked()] == [['dev', '-d']]

    def test_down_leaves_a_joe_it_did_not_start_alone(self, stack, capsys):
        assert family.down(SimpleNamespace()) == 0
        assert stack.asked() == [{'args': ['stop'], 'engine': None}]
        assert 'not started by ./al family up' in capsys.readouterr().out
