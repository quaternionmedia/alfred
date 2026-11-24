"""`GET /fonts` answers the fonts this machine has, as startup found them.

The template editor's font field offers what this route answers. Its browser
tests serve the list themselves (website/e2e/templates.spec.js), so they pass
whatever the server would have said, and `unit/test_fonts.py` holds the parse
of fontconfig's lines, not what reaches the route. Here nothing is stubbed:
the app's startup runs `checkFonts`, which asks fontconfig and stores a
document per family, and the route answers from the database.

Needs `fc-list`, which the api image has. Where it is missing the tier's `api`
fixture leaves `checkFonts` out, so there is no list to check.
"""

import shutil

import pytest

pytestmark = [
    pytest.mark.needs_db,
    pytest.mark.skipif(
        shutil.which('fc-list') is None, reason='no fontconfig to list the fonts'
    ),
]


DROPPED = 'Dropped-By-A-Later-Image'


@pytest.fixture(scope='module', autouse=True)
def a_family_an_earlier_start_stored(db):
    """In the database before this module's app starts, as a font an earlier
    image had and this one does not would be: the collection outlives the
    image."""
    db.fonts.insert_one({'family': DROPPED, 'style': ['Regular']})


@pytest.fixture
def listed(api, make_account):
    res = api.get('/fonts', headers=make_account('typesetter').headers)
    assert res.status_code == 200, res.text
    return res.json()


def test_a_family_fontconfig_no_longer_lists_is_forgotten(listed):
    assert DROPPED not in listed, 'a font this machine does not have is offered'


def test_every_family_fontconfig_lists_is_answered_once(listed):
    """What fontconfig lists now, asked again here, is what the route says."""
    from alfred.main import font_styles, installed_fonts

    families = {family for family, _ in font_styles(installed_fonts())}
    assert families, 'fontconfig lists no font, so there is nothing to compare'
    assert sorted(set(listed)) == sorted(families)
    repeated = sorted({name for name in listed if listed.count(name) > 1})
    assert not repeated, f'listed more than once: {repeated}'


def test_each_is_a_name_the_editor_can_send_back(listed):
    """A non-empty string with its spaces as hyphens, as the template's `font`
    takes it: the editor shows `DejaVu Sans` and sends `DejaVu-Sans`."""
    assert all(isinstance(name, str) and name for name in listed), listed
    spaced = [name for name in listed if ' ' in name]
    assert not spaced, f'names with spaces, which the editor cannot send: {spaced}'


def test_it_needs_a_session(api):
    assert api.get('/fonts').status_code == 401
