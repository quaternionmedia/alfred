"""The recipes every account starts with.

Each is data as a stored recipe is, owned by nobody and read by every
account, and each is the shape of one thing a person asks of a long
recording. The first values are the advice the round was built on -- clips
of eight to twelve seconds, about twenty-five of them from an evening's
recording -- and hold until they are measured against what people keep and
drop (`docs/drafts.md`).
"""

from typing import List


def knob(name, text, default):
    """A field the editor draws as a line of text, as a form project's."""
    return {
        'type': 'Text',
        'attrs': {'name': name, 'text': text, 'defaultValue': str(default)},
    }


def var(name):
    return {'var': name}


BUILTIN: List[dict] = [
    {
        'name': 'highlights',
        'label': 'Highlights',
        'description': (
            'The stretches where the most is said, and where the talking gets loud '
            'while the picture moves: each a short of its own.'
        ),
        'fields': [
            knob('shortest', 'Shortest clip, seconds', 8),
            knob('longest', 'Longest clip, seconds', 12),
            knob('count', 'How many', 25),
        ],
        'steps': [
            {
                'op': 'windows',
                'shortest': var('shortest'),
                'longest': var('longest'),
                'every': 2,
            },
            {'op': 'dialogue', 'weight': 1},
            {'op': 'spikes', 'weight': 1},
            {'op': 'top', 'count': var('count')},
            {'op': 'compose', 'how': 'each'},
        ],
    },
    {
        'name': 'teaser',
        'label': 'Teaser',
        'description': 'The best stretches, in order, as one short piece of a chosen length.',
        'fields': [
            knob('shortest', 'Shortest stretch, seconds', 8),
            knob('longest', 'Longest stretch, seconds', 12),
            knob('target', 'The teaser, seconds', 60),
        ],
        'steps': [
            {
                'op': 'windows',
                'shortest': var('shortest'),
                'longest': var('longest'),
                'every': 2,
            },
            {'op': 'dialogue', 'weight': 1},
            {'op': 'spikes', 'weight': 1},
            {'op': 'top', 'count': 500},
            {'op': 'compose', 'how': 'together', 'target': var('target')},
        ],
    },
    {
        'name': 'chapters',
        'label': 'Chapters',
        'description': 'One draft for each stretch between long pauses.',
        'fields': [knob('pause', 'A pause this long ends a chapter, seconds', 4)],
        'steps': [
            {'op': 'chapters', 'pause': var('pause')},
            {'op': 'compose', 'how': 'each'},
        ],
    },
    {
        'name': 'excerpts',
        'label': 'Excerpts',
        'description': (
            'Stretches cut at pauses and at the ends of sentences, as the excerpt '
            'flow proposes them, each a draft of its own.'
        ),
        'fields': [
            knob('pause', 'A pause this long ends a stretch, seconds', 1),
            knob('shortest', 'Shortest excerpt, seconds', 10),
            knob('longest', 'Longest excerpt, seconds', 90),
        ],
        'steps': [
            {
                'op': 'spans',
                'pause': var('pause'),
                'shortest': var('shortest'),
                'longest': var('longest'),
            },
            {'op': 'compose', 'how': 'each'},
        ],
    },
    {
        'name': 'tight-cut',
        'label': 'Tight cut',
        'description': 'The whole source, its long pauses shortened and its filler words dropped.',
        'fields': [
            knob('longer_than', 'A pause longer than this is cut, seconds', 1.5),
            knob('to', 'What is left of it, seconds', 0.5),
            knob(
                'fillers',
                'The words to drop, separated by commas',
                'um, uh, er, ah, erm, hmm',
            ),
        ],
        'steps': [
            {'op': 'fillers', 'words': var('fillers')},
            {'op': 'tighten', 'longer_than': var('longer_than'), 'to': var('to')},
            {'op': 'compose', 'how': 'whole'},
        ],
    },
    {
        'name': 'quotes',
        'label': 'Quotes',
        'description': (
            'Each sentence that stands on its own as a tall short with its words drawn in.'
        ),
        'fields': [
            knob('shortest', 'Shortest quote, seconds', 3),
            knob('longest', 'Longest quote, seconds', 20),
            knob('count', 'How many', 25),
        ],
        'steps': [
            {'op': 'sentences'},
            {'op': 'keep', 'shortest': var('shortest'), 'longest': var('longest')},
            {'op': 'dialogue', 'weight': 1},
            {'op': 'top', 'count': var('count')},
            {'op': 'compose', 'how': 'each'},
            {'op': 'render', 'width': 1080, 'height': 1920, 'captions': True},
        ],
    },
]

BY_NAME = {recipe['name']: recipe for recipe in BUILTIN}
