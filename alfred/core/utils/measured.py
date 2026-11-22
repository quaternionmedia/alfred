"""What the recipes' runs left, and what became of it: the measure a
recipe's first values are held against.

A recipe's defaults are a guess until real recordings have been cut by them
and people have kept, dropped, edited and rendered what came out. This reads
that signal from the projects: each source's drafts as they stand, what the
source keeps of the drafts dropped from it (`drafts_dropped`), and the
renders made from a draft. Nothing here changes anything; `scripts/measured.py`
prints the report, and `./al measured` runs it over the host run's database.

What is counted, per source and per recipe:

- `made`: drafts the runs left, held and dropped together;
- `held`: drafts still there; `dropped`: remembered on the source;
- `edited`: held drafts whose timeline is no longer the length the recipe
  cut (`made_duration`), by more than a frame or so, so what a recipe's own
  edits took out is not counted as a person's;
- `rendered`: held drafts with a render;
- the lengths, in seconds: the mean length as made, as held now, and as
  rendered, so a default that is always trimmed shows.
"""

from statistics import mean
from typing import Any, Dict, Iterable, List, Optional

# A held draft shorter or longer than it was made by more than this, in
# seconds, counts as edited: a frame at the slowest rate the editor shows.
EDITED_BEYOND = 0.05


def _time(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def span_seconds(spans: Iterable) -> float:
    """How long the spans a draft took run, together."""
    total = 0.0
    for span in spans or []:
        if isinstance(span, (list, tuple)) and len(span) == 2:
            start, end = _time(span[0]), _time(span[1])
            if start is not None and end is not None and end > start:
                total += end - start
    return round(total, 3)


def made_length(provenance: dict) -> float:
    """How long a draft was as the recipe cut it: its `made_duration`, or,
    where it carries none, how long its spans run together."""
    length = _time(provenance.get('made_duration'))
    return (
        round(length, 3)
        if length is not None
        else span_seconds(provenance.get('spans'))
    )


def _mean(values: List[float]) -> Optional[float]:
    return round(mean(values), 2) if values else None


def report(projects: Iterable[dict], renders: Iterable[dict] = ()) -> Dict[str, Any]:
    """The measure over `projects` (every project, sources and drafts among
    them) and `renders` (every render, each with its `project_id`), as
    `{sources: {<source id>: {name, recipes: {<recipe>: {...}}}}, totals}`."""
    projects = list(projects)
    rendered_of: Dict[str, List[dict]] = {}
    for render in renders:
        project_id = render.get('project_id')
        if project_id is not None:
            rendered_of.setdefault(str(project_id), []).append(render)
    by_id = {str(p.get('_id')): p for p in projects}
    sources: Dict[str, dict] = {}

    def recipe_of(source_id: str, recipe: str) -> dict:
        source = sources.setdefault(
            source_id,
            {'name': (by_id.get(source_id) or {}).get('name'), 'recipes': {}},
        )
        return source['recipes'].setdefault(
            recipe,
            {
                'made': 0,
                'held': 0,
                'dropped': 0,
                'edited': 0,
                'rendered': 0,
                '_made': [],
                '_held': [],
                '_rendered': [],
            },
        )

    for project in projects:
        source = project.get('source')
        if not isinstance(source, dict) or not source.get('project'):
            continue
        tally = recipe_of(str(source['project']), str(source.get('recipe') or '?'))
        made = made_length(source)
        now = _time((project.get('edl') or {}).get('duration'))
        tally['made'] += 1
        tally['held'] += 1
        tally['_made'].append(made)
        if now is not None:
            tally['_held'].append(now)
            if round(abs(now - made), 3) > EDITED_BEYOND:
                tally['edited'] += 1
        renders_of_it = rendered_of.get(str(project.get('_id')), [])
        if renders_of_it:
            tally['rendered'] += 1
            lengths = [_time(r.get('duration')) for r in renders_of_it]
            lengths = [length for length in lengths if length is not None]
            if lengths:
                tally['_rendered'].append(lengths[-1])
    for project in projects:
        for dropped in project.get('drafts_dropped') or []:
            if not isinstance(dropped, dict):
                continue
            tally = recipe_of(
                str(project.get('_id')), str(dropped.get('recipe') or '?')
            )
            tally['made'] += 1
            tally['dropped'] += 1
            tally['_made'].append(made_length(dropped))
    totals = {'made': 0, 'held': 0, 'dropped': 0, 'edited': 0, 'rendered': 0}
    for source in sources.values():
        for tally in source['recipes'].values():
            tally['length'] = {
                'made': _mean(tally.pop('_made')),
                'held': _mean(tally.pop('_held')),
                'rendered': _mean(tally.pop('_rendered')),
            }
            for key in totals:
                totals[key] += tally[key]
    return {'sources': sources, 'totals': totals}


def lines(measured: Dict[str, Any]) -> List[str]:
    """The report as lines a person reads: one per source and recipe, and the
    totals. A source is named by its id alone, so the lines carry no project's name."""
    out = []
    for source_id, source in sorted(measured['sources'].items()):
        for recipe, tally in sorted(source['recipes'].items()):
            length = tally['length']
            said = ', '.join(
                f'{what} {value:g} s'
                for what, value in (
                    ('made', length['made']),
                    ('held', length['held']),
                    ('rendered', length['rendered']),
                )
                if value is not None
            )
            out.append(
                f'{source_id} {recipe}: made {tally["made"]}, held {tally["held"]}, '
                f'dropped {tally["dropped"]}, edited {tally["edited"]}, '
                f'rendered {tally["rendered"]}; mean length {said or "unknown"}'
            )
    totals = measured['totals']
    out.append(
        f'in all: made {totals["made"]}, held {totals["held"]}, dropped '
        f'{totals["dropped"]}, edited {totals["edited"]}, rendered {totals["rendered"]}'
    )
    return out
