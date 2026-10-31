"""Play each walkthrough's recording on the page it walks, where one is on disk.

A mkdocs hook (`hooks:` in mkdocs.yml). `./al recipes` records the `@recipe`
walkthroughs into `docs/recipes/<recipe>.webm`, which git ignores, and notes in
`website/recipe-videos.json` the second each recipe starts at, after the login
in front of it. A page places a walkthrough with a marker on a line of its own,
`<!-- recipe: <title> -->`. Where the recording is there, the marker becomes a
player opening at the recipe's start; where none is, as in CI and on the
published site, the marker stays a comment and the page shows nothing. So the
docs a person serves locally with `./al docs` play every walkthrough in full,
and the committed and published docs carry only the screenshots.

The slug is the one `website/e2e/collect-recipe-videos.js` names the file by;
`website/e2e/cookbook.js` lists each walkthrough with the page its marker is on.
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / 'website' / 'recipe-videos.json'
MARKER = re.compile(r'^<!-- recipe: (?P<title>.+?) -->$')


def slug_for(title):
    """The file name collect-recipe-videos.js gives the recipe called `title`."""
    return re.sub(r'^-|-$', '', re.sub(r'[^a-z0-9]+', '-', title, flags=re.I)).lower()


def starts(manifest=MANIFEST):
    """Each recorded recipe's start, in seconds, by slug; none without a manifest."""
    try:
        listed = json.loads(manifest.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return {r['slug']: float(r.get('start') or 0) for r in listed.get('recipes', [])}


def with_recordings(markdown, url_of, start_of):
    """`markdown` with each marker whose recording `url_of` finds made a player.

    `url_of(path)` answers the URL of a docs file relative to the page, or None
    when there is no such file; `start_of` maps a slug to its start second.
    """
    out = []
    for line in markdown.split('\n'):
        found = MARKER.match(line)
        url = found and url_of(f'recipes/{slug_for(found["title"])}.webm')
        if not url:
            out.append(line)
            continue
        start = start_of.get(slug_for(found['title']), 0)
        fragment = f'#t={start:g}' if start else ''
        out.append(
            f'<video controls muted playsinline preload="metadata" '
            f'src="{url}{fragment}" aria-label="The recording of {found["title"]}" '
            'style="width:100%"></video>'
        )
    return '\n'.join(out)


def on_page_markdown(markdown, page, config, files):
    def url_of(path):
        file = files.get_file_from_path(path)
        return None if file is None else file.url_relative_to(page.file)

    return with_recordings(markdown, url_of, starts())
