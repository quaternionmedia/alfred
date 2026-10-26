"""Every picture the docs show is there, and every one there is shown.

`./al recipes` makes the docs' screenshots from the running app, into
`docs/assets/screens/` (website/e2e/screens.spec.js and recipes.spec.js,
through screens.js). They are committed, so
these hold the pages and the files to each other: a page showing a picture
that is not there, a picture nothing shows, a screenshot the spec no longer
takes, and a page that no longer opens with what it shows. The recipes' GIFs
are not committed (test_cookbook.py), so no page here shows one.

mkdocs checks the links of the pages it builds, and not the README, which
GitHub shows; nor does it notice a file nothing links. Hence these.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / 'docs'
SCREENS = DOCS / 'assets' / 'screens'
# The specs that take them, each with `save(page, '<name>')`.
SCREENS_SPECS = [
    REPO / 'website' / 'e2e' / 'screens.spec.js',
    REPO / 'website' / 'e2e' / 'recipes.spec.js',
]

# The pages a person reads first, and what each opens with under its title.
SHOWN_FIRST = [
    'README.md',
    'docs/index.md',
    'docs/captions.md',
    'docs/examples/render.md',
    'docs/about/index.md',
    'docs/about/render.md',
]
# Opens with what `./al family` prints, rather than a picture of a terminal.
SHOWN_AS_OUTPUT = 'docs/family.md'

MARKDOWN_IMAGE = re.compile(r'!\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)')
HTML_IMAGE = re.compile(r'<img\b[^>]*\bsrc=["\']([^"\']+)["\']', re.IGNORECASE)
FENCE = re.compile(r'^(```|~~~).*?^\1', re.MULTILINE | re.DOTALL)

DESKTOP = (1280, 800)
PHONE = (390, 844)
MAX_SCREEN_BYTES = 250 * 1024


def pages():
    return [REPO / 'README.md'] + sorted(DOCS.rglob('*.md'))


def images_on(page):
    """What a page shows as an image, resolved; code blocks are left out."""
    text = FENCE.sub('', page.read_text(encoding='utf-8'))
    for target in MARKDOWN_IMAGE.findall(text) + HTML_IMAGE.findall(text):
        if re.match(r'[a-z][a-z0-9+.-]*:', target, re.IGNORECASE):
            continue  # another host's, or a data: URI
        yield target, (page.parent / target.split('#')[0].split('?')[0]).resolve()


def made_by_recipes():
    """The pictures `./al recipes` makes, as they are on disk."""
    return sorted(SCREENS.glob('*.png'))


def png_size(path):
    """A PNG's width and height, from its header."""
    head = path.read_bytes()[:24]
    assert head[:8] == b'\x89PNG\r\n\x1a\n', f'{path.name} is not a PNG'
    return int.from_bytes(head[16:20], 'big'), int.from_bytes(head[20:24], 'big')


def lines_after_title(path):
    """The page's non-blank lines after its H1, which must be its first."""
    lines = path.read_text(encoding='utf-8').splitlines()
    assert lines and lines[0].startswith('# '), f'{path} does not open with an H1'
    return [line for line in lines[1:] if line.strip()]


class TestEveryPictureIsThere:
    def test_every_image_a_page_shows_exists(self):
        missing = [
            f'{page.relative_to(REPO)}: {target}'
            for page in pages()
            for target, resolved in images_on(page)
            if not resolved.is_file()
        ]
        assert not missing, f'pages show images that are not there: {missing}'


class TestEveryPictureIsShown:
    def test_every_screen_is_shown_by_a_page(self):
        """A screenshot nothing shows is weight in the repository."""
        shown = {resolved for page in pages() for _, resolved in images_on(page)}
        unshown = [
            str(path.relative_to(REPO))
            for path in made_by_recipes()
            if path.resolve() not in shown
        ]
        assert not unshown, (
            f'{unshown} are shown by no page. Show each under a page title, '
            'or stop making it.'
        )


class TestTheScreens:
    def screens_the_specs_take(self):
        return {
            name
            for spec in SCREENS_SPECS
            for name in re.findall(
                r"\bsave\(\s*\w+,\s*'([a-z0-9-]+)'\s*\)",
                spec.read_text(encoding='utf-8'),
            )
        }

    def test_the_screens_are_the_ones_the_specs_take(self):
        taken = self.screens_the_specs_take()
        assert len(taken) >= 9, 'found too few screens in the specs to be checking'
        there = {path.stem for path in SCREENS.glob('*.png')}
        assert there == taken, (
            f'the specs take {sorted(taken - there)} that are not in '
            f'docs/assets/screens, which has {sorted(there - taken)} they do not '
            'take. Run ./al recipes.'
        )

    def test_each_screen_is_a_desktop_or_a_phone_and_small(self):
        problems = []
        for path in sorted(SCREENS.glob('*.png')):
            expected = PHONE if path.stem.startswith('phone-') else DESKTOP
            size = png_size(path)
            if size != expected:
                problems.append(f'{path.name} is {size}, not {expected}')
            if path.stat().st_size > MAX_SCREEN_BYTES:
                problems.append(f'{path.name} is {path.stat().st_size} bytes')
        assert not problems, problems


class TestThePagesShowFirst:
    @pytest.mark.parametrize('name', SHOWN_FIRST)
    def test_the_page_opens_with_a_picture_and_its_caption(self, name):
        """Under the title: the picture, then one line of italic caption."""
        lines = lines_after_title(REPO / name)
        assert (
            lines[0].lstrip().startswith(('![', '<img'))
        ), f'{name} does not open with a picture under its title: {lines[0]!r}'
        caption = lines[1].strip()
        assert re.fullmatch(r'\*[^*].*[^*]\*', caption), (
            f'{name}: the line under its picture is not a one-line italic '
            f'caption: {caption!r}'
        )

    @pytest.mark.parametrize('name', SHOWN_FIRST)
    def test_the_picture_reads_the_same_on_github_and_the_site(self, name):
        """No attr_list on it, and raw `<img>` only where its path holds.

        GitHub prints an attr_list (`{ width=... }`) as text. mkdocs rewrites
        a Markdown image's path for the page's URL, a directory deeper than
        its file, but leaves a raw `<img>` as written -- so a relative `src`
        reaches the same file on both only from an index page or the README.
        """
        picture = lines_after_title(REPO / name)[0]
        assert not re.search(r'\)\s*\{', picture), (
            f'{name}: an attr_list on its picture shows as text on GitHub; '
            'use <img width=...> on an index page, or a plain image'
        )
        if HTML_IMAGE.search(picture):
            assert Path(name).name in ('index.md', 'README.md'), (
                f'{name}: a raw <img> on a page that is not an index has a '
                'src the docs site resolves a directory too deep'
            )

    def test_the_family_page_opens_with_what_the_command_prints(self):
        lines = lines_after_title(REPO / SHOWN_AS_OUTPUT)
        assert lines[0].strip() == '```text' and lines[1].startswith(
            '$ ./al family'
        ), f'{SHOWN_AS_OUTPUT} does not open with the output of ./al family'
