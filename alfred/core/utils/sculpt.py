"""Running a recipe over a source: the arithmetic behind the drafts.

A `Source` is what a long project gives the recipe: its clips, its captions,
its words, and what the engines measured of its timeline, the level over
time and the motion over time (`routes.sound`, `routes.motion`), all in
timeline seconds. `run` takes the recipe's steps, the values a person set
for its fields, and the source, and leaves `Draft`s: each a timeline cut
from the source by `utils.cut`, with its captions and its words moved into
it, the spans of the source it took, and the scores it was chosen by.

The steps run in order over one state: the candidates (stretches of the
source a *segment* step found, each with the scores the *score* steps
gave it, thinned by the *filter* steps), the ranges the *edit* steps cut
out of whatever is kept, and how the *compose* steps make the drafts. The
operations and their parameters are `models.recipes.OPERATIONS`; the
arithmetic of each is here, in a function named for it.

Nothing here reaches the database, an engine or a model: what the language
engine read over the source, its topics over time, arrives in the `Source`,
and `label` titles each candidate by the topic live over it; a labeller, for
a category, is a later step, and `label` leaves a note where there is none.
"""

import math
import re
from bisect import bisect_left
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from ..models.recipes import OPERATIONS, RecipeError, coerce, is_reference
from .cut import cut_ranges, timeline_end, to_ms

# What ends a sentence, once closing quotes and brackets are set aside.
_SENTENCE_END = re.compile(r'[.!?…]["\')\]”’»]*$')
# What is not part of a word when a filler is looked for.
_PUNCTUATION = re.compile(r'^[^\w]+|[^\w]+$')


@dataclass
class Source:
    """A long project as a recipe reads it, every time in timeline seconds."""

    clips: list
    captions: list = field(default_factory=list)
    words: list = field(default_factory=list)
    # `{rate, values}`, the timeline's level over time, 0 to 1; None unheard.
    levels: Optional[dict] = None
    # `{rate, values}`, the picture's motion over time, 0 to 1; None unmeasured.
    motion: Optional[dict] = None
    # `[{start, end}]`, the timeline's silences.
    silences: list = field(default_factory=list)
    # `[{name, points: [{time, intensity}]}]`, the topics the language engine
    # read over the source's words, strongest first; empty where it read none.
    topics: list = field(default_factory=list)
    # Why the engine read nothing, where it did not; None where it did.
    unread: Optional[str] = None

    @property
    def duration(self) -> float:
        return timeline_end(self.clips)

    @property
    def timeline(self) -> dict:
        return {'clips': self.clips, 'captions': self.captions, 'words': self.words}


@dataclass
class Candidate:
    """A stretch of the source a recipe may keep."""

    start: float
    end: float
    scores: Dict[str, float] = field(default_factory=dict)
    chapter: Optional[int] = None
    title: str = ''

    @property
    def length(self) -> float:
        return to_ms(self.end - self.start)

    def total(self, weights: Dict[str, float]) -> float:
        return sum(
            weights.get(name, 1.0) * value for name, value in self.scores.items()
        )


@dataclass
class Draft:
    """What a recipe leaves: a timeline of its own, cut from the source."""

    # Numbered from 1 in timeline order, as the draft's name ends.
    number: int
    description: str
    # The spans of the source it took, each `[start, end]`.
    spans: List[List[float]]
    # `{clips, duration, captions, words}`.
    timeline: dict
    scores: Dict[str, float]
    render_settings: Optional[dict] = None
    captions_drawn: bool = False
    # What it is about, where a `label` step found a topic live over it.
    title: str = ''


@dataclass
class Run:
    drafts: List[Draft]
    # What the run has to say: a step skipped, nothing found.
    notes: List[str]
    # How many candidates the steps left.
    candidates: int


# --- reading the words -----------------------------------------------------------


def _time(value) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def spoken(items: Sequence[dict]) -> List[dict]:
    """The words or captions that say something, each with numeric times, in
    the order they start."""
    kept = []
    for item in items or []:
        start, end = _time(item.get('start')), _time(item.get('end'))
        text = str(item.get('text') or '').strip()
        if start is None or end is None or end < start or not text:
            continue
        kept.append({**item, 'start': start, 'end': end, 'text': text})
    return sorted(kept, key=lambda i: (i['start'], i['end']))


