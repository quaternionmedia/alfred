"""Who spoke, by the sound: the audio engine's speaker turns moved onto a
project's timeline, and the words nobody has named given a letter by them.

The engine (`audio_engine.SPEAKERS`, through vox's `speakers` feature) hears
one file at a time and letters the voices it tells apart, A, B and on, in
the order first heard, knowing whose none of them is. `turns_on` moves each
file's turns onto the timeline through the clips' windows, as the sound and
the motion are moved (`sound.levels`); `named` gives each word that carries
no speaker the letter of the turn its middle falls in. A word a person has
named keeps the name, and a word heard in no turn stays unnamed. Nothing
here reaches the engine or the database: `routes.captions` does, and the
Transcript panel offers it.
"""

from bisect import bisect_right
from collections.abc import Callable, Sequence
from typing import Dict, List, Optional, Tuple

from . import sound


def _time(value) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def turns_on(
    at: Sequence[dict], turns_of: Callable[[str], Optional[list]]
) -> List[dict]:
    """The engine's turns of each sounding file moved onto the timeline: each
    `{start, end, speaker}` in timeline seconds, held to the clip's window.
    `at` is the timeline as `sound.placed` lays it; `turns_of(name)` is a
    file's turns in its own seconds, or None for a file not heard. Each file's
    voices are lettered on their own, so where the timeline hears more than
    one file a letter is prefixed with the file's number, A of the second
    file reading `2A`: the same letter in two files may be two people."""
    files = list(
        dict.fromkeys(
            str(a['clip'].get('name')) for a in at if sound.sounding(a['clip'])
        )
    )
    prefix = len(files) > 1
    found: List[dict] = []
    for a in at:
        clip = a['clip']
        if not sound.sounding(clip):
            continue
        measured = turns_of(str(clip.get('name')))
        if not measured:
            continue
        number = files.index(str(clip.get('name'))) + 1
        start, length, inpoint = a['start'], a['length'], a['inpoint']
        for turn in measured:
            first, last = _time(turn.get('start')), _time(turn.get('end'))
            if first is None or last is None:
                continue
            low, high = max(first - inpoint, 0.0), min(last - inpoint, length)
            if high <= low:
                continue
            letter = ' '.join(str(turn.get('speaker') or '?').split())
            found.append(
                {
                    'start': round(start + low, 3),
                    'end': round(start + high, 3),
                    'speaker': f'{number}{letter}' if prefix else letter,
                }
            )
    return sorted(found, key=lambda t: (t['start'], t['end']))


def named(words: Sequence[dict], turns: Sequence[dict]) -> Tuple[List[dict], int]:
    """`words` with each word that carries no speaker given the letter of the
    turn its middle falls in; the words a person named, and the words heard
    in no turn, as they were. Returns the words and how many were named."""
    ordered = sorted(turns, key=lambda t: (t['start'], t['end']))
    starts = [t['start'] for t in ordered]
    out: List[dict] = []
    count = 0
    for word in words:
        if word.get('speaker'):
            out.append(dict(word))
            continue
        first, last = _time(word.get('start')), _time(word.get('end'))
        if first is None or last is None:
            out.append(dict(word))
            continue
        middle = (first + last) / 2
        chosen = None
        # The last turn starting at or before the middle, and the few before
        # it, since turns of stacked clips may overlap.
        i = bisect_right(starts, middle) - 1
        for j in range(i, max(-1, i - 4), -1):
            if ordered[j]['start'] <= middle <= ordered[j]['end']:
                chosen = ordered[j]
                break
        if chosen is None:
            out.append(dict(word))
            continue
        out.append({**word, 'speaker': chosen['speaker']})
        count += 1
    return out, count


def counted(words: Sequence[dict]) -> Dict[str, int]:
    """How many words each speaker has, by name, in the order first heard."""
    found: Dict[str, int] = {}
    for word in words:
        speaker = word.get('speaker')
        if speaker:
            found[speaker] = found.get(speaker, 0) + 1
    return found
