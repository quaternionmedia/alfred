"""`./al family`: alfred and the repositories it works with, on one machine.

scripts/family.py finds each repository, plans each one's quick suite, starts
joe and the dev stack together, and checks the whole path live. What is tested
here is what decides: where a repository is taken to be, which commands are
its suite (and why there are none), what is said about a vendored pin, whether
what holds joe's port can be used, and that nothing it prints carries a
secret. Starting the stack and the live check are run against a real stack by
hand (docs/family.md), as the browser suite's recipes are.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

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
