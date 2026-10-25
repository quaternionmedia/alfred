"""Show each walkthrough's recording in the cookbook, where one is on disk.

A mkdocs hook (`hooks:` in mkdocs.yml). `./al recipes` records the `@recipe`
walkthroughs into `docs/recipes/<recipe>.webm`, which git ignores, and notes in
`website/recipe-videos.json` the second each recipe starts at, after the login
in front of it. Where a recording is there, the cookbook's line for that recipe
gets a player under it, opening at the recipe's start; where none is, as in CI
and on the published site, the page is left as it was generated. So the docs a
person serves locally with `./al docs` play every walkthrough in full, and the
committed and published docs carry only the screenshots.

The slug is the one `website/e2e/collect-recipe-videos.js` names the file by.
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / 'website' / 'recipe-videos.json'
COOKBOOK = 'cookbook.md'
RECIPE = re.compile(r'^- \*\*recipe: (?P<title>.+)\*\*$')


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
    """`markdown` with a player under each recipe whose recording `url_of` finds.

    `url_of(path)` answers the URL of a docs file relative to the page, or None
    when there is no such file; `start_of` maps a slug to its start second.
    """
    out = []
    for line in markdown.split('\n'):
        out.append(line)
        found = RECIPE.match(line)
        if not found:
            continue
        slug = slug_for(found['title'])
        url = url_of(f'recipes/{slug}.webm')
        if url is None:
            continue
        start = start_of.get(slug, 0)
        fragment = f'#t={start:g}' if start else ''
        out += [
            '',
            f'  <video controls muted playsinline preload="metadata" '
            f'src="{url}{fragment}" aria-label="The recording of {found["title"]}" '
            'style="width:100%"></video>',
            '',
        ]
    return '\n'.join(out)


def on_page_markdown(markdown, page, config, files):
    if page.file.src_uri != COOKBOOK:
        return markdown

    def url_of(path):
        file = files.get_file_from_path(path)
        return None if file is None else file.url_relative_to(page.file)

    return with_recordings(markdown, url_of, starts())