def ends_sentence(text: str) -> bool:
    return bool(_SENTENCE_END.search(text.rstrip()))


def timecode(seconds: float) -> str:
    whole = int(max(0, seconds))
    h, rest = divmod(whole, 3600)
    mn, s = divmod(rest, 60)
    return f'{h}:{mn:02d}:{s:02d}' if h else f'{mn}:{s:02d}'


def words_in(words: Sequence[dict], start: float, end: float) -> List[dict]:
    """The words whose middle lies in `[start, end]`; `words` are `spoken`."""
    return [w for w in words if start <= (w['start'] + w['end']) / 2 <= end]


# --- segment -------------------------------------------------------------------


def windows(
    words: Sequence[dict], shortest: float, longest: float, every: float
) -> List[Candidate]:
    """Candidate windows along the source: from each word's start, every
    `every` seconds or so, to the end of a word between `shortest` and
    `longest` later, the last sentence's end in that range preferred, else
    the last word's end. A start with no word's end in range makes none."""
    if shortest > longest:
        raise RecipeError(
            f'windows: shortest ({shortest:g}) is longer than longest ({longest:g})'
        )
    starts = [w['start'] for w in words]
    found: List[Candidate] = []
    if not words:
        return found
    t = words[0]['start']
    last = words[-1]['end']
    seen = set()
    while t <= last - shortest:
        i = bisect_left(starts, t)
        if i >= len(words):
            break
        s = words[i]['start']
        lo, hi = s + shortest, s + longest
        in_range = [w for w in words[i:] if lo <= w['end'] <= hi]
        if in_range:
            sentence_ends = [w for w in in_range if ends_sentence(w['text'])]
            e = (sentence_ends or in_range)[-1]['end']
            key = (to_ms(s), to_ms(e))
            if key not in seen:
                seen.add(key)
                found.append(Candidate(start=key[0], end=key[1]))
        t = s + every
    return found


def chapters(words: Sequence[dict], pause: float) -> List[Candidate]:
    """The stretches between pauses of `pause` seconds or more, numbered."""
    found: List[Candidate] = []
    for word in words:
        if found and word['start'] - found[-1].end < pause:
            found[-1].end = max(found[-1].end, word['end'])
        else:
            found.append(
                Candidate(start=word['start'], end=word['end'], chapter=len(found) + 1)
            )
    for c in found:
        c.start, c.end = to_ms(c.start), to_ms(c.end)
    return found


def sentences(captions: Sequence[dict]) -> List[Candidate]:
    """Each sentence of the transcript: captions joined until one ends a
    sentence."""
    found: List[Candidate] = []
    open_one: Optional[Candidate] = None
    for caption in captions:
        if open_one is None:
            open_one = Candidate(start=caption['start'], end=caption['end'])
        else:
            open_one.end = max(open_one.end, caption['end'])
        if ends_sentence(caption['text']):
            found.append(open_one)
            open_one = None
    if open_one is not None:
        found.append(open_one)
    for c in found:
        c.start, c.end = to_ms(c.start), to_ms(c.end)
    return found


def _stretches(captions: Sequence[dict], gap: float) -> List[List[dict]]:
    runs: List[List[dict]] = []
    for caption in captions:
        if runs and caption['start'] - runs[-1][-1]['end'] < gap:
            runs[-1].append(caption)
        else:
            runs.append([caption])
    return runs


def _length(run: Sequence[dict]) -> float:
    return run[-1]['end'] - run[0]['start']


def _pieces(stretch: Sequence[dict], longest: float) -> List[List[dict]]:
    cut: List[List[dict]] = []
    i = 0
    while i < len(stretch):
        start = stretch[i]['start']
        last_fit, last_sentence = i, None
        j = i
        while j < len(stretch) and stretch[j]['end'] - start <= longest:
            last_fit = j
            if ends_sentence(stretch[j]['text']):
                last_sentence = j
            j += 1
        end = last_fit if last_sentence is None else last_sentence
        cut.append(list(stretch[i : end + 1]))
        i = end + 1
    return cut


