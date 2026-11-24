# Contributing to Alfred

Alfred is governed by the [Quaternion Media
constitution](https://github.com/quaternionmedia/qm), vendored at
`governance/qm`. This file is the practical version: what to run, what the
gates check, and the two rules that are easy to break by accident.

Read [AGENTS.md](AGENTS.md) first if you are an AI coding agent, or are about
to point one at this repository: it is the entry point.

## The two rules that catch people out

**Everything arrives as a pull request.** Work on a branch, in this repo and in
the `governance/qm` submodule when you touch this project's records. Nobody
merges their own work, agents especially, however mechanical the change looks.
If a PR cannot be opened, hand the branch over instead of merging it.

**Contributor fields name humans.** No co-author trailer may point at an
address nobody reads, a model vendor's `noreply@` in particular, whether your
tooling adds it by default or you type it. Tool involvement is welcome in a
`Tools:` note on the artifact, never in a byline. The person who ran the tool
is the contributor of record.

## Getting a working copy

```sh
git clone --recurse-submodules https://github.com/quaternionmedia/alfred.git
cd alfred
./al init          # builds the website image, which carries its dependencies
./al dev           # the stack, on http://localhost:8000
```

[README.md](README.md) covers the Windows symlink step, and a first run with
nothing to download.

## Running the tests

```sh
./al pytest                       # API suite, plus black --check and ruff, in Docker
./al test                         # browser suite, in Docker, on a stack it builds

pdm install -G test               # or on the host: Python deps and test extras
pdm run pytest                    # unit + pipeline suite
pdm run pytest -m "not needs_ffmpeg and not needs_db"   # no external tools

cd website && yarn install        # yarn: website/yarn.lock is the lockfile
npx playwright install chromium
yarn e2e                          # end-to-end, against a running ./al dev
```

On the host, `pdm install` takes `al-otto` from `alfred/otto` as a copy rather
than editable, and has no vox at all. `pip install -e alfred/otto --no-deps`
and `pip install -e alfred/vox --no-deps` in that environment make the suite
test the vendored engines the image runs, which
`tests/unit/test_stack_config.py` checks. `pdm install -G render` adds the
engine's render extra (gizeh), which its text templates draw with.

A change that crosses repositories (alfred and otto, vox, joe or qmcp) has a
loop of its own: `./al family loop` runs each repository's quick suite, brings
the dev stack up with joe as its audio engine, checks the whole path live, and
takes it down. `./al family` alone says where each repository is, and whether
alfred's pins match the checkouts beside it ([docs/family.md](docs/family.md)).

The backend suite's tally is kept in [tests/README.md](tests/README.md), not
here, where it would go stale with the next test; Playwright prints the
browser suite's after every run.

Before you change a test:

- **Marked tiers skip themselves when their tool is absent**: `needs_docker`,
  `needs_ffmpeg`, `needs_imagemagick`. `conftest.py` probes for the capability,
  not the binary, because ffmpeg reaches moviepy through `imageio_ffmpeg` and
  is usually not on PATH.
- **The `@recipe` and `@screens` specs are excluded.** Recipes pause between
  steps so their GIFs are watchable; `./al recipes` runs both.
- **Known defects are pinned as strict `xfail`.** Fixing one turns the suite
  red as `XPASS(strict)`, the prompt to remove the marker. That is not a broken
  test. [tests/README.md](tests/README.md) says how to record one.

## The docs are generated from the tests

The docs' prose and screenshots come from the end-to-end suite, and so do
the recipes' GIFs:

```sh
./al cookbook      # regenerate docs/cookbook.md from the specs
./al recipes       # take the @screens screenshots, record the @recipe GIFs, then regenerate
```

`./al recipes` runs against a dev stack you already have up (`E2E_BASE_URL` if
it is not on :8000). It writes each screen as `docs/assets/screens/<name>.png`
and each passing recipe as `docs/recipes/<recipe>.gif`, converting with the
ffmpeg in the api container, and exits non-zero if any step fails. Both build
their own demo data and show nothing else, so recording on your own stack
publishes none of your projects. Commit the screenshots;
`tests/unit/test_docs_images.py` holds each to a page that shows it. The GIFs
stay out of git -- one does not compress against its last version, so every
refresh would add megabytes to history -- and stay on the machine that
recorded them; `tests/unit/test_cookbook.py` fails if one is tracked or linked.
There, `./al docs` plays each recipe's whole recording under its line in the
cookbook, from the recipe's start (`scripts/docs_recordings.py`, a mkdocs
hook); the published docs, built without them, show the screenshots only.

