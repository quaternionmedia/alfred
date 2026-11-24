"""`./al recipes`' last two steps: the recordings collected, then made GIFs.

`website/e2e/collect-recipe-videos.js` reads Playwright's JSON report, copies
each passing recipe's recording into docs/recipes, and lists it in
`website/recipe-videos.json`; `scripts/recipe_gifs.py` turns each listed one
into a GIF that fits MAX_BYTES, or fails the run naming it. What is held here
is what decides which pictures the docs end up with: only a recipe that
passed gets one, a run that reached no recipe deletes nothing, a GIF too big
at every setting is not kept, and an ffmpeg that fails says so.

Neither needs a dev stack. The collector is copied into a scratch tree, where
`__dirname` puts its docs/recipes and its list, and run by node against a
report written here. The converter runs against a stand-in for ffmpeg: a
small Python program that writes a GIF of the size a test asks for at each
frame rate, or fails as ffmpeg does, run by the converter's own call.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
COLLECTOR = REPO / 'website' / 'e2e' / 'collect-recipe-videos.js'


def load():
    spec = importlib.util.spec_from_file_location(
        'recipe_gifs', REPO / 'scripts' / 'recipe_gifs.py'
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


recipe_gifs = load()


# --- the converter ----------------------------------------------------------

FAKE_FFMPEG = r'''
"""ffmpeg, as far as recipe_gifs.py can tell.

