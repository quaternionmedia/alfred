"""The template editor's font list, as startup reads it from fontconfig.

`checkFonts` runs `fc-list -f '"%{family}-%{style}\\n"'` and stores a font
per family. The integration suite removes it where `fc-list` is missing, so
the parse is held here, against lines fontconfig writes.
"""

from alfred.main import font_styles


def test_a_line_gives_its_family_and_styles_with_spaces_as_hyphens():
    assert font_styles(['DejaVu Sans-Bold Oblique']) == [
        ('DejaVu-Sans', ['Bold-Oblique'])
    ]


def test_a_line_naming_several_families_gives_each_the_line_s_styles():
    """fontconfig lists a font's localised family names together."""
    found = font_styles(['Noto Sans CJK JP,Noto Sans CJK JP Regular-Regular,Book'])
    assert found == [
        ('Noto-Sans-CJK-JP', ['Regular', 'Book']),
        ('Noto-Sans-CJK-JP-Regular', ['Regular', 'Book']),
    ]


def test_blank_and_styleless_lines_name_no_font():
    """`fc-list`'s output ends in a newline, so its last line is blank; a line
    with no hyphen has no style to give.

    Mutation: drop the length check and this raises an IndexError.
    """
    assert font_styles(['', 'Lonely', 'Free Serif-Italic', '']) == [
        ('Free-Serif', ['Italic'])
    ]


def test_families_come_back_in_the_order_fontconfig_lists_them():
    """Startup stores them in this order, so a family listed twice keeps the
    styles of its later line, as it always has."""
    found = font_styles(['Free Sans-Bold', 'Free Mono-Regular', 'Free Sans-Regular'])
    assert [family for family, _ in found] == ['Free-Sans', 'Free-Mono', 'Free-Sans']
