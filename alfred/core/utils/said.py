"""What was said over stretches of a file, from the projects that play it.

An edit that lengthens a clip, slips it, rolls or slides a cut, or adds a
clip shows material of a file that the project's own words and captions do
not cover: they were heard over the timeline as it was. The same file's
material may be covered elsewhere: by the project the draft was cut from,
and the one that was cut from, and by any other project of the owner whose
timeline plays it and holds words. `said` gathers what those sources say
over a stretch of the file, in the file's own seconds, nearest source first:
each second is taken from the first source that plays it, so a word a person
corrected in a draft is the word a later draft of it gets, and a stretch a
nearer source played and heard nothing in stays silent.

Pure: the sources arrive as stored projects (`edl`, `words`, `captions`),
and `routes.captions` reaches the database for them.
"""

from typing import Dict, List, Optional, Sequence, Tuple

from .sound import placed

# The clips that play a file's sound and picture.
MEDIA = ('video', 'audio')
# Times are kept to the millisecond, as the editor keeps them.
MS = 0.001

Span = Tuple[float, float]


def _ms(value: float) -> float:
    return round(float(value), 3)


def _number(value) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _times(item: dict) -> Optional[Span]:
    start, end = _number(item.get('start')), _number(item.get('end'))
    if start is None or end is None or end < start:
        return None
    return start, end


def windows_of(project: dict, name: str) -> List[dict]:
    """The stretches of the project's timeline that play file `name`: each
    `{start, length, inpoint}`, timeline seconds and the file's."""
    return [
        at
        for at in placed((project.get('edl') or {}).get('clips') or [])
        if at['clip'].get('type') in MEDIA
        and at['clip'].get('name') == name
        and at['length'] > 0
    ]


def merged(spans: Sequence[Span]) -> List[Span]:
    out: List[List[float]] = []
    for a, b in sorted(spans):
        if b - a < MS:
            continue
        if out and a <= out[-1][1] + MS:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def intersect(xs: Sequence[Span], ys: Sequence[Span]) -> List[Span]:
    return merged(
        [
            (max(a, c), min(b, d))
            for a, b in xs
            for c, d in ys
            if min(b, d) - max(a, c) >= MS
        ]
    )


def subtract(xs: Sequence[Span], ys: Sequence[Span]) -> List[Span]:
    out = list(merged(xs))
    for c, d in merged(ys):
        nxt = []
        for a, b in out:
            if d <= a or c >= b:
                nxt.append((a, b))
                continue
            if c - a >= MS:
                nxt.append((a, c))
            if b - d >= MS:
                nxt.append((d, b))
        out = nxt
    return out


def _onto_file(item: dict, windows: Sequence[dict]) -> Optional[Tuple[dict, Span]]:
    """`item` in the file's seconds, through the window its middle is in, cut
    to that window: `(item, (start, end))`; None when it is over none."""
    times = _times(item)
    if times is None:
        return None
    start, end = times
    middle = (start + end) / 2
    for at in windows:
        if at['start'] <= middle < at['start'] + at['length'] or (
            start == end == middle
            and at['start'] <= middle <= at['start'] + at['length']
        ):
            lo = max(start, at['start'])
            hi = min(end, at['start'] + at['length'])
            offset = at['inpoint'] - at['start']
            return item, (lo + offset, hi + offset)
    return None


def heard(project: dict, name: str) -> Tuple[List[Span], List[dict], List[dict]]:
    """What `project` plays of file `name` and says over it: the file's
    stretches it plays, and its words and captions there, each moved into the
    file's seconds and cut to the stretch its middle is in."""
    windows = windows_of(project, name)
    plays = merged([(at['inpoint'], at['inpoint'] + at['length']) for at in windows])
    words = []
    for word in project.get('words') or []:
        found = _onto_file(word, windows)
        if found:
            item, (a, b) = found
            words.append({**item, 'start': _ms(a), 'end': _ms(b)})
    captions = []
    for caption in project.get('captions') or []:
        found = _onto_file(caption, windows)
        if found:
            item, (a, b) = found
            captions.append(
                {'start': _ms(a), 'end': _ms(b), 'text': str(item.get('text') or '')}
            )
    words.sort(key=lambda w: (w['start'], w['end']))
    captions.sort(key=lambda c: (c['start'], c['end']))
    return plays, words, captions


def _middle_in(item: dict, a: float, b: float) -> bool:
    middle = (item['start'] + item['end']) / 2
    return a <= middle < b


def _caption_in(
    caption: dict, a: float, b: float, words: Sequence[dict]
) -> Optional[dict]:
    """`caption` within `[a, b]`: whole where it lies in it, else cut to it,
    saying the words said in what is left; None where none are."""
    start, end = caption['start'], caption['end']
    if end <= a or start >= b:
        return None
    if start >= a - MS and end <= b + MS:
        return dict(caption)
    lo, hi = max(start, a), min(end, b)
    text = ' '.join(
        str(w.get('text') or '').strip()
        for w in words
        if _middle_in(w, lo, hi) and str(w.get('text') or '').strip()
    )
    if not text or hi - lo < MS:
        return None
    return {'start': _ms(lo), 'end': _ms(hi), 'text': text}


def said(
    sources: Sequence[dict], name: str, start: float, end: float
) -> Dict[str, list]:
    """The words and captions said over file `name` from `start` to `end`
    seconds, in the file's seconds: each stretch from the first of `sources`
    that plays it. `{words, captions}`, each in the order they are said."""
    remaining = merged([(float(start), float(end))])
    words: List[dict] = []
    captions: List[dict] = []
    for source in sources:
        if not remaining:
            break
        plays, heard_words, heard_captions = heard(source, name)
        taken = intersect(remaining, plays)
        if not taken:
            continue
        for a, b in taken:
            words.extend(w for w in heard_words if _middle_in(w, a, b))
            for caption in heard_captions:
                cut = _caption_in(caption, a, b, heard_words)
                if cut:
                    captions.append(cut)
        remaining = subtract(remaining, taken)
    words.sort(key=lambda w: (w['start'], w['end']))
    captions.sort(key=lambda c: (c['start'], c['end']))
    return {'words': words, 'captions': captions}