Writes the GIF a test's plan sizes for the frame rate asked, logging each
call. Fails as ffmpeg does -- a reason on stderr, a non-zero status, and
what it had written left behind -- for a recording that is not there, or a
recipe the plan says fails.
"""
import json
import re
import sys
from pathlib import Path

plan = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
args = sys.argv[2:]
source, target = Path(args[args.index('-i') + 1]), Path(args[-1])
graph = args[args.index('-vf') + 1]
call = {
    'slug': target.stem,
    'fps': int(re.search(r'\bfps=(\d+)', graph).group(1)),
    'colours': int(re.search(r'max_colors=(\d+)', graph).group(1)),
    'start': float(args[args.index('-ss') + 1]) if '-ss' in args else None,
}
with Path(plan['log']).open('a', encoding='utf-8') as log:
    log.write(json.dumps(call) + '\n')
if not source.is_file():
    sys.stderr.write(f'{source}: No such file or directory\n')
    sys.exit(1)
size = plan['sizes'].get(call['slug'], {}).get(str(call['fps']), 1000)
target.write_bytes(b'GIF89a' + bytes(size - 6))
if call['slug'] in plan['fails']:
    sys.stderr.write(plan['fails'][call['slug']] + '\n')
    sys.exit(1)
'''


@pytest.fixture
def converter(tmp_path, monkeypatch):
    """recipe_gifs.main() against a scratch tree and the stand-in ffmpeg.

    `run(recipes, sizes={slug: {fps: bytes}}, fails={slug: reason})` writes
    the list the collector would have, a recording for each recipe, and runs
    the converter. Each GIF is 1000 bytes unless `sizes` says otherwise.
    """
    recipes_dir = tmp_path / 'docs' / 'recipes'
    recipes_dir.mkdir(parents=True)
    manifest = tmp_path / 'website' / 'recipe-videos.json'
    manifest.parent.mkdir()
    fake = tmp_path / 'fake_ffmpeg.py'
    fake.write_text(FAKE_FFMPEG, encoding='utf-8')
    plan_file = tmp_path / 'plan.json'
    log = tmp_path / 'ffmpeg.log'

    def ffmpeg_run(argv, **kwargs):
        # The converter's own call, with its own keywords, so its check=True
        # and text=True are what turn a failure into the message it prints.
        return subprocess.run(
            [sys.executable, str(fake), str(plan_file), *argv[1:]], **kwargs
        )

    monkeypatch.setattr(recipe_gifs, 'REPO', tmp_path)
    monkeypatch.setattr(recipe_gifs, 'RECIPES', recipes_dir)
    monkeypatch.setattr(recipe_gifs, 'MANIFEST', manifest)
    monkeypatch.setattr(recipe_gifs, 'ffmpeg', lambda: 'ffmpeg')
    monkeypatch.setattr(
        recipe_gifs,
        'subprocess',
        SimpleNamespace(
            run=ffmpeg_run, CalledProcessError=subprocess.CalledProcessError
        ),
    )

    def run(recipes, sizes=None, fails=None, record=True):
        if recipes is not None:
            manifest.write_text(json.dumps({'recipes': recipes}), encoding='utf-8')
            for recipe in recipes if record else []:
                (recipes_dir / f'{recipe["slug"]}.webm').write_bytes(b'webm')
        plan = {'sizes': sizes or {}, 'fails': fails or {}, 'log': str(log)}
        plan_file.write_text(json.dumps(plan), encoding='utf-8')
        code = recipe_gifs.main()
        calls = log.read_text(encoding='utf-8').splitlines() if log.exists() else []
        return SimpleNamespace(
            code=code,
            calls=[json.loads(call) for call in calls],
            gifs=sorted(path.name for path in recipes_dir.glob('*.gif')),
        )

    run.recipes = recipes_dir
    return run


def settings_tried(result, slug):
    return [
        (call['fps'], call['colours']) for call in result.calls if call['slug'] == slug
    ]


class TestTheConverter:
    def test_a_gif_that_fits_is_made_once_from_the_recipes_start(
        self, converter, capsys
    ):
        result = converter([{'slug': 'open-a-project', 'start': 3.25}])
        assert result.code == 0
        assert result.gifs == ['open-a-project.gif']
        assert result.calls == [
            {'slug': 'open-a-project', 'fps': 8, 'colours': 128, 'start': 3.25}
        ]
        assert '(8 fps, 128 colours)' in capsys.readouterr().out

    def test_a_recipe_from_its_first_second_is_not_seeked(self, converter):
        """The login it cuts is in front of the recipe; with none, no -ss."""
        result = converter([{'slug': 'open-a-project', 'start': 0}])
        assert result.code == 0 and result.calls[0]['start'] is None

    def test_one_too_big_is_made_again_at_each_lower_setting_until_it_fits(
        self, converter, capsys
    ):
        over = recipe_gifs.MAX_BYTES + 1
        result = converter(
            [{'slug': 'busy', 'start': 0}, {'slug': 'calm', 'start': 0}],
            sizes={'busy': {'8': over, '6': over, '5': 1000}, 'calm': {'8': over}},
        )
        assert result.code == 0
        assert settings_tried(result, 'busy') == list(recipe_gifs.SETTINGS)
        assert settings_tried(result, 'calm') == list(recipe_gifs.SETTINGS[:2])
        assert result.gifs == ['busy.gif', 'calm.gif']
        out = capsys.readouterr().out
        assert 'busy.gif' in out and '(5 fps, 64 colours)' in out
        assert '(6 fps, 96 colours)' in out

    def test_one_still_too_big_fails_the_run_naming_the_recipe(self, converter, capsys):
        """And is not kept: a GIF over the cap is not published. The others
        are still made."""
        over = recipe_gifs.MAX_BYTES + 1
        result = converter(
            [{'slug': 'huge', 'start': 0}, {'slug': 'small', 'start': 0}],
            sizes={'huge': {'8': over, '6': over, '5': over}},
        )
        assert result.code == 1
        assert settings_tried(result, 'huge') == list(recipe_gifs.SETTINGS)
        assert result.gifs == ['small.gif']
        err = capsys.readouterr().err
        assert f'huge: {over} bytes even at 5 fps, over {recipe_gifs.MAX_BYTES}' in err
        assert 'small' not in err

    def test_an_ffmpeg_failure_fails_the_run_with_its_reason(self, converter, capsys):
        """What ffmpeg had written is removed: a broken file is no GIF."""
        reason = 'Invalid data found when processing input'
        result = converter(
            [{'slug': 'broken', 'start': 0}, {'slug': 'fine', 'start': 0}],
            fails={'broken': reason},
        )
        assert result.code == 1
        assert result.gifs == ['fine.gif']
        assert settings_tried(result, 'broken') == [recipe_gifs.SETTINGS[0]]
        assert f'broken: ffmpeg failed: {reason}' in capsys.readouterr().err

    def test_a_listed_recording_that_is_missing_is_an_ffmpeg_failure(
        self, converter, capsys
    ):
        result = converter([{'slug': 'gone', 'start': 0}], record=False)
        assert result.code == 1 and result.gifs == []
        err = capsys.readouterr().err
        assert 'gone: ffmpeg failed:' in err and 'No such file' in err

    def test_with_no_list_nothing_is_converted_and_the_run_fails(
        self, converter, capsys
    ):
        """The collector removes the list when the run reached no recipe, so
        the GIFs an earlier run made are left as they were."""
        (converter.recipes / 'earlier.gif').write_bytes(b'GIF89a')
        result = converter(None)
        assert result.code == 1 and result.calls == []
        assert result.gifs == ['earlier.gif']
        assert 'collect-recipe-videos.js' in capsys.readouterr().err

    def test_with_no_ffmpeg_the_run_fails_and_says_so(
        self, converter, monkeypatch, capsys
    ):
        monkeypatch.setattr(recipe_gifs, 'ffmpeg', lambda: None)
        result = converter([{'slug': 'open-a-project', 'start': 0}])
        assert result.code == 1 and result.calls == []
        assert 'no ffmpeg' in capsys.readouterr().err


# --- the collector ----------------------------------------------------------


def report_of(*results, errors=()):
    """A Playwright JSON report: one spec per `(title, status, video, start)`,
    in a describe block, as the docs project writes them."""
    specs = []
    for title, status, video, start in results:
        annotations = (
            []
            if start is None
            else [{'type': 'recipe-starts', 'description': f'{start:.2f}'}]
        )
        attachments = (
            []
            if video is None
            else [{'name': 'video', 'contentType': 'video/webm', 'path': str(video)}]
        )
        specs.append(
            {
                'title': title,
                'tests': [
                    {
                        'annotations': [],
                        'projectName': 'docs',
                        'results': [
                            {
                                'status': status,
                                'annotations': annotations,
                                'attachments': attachments,
                            }
                        ],
                    }
                ],
            }
        )
    suite = {'title': 'recipes.spec.js', 'specs': [], 'suites': []}
    if specs:
        suite['suites'].append({'title': '@recipe walkthroughs', 'specs': specs})
    return {'suites': [suite] if specs else [], 'errors': list(errors)}


@pytest.fixture
def collector(tmp_path):
    """Run the collector from a scratch tree, against a report written here.

    The script finds docs/recipes and the list from its own directory, so a
    copy at <tmp>/website/e2e/ writes to <tmp>/docs/recipes and
    <tmp>/website/recipe-videos.json, and nothing in the checkout is touched.
    docs/recipes starts with what an earlier run left: a GIF, a recording and
    a placeholder, and a file that is none of those.
    """
    if shutil.which('node') is None:
        pytest.skip('the collector runs under node, and there is none here')
    e2e = tmp_path / 'website' / 'e2e'
    e2e.mkdir(parents=True)
    shutil.copy(COLLECTOR, e2e / COLLECTOR.name)
    recipes = tmp_path / 'docs' / 'recipes'
    recipes.mkdir(parents=True)
    earlier = ['earlier.gif', 'earlier.webm', 'placeholder.svg', 'notes.txt']
    for name in earlier:
        (recipes / name).write_bytes(b'from an earlier run')
    manifest = tmp_path / 'website' / 'recipe-videos.json'
    manifest.write_text(
        '{"recipes": [{"slug": "earlier", "start": 0}]}', encoding='utf-8'
    )
    videos = tmp_path / 'test-results'
    videos.mkdir()

    def video(name):
        path = videos / name / 'video.webm'
        path.parent.mkdir()
        path.write_bytes(f'recording of {name}'.encode())
        return path

    def run(report):
        path = tmp_path / 'website' / 'recipe-report.json'
        path.write_text(
            report if isinstance(report, str) else json.dumps(report),
            encoding='utf-8',
        )
        result = subprocess.run(
            ['node', str(e2e / COLLECTOR.name), str(path)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
        result.files = sorted(p.name for p in recipes.iterdir())
        result.listed = (
            json.loads(manifest.read_text(encoding='utf-8'))['recipes']
            if manifest.exists()
            else None
        )
        return result

    return SimpleNamespace(
        run=run, video=video, recipes=recipes, earlier=sorted(earlier)
    )


class TestTheCollector:
    def test_only_the_recipes_that_passed_are_kept(self, collector):
        """A recipe that failed leaves no recording, and the screenshots the
        docs project also takes are not recipes. What an earlier run left is
        cleared first, but for a file that is no GIF, recording or picture."""
        result = collector.run(
            report_of(
                (
                    'recipe: choose a project and edit its timeline',
                    'passed',
                    collector.video('passed'),
                    4.5,
                ),
                (
                    'recipe: render the timeline and deliver the result',
                    'failed',
                    collector.video('failed'),
                    3.0,
                ),
                ('screens: the editor', 'passed', collector.video('screen'), None),
            )
        )
        assert result.returncode == 0, result.stderr
        assert result.files == [
            'choose-a-project-and-edit-its-timeline.webm',
            'notes.txt',
        ]
        assert result.listed == [
            {'slug': 'choose-a-project-and-edit-its-timeline', 'start': 4.5}
        ]
        copied = collector.recipes / 'choose-a-project-and-edit-its-timeline.webm'
        assert copied.read_bytes() == b'recording of passed'

    def test_a_run_whose_recipes_all_failed_clears_their_gifs(self, collector):
        """They ran and broke: their GIFs go, rather than claiming they work."""
        result = collector.run(
            report_of(
                (
                    'recipe: open the editor and look around',
                    'failed',
                    collector.video('failed'),
                    2.0,
                )
            )
        )
        assert result.returncode == 0, result.stderr
        assert result.files == ['notes.txt']
        assert result.listed == []

    @pytest.mark.parametrize(
        'report',
        [
            pytest.param(
                report_of(
                    errors=[{'message': 'Error: connect ECONNREFUSED 127.0.0.1:8000'}]
                ),
                id='global setup failed',
            ),
            pytest.param(
                report_of(('screens: the editor', 'passed', None, None)),
                id='no recipe in the run',
            ),
            pytest.param('{"suites": [', id='a report cut short'),
            pytest.param('', id='an empty report'),
        ],
    )
    def test_a_run_that_reached_no_recipe_leaves_docs_recipes_alone(
        self, collector, report
    ):
        """It says nothing about any recipe, so deletes nothing; and leaves
        no list, so the converter does not work from an earlier run's."""
        result = collector.run(report)
        assert result.returncode == 1
        assert result.files == collector.earlier
        assert result.listed is None
        assert 'docs/recipes is left as it was' in result.stderr
