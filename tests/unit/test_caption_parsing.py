"""K2 -- reading captions from SubRip, WebVTT and JSON.

Subtitle files come from every tool there is, so the readers forgive what is
unambiguous -- byte-order marks, CRLF and CR, `,` or `.` before the
milliseconds, hours past 99 or none at all, cue identifiers or none, cue
settings, NOTE/STYLE/REGION blocks, markup -- and say which line they could
not read when it is not.
"""

import pytest

from alfred.core.utils.captions import (
    MAX_CAPTIONS,
    CaptionFormatError,
    parse,
    parse_json,
    parse_srt,
    parse_vtt,
)


def triples(parsed):
    return [(c.start, c.end, c.text) for c in parsed.captions]


SRT = """1
00:00:01,000 --> 00:00:04,000
Hello there

2
00:00:05,500 --> 00:00:07,250
Two lines
of text
"""


class TestSubRip:
    def test_the_plain_case(self):
        assert triples(parse_srt(SRT)) == [
            (1.0, 4.0, 'Hello there'),
            (5.5, 7.25, 'Two lines\nof text'),
        ]

    def test_a_byte_order_mark_and_crlf(self):
        text = '﻿' + SRT.replace('\n', '\r\n')
        assert triples(parse_srt(text)) == triples(parse_srt(SRT))

    def test_old_mac_line_ends(self):
        assert triples(parse_srt(SRT.replace('\n', '\r'))) == triples(parse_srt(SRT))

    def test_bytes_are_read_as_utf8(self):
        assert parse_srt(SRT.encode('utf-8')).captions[0].text == 'Hello there'

    def test_a_dot_before_the_milliseconds(self):
        text = '1\n00:00:01.500 --> 00:00:02.000\nDotted\n'
        assert triples(parse_srt(text)) == [(1.5, 2.0, 'Dotted')]

    def test_more_hours_than_two_digits_hold(self):
        text = '1\n100:00:00,000 --> 123:04:05,678\nA long film\n'
        [(start, end, _)] = triples(parse_srt(text))
        assert start == 360000.0
        assert end == 123 * 3600 + 4 * 60 + 5.678

    def test_short_fractions_are_fractions(self):
        text = '1\n00:00:01,5 --> 00:00:02,25\nHalf\n'
        assert triples(parse_srt(text)) == [(1.5, 2.25, 'Half')]

    def test_coordinates_after_the_timing_are_ignored(self):
        text = '1\n00:00:01,000 --> 00:00:02,000 X1:40 X2:600 Y1:20 Y2:50\nPlaced\n'
        assert triples(parse_srt(text)) == [(1.0, 2.0, 'Placed')]

    def test_no_index_numbers(self):
        text = (
            '00:00:01,000 --> 00:00:02,000\nOne\n\n00:00:03,000 --> 00:00:04,000\nTwo\n'
        )
        assert [c.text for c in parse_srt(text).captions] == ['One', 'Two']

    def test_no_blank_line_between_cues(self):
        text = (
            '1\n00:00:01,000 --> 00:00:02,000\nOne\n'
            '2\n00:00:03,000 --> 00:00:04,000\nTwo\n'
        )
        assert triples(parse_srt(text)) == [(1.0, 2.0, 'One'), (3.0, 4.0, 'Two')]

    def test_extra_blank_lines_and_trailing_whitespace(self):
        text = '\n\n\n1  \n00:00:01,000 --> 00:00:02,000   \n  Spaced   out  \n\n\n\n'
        assert triples(parse_srt(text)) == [(1.0, 2.0, 'Spaced out')]

    def test_markup_is_not_drawn(self):
        text = (
            '1\n00:00:01,000 --> 00:00:02,000\n'
            '{\\an8}<i>Italic</i> and <font color="#ff0000">red</font> &amp; more\n'
        )
        assert parse_srt(text).captions[0].text == 'Italic and red & more'

    def test_empty_and_lengthless_cues_are_skipped_and_counted(self):
        text = (
            '1\n00:00:01,000 --> 00:00:02,000\n<i></i>\n\n'
            '2\n00:00:03,000 --> 00:00:03,000\nNo length\n\n'
            '3\n00:00:05,000 --> 00:00:04,000\nBackwards\n\n'
            '4\n00:00:06,000 --> 00:00:07,000\nKept\n'
        )
        parsed = parse_srt(text)
        assert [c.text for c in parsed.captions] == ['Kept']
        assert parsed.skipped == 3

    def test_cues_come_back_in_order(self):
        text = (
            '1\n00:00:05,000 --> 00:00:06,000\nLater\n\n'
            '2\n00:00:01,000 --> 00:00:02,000\nSooner\n'
        )
        assert [c.text for c in parse_srt(text).captions] == ['Sooner', 'Later']

    def test_an_unreadable_line_is_named(self):
        text = '1\n00:00:01,000 --> 00:00:02,000\nFine\n\nnot a cue\nat all\n'
        with pytest.raises(CaptionFormatError, match='line 5'):
            parse_srt(text)

    def test_an_impossible_time_is_named(self):
        text = '1\n00:00:61,000 --> 00:01:02,000\nSixty-one seconds\n'
        with pytest.raises(CaptionFormatError, match='line 2'):
            parse_srt(text)

    def test_nothing_is_no_captions(self):
        assert parse_srt('').captions == []
        assert parse_srt('﻿\n\n').captions == []

    def test_too_many_cues_is_refused(self):
        cue = '00:00:01,000 --> 00:00:02,000\nx\n\n'
        with pytest.raises(CaptionFormatError, match=str(MAX_CAPTIONS)):
            parse_srt(cue * (MAX_CAPTIONS + 1))


