"""K2 -- what a caption is, and the textBox clip it becomes.

`utils.captions` owns the mapping: one textBox template clip per caption,
after the timeline's clips, with explicit timing and no fades, styled from
the project's style -- and, where the style says nothing, from defaults
relative to the frame being rendered. These pin the shape of those clips; the
pipeline tier encodes them and looks at the pixels.
"""

import math

import pytest
from otto.models import Edl
from otto.render import _check_position, clipTiming
from pydantic import ValidationError

from alfred.core.models.captions import Caption, CaptionStyle, clean_caption_text
from alfred.core.utils.captions import (
    DEFAULT_FONTSIZE,
    MAX_CAPTIONS,
    MAX_WIDTH,
    MIN_PIXELS,
    TooManyCaptions,
    box_width,
    caption_clips,
    caption_fontsize,
    checked_captions,
    timeline_end,
    with_captions,
)


def cap(start, end, text='words'):
    return Caption(start=start, end=end, text=text)


class TestACaption:
    def test_times_are_kept_to_the_millisecond(self):
        assert cap(1.23456, 2.0004).start == 1.235

    @pytest.mark.parametrize(
        'start, end',
        [(-0.1, 1), (2, 2), (3, 1), (math.nan, 1), (0, math.inf), (0, 4e6)],
    )
    def test_impossible_times_are_refused(self, start, end):
        with pytest.raises(ValidationError):
            cap(start, end)

    @pytest.mark.parametrize('text', ['', '   ', '\n\t\n', '\x00\x07'])
    def test_text_has_to_say_something(self, text):
        with pytest.raises(ValidationError, match='some text'):
            cap(0, 1, text)

    def test_text_is_bounded(self):
        cap(0, 1, 'x' * 500)
        with pytest.raises(ValidationError, match='500'):
            cap(0, 1, 'x' * 501)

    def test_text_is_tidied(self):
        assert clean_caption_text(' one\r\n\r\n  two\tthree  \x07') == (
            'one\ntwo three'
        )


class TestAStyle:
    def test_everything_is_optional_and_enabled_by_default(self):
        style = CaptionStyle()
        assert style.enabled is True
        assert style.fontsize is None and style.position is None

    @pytest.mark.parametrize(
        'given, stored',
        [('#FFF', '#ffffff'), ('abcdef', '#abcdef'), ('#00ff7F', '#00ff7f')],
    )
    def test_colours_are_hex(self, given, stored):
        assert CaptionStyle(color=given).color == stored

    @pytest.mark.parametrize('colour', ['red', '#12', 'rgb(1,2,3)', '#ggg'])
    def test_other_colours_are_refused(self, colour):
        with pytest.raises(ValidationError):
            CaptionStyle(color=colour)

    @pytest.mark.parametrize('none', ['', 'none', 'transparent'])
    def test_no_box_is_said_with_an_empty_bg(self, none):
        assert CaptionStyle(bg=none).bg == ''

    @pytest.mark.parametrize(
        'position', ['bottom', 'top', 'center', ['left', 'bottom'], ('right', 'top')]
    )
    def test_positions_otto_accepts(self, position):
        stored = CaptionStyle(position=position).position
        _check_position(stored, 'style')  # otto's own check, which raises

    @pytest.mark.parametrize('position', ['middle', ['bottom', 'left'], [10, 20]])
    def test_other_positions_are_refused(self, position):
        with pytest.raises(ValidationError):
            CaptionStyle(position=position)

    @pytest.mark.parametrize(
        'given, stored', [('left', 'west'), ('right', 'east'), ('center', 'center')]
    )
    def test_alignment(self, given, stored):
        assert CaptionStyle(align=given).align == stored

    @pytest.mark.parametrize('font', ['/etc/passwd', '@file', '../x', 'a' * 65, ''])
    def test_a_font_is_a_name_not_a_path(self, font):
        with pytest.raises(ValidationError):
            CaptionStyle(font=font)

    @pytest.mark.parametrize('size', [7, 201, math.nan])
    def test_sizes_are_bounded(self, size):
        with pytest.raises(ValidationError):
            CaptionStyle(fontsize=size)


class TestAList:
    def test_in_order_of_start_then_end(self):
        ordered = checked_captions([cap(5, 6), cap(1, 3), cap(1, 2)])
        assert [(c.start, c.end) for c in ordered] == [(1, 2), (1, 3), (5, 6)]

    def test_at_most_max_captions(self):
        checked_captions([cap(i, i + 1) for i in range(MAX_CAPTIONS)])
        with pytest.raises(TooManyCaptions):
            checked_captions([cap(i, i + 1) for i in range(MAX_CAPTIONS + 1)])

    def test_none_is_empty(self):
        assert checked_captions(None) == []


