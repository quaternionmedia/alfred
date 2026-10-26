"""`./al loop` (scripts/loop.py): which suites run, and that two runs share nothing."""

import importlib.util
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]


def load():
    sys.path.insert(0, str(REPO / 'scripts'))
    spec = importlib.util.spec_from_file_location('loop', REPO / 'scripts' / 'loop.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


loop = load()
CHECKOUT = loop.family.compose_project(REPO, {})


def flags(**given):
    defaults = dict(
        name='main',
        only=None,
        skip=None,
        stack=False,
        keep=False,
        recipes=False,
        family=False,
        port=None,
        joe=None,
        grep=None,
        projects=None,
    )
    return SimpleNamespace(**dict(defaults, **given))


def everywhere(name):
    """Every tool is found."""
    return f'/bin/{name}'


class TestWhichSuites:
    def test_a_bare_run_is_the_four_that_need_no_stack(self):
        assert loop.chosen(flags()) == ['quick', 'pytest', 'e2e', 'docs']

    def test_only_and_skip(self):
        assert loop.chosen(flags(only='docs,quick')) == ['quick', 'docs']
        assert loop.chosen(flags(skip='e2e,pytest')) == ['quick', 'docs']

    def test_a_stack_is_asked_for_by_stack_keep_or_recipes(self):
        for given in (dict(stack=True), dict(keep=True), dict(recipes=True)):
            assert 'stack' in loop.chosen(flags(**given)), given

    def test_recipes_named_as_a_suite_are_the_stack_s_step(self):
        args = flags(only='recipes')
        assert loop.chosen(args) == ['stack'] and args.recipes

    def test_an_unknown_suite_is_refused_by_name(self):
        with pytest.raises(SystemExit, match='no suite called pytset'):
            loop.chosen(flags(only='pytset'))


class TestWhatARunIsCalled:
    def test_main_s_stack_is_the_dev_stack(self):
        """`./al stop` and `./al family down` keep working on it."""
        run = loop.Run('main', root=REPO, env={})
        env = run.stack_env()
        assert env['COMPOSE_PROJECT_NAME'] == CHECKOUT
        assert (env['ALFRED_PORT'], env['ALFRED_HMR_PORT'], env['ALFRED_DB_PORT']) == (
            '8000',
            '8001',
            '27017',
        )
        assert Path(env['ALFRED_FAMILY_STATE']) == REPO / '.family'
        assert 'ALFRED_DB_DIR' not in env

    def test_another_run_s_stack_has_its_own_of_everything(self):
        run = loop.Run('b', 8100, root=REPO, env={})
        env = run.stack_env()
        assert env['COMPOSE_PROJECT_NAME'] == f'{CHECKOUT}-b'
        assert (env['ALFRED_PORT'], env['ALFRED_HMR_PORT'], env['ALFRED_DB_PORT']) == (
            '8100',
            '8101',
            '27117',
        )
        assert env['ALFRED_DB_DIR'] == './.loop/b/database'
        assert Path(env['ALFRED_FAMILY_STATE']) == REPO / '.loop' / 'b' / 'family'

    def test_two_runs_share_no_project_port_or_directory(self):
        # Mutation: name projects after the checkout alone -- this fails.
        a, b = loop.Run('a', 8100, root=REPO), loop.Run('b', 8200, root=REPO)
        traces = []
        for run in (a, b):
            plans = [
                loop.steps_for(suite, run, flags(name=run.name, stack=True), everywhere)
                for suite in ('pytest', 'e2e', 'stack')
            ]
            envs = [step.env for steps, _ in plans for step in steps]
            traces.append(
                {
                    env[key]
                    for env in envs
                    for key in (
                        'COMPOSE_PROJECT_NAME',
                        'ALFRED_PORT',
                        'ALFRED_DB_PORT',
                        'ALFRED_DB_DIR',
                        'E2E_OUTPUT',
                    )
                    if key in env
                }
            )
        assert traces[0] and traces[1] and not traces[0] & traces[1]

    def test_a_run_name_is_one_compose_and_a_directory_can_carry(self):
        assert loop.NAME.match('slow-e2e_2')
        for bad in ('Main', '../x', 'a b', '', '-x'):
            assert not loop.NAME.match(bad), bad

    def test_a_free_block_of_ports_is_found_past_the_taken_ones(self):
        held = {8100, 8201}
        assert loop.free_port(lambda port: port in held) == 8300
        assert loop.free_port(lambda port: True) is None


class TestWhatEachSuiteRuns:
    def plan(self, suite, **given):
        args = flags(**given)
        run = loop.Run(args.name, args.port, root=REPO, env={})
        steps, reason = loop.steps_for(suite, run, args, everywhere)
        assert steps, reason
        return steps

    def test_pytest_and_e2e_run_under_the_run_s_project(self):
        pytest_steps = self.plan('pytest', name='fast')
        assert pytest_steps[0].argv[-1] == 'pytest'
        assert pytest_steps[0].env['COMPOSE_PROJECT_NAME'] == f'{CHECKOUT}-fast'
        assert f'{CHECKOUT}-fast-pytest' in pytest_steps[-1].argv
        assert pytest_steps[-1].always
        e2e = self.plan('e2e', name='fast')[0]
        assert e2e.argv[-1] == 'test' and e2e.env['E2E_OUTPUT'] == '.loop/fast'

    def test_e2e_passes_a_grep_and_projects_through(self):
        env = self.plan('e2e', grep='@slow', projects='chromium,docs')[0].env
        assert env['E2E_ARGS'] == '--grep @slow'
        assert env['E2E_PROJECTS'] == '--project=chromium --project=docs'

    def test_the_stack_replaces_comes_up_is_checked_and_goes_down(self):
        steps = self.plan('stack', stack=True)
        assert [step.label for step in steps] == ['replace', 'up', 'smoke', 'down']
        assert steps[-1].after == 'up'
        kept = self.plan('stack', stack=True, keep=True)
        assert [step.label for step in kept] == ['replace', 'up', 'smoke']

    def test_recipes_are_taken_against_the_run_s_own_stack(self):
        steps = self.plan('stack', name='shots', port=8300, recipes=True)
        recipes = next(step for step in steps if step.label == './al recipes')
        assert recipes.env['E2E_BASE_URL'] == 'http://127.0.0.1:8300'
        assert recipes.env['COMPOSE_PROJECT_NAME'] == f'{CHECKOUT}-shots'

    def test_a_suite_that_cannot_run_here_says_why(self):
        run = loop.Run('main', root=REPO, env={})
        steps, reason = loop.steps_for('pytest', run, flags(), lambda name: None)
        assert not steps and 'shell' in reason

    def test_no_step_is_handed_anything_but_names_ports_and_paths(self):
        """Step env is printed: names, ports and paths only."""
        allowed = re.compile(
            r'^(COMPOSE_PROJECT_NAME|ALFRED_(PORT|HMR_PORT|DB_PORT|DB_DIR|'
            r'FAMILY_STATE|FAMILY_JOE)|E2E_(OUTPUT|ARGS|PROJECTS|BASE_URL)|'
            r'NO_MKDOCS_2_WARNING)$'
        )
        args = flags(stack=True, recipes=True, family=True, joe='../joe', grep='x')
        run = loop.Run('main', root=REPO, env={})
        for suite in loop.SUITES:
            steps, _ = loop.steps_for(suite, run, args, everywhere)
            for step in steps:
                assert all(allowed.match(key) for key in step.env), (suite, step.env)


class TestRunningSteps:
    def script(self, tmp_path, code):
        return [sys.executable, '-c', code]

    def test_a_stack_whose_up_failed_is_not_taken_down(self, tmp_path):
        """A refused `up` must not stop someone else's stack."""
        # Mutation: drop run_suite's check of `after` -- this fails.
        marks = tmp_path / 'marks'
        mark = f'open(r"{marks}", "a").write("{{}}\\n")'
        steps = [
            loop.Step('replace', self.script(tmp_path, mark.format('replace'))),
            loop.Step('up', self.script(tmp_path, 'raise SystemExit(1)')),
            loop.Step('smoke', self.script(tmp_path, mark.format('smoke'))),
            loop.Step('down', self.script(tmp_path, mark.format('down')), after='up'),
        ]
        results = []
        loop.run_suite('stack', steps, tmp_path / 'stack.log', loop.Children(), results)
        assert marks.read_text().split() == ['replace']
        ((suite, ok, _, failed),) = results
        assert not ok and failed.label == 'up'

    def test_a_stack_that_came_up_goes_down_even_when_smoke_fails(self, tmp_path):
        marks = tmp_path / 'marks'
        mark = f'open(r"{marks}", "a").write("{{}}\\n")'
        steps = [
            loop.Step('up', self.script(tmp_path, mark.format('up'))),
            loop.Step('smoke', self.script(tmp_path, 'raise SystemExit(1)')),
            loop.Step('down', self.script(tmp_path, mark.format('down')), after='up'),
        ]
        results = []
        loop.run_suite('stack', steps, tmp_path / 'stack.log', loop.Children(), results)
        assert marks.read_text().split() == ['up', 'down']
        assert results[0][3].label == 'smoke'

    def test_a_second_run_of_the_same_name_is_refused(
        self, tmp_path, monkeypatch, capsys
    ):
        monkeypatch.setattr(loop, 'ROOT', tmp_path)
        (tmp_path / '.loop' / 'x' / 'running').mkdir(parents=True)
        assert loop.main(['x', '--only', 'docs']) == 1
        assert 'a run named x is going already' in capsys.readouterr().out


class TestWhatALogSays:
    def test_pytest_through_nox_in_compose(self):
        log = '\n'.join(
            [
                'alfred-main-pytest-pytest-1  | ===== 1892 passed, 8 skipped, 8 xfailed in 301.22s (0:05:01) =====',
                'alfred-main-pytest-pytest-1  | nox > Ran multiple sessions:',
                'alfred-main-pytest-pytest-1  | nox > * formatting: success',
                'alfred-main-pytest-pytest-1  | nox > * lint: failed',
            ]
        )
        assert (
            loop.summary('pytest', log)
            == '1892 passed, 8 skipped, 8 xfailed; lint failed'
        )

    def test_playwright_through_compose(self):
        log = '\n'.join(
            [
                'alfred-main-e2e-e2e-1  |   2 failed',
                'alfred-main-e2e-e2e-1  |     [chromium] › flow.spec.js:3:1 › x',
                'alfred-main-e2e-e2e-1  |   1 flaky',
                'alfred-main-e2e-e2e-1  |   399 passed (5.2m)',
            ]
        )
        assert loop.summary('e2e', log) == '399 passed, 2 failed, 1 flaky'

    def test_the_others(self):
        assert loop.summary('quick', '....\n141 passed in 3.20s') == '141 passed'
        assert loop.summary('docs', 'INFO -  Documentation built in 4.1 seconds') == (
            'built, strict'
        )
        assert loop.summary('stack', 'PASS  x\n8 pass, 1 skip') == '8 pass, 1 skip'
        assert loop.summary('e2e', 'nothing counted') == ''

    def test_a_failure_names_the_failed_tests(self):
        # Mutation: report the log's last lines only -- this fails.
        log = '\n'.join(
            [
                'alfred-check-e2e-e2e-1  |   1) [chromium] › e2e/a.spec.js:3:1 › a thing works',
                'alfred-check-e2e-e2e-1  |     Error: nope',
                'alfred-check-e2e-e2e-1  |   1) [chromium] › e2e/a.spec.js:3:1 › a thing works',
                'alfred-main-pytest-pytest-1  | FAILED tests/unit/test_x.py::test_y - assert 1',
                'alfred-check-e2e-db-1  | shutting down',
            ]
        )
        assert loop.failures(log) == [
            '1) [chromium] › e2e/a.spec.js:3:1 › a thing works',
            'FAILED tests/unit/test_x.py::test_y - assert 1',
        ]

    def test_minutes_and_seconds(self):
        assert (loop.took(9.6), loop.took(372)) == ('9s', '6m12s')


class TestTheFilesItReliesOn:
    """Isolation lives in the compose files and ./al."""

    def test_every_image_this_checkout_builds_is_named_after_it(self):
        # Mutation: put back `image: alfred_api` in test_e2e.yml -- this fails.
        for name in ('docker-compose.yml', 'dev.yml', 'test_e2e.yml', 'pytest.yml'):
            text = (REPO / name).read_text(encoding='utf-8')
            fixed = re.findall(r'^\s*image: (alfred_\w+)', text, re.M)
            assert not fixed, f'{name} names {fixed} for every checkout alike'
            assert '${ALFRED_IMAGES:-alfred}_' in text, name

    def test_al_names_them_after_the_checkout(self):
        al = (REPO / 'al').read_text(encoding='utf-8')
        assert re.search(
            r'^ALFRED_IMAGES=\$\(imagePrefix\)\nexport ALFRED_IMAGES$', al, re.M
        )

    def test_a_second_stack_can_have_its_own_database(self):
        text = (REPO / 'docker-compose.yml').read_text(encoding='utf-8')
        assert '${ALFRED_DB_DIR:-./database}:/data/db' in text

    def test_a_browser_run_takes_its_projects_arguments_and_output(self):
        text = (REPO / 'test_e2e.yml').read_text(encoding='utf-8')
        assert 'playwright test $$E2E_PROJECTS $$E2E_ARGS' in text
        assert 'E2E_OUTPUT: ${E2E_OUTPUT:-}' in text
        config = (REPO / 'website' / 'playwright.config.js').read_text(encoding='utf-8')
        assert 'process.env.E2E_OUTPUT' in config and 'outputDir' in config