def _joined(pieces: Sequence[Sequence[dict]], shortest: float, longest: float):
    kept: List[List[dict]] = []
    left_out = 0
    pending: List[dict] = []
    for piece in pieces:
        piece = pending + list(piece)
        pending = []
        if _length(piece) >= shortest:
            kept.append(piece)
        elif kept and _length(kept[-1] + piece) <= longest:
            kept[-1] = kept[-1] + piece
        else:
            pending = piece
    if pending:
        left_out += 1
    return kept, left_out


def spans(
    captions: Sequence[dict],
    pause: float,
    chapter_pause: float,
    shortest: float,
    longest: float,
) -> List[Candidate]:
    """Stretches cut at pauses and at the ends of sentences, between
    `shortest` and `longest` seconds, each in its chapter: the excerpt
    flow's proposal (qmcp's `alfred_excerpts.propose`), over the captions."""
    if not 0 < shortest <= longest:
        raise RecipeError(
            f'spans: shortest ({shortest:g}) must be at most longest ({longest:g})'
        )
    if not 0 < pause <= chapter_pause:
        raise RecipeError(
            f'spans: pause ({pause:g}) must be at most chapter_pause ({chapter_pause:g})'
        )
    found: List[Candidate] = []
    for number, part in enumerate(_stretches(captions, chapter_pause), start=1):
        for stretch in _stretches(part, pause):
            kept, _ = _joined(_pieces(stretch, longest), shortest, longest)
            for run in kept:
                found.append(
                    Candidate(
                        start=to_ms(run[0]['start']),
                        end=to_ms(run[-1]['end']),
                        chapter=number,
                    )
                )
    return found


def silences(quiet: Sequence[dict], longer_than: float) -> List[Candidate]:
    """The silences longer than `longer_than` seconds."""
    found = []
    for s in quiet or []:
        start, end = _time(s.get('start')), _time(s.get('end'))
        if start is not None and end is not None and end - start > longer_than:
            found.append(Candidate(start=to_ms(start), end=to_ms(end)))
    return found


# --- score ---------------------------------------------------------------------


def normalised(
    candidates: Sequence[Candidate], name: str, raw: Sequence[float]
) -> None:
    """Write `raw` onto the candidates as `name`, scaled so the highest is 1."""
    top = max(raw, default=0.0)
    for candidate, value in zip(candidates, raw, strict=True):
        candidate.scores[name] = round(value / top, 4) if top > 0 else 0.0


def dialogue(candidates: Sequence[Candidate], words: Sequence[dict]) -> None:
    """How much is said in each candidate: words a second over its whole
    length, so a stretch with a break in it scores by what is said around
    the break. Scaled so the most talkative candidate is 1."""
    raw = [
        len(words_in(words, c.start, c.end)) / c.length if c.length > 0 else 0.0
        for c in candidates
    ]
    normalised(candidates, 'dialogue', raw)


def _per_second(series: Optional[dict], duration: float) -> List[float]:
    """A `{rate, values}` series as one value a second, the highest in each."""
    if not series:
        return []
    rate = series.get('rate') or 0
    values = series.get('values') or []
    if not rate or not values:
        return []
    seconds = (
        int(math.ceil(duration)) if duration > 0 else int(math.ceil(len(values) / rate))
    )
    out = []
    for s in range(seconds):
        lo, hi = int(math.floor(s * rate)), int(math.ceil((s + 1) * rate))
        slice_ = values[lo:hi]
        out.append(max((float(v) for v in slice_), default=0.0))
    return out


def _usual(values: Sequence[float]) -> float:
    """The baseline of a series: the mean of what is above 0."""
    heard = [v for v in values if v > 0]
    return sum(heard) / len(heard) if heard else 0.0


