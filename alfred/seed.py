"""The projects an empty database starts with: one made from a form, one from
a timeline. Templates only, so each renders on any install, with no media and
no network.

A form project's `logic` is json-logic, which the editor evaluates over the
form's values on the Render stage (`website/src/ProjectForm.js`). `var` reads
a field by its name, or the frame's `width` and `height`. See
docs/about/project.md.
"""

WIDTH = {"var": "width"}
HEIGHT = {"var": "height"}
# A select's value is a string; `+` reads it as a number.
SECONDS = {"+": [{"var": "duration"}]}
AFTER_THE_FIRST = {"-": [SECONDS, 1]}
# From one frame to the right, to its place, over otto's first second.
FLY_IN = {
    "name": "bezier2",
    "data": {"c1x": 1, "c1y": 0, "ax": 0, "ay": 0, "c2x": 0, "c2y": 1},
}


def share(fraction, of):
    """`fraction` of the frame's width or height, in whole pixels."""
    return {"floor": {"*": [fraction, of]}}


def scaled(divisor):
    """A font size that keeps its proportion to the frame at any size."""
    return {"/": [{"sqrt": {"*": [WIDTH, HEIGHT]}}, divisor]}


def layer(template, start, duration, **data):
    """A template clip, its data evaluated over the form's values."""
    return {
        "eachKey": {
            "type": "template",
            "name": template,
            "start": start,
            "duration": duration,
            "data": {"eachKey": data},
        }
    }


ANNOUNCEMENT = {
    "name": "Announcement",
    "logic": {
        "merge": [
            layer("makeColor", 0, SECONDS, color={"var": "background"}),
            layer(
                "textBox",
                0,
                SECONDS,
                text={"var": "headline"},
                color={"var": "textcolor"},
                method="caption",
                fontsize=scaled(14),
                textsize=[share(0.9, WIDTH), share(0.3, HEIGHT)],
                position=["center", share(0.08, HEIGHT)],
                fxs={"preserve": [FLY_IN]},
            ),
            layer(
                "textBox",
                1,
                AFTER_THE_FIRST,
                text={"var": "details"},
                color={"var": "textcolor"},
                method="caption",
                fontsize=scaled(32),
                textsize=[share(0.9, WIDTH), share(0.4, HEIGHT)],
                position="center",
                align={"if": [{"==": [{"var": "align"}, "left"]}, "west", "center"]},
            ),
            layer(
                "textBox",
                1,
                AFTER_THE_FIRST,
                text={"var": "fineprint"},
                color={"var": "textcolor"},
                method="caption",
                fontsize=scaled(60),
                textsize=[share(0.9, WIDTH), share(0.15, HEIGHT)],
                position=["center", "bottom"],
                align="west",
            ),
        ]
    },
    # `defaultValue` fills a field once; `value` would be written back over
    # what was typed at every redraw.
    "fields": [
        {
            "type": "Text",
            "attrs": {
                "name": "headline",
                "text": "Headline",
                "defaultValue": "Something new",
            },
        },
        {
            "type": "Textarea",
            "attrs": {
                "name": "details",
                "text": "Details",
                "defaultValue": "What it is, where and when. "
                "A long line wraps to fit the frame.",
            },
        },
        {
            "type": "Selector",
            "attrs": {"name": "align", "text": "Details aligned"},
            "children": ["center", "left"],
        },
        {
            "type": "Textarea",
            "attrs": {
                "name": "fineprint",
                "text": "Fine print",
                "defaultValue": "Terms, dates and a web address go here.",
            },
        },
        {
            "type": "Selector",
            "attrs": {"name": "duration", "text": "Seconds"},
            "children": ["15", "10", "30"],
        },
        {
            "type": "Color",
            "attrs": {
                "name": "background",
                "text": "Background",
                "defaultValue": "#101820",
            },
        },
        {
            "type": "Color",
            "attrs": {"name": "textcolor", "text": "Text", "defaultValue": "#f2f2f2"},
        },
    ],
}

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