class TestTheClips:
    SIZE = (1920, 1080)

    def test_one_textbox_template_clip_per_caption(self):
        clips = caption_clips([cap(1, 2.5, 'Hello'), cap(3, 4, 'Bye')], None, self.SIZE)
        assert [c['name'] for c in clips] == ['textBox', 'textBox']
        assert all(c['type'] == 'template' for c in clips)
        assert [c['data']['text'] for c in clips] == ['Hello', 'Bye']

    def test_explicit_timing_and_no_fades(self):
        [clip] = caption_clips([cap(1.25, 3.5)], None, self.SIZE)
        assert (clip['start'], clip['duration']) == (1.25, 2.25)
        assert (clip['fadeIn'], clip['fadeOut']) == (0, 0)
        timing = clipTiming(Edl.parse_obj({'clips': [clip]}).clips[0])
        assert (timing.start, timing.length) == (1.25, 2.25)

    def test_the_defaults_are_bottom_centred_white_on_a_box(self):
        [clip] = caption_clips([cap(0, 1)], CaptionStyle(), self.SIZE)
        data = clip['data']
        assert data['position'] == 'bottom'
        assert data['align'] == 'center'
        assert data['color'] == '#ffffff'
        assert data['bg'] == '#000000'
        assert data['fontsize'] == DEFAULT_FONTSIZE
        assert data['method'] == 'caption'

    def test_the_size_follows_the_frame(self):
        style = CaptionStyle(fontsize=60)
        assert caption_fontsize(style, 1080) == 60
        assert caption_fontsize(style, 720) == 40
        assert caption_fontsize(CaptionStyle(), 2160) == 108
        assert caption_fontsize(CaptionStyle(), 90) == MIN_PIXELS

    def test_the_safe_area(self):
        """The clip is the frame inset by the margin top and bottom, placed
        that far down; the caption's position is within it."""
        [clip] = caption_clips([cap(0, 1)], None, self.SIZE)
        assert clip['clipsize'] == [1920, 1080 - 2 * 54]
        assert clip['position'] == [0, 54]
        assert clip['relative'] is False

    def test_the_style_s_fields_are_the_template_s(self):
        style = CaptionStyle(
            fontsize=40,
            color='#ffcc00',
            bg='#202020',
            position='top',
            align='west',
            font='DejaVu-Sans-Bold',
        )
        [clip] = caption_clips([cap(0, 1)], style, self.SIZE)
        data = clip['data']
        assert (
            data['color'],
            data['bg'],
            data['position'],
            data['align'],
            data['font'],
        ) == ('#ffcc00', '#202020', 'top', 'west', 'DejaVu-Sans-Bold')

    def test_no_box_leaves_bg_out(self):
        [clip] = caption_clips([cap(0, 1)], CaptionStyle(bg=''), self.SIZE)
        assert 'bg' not in clip['data']

    def test_a_pair_of_words_goes_out_as_a_list(self):
        [clip] = caption_clips(
            [cap(0, 1)], CaptionStyle(position=['left', 'top']), self.SIZE
        )
        assert clip['data']['position'] == ['left', 'top']

    def test_disabled_draws_nothing(self):
        assert caption_clips([cap(0, 1)], CaptionStyle(enabled=False), self.SIZE) == []

    def test_until_cuts_and_drops(self):
        clips = caption_clips(
            [cap(0, 2), cap(1.5, 4), cap(3, 5)], None, self.SIZE, until=3
        )
        assert [(c['start'], c['duration']) for c in clips] == [(0, 2), (1.5, 1.5)]

    def test_every_clip_is_one_otto_accepts(self):
        clips = caption_clips(
            [cap(0, 1), cap(1, 2)],
            CaptionStyle(position=['right', 'bottom']),
            self.SIZE,
        )
        edl = Edl.parse_obj({'clips': clips})
        for clip in edl.clips:
            _check_position(clip.position, 'clip')
            _check_position(clip.data.position, 'data')
            assert tuple(clip.data.textsize) == (clip.data.textsize[0], None)


class TestTheBox:
    def test_it_fits_the_line_not_the_frame(self):
        assert box_width('Hi', 54, 1920) < box_width('Hello there, everyone', 54, 1920)

    def test_wide_letters_are_wider(self):
        assert box_width('mmmm', 54, 1920) > box_width('iiii', 54, 1920)

    def test_it_never_passes_the_widest_a_caption_may_be(self):
        assert box_width('x' * 400, 54, 1920) == int(1920 * MAX_WIDTH)

    def test_the_longest_line_decides(self):
        assert box_width('short\na much longer line', 54, 1920) == box_width(
            'a much longer line', 54, 1920
        )

    def test_full_width_characters_count_as_full_width(self):
        assert box_width('字幕字幕', 54, 1920) >= 4 * 54


class TestATimeline:
    def test_its_stated_duration(self):
        assert timeline_end(Edl.parse_obj({'clips': [], 'duration': 9})) == 9

    def test_where_its_last_clip_ends(self):
        edl = Edl.parse_obj(
            {
                'clips': [
                    {'type': 'video', 'start': 2, 'duration': 3},
                    {'type': 'video', 'inpoint': 1, 'outpoint': 2},
                ]
            }
        )
        assert timeline_end(edl) == 5

    def test_unreadable_timing_is_unknown(self):
        edl = Edl.parse_obj({'clips': [{'type': 'video', 'duration': -1}]})
        assert timeline_end(edl) is None


class TestWithCaptions:
    def test_after_the_timeline_s_own_clips(self):
        edl = {'clips': [{'type': 'template', 'name': 'makeColor', 'duration': 3}]}
        out = with_captions(edl, [cap(0, 1)], None, (320, 180))
        assert [c['name'] for c in out['clips']] == ['makeColor', 'textBox']
        assert edl['clips'] == [
            {'type': 'template', 'name': 'makeColor', 'duration': 3}
        ]

    def test_nothing_to_draw_is_the_edl_itself(self):
        edl = {'clips': []}
        assert with_captions(edl, [], None, (320, 180)) is edl
        assert (
            with_captions(edl, [cap(0, 1)], CaptionStyle(enabled=False), (320, 180))
            is edl
        )