def spike_seconds(
    source: Source, level_above: float, motion_above: float, where_words: bool
) -> List[int]:
    """The seconds of the source where the level is above `level_above`
    times its usual and the picture moves above `motion_above` times its
    usual, at once; with `where_words`, only seconds in which a word is
    said. Each usual is a baseline over the whole source."""
    duration = source.duration
    level = _per_second(source.levels, duration)
    motion = _per_second(source.motion, duration)
    if not level or not motion:
        return []
    usual_level, usual_motion = _usual(level), _usual(motion)
    said = set()
    if where_words:
        for w in spoken(source.words):
            for s in range(int(math.floor(w['start'])), int(math.ceil(w['end'])) + 1):
                said.add(s)
    found = []
    for s in range(min(len(level), len(motion))):
        if where_words and s not in said:
            continue
        if (
            level[s] > level_above * usual_level
            and motion[s] > motion_above * usual_motion
        ):
            found.append(s)
    return found


def spikes(
    candidates: Sequence[Candidate],
    source: Source,
    level_above: float,
    motion_above: float,
    where_words: bool,
) -> Optional[str]:
    """Each candidate's share of seconds with a spike in them, scaled so the
    spikiest is 1. Returns a note when the source lacks a measure, and
    scores nothing then."""
    if not source.levels or not (source.levels.get('values') or []):
        return 'spikes: the source has no level over time, so it was not scored'
    if not source.motion or not (source.motion.get('values') or []):
        return 'spikes: the source has no motion over time, so it was not scored'
    seconds = spike_seconds(source, level_above, motion_above, where_words)
    raw = []
    for c in candidates:
        inside = sum(1 for s in seconds if c.start <= s < c.end)
        raw.append(inside / c.length if c.length > 0 else 0.0)
    normalised(candidates, 'spikes', raw)
    return None


# --- filter ----------------------------------------------------------------------


def top(
    candidates: Sequence[Candidate], weights: Dict[str, float], count: int
) -> List[Candidate]:
    """The `count` highest-scored candidates that do not overlap, in timeline
    order. A candidate with no scores counts as 0, so without a score step
    the first in time are kept."""
    ranked = sorted(
        enumerate(candidates),
        key=lambda pair: (-pair[1].total(weights), pair[1].start, pair[0]),
    )
    kept: List[Candidate] = []
    for _, candidate in ranked:
        if len(kept) >= count:
            break
        if any(candidate.start < k.end and k.start < candidate.end for k in kept):
            continue
        kept.append(candidate)
    return sorted(kept, key=lambda c: c.start)


def keep(
    candidates: Sequence[Candidate], shortest: float, longest: float
) -> List[Candidate]:
    return [c for c in candidates if shortest <= c.length <= longest]


def filler_ranges(words: Sequence[dict], fillers: Sequence[str]) -> List[List[float]]:
    """The stretches each filler word is said in."""
    wanted = {f.strip().lower() for f in fillers if f.strip()}
    out = []
    for w in words:
        bare = _PUNCTUATION.sub('', w['text']).lower()
        if bare in wanted and w['end'] > w['start']:
            out.append([w['start'], w['end']])
    return out


# --- edit ------------------------------------------------------------------------


def tighten_ranges(
    words: Sequence[dict], longer_than: float, to: float
) -> List[List[float]]:
    """Every pause between words longer than `longer_than` seconds, less the
    `to` seconds of it that are kept."""
    out = []
    for before, after in zip(words, words[1:], strict=False):
        gap = after['start'] - before['end']
        if gap > longer_than:
            out.append([to_ms(before['end'] + to), to_ms(after['start'])])
    return out


# --- compose ---------------------------------------------------------------------


def _complement(
    spans_: Sequence[Sequence[float]], duration: float
) -> List[List[float]]:
    """What of `[0, duration]` the sorted, non-overlapping `spans_` leave out."""
    out = []
    at = 0.0
    for start, end in spans_:
        if start > at:
            out.append([at, start])
        at = max(at, end)
    if at < duration:
        out.append([at, duration])
    return out


# The longest a title is: a topic is a word or a few.
MAX_TITLE_CHARS = 60


