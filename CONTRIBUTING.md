# Contributing to Alfred

Alfred is governed by the [Quaternion Media
constitution](https://github.com/quaternionmedia/qm), vendored at
`governance/qm`. This file is the practical version: what to run, what the
gates check, and the two rules that are easy to break by accident.

Read [AGENTS.md](AGENTS.md) first if you are an AI coding agent, or if you are
about to point one at this repository. It is the entry point, and it is short.

## The two rules that catch people out

**Everything arrives as a pull request.** Work on a branch, in this repo and in
the `governance/qm` submodule when you touch this project's records. Nobody
merges their own work — that applies to agents especially, and to changes that
look mechanical. If a PR cannot be opened, hand the branch over rather than
merging it.

**Contributor fields name humans.** No co-author trailer may point at an
address nobody reads — a model vendor's `noreply@` in particular, whether your
tooling adds it by default or you type it. Disclosing that a tool was involved
is welcome and belongs in a `Tools:` note on the artifact, never in a byline.
The person who ran the tool is the contributor of record.

## Getting a working copy

```sh
git clone --recurse-submodules https://github.com/quaternionmedia/alfred.git
cd alfred
./al init          # builds the website image, which carries its dependencies
./al dev           # the stack, on http://localhost:8000
```

On Windows, enable Developer Mode and `git config core.symlinks true` once per
clone — `CLAUDE.md` and `.github/copilot-instructions.md` are real symlinks to
`AGENTS.md`.

You do not need to download anything to have something to edit. Open the app,
go to the **Source** stage, and press *Generate a demo project* and *Generate
demo media*: both are synthesised locally with ffmpeg.

## Running the tests

```sh
./al pytest                          # the backend suite, plus black and ruff
./al test                            # the browser suite, on a stack it builds

pdm install -G test                  # or on the host: the backend suite,
pdm run pytest
cd website && yarn install           # and the browser suite, against ./al dev
npx playwright install chromium
yarn e2e
```

The backend suite's current tally is kept in [tests/README.md](tests/README.md)
rather than here, where a count goes stale with the next test anyone writes;
Playwright prints the browser suite's own at the end of every run.

Three things worth knowing before you change a test:

- **Marked tiers skip themselves when their tool is absent** — `needs_docker`,
  `needs_ffmpeg`, `needs_imagemagick`. `conftest.py` probes for the capability
  rather than the binary, because ffmpeg reaches moviepy through
  `imageio_ffmpeg` and is usually not on PATH.
- **The recipe walkthroughs are not in that run.** They pause between steps so
  the recordings are watchable, and are tagged `@recipe` and excluded. `./al
  recipes` runs them.
- **Known defects are pinned as strict `xfail`.** Fixing one turns the suite
  red as `XPASS(strict)`, which is the prompt to remove the marker. That is
  working as intended, not a broken test.

## The docs are generated from the tests

`docs/cookbook.md` is generated from the end-to-end suite, and the `@recipe`
walkthroughs in it are what the recordings capture:

```sh
./al cookbook      # regenerate the prose from the specs
./al recipes       # record the @recipe walkthroughs as video, then regenerate
```

`./al recipes` runs against a dev stack you already have up (`E2E_BASE_URL`
if it is not on :8000). The recordings stay on your machine: each passing
recipe's is copied to `docs/recipes/<recipe>.webm`, which git ignores, beside
an SVG stub that names the recipe and says a polished recording is pending.
The stubs are committed, and the cookbook shows each under its recipe. It
links only what git tracks, so a committed cookbook never names a file a clean
checkout lacks; a new recipe's stub appears once you `git add docs/recipes`
and regenerate.

So **do not edit `docs/cookbook.md` by hand** — change the tests and
regenerate. `tests/unit/test_cookbook.py` fails if the committed file drifts
from the specs, including a check that regenerating produces it byte for byte.

The reasoning: prose describing behaviour goes stale silently, and a test
describing behaviour goes red. A recipe that breaks has no stub or video
rather than a misleading one.

## Before opening a pull request

```sh
./al nox -s blacken                  # Black, with -S
./al nox -s lint                     # Ruff
./al pytest                          # all three, and the suite
python governance/qm/project-seed/ci/check_pr_base.py --base main --head <your-branch>
```

Paste the `check_pr_base.py` output into the PR description. It reports five
things a description usually asserts without evidence — what the branch is
based on, what it carries, who wrote it, which paths it touches, and whether
any commit already belongs to another open PR.

### If you changed a submodule

`alfred/otto`, `alfred/vox` and `governance/qm` are submodules. **Push the
submodule branch and get it merged before bumping the pointer here.** A
pointer bump to an unpushed commit is internally consistent, passes every
local check, and fails in CI as:

```
fatal: remote error: upload-pack: not our ref <sha>
```

`submodule-check.yml` catches it with a message that names the cause. Two other
QM projects hit the cryptic version first, which is why the check exists.

## What CI checks

| Workflow | What it does |
|---|---|
| `CI.yml` | Black, Ruff, the backend suite, and the browser suite through `playwright.yml` |
| `playwright.yml` | the browser suite, against the stack `test_e2e.yml` builds — the same run as `./al test` |
| `submodule-check.yml` | every submodule pin is reachable on its own remote |
| `adr-lint.yml` | decision-record discipline, run from the governance submodule |
| `reuse-lint.yml` | copyright and licence headers — **reporting only** |

One of those needs saying plainly rather than leaving to be discovered:

**REUSE is not blocking yet.** As of 2026-08-08, 0 of 206 files carry
copyright or licence information and there is no `LICENSES/` directory.
Blocking on that would stop every pull request on a gap none of them
introduced. Removing the `continue-on-error` line is the moment that changes,
and the adoption record should record the date when it does.

The browser suite needs nothing running beforehand: `test_e2e.yml` builds the
site and starts the api, a render worker and a database from the checkout, so
the `@slow` specs that wait on a real encode run in CI too, and `./al test`
reproduces a CI failure with nothing else set up.

## Where decisions live

This project's decision records are in `governance/qm/adr/`, inside the
submodule on this project's own branch — not at this repository's root. Drafts
are `DRAFT-*.md` and carry no number; numbering happens at ratification, and a
human ratifies.

A draft has no memory: if a decision changes while drafting, rewrite it as
though the final position were held from the start. `adr-lint.yml` enforces
that by rejecting revision-narrating vocabulary — "previously", "originally",
"corrected" and the rest.

Retrospectives and other material *for* deciding are not decision records.
[docs/retrospective-0.3.0.md](docs/retrospective-0.3.0.md) is an example, and
it says at the top why it is not in `adr/`.

## Known gaps

Listed so nobody has to rediscover them:

- The production stack has not been started during this release's work. Every
  verified claim concerns the dev stack and the test suites.
- Hot reload for the frontend does not work when the host is not Linux —
  inotify events do not cross a Docker bind mount. `website/dev-watch.js`
  polls instead; the trade is no HMR.
- `PUT /project/{id}` replaces the whole document, so a partial body nulls
  every field it omits. Use `PUT /project/{id}/settings` for settings. The
  general defect is unresolved.
- MongoDB is SSPL-licensed and fills three roles at once; object storage is
  reached through a vendor SDK behind a seam that has one other implementation.
  Both are in the adoption record.
