"""The tour: the editor's user journeys, a stage at a time, and what a person said of each.

A journey is one of docs/journeys.md's, by its anchor and its heading. Its
stages are the stages of the flow it goes through (website/src/Stages.js), each
with the line the rail shows for it, and what there is to try on it: the
journey's own steps on that stage, read from docs/journeys.md, so the tour has
no words of its own. What takes the editor to a stage is declared beside it, from
three things the editor already does for a person (`PUTS`); none of them makes,
renders, sends or deletes anything.

Feedback is a person's word on one stage: ``works``, or ``off`` with what is
off, under the name they give. Each is kept in the database, with the moment and
the commit the server ran, and never rewritten: the latest for a stage is its
feedback. A word is of the build it was said of: once the server runs another
commit it is still shown, as said of an earlier build, and the stage waits for a
word again. Words are kept only where ``ALFRED_TOUR_WORDS`` is set, which a
production stack refuses (config.py). The box over the editor is
website/src/Tour.js; the routes are core/routes/tour.py.

What the project's roadmap claims of these journeys is not read here: it is
project/ROADMAP.md on alfred's branch of the governance corpus, and
``qmcp tour`` reads it beside ``GET /tour`` and ``GET /tour/feedback``.
"""

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
JOURNEYS_PAGE = REPO / 'docs' / 'journeys.md'
# Where the editor serves that page, for a step's link.
JOURNEYS_HREF = '/docs/journeys/'

VERDICTS = ('works', 'off')
NAME_MOST = 80  # a name is kept this long at most

# The flow's stages as the rail names them (website/src/Stages.js's STAGES):
# a journey's stage is one of them, with the rail's words for it.
FLOW = {
    'source': ('Source', 'Choose a project and its material'),
    'edit': ('Edit', 'Arrange clips on the timeline'),
    'render': ('Render', 'Turn the timeline into a video'),
    'deliver': ('Deliver', 'Send the finished render onward'),
}

# What takes the editor to a stage, each named for the control that does it,
# and done only where it is not so already (website/src/tourStage.js):
#   project  -- the first of `names` that Projects lists, chosen by its row
#   stage    -- the stage chosen on the rail
#   panel    -- the panel brought forward by its tab, on a wide screen
PUTS = ('project', 'stage', 'panel')

# The seeded demo, or the one Generate a demo project makes.
DEMO = ['Timeline demo', 'Demo']


def _stage(stage: str, steps: List[int], *puts: dict) -> dict:
    return {
        'stage': stage,
        'steps': steps,
        'puts': [*puts, {'do': 'stage', 'stage': stage}],
    }


def _project(*names: str) -> dict:
    return {'do': 'project', 'names': list(names)}


def _panel(panel: str) -> dict:
    return {'do': 'panel', 'panel': panel}


# docs/journeys.md's journeys that go through the editor's stages, in the
# page's order. A stage names the page's steps that happen on it. "On a phone",
# "Coming back" and "Saving" are the same stages seen another way, "An account"
# is before the editor, and "With an assistant" is outside it.
JOURNEYS = [
    {
        'id': 'first-video',
        'name': 'A first video',
        'stages': [
            _stage('source', [1, 2], _project(*DEMO)),
            _stage('edit', [3], _project(*DEMO)),
            _stage('render', [4], _project(*DEMO)),
            _stage('deliver', [5], _project(*DEMO)),
        ],
    },
    {
        'id': 'your-own-footage',
        'name': 'Your own footage',
        'stages': [_stage('source', [1, 2, 3, 4])],
    },
    {
        'id': 'arrange-and-title',
        'name': 'Arrange and title',
        'stages': [_stage('edit', [1, 2, 3, 4], _project(*DEMO), _panel('template'))],
    },
    {
        'id': 'render-and-deliver',
        'name': 'Render and deliver',
        'stages': [
            _stage('render', [1, 2], _project(*DEMO)),
            _stage('deliver', [3, 4], _project(*DEMO)),
        ],
    },
    {
        'id': 'from-a-form',
        'name': 'From a form',
        'stages': [
            _stage('source', [1], _project('Announcement')),
            _stage('render', [2, 3, 4], _project('Announcement')),
        ],
    },
    {
        'id': 'captions-and-cutting-by-words',
        'name': 'Captions and cutting by words',
        'stages': [
            _stage('edit', [1, 2, 3], _project(*DEMO), _panel('transcript')),
            _stage('render', [4], _project(*DEMO)),
        ],
    },
]


def stage_id(journey: str, stage: str) -> str:
    return f'{journey}/{stage}'


