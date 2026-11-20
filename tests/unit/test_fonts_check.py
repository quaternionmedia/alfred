"""The font check on a host without fontconfig.

`checkFonts` asks `fc-list`, which the api image has and a bare host may not.
Without it the list is unknown, which is not an empty list: the collection is
left as it was, and the start-up log says why.
"""

import asyncio

from alfred import main


def test_without_fc_list_the_font_list_is_unknown(monkeypatch):
    monkeypatch.setattr(main, 'which', lambda name: None)
    assert main.installed_fonts() is None


def test_an_unknown_list_leaves_the_collection_and_says_so(monkeypatch, capsys):
    """Mutation: treat an absent fc-list as an empty list -- red, every family
    would be dropped; swallow the None silently -- red, nothing is said."""
    calls = []

    class Fonts:
        async def update_one(self, *args, **kwargs):
            calls.append('update')

        async def delete_many(self, *args, **kwargs):
            calls.append('delete')

    class Db:
        fonts = Fonts()

    monkeypatch.setattr(main, 'get_db', lambda: Db())
    monkeypatch.setattr(main, 'installed_fonts', lambda: None)
    asyncio.run(main.checkFonts())
    assert calls == []
    assert 'fc-list' in capsys.readouterr().out
