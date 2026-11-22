"""The cut's arithmetic, held equal to the browser's by the shared fixtures.

`alfred/core/utils/cut.py` is the twin of `website/src/ClipWindow.js`. The
fixtures under `tests/fixtures/{cut,follow,excerpt}/` are each a timeline,
its captions and its words, what is done to it, and what comes out; this
module runs the Python over them and `website/e2e/cut-fixtures.spec.js` runs
the JavaScript. A fixture both pass is a case the two agree on; a change to
either implementation that moves an answer reddens its own suite.
"""

import json
from pathlib import Path

import pytest

from alfred.core.utils import cut

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures'


def fixtures(folder):
    files = sorted((FIXTURES / folder).glob('*.json'))
    assert files, f'no fixtures under tests/fixtures/{folder}'
    return [pytest.param(path, id=path.stem) for path in files]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


@pytest.mark.parametrize('path', fixtures('cut'))
def test_cut_ranges_matches_the_fixture(path):
    fixture = read(path)
    given = json.loads(json.dumps(fixture['given']))
    assert cut.cut_ranges(fixture['given'], fixture['ranges']) == fixture['expect']
    # Pure: nothing it is given is changed.
    assert fixture['given'] == given


@pytest.mark.parametrize('path', fixtures('follow'))
def test_follow_clips_matches_the_fixture(path):
    fixture = read(path)
    given = json.loads(json.dumps(fixture['given']))
    assert cut.follow_clips(fixture['given']) == fixture['expect']
    assert fixture['given'] == given


@pytest.mark.parametrize('path', fixtures('excerpt'))
def test_excerpt_matches_the_fixture(path):
    fixture = read(path)
    given = json.loads(json.dumps(fixture['given']))
    assert (
        cut.excerpt(fixture['given'], fixture['start'], fixture['end'])
        == fixture['expect']
    )
    assert fixture['given'] == given


class TestExcerptRefusals:
    TIMELINE = {
        'clips': [
            {
                'type': 'video',
                'name': 'videos/a.mp4',
                'start': 0,
                'duration': 4,
                'inpoint': 0,
            }
        ]
    }

    def test_a_span_with_no_length(self):
        with pytest.raises(cut.NothingToExcerpt):
            cut.excerpt(self.TIMELINE, 2, 2)

    def test_a_span_past_the_end(self):
        with pytest.raises(cut.NothingToExcerpt):
            cut.excerpt(self.TIMELINE, 5, 9)

    def test_a_span_backwards(self):
        with pytest.raises(cut.NothingToExcerpt):
            cut.excerpt(self.TIMELINE, 3, 1)

    def test_an_empty_timeline(self):
        with pytest.raises(cut.NothingToExcerpt):
            cut.excerpt({'clips': []}, 0, 1)


class TestRounding:
    def test_to_the_millisecond_a_half_goes_up(self):
        # As the browser's Math.round: 0.0005 s is a millisecond, not nothing.
        assert cut.to_ms(0.0005) == 0.001
        assert cut.to_ms(1.0015) == 1.002
        assert cut.to_ms(2.5e-3) == 0.003

    def test_a_number_as_the_browser_reads_it(self):
        assert cut.clip_seconds({'duration': '2.5'}) == 2.5
        assert cut.clip_seconds({'duration': 'soon'}) == 0
        assert cut.clip_seconds({'duration': None}) == 0
        assert cut.clip_seconds({}) == 0
        assert cut.in_of({'inpoint': ''}) == 0