So **do not edit `docs/cookbook.md` by hand**: change the tests and
regenerate. `tests/unit/test_cookbook.py` fails if the committed file drifts
from the specs, or regenerating does not produce it byte for byte. Prose
describing behaviour goes stale silently; a test describing behaviour goes red.
A recipe that breaks leaves no GIF rather than a misleading one.

## Before opening a pull request

```sh
./al nox -s blacken                  # Black, with -S
./al nox -s lint                     # Ruff
./al pytest                          # black --check, ruff, and the suite
python governance/qm/project-seed/ci/check_pr_base.py --base main --head <your-branch>
```

Paste the `check_pr_base.py` output into the PR description. It reports five
things a description usually asserts without evidence: what the branch is
based on, what it carries, who wrote it, which paths it touches, and whether
any commit already belongs to another open PR.

### If you changed a submodule

`alfred/otto`, `alfred/vox` and `governance/qm` are submodules. **Push the
submodule branch and get it merged before bumping the pointer here.** A bump to
an unpushed commit is internally consistent, passes every local check, and
fails in CI as:

```
fatal: remote error: upload-pack: not our ref <sha>
```

`submodule-check.yml` catches it with a message that names the cause. It
exists because two other QM projects hit the cryptic version first.

## What CI checks

| Workflow | What it does |
|---|---|
| `CI.yml` | Black, Ruff, the backend suite, and the browser suite through `playwright.yml` |
| `playwright.yml` | the browser suite, against the stack `test_e2e.yml` builds — the same run as `./al test` |
| `submodule-check.yml` | every submodule pin is reachable on its own remote |
| `adr-lint.yml` | decision-record discipline, run from the governance submodule |
| `reuse-lint.yml` | copyright and licence headers — **reporting only** |

**REUSE is not blocking yet.** As of 2026-08-08, 0 of 206 files carry
copyright or licence information, and there is no `LICENSES/` directory;
blocking would stop every pull request on a gap none of them introduced.
Removing the `continue-on-error` line changes that, and the adoption record
should record the date when it does.

The browser suite needs nothing running beforehand: `test_e2e.yml` builds the
site and starts the api, a render worker and a database from the checkout, so
the `@slow` specs that wait on a real encode run in CI too, and `./al test`
reproduces a CI failure with nothing else set up.

## Where decisions live

This project's decision records are in `governance/qm/adr/`, inside the
submodule on this project's own branch, not at this repository's root. Drafts
are `DRAFT-*.md`, unnumbered until a human ratifies them.

A draft has no memory: if a decision changes while drafting, rewrite it as
though the final position were held from the start. `adr-lint.yml` enforces
that by rejecting revision-narrating vocabulary: "previously", "originally",
"corrected" and the rest. Retrospectives and other material *for* deciding are
not decision records; [docs/retrospective-0.3.0.md](docs/retrospective-0.3.0.md)
is one, and says at the top why it is not in `adr/`.

## Known gaps

- The production stack has not been started during this release's work. Every
  verified claim concerns the dev stack and the test suites.
- Frontend hot reload does not work on a non-Linux host: inotify events do not
  cross a Docker bind mount. `website/dev-watch.js` polls instead, at the cost
  of HMR.
- `PUT /project/{id}` replaces the whole document, so a partial body nulls
  every field it omits. Use `PUT /project/{id}/settings` for settings. The
  general defect is unresolved.
- MongoDB is SSPL-licensed and fills three roles at once; object storage is
  reached through a vendor SDK behind a seam that has one other implementation.
  Both are in the adoption record.