VTT = """WEBVTT - with a title

NOTE this is a comment
that spans two lines

STYLE
::cue { color: yellow }

REGION
id:fred width:40%

intro
00:01.000 --> 00:04.000 align:start position:10% line:0
<v Roger>Hi <c.yellow>there</c>, &lt;friend&gt;

00:00:05.000 --> 00:00:06.500
<00:00:05.500>Karaoke <b>style</b>
"""


class TestWebVtt:
    def test_blocks_identifiers_settings_and_markup(self):
        assert triples(parse_vtt(VTT)) == [
            (1.0, 4.0, 'Hi there, <friend>'),
            (5.0, 6.5, 'Karaoke style'),
        ]

    def test_a_missing_header_is_forgiven(self):
        text = '00:01.000 --> 00:02.000\nNo header\n'
        assert triples(parse_vtt(text)) == [(1.0, 2.0, 'No header')]

    def test_a_byte_order_mark_and_crlf(self):
        text = '﻿' + VTT.replace('\n', '\r\n')
        assert triples(parse_vtt(text)) == triples(parse_vtt(VTT))

    def test_hours_past_ninety_nine(self):
        text = 'WEBVTT\n\n101:00:00.000 --> 101:00:01.000\nLate\n'
        assert parse_vtt(text).captions[0].start == 101 * 3600

    def test_a_note_mid_file(self):
        text = (
            'WEBVTT\n\n00:01.000 --> 00:02.000\nOne\n\n'
            'NOTE\nnothing to see\n\n00:03.000 --> 00:04.000\nTwo\n'
        )
        assert [c.text for c in parse_vtt(text).captions] == ['One', 'Two']

    def test_a_comma_is_forgiven_too(self):
        text = 'WEBVTT\n\n00:00:01,000 --> 00:00:02,000\nSubRip habits\n'
        assert triples(parse_vtt(text)) == [(1.0, 2.0, 'SubRip habits')]


class TestJson:
    def test_a_list(self):
        text = '[{"start": 1, "end": 2.5, "text": "One"}]'
        assert triples(parse_json(text)) == [(1.0, 2.5, 'One')]

    def test_alfred_s_own_answer(self):
        text = '{"captions": [{"start": 0, "end": 1, "text": "Mine"}], "style": {}}'
        assert triples(parse_json(text)) == [(0.0, 1.0, 'Mine')]

    def test_a_speech_engine_s_segments(self):
        text = (
            '{"text": "x", "segments": [{"id": 0, "start": 0.5, "end": 1.5, '
            '"text": " Hello.", "words": []}]}'
        )
        assert triples(parse_json(text)) == [(0.5, 1.5, 'Hello.')]

    def test_timestamps_as_strings(self):
        text = '[{"start": "00:00:01.000", "end": "00:00:02,500", "text": "Stamped"}]'
        assert triples(parse_json(text)) == [(1.0, 2.5, 'Stamped')]

    def test_seconds_as_strings(self):
        assert (
            parse_json('[{"start": "1.5", "end": "2", "text": "s"}]').captions[0].start
            == 1.5
        )

    def test_a_byte_order_mark(self):
        assert parse_json('﻿[{"start": 0, "end": 1, "text": "x"}]').captions

    def test_missing_text_is_skipped(self):
        parsed = parse_json(
            '[{"start": 0, "end": 1}, {"start": 1, "end": 2, "text": ""}]'
        )
        assert parsed.captions == [] and parsed.skipped == 2

    @pytest.mark.parametrize(
        'text, where',
        [
            ('{"start": 0', 'line 1'),
            ('{"nothing": []}', 'captions'),
            ('[1, 2]', 'caption 1'),
            ('[{"end": 1, "text": "x"}]', 'no start'),
            ('[{"start": true, "end": 1, "text": "x"}]', 'caption 1'),
            ('[{"start": "soon", "end": 1, "text": "x"}]', 'caption 1'),
            ('[{"start": 0, "end": 1e999, "text": "x"}]', 'finite'),
        ],
    )
    def test_what_cannot_be_read_says_where(self, text, where):
        with pytest.raises(CaptionFormatError, match=where):
            parse_json(text)


class TestParse:
    def test_the_format_chooses_the_reader(self):
        assert parse('srt', SRT).captions == parse_srt(SRT).captions
        assert parse('vtt', VTT).captions == parse_vtt(VTT).captions

    def test_an_unknown_format(self):
        with pytest.raises(CaptionFormatError, match='srt, vtt, json'):
            parse('ass', '')

    def test_text_is_held_to_a_caption_s_limit(self):
        text = '1\n00:00:01,000 --> 00:00:02,000\n' + 'x' * 501 + '\n'
        with pytest.raises(CaptionFormatError, match='line 2: .*500'):
            parse_srt(text)
