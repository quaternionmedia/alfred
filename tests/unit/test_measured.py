"""The measure of what the recipes' runs left (`alfred/core/utils/measured.py`),
over projects and renders as dicts: no database."""

from alfred.core.utils import measured
from alfred.core.utils.measured import lines, report, span_seconds

SOURCE = 'aaaaaaaaaaaaaaaaaaaaaaaa'


def draft(number, spans, duration, recipe='highlights'):
    return {
        '_id': f'd{number:023d}',
        'name': f'the show – Highlights {number}',
        'edl': {'duration': duration},
        'source': {'project': SOURCE, 'recipe': recipe, 'spans': spans, 'scores': {}},
    }


def test_spans_add_up_and_a_bad_span_counts_nothing():
    assert span_seconds([[10, 19.5], [30, 39]]) == 18.5
    assert span_seconds([[10, 5], ['x', 2], [1]]) == 0
    assert span_seconds(None) == 0


def test_held_dropped_edited_and_rendered_are_counted_per_source_and_recipe():
    """Mutation: count a dropped draft as held, or an edited one as not -- red."""
    projects = [
        {
            '_id': SOURCE,
            'name': 'the show',
            'drafts_dropped': [
                {
                    'id': 'gone',
                    'recipe': 'highlights',
                    'spans': [[0, 8]],
                    'duration': 8,
                },
            ],
        },
        draft(1, [[10, 19.5]], 9.5),
        draft(2, [[30, 39]], 7.0),
        draft(3, [[50, 60]], 10.0, recipe='chapters'),
        {'_id': 'plain', 'name': 'not a draft', 'edl': {'duration': 3}},
    ]
    renders = [{'project_id': draft(1, [], 0)['_id'], 'duration': 9.0}]
    found = report(projects, renders)
    assert set(found['sources']) == {SOURCE}
    highlights = found['sources'][SOURCE]['recipes']['highlights']
    assert highlights == {
        'made': 3,
        'held': 2,
        'dropped': 1,
        'edited': 1,
        'rendered': 1,
        'length': {'made': 8.83, 'held': 8.25, 'rendered': 9.0},
    }
    chapters = found['sources'][SOURCE]['recipes']['chapters']
    assert (chapters['made'], chapters['held'], chapters['edited']) == (1, 1, 0)
    assert found['totals'] == {
        'made': 4,
        'held': 3,
        'dropped': 1,
        'edited': 1,
        'rendered': 1,
    }


def test_a_difference_within_a_frame_is_not_an_edit():
    found = report([draft(1, [[0, 10]], 10.0 + measured.EDITED_BEYOND)])
    assert found['sources'][SOURCE]['recipes']['highlights']['edited'] == 0


def test_the_lines_name_a_source_by_its_id_alone():
    """Mutation: print the source's name -- red; the figures travel to a page."""
    projects = [{'_id': SOURCE, 'name': 'the show'}, draft(1, [[0, 10]], 10.0)]
    said = lines(report(projects))
    assert said == [
        f'{SOURCE} highlights: made 1, held 1, dropped 0, edited 0, rendered 0; '
        'mean length made 10 s, held 10 s',
        'in all: made 1, held 1, dropped 0, edited 0, rendered 0',
    ]
    assert 'the show' not in ''.join(said)


def test_no_drafts_is_an_empty_report():
    assert report([{'_id': 'p', 'name': 'x'}]) == {
        'sources': {},
        'totals': {'made': 0, 'held': 0, 'dropped': 0, 'edited': 0, 'rendered': 0},
    }