def live_topic(topics: Sequence[dict], start: float, end: float) -> str:
    """The topic with the most intensity of points within `[start, end]`, the
    first of two that tie; '' where no topic has a point there."""
    best, most = '', 0.0
    for topic in topics or []:
        weight = 0.0
        for point in topic.get('points') or []:
            when = _time(point.get('time'))
            if when is not None and start <= when <= end:
                intensity = _time(point.get('intensity'))
                weight += 1.0 if intensity is None else intensity
        if weight > most:
            best, most = ' '.join(str(topic.get('name') or '').split()), weight
    return best[:MAX_TITLE_CHARS]


def titles(candidates: Sequence[Candidate], topics: Sequence[dict]) -> None:
    """Each candidate titled by the topic live over it, where one is."""
    for c in candidates:
        found = live_topic(topics, c.start, c.end)
        if found:
            c.title = found


def _describe(candidate: Candidate, weights: Dict[str, float]) -> str:
    where = f'{timecode(candidate.start)}-{timecode(candidate.end)} of the source'
    parts = [where]
    if candidate.chapter is not None:
        parts.append(f'chapter {candidate.chapter}')
    if candidate.title:
        parts.append(candidate.title)
    if candidate.scores:
        parts.append(
            'scored '
            + ', '.join(
                f'{name} {value:.2f}'
                for name, value in sorted(candidate.scores.items())
            )
        )
    return '; '.join(parts)


def make_draft(
    source: Source,
    spans_: Sequence[Sequence[float]],
    edits: Sequence[Sequence[float]],
    number: int,
    description: str,
    scores: Dict[str, float],
) -> Optional[Draft]:
    """A draft from the source: everything outside `spans_` cut, and `edits`
    cut with it. None when nothing of the timeline is left."""
    duration = source.duration
    ranges = _complement(sorted(spans_), duration) + [list(r) for r in edits]
    cut = cut_ranges(source.timeline, ranges)
    if not cut['clips']:
        return None
    timeline = {
        'clips': cut['clips'],
        'duration': timeline_end(cut['clips']),
        'captions': cut['captions'],
        'words': cut['words'],
    }
    return Draft(
        number=number,
        description=description,
        spans=[[to_ms(a), to_ms(b)] for a, b in sorted(spans_)],
        timeline=timeline,
        scores=dict(scores),
    )


# --- running -----------------------------------------------------------------------


@dataclass
class State:
    candidates: List[Candidate] = field(default_factory=list)
    weights: Dict[str, float] = field(default_factory=dict)
    edits: List[List[float]] = field(default_factory=list)
    how: str = 'each'
    target: float = 0.0
    render_settings: Optional[dict] = None
    captions_drawn: bool = False
    notes: List[str] = field(default_factory=list)


def resolve(step: dict, values: dict, fields: Sequence[dict]) -> dict:
    """A step's parameters as it runs: each from the step, a field it reads
    (`{"var": name}`, from `values`, else the field's `defaultValue`), or the
    operation's default; every one coerced and checked."""
    op = step['op']
    parameters = OPERATIONS[op]['parameters']
    defaults = {}
    for f in fields or []:
        attrs = f.get('attrs') if isinstance(f, dict) else None
        if isinstance(attrs, dict) and isinstance(attrs.get('name'), str):
            defaults[attrs['name']] = attrs.get('defaultValue')
    out = {}
    for name, parameter in parameters.items():
        where = f'{op}: {name}'
        if name not in step:
            out[name] = parameter.default
            continue
        value = step[name]
        if is_reference(value):
            key = value['var']
            value = (
                values.get(key)
                if values and values.get(key) not in (None, '')
                else defaults.get(key)
            )
            if value in (None, ''):
                value = parameter.default
        out[name] = coerce(parameter, value, where)
    return out


