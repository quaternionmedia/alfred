#!/usr/bin/env python3
"""Turn the recipes' recordings into GIFs, beside them and out of git.

`./al recipes` runs this in the dev stack's api container, which has ffmpeg
(through imageio-ffmpeg) and the checkout at /app:

    docker compose -f docker-compose.yml -f dev.yml exec -T api \\
        python scripts/recipe_gifs.py

It reads `website/recipe-videos.json`, which
`website/e2e/collect-recipe-videos.js` writes: each passing recipe's name,
and the second its recipe starts at in the recording. For each it turns
`docs/recipes/<recipe>.webm` into `docs/recipes/<recipe>.gif`:

- from the recipe's start, so the login in front of it is cut;
- 720 pixels wide, 8 frames a second;
- one palette for the clip, built from what moves, and each frame stored as
  the rectangle that changed.

A GIF over MAX_BYTES is made again at a lower rate and fewer colours; one
still over it fails the run, naming the recipe, as does any ffmpeg failure.

The standard library, and ffmpeg: imageio-ffmpeg's, else one on PATH. Where
it runs as root, as in the container, what it writes is given to the owner
of docs/recipes, so a Linux checkout is not left with root's files.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RECIPES = REPO / 'docs' / 'recipes'
MANIFEST = REPO / 'website' / 'recipe-videos.json'

WIDTH = 720
MAX_BYTES = 1_500_000
# Frame rate and palette size, tried in turn until a GIF fits MAX_BYTES.
SETTINGS = ((8, 128), (6, 96), (5, 64))


def ffmpeg():
    """The ffmpeg to run, or None."""
    try:
        import imageio_ffmpeg
    except ImportError:
        return shutil.which('ffmpeg')
    return imageio_ffmpeg.get_ffmpeg_exe()


def to_gif(binary, source, target, start, fps, colours):
    """Write one GIF, raising CalledProcessError with ffmpeg's reasons."""
    graph = (
        f'fps={fps},scale={WIDTH}:-1:flags=lanczos,split[a][b];'
        f'[a]palettegen=max_colors={colours}:stats_mode=diff[p];'
        '[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle'
    )
    subprocess.run(
        [binary, '-hide_banner', '-loglevel', 'error', '-y']
        + (['-ss', f'{start:.2f}'] if start > 0 else [])
        + ['-i', str(source), '-vf', graph, '-loop', '0', str(target)],
        check=True,
        capture_output=True,
        text=True,
    )


def give_to_owner(path):
    """Owned as docs/recipes is, where this runs as root."""
    if getattr(os, 'geteuid', lambda: None)() != 0:
        return
    owner = RECIPES.stat()
    try:
        os.chown(path, owner.st_uid, owner.st_gid)
    except OSError:
        pass  # a mount that keeps its own owners


def main():
    if not MANIFEST.is_file():
        print(
            f'no {MANIFEST.relative_to(REPO)}: run website/e2e/collect-recipe-videos.js '
            'first (./al recipes runs both)',
            file=sys.stderr,
        )
        return 1
    binary = ffmpeg()
    if not binary:
        print('no ffmpeg: neither imageio-ffmpeg nor one on PATH', file=sys.stderr)
        return 1

    recipes = json.loads(MANIFEST.read_text(encoding='utf-8'))['recipes']
    failed = []
    total = 0
    for recipe in recipes:
        slug = recipe['slug']
        source = RECIPES / f'{slug}.webm'
        target = RECIPES / f'{slug}.gif'
        try:
            for fps, colours in SETTINGS:
                to_gif(binary, source, target, float(recipe['start']), fps, colours)
                if target.stat().st_size <= MAX_BYTES:
                    break
        except subprocess.CalledProcessError as exc:
            target.unlink(missing_ok=True)
            failed.append(f'{slug}: ffmpeg failed: {exc.stderr.strip()[-400:]}')
            continue
        size = target.stat().st_size
        if size > MAX_BYTES:
            target.unlink()
            failed.append(f'{slug}: {size} bytes even at {fps} fps, over {MAX_BYTES}')
            continue
        give_to_owner(target)
        total += size
        print(f'  {slug}.gif  {size / 1024:.0f} kB  ({fps} fps, {colours} colours)')

    print(f'docs/recipes: {len(recipes) - len(failed)} GIFs, {total / 1024:.0f} kB')
    for problem in failed:
        print(f'  failed: {problem}', file=sys.stderr)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
