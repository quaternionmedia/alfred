"""The projects an empty database starts with: one made from a form, one from
a timeline. Templates only, so each renders on any install, with no media and
no network.

A form project's `logic` is json-logic, which the editor evaluates over the
form's values on the Render stage (`website/src/ProjectForm.js`). `var` reads
a field by its name, or the frame's `width` and `height`. See
docs/about/project.md.
"""

import json
from pathlib import Path

# A file, so any account can POST it to /project, and the browser suite too.
ANNOUNCEMENT = json.loads(
    (Path(__file__).parent / 'examples' / 'announcement.json').read_text('utf-8')
)

TIMELINE_DEMO = {
    "name": "Timeline demo",
    "logic": {},
    "fields": [],
    "edl": {
        "clips": [
            {
                "type": "template",
                "name": "title",
                "duration": 3.0,
                "start": 0.0,
                "data": {"text": "Alfred", "color": "#f2aa4c"},
            },
            {
                "type": "template",
                "name": "textBox",
                "duration": 4.0,
                "start": 3.0,
                "data": {
                    "text": "Drama is life with the dull bits cut out.",
                    "color": "#f2aa4c",
                },
            },
            {
                "type": "template",
                "name": "makeColor",
                "duration": 2.0,
                "start": 7.0,
                "data": {"color": "#f2aa4c"},
            },
        ],
        "duration": 9.0,
    },
}

seed = [ANNOUNCEMENT, TIMELINE_DEMO]


def owned_by(owner, projects=None):
    """Copies of the seed projects, each belonging to `owner`.

    Copies, because `insert_many` writes an `_id` into every document it is
    handed, and a second insert from the same process would reuse it.
    `owner=None` leaves the field out, which is how a project with no owner is
    stored.
    """
    projects = seed if projects is None else projects
    if owner is None:
        return [dict(project) for project in projects]
    return [dict(project, owner=owner) for project in projects]