def apply(
    step_name: str, p: dict, state: State, source: Source, words: list, captions: list
):
    """One step over the state."""
    if step_name == 'windows':
        state.candidates = windows(words, p['shortest'], p['longest'], p['every'])
    elif step_name == 'chapters':
        state.candidates = chapters(words, p['pause'])
    elif step_name == 'sentences':
        state.candidates = sentences(captions)
    elif step_name == 'spans':
        state.candidates = spans(
            captions, p['pause'], p['chapter_pause'], p['shortest'], p['longest']
        )
    elif step_name == 'silences':
        state.candidates = silences(source.silences, p['longer_than'])
    elif step_name == 'dialogue':
        dialogue(state.candidates, words)
        state.weights['dialogue'] = p['weight']
    elif step_name == 'spikes':
        note = spikes(
            state.candidates,
            source,
            p['level_above'],
            p['motion_above'],
            p['where_words'],
        )
        state.weights['spikes'] = p['weight']
        if note:
            state.notes.append(note)
    elif step_name == 'label':
        if p['title']:
            if source.topics:
                titles(state.candidates, source.topics)
            else:
                state.notes.append(
                    'label: nothing was titled: '
                    + (source.unread or 'no topic was read over the source')
                )
        if p['categories']:
            state.notes.append(
                'label: no labeller is configured, so no category was given'
            )
    elif step_name == 'top':
        count = p['count']
        if p['per_hour'] > 0:
            count = max(1, int(math.ceil(p['per_hour'] * source.duration / 3600.0)))
        state.candidates = top(state.candidates, state.weights, count)
    elif step_name == 'keep':
        state.candidates = keep(state.candidates, p['shortest'], p['longest'])
    elif step_name == 'fillers':
        state.edits.extend(filler_ranges(words, p['words'].split(',')))
    elif step_name == 'tighten':
        state.edits.extend(tighten_ranges(words, p['longer_than'], p['to']))
    elif step_name == 'excerpt':
        state.how = 'each'
    elif step_name == 'compose':
        state.how = p['how']
        state.target = p['target']
    elif step_name == 'render':
        state.render_settings = {'width': p['width'], 'height': p['height']}
        state.captions_drawn = p['captions']
    else:  # pragma: no cover - the registry and this list are one
        raise RecipeError(f'{step_name}: no arithmetic for this operation')


def compose(state: State, source: Source) -> List[Draft]:
    """The drafts the state describes."""
    drafts: List[Draft] = []
    kept = sorted(state.candidates, key=lambda c: c.start)
    if state.how == 'whole':
        draft = make_draft(
            source, [[0.0, source.duration]], state.edits, 1, 'the whole source', {}
        )
        return [draft] if draft else []
    if state.how == 'together':
        chosen = kept
        if state.target > 0:
            ranked = sorted(kept, key=lambda c: (-c.total(state.weights), c.start))
            chosen, total = [], 0.0
            for c in ranked:
                if total + c.length > state.target and chosen:
                    continue
                chosen.append(c)
                total += c.length
            chosen.sort(key=lambda c: c.start)
        if not chosen:
            return []
        scores: Dict[str, float] = {}
        for c in chosen:
            for name, value in c.scores.items():
                scores[name] = round(scores.get(name, 0.0) + value / len(chosen), 4)
        description = f'{len(chosen)} stretches of the source, in order'
        draft = make_draft(
            source,
            [[c.start, c.end] for c in chosen],
            state.edits,
            1,
            description,
            scores,
        )
        return [draft] if draft else []
    for number, c in enumerate(kept, start=1):
        draft = make_draft(
            source,
            [[c.start, c.end]],
            state.edits,
            number,
            _describe(c, state.weights),
            c.scores,
        )
        if draft:
            draft.title = c.title
            drafts.append(draft)
    return drafts


def run(
    steps: Sequence[dict],
    values: Optional[dict],
    fields: Sequence[dict],
    source: Source,
) -> Run:
    """The recipe's `steps`, with `values` for its `fields`, over `source`."""
    state = State()
    words = spoken(source.words)
    captions = spoken(source.captions)
    for step in steps:
        p = resolve(step, values or {}, fields)
        apply(step['op'], p, state, source, words, captions)
    if not state.candidates and state.how != 'whole':
        state.notes.append('no stretch of the source was found to keep')
    drafts = compose(state, source)
    for draft in drafts:
        draft.render_settings = (
            dict(state.render_settings) if state.render_settings else None
        )
        draft.captions_drawn = state.captions_drawn
    return Run(drafts=drafts, notes=state.notes, candidates=len(state.candidates))