def stage_ids() -> List[str]:
    return [stage_id(j['id'], s['stage']) for j in JOURNEYS for s in j['stages']]


# --- the journeys page -------------------------------------------------------

SECTION = re.compile(r'^## .*\{ #(?P<anchor>[a-z0-9-]+) \}\s*$')
STEP = re.compile(r'^(?P<number>\d+)\. (?P<text>.*)$')
LINK = re.compile(r'\[([^\]]+)\]\([^)]+\)')


def _plain(text: str) -> str:
    """A step's words as a person reads them: no emphasis marks, links as their text."""
    return ' '.join(LINK.sub(r'\1', text).replace('**', '').split())


def steps(page: Path = JOURNEYS_PAGE) -> Dict[str, Dict[int, str]]:
    """Each journey's numbered steps, by anchor: a step's first paragraph."""
    if not page.is_file():
        return {}
    found: Dict[str, Dict[int, str]] = {}
    anchor, number, words = None, None, []

    def close():
        if anchor and number is not None and words:
            found.setdefault(anchor, {})[number] = _plain(' '.join(words))

    for line in page.read_text(encoding='utf-8').splitlines():
        heading = SECTION.match(line)
        if heading or line.startswith('## '):
            close()
            anchor, number, words = (heading['anchor'] if heading else None), None, []
            continue
        step = STEP.match(line)
        if step and anchor:
            close()
            number, words = int(step['number']), [step['text']]
        elif number is not None and words and line.startswith('   ') and line.strip():
            words.append(line.strip())
        elif number is not None and not line.strip():
            close()
            words = []
    close()
    return found


def _tries(
    journey: str, numbers: List[int], said: Dict[str, Dict[int, str]]
) -> List[dict]:
    """What to try on a stage: the journey's steps on it, each a link to the journey."""
    on_page = said.get(journey, {})
    return [
        {
            'heading': on_page[n],
            'index': n,
            'href': f'{JOURNEYS_HREF}#{journey}',
        }
        for n in numbers
        if n in on_page
    ]


# --- the build, and the words ------------------------------------------------


def _git(*args: str) -> Optional[str]:
    try:
        done = subprocess.run(
            ['git', '-C', str(REPO), *args], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def running() -> dict:
    """The commit the server's code is, and whether its tree has changes beside it."""
    commit = _git('rev-parse', '--short=8', 'HEAD')
    changes = _git('status', '--porcelain', '--untracked-files=no')
    return {'commit': commit, 'changed': bool(changes) if changes is not None else None}


class Refused(ValueError):
    """A word the tour does not keep, saying why."""


def word(stage: str, verdict: str, note: str = '', by: str = '') -> dict:
    """The record of the word of the person ``by`` on ``stage``, ``journey/stage``."""
    if stage not in stage_ids():
        raise LookupError(f'no journey has a stage {stage}')
    if verdict not in VERDICTS:
        raise Refused(f'a word is one of {", ".join(VERDICTS)}, not {verdict!r}')
    note, by = note.strip(), by.strip()
    if verdict == 'off' and not note:
        raise Refused('say what is off')
    if not by:
        raise Refused('say who is saying it')
    return {
        'stage': stage,
        'verdict': verdict,
        'note': note,
        'by': by[:NAME_MOST],
        'at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        **running(),
    }


def document(said: Optional[List[dict]], page: Path = JOURNEYS_PAGE) -> dict:
    """The tour as the box reads it: the journeys in their order, each stage with
    its line, what to try on it, what takes the editor there and its latest word,
    and the commit the server runs. ``said`` is every word kept, oldest first, or
    None where this server keeps none: then ``words`` is false and no stage has
    a word. A server that cannot say its commit ties no word to a build."""
    now, latest = running(), {r['stage']: r for r in said or []}
    on_page = steps(page)

    def feedback(stage: str) -> Optional[dict]:
        record = latest.get(stage)
        if record is None:
            return None
        current = now['commit'] is None or record.get('commit') == now['commit']
        return {**record, 'current': current}

    return {
        **now,
        'words': said is not None,
        'journeys': [
            {
                'id': j['id'],
                'name': j['name'],
                'stages': [
                    {
                        'id': stage_id(j['id'], s['stage']),
                        'journey': j['id'],
                        'stage': s['stage'],
                        'title': FLOW[s['stage']][0],
                        'words': FLOW[s['stage']][1],
                        'tries': _tries(j['id'], s['steps'], on_page),
                        'puts': s['puts'],
                        'feedback': feedback(stage_id(j['id'], s['stage'])),
                    }
                    for s in j['stages']
                ],
            }
            for j in JOURNEYS
        ],
    }
