# AGENTS.md

This project is governed by the Quaternion Media constitution, vendored at
`governance/qm` (a submodule pinned to this project's `project/alfred`
branch of that repo). If you are an AI coding agent opening this repo with
no other briefing, read this file fully before your first commit or edit.

## Before you do anything

1. Read `governance/qm/README.md` and `governance/qm/PRINCIPLES.md` in full
   — the namespaces/precedence rules and the charter. Both are short.
2. This project's own decision records live in `governance/qm/adr/` — inside
   the submodule, on this project's own branch, not at this repo's root — as
   `ADR-NNNN` (numbered locally, at ratification) or `DRAFT-*.md` before
   ratification. A human ratifies; you draft.
3. **Everything you produce arrives as a pull request.** Work on a branch and
   open a PR for human review — in this repo, and in the `governance/qm`
   submodule when you touch this project's records there. Never commit to,
   merge into, or push a shared branch directly, and never merge your own
   work, however small or mechanical the change looks. If you cannot open a
   PR, hand the branch back rather than merging it.
4. **Human-only contributorship applies to every commit you make here** (see
   `governance/qm/records/DRAFT-human-only-contributorship.md`): do not add
   yourself, your model name, or any co-author trailer naming an unmonitored
   address (e.g. a vendor `noreply@` address) to any commit. If your default
   tooling normally appends a `Co-Authored-By:` trailer, suppress it for
   this repo. Tool involvement is disclosed as a `Tools:` note where the
   artifact calls for one, never as a byline.
5. Follow the drafting-session handoff contract in
   `governance/qm/adr/README.md` before writing or amending any record.
6. A QM record may be tightened by this project's own records, never
   relaxed — see `governance/qm/README.md`'s "Namespaces and precedence."
7. Banned in any pre-ratification `DRAFT-*.md` record: "previously",
   "originally", "earlier draft", "re-review", "renumber", "retroactive",
   "supersedes the ... (stance|finding)", "corrected". Drafts are rewritten
   in place, not narrated. The ADR lint enforces this over prose only, so
   quoting the list in a code span is fine.
8. **Logging and secrets: print no secret, anywhere.** Not into a terminal,
   a log, a commit, a pull request or a report. That means the values in
   `.secret_key`, `.secret_key.local`, `.cred`, `cred.json`,
   `cred_api.json`, `.email`, `.magick` or any env file; tokens; passwords;
   session cookies; and the `sig` of a signed URL. The committed key files
   are development stubs, but the habit is the guard: the same commands run
   against a real deployment. In practice:
   - `docker compose config --no-interpolate`, never plain `config`, which
     writes the env files' values into its output (this is how a stub leaked
     into a session log);
   - list variables by name (`env | cut -d= -f1`), never with values;
   - write `sig=…`, and name a test account rather than quoting its password.

   If one slips out, say so in your report or PR, by name. `./al family` and
   the scripts under `scripts/` redact what they print. Keep it that way in
   anything you add.
9. **Deliver into the repository, never to a hosted page.** A report, a demo,
   a preview or a handoff is a committed file (a docs page, a screenshot, the
   regenerated cookbook) and reaches a reviewer as a pull request, or as the
   dev stack and `./al docs` left running for them to look at. Publish nothing
   to a page a chat product hosts outside the org's repositories: it is not
   versioned with the code, cannot be reviewed as a diff, and goes stale
   unseen. The recipes' recordings stay out of git and play only in docs
   served locally.

## One-time setup on a fresh clone (Windows)

`CLAUDE.md` and `.github/copilot-instructions.md` are real symlinks to this
file, not copies — POSIX checkouts resolve them with no setup. On Windows,
enable Developer Mode (Settings → For developers) and run `git config
core.symlinks true` once per clone, then `git checkout -- .` if the files
were already checked out before that. Skipping this doesn't break
anything — the files degrade to one-line pointers containing just the
target path — but it isn't the intended, tested experience; see the
IDE-integrated governance discovery record in `governance/qm/records/` for
what was actually verified.

<!-- Project-specific setup commands, test commands, and conventions belong
     below this line; this seed only carries the governance-discovery part. -->

## What Alfred is

A browser video editor whose previews and renders are all made server-side, by
a self-hosted stack built as a **small control plane** (`alfred/`)
orchestrating two parallel engines. **otto** renders the picture: a separate
public QM package, consumed as `al-otto` and vendored at `alfred/otto`. **vox**
carries the sound: QM's audio-engine seam, vendored at `alfred/vox`, driving an
engine such as joe over HTTP. Both are submodules, installed editable from
there the same way everywhere (the image, nox and CI) with `--no-deps`; what
they need comes from alfred's lockfiles (`requirements.lock`, and
`requirements-render.lock` for otto's `render` extra), so nothing is resolved
on the day of a build. The `Dockerfile` says more.

The seam owns auth, project, render and caption lifecycle state, and
orchestration. It does not own video or audio handling, and only
`alfred/core/utils/audio_engine.py` knows how the audio engine is reached
(docs/captions.md). Keep it that way; see the control-plane record in
`governance/qm/adr/`.

Media work is otto's, through its public API: a render (`renderMultitrack`, by
a named `preset` that a render's `quality` passes through to), a preview frame
(`renderFrame`), a timeline's sound (`renderSound`), what a library file holds
(`otto.media.probe`) and the demo clips (`otto.demo.demoClip`). `alfred/`
imports no media library and runs no ffmpeg; what the engine needs that otto
does not expose is a change to otto, pinned here. Each of those calls blocks,
and `tests/unit/test_blocking_calls.py` lists it, so no coroutine calls one.

- `alfred/core/routes/` — API surface (FastAPI routers)
- `alfred/core/models/` — Beanie/Pydantic documents
- `alfred/core/utils/` — DB, Celery tasks, storage, email, captions, and the
  audio-engine adapter
- `website/` — mithril SPA, built with parcel
- `governance/qm/` — the constitution and this project's `adr/`

## Clone and setup

```sh
git clone --recurse-submodules https://github.com/quaternionmedia/alfred.git
git submodule update --init --recursive   # if cloned without --recurse-submodules
./al init                                 # install website dependencies
```

## Common commands

Everything routes through `./al`, the repo-root task runner. `./al` with no
arguments prints the full command list.

| Command | What it does |
|---|---|
| `./al dev` | Run the dev stack; app on http://localhost:8000 (`ALFRED_PORT` to move it) |
| `./al dev --build` | Rebuild images first |
| `./al stop` | Stop the dev stack |
| `./al demo` | Download demo media into `videos/` (needs network; the app can generate its own) |
| `./al pytest` | Run the API test suite in Docker |
| `./al nox -s lint` | Ruff |
| `./al nox -s blacken` | Black (`-S`, single quotes) |
| `./al docs` | Serve mkdocs locally on :4000 |
| `./al family` | Every repository alfred works with: status, the vendored pins, what's off |
| `./al family loop` | Each one's quick suite, then joe and the dev stack together, a live check, and down ([docs/family.md](docs/family.md)) |
| `./al prod` | Production stack (expects a running traefik and the production `ALFRED_SECRET_KEY` exported) |

Tests can also run directly: `nox -f tests/noxfile.py -s coverage`.

### Dev server notes

These bite on a first run, and none is obvious from the error. The docs site
shows this list as its dev-server page (`docs/dev-server.md` includes it
between the markers), so it is kept here only.

<!-- --8<-- [start:dev-server-notes] -->
- **Port 8000 fails silently.** If something else already holds 8000, Docker
  still starts the stack and reports it healthy, but every request from your
  machine reaches the other application: the host port belongs to whoever
  bound it first. Nothing errors; 27017 below is the loud version of the same
  problem. `./al dev` refuses to start when 8000 already answers, and names
  the occupant from its OpenAPI title. Override rather than kill whatever has
  it: `ALFRED_PORT=8100 ./al dev`. `ALFRED_DB_PORT` and `ALFRED_HMR_PORT` do
  the same for the other two.

  The general rule, worth more than the fix: **a test result is only as good
  as your knowledge of what served it.** Before trusting a number, confirm the
  server's identity; `curl localhost:$PORT/openapi.json` names it. During
  0.3.0 it answered `Apothecary API`, another QM service on 8000, for a whole
  session while Alfred served correctly on its own network; see [the
  verification retrospective](https://github.com/quaternionmedia/alfred/blob/main/docs/retrospective-verification-discipline.md).
- **Port 27017.** `dev.yml` publishes MongoDB on the host's loopback, for
  attaching a GUI; nothing in the app needs it there. If anything else holds
  27017 (a standalone `mongod`, another project's container), the stack fails
  with `Bind for 127.0.0.1:27017 failed: port is already allocated`, which
  names the port but not the culprit. Find it with `docker ps`, or move it
  with `ALFRED_DB_PORT`.
- **Loopback only, unless you ask.** `dev.yml` publishes the api, the HMR port
  and the database on `127.0.0.1`, so the dev stack is reachable from this
  machine and nowhere else. With `ALFRED_DEV_SKIP_AUTH=1` every request is
  served as a superuser, so on every interface that would be anyone on the
  network. To try the app from a phone on the same network, opt in for that
  run with `ALFRED_BIND=0.0.0.0 ./al dev` and browse to this machine's LAN
  address. Do it with the auth bypass off, or on a network you trust; `./al
  dev` warns when both are set. The database ignores `ALFRED_BIND` and stays
  on loopback; `ALFRED_DB_BIND` moves it, for someone who means to.
- **The signing key.** The committed `.secret_key` is a stub that leaves
  `ALFRED_SECRET_KEY` empty, and an empty key still signs: PyJWT accepts it,
  so anyone could mint a development session for any account. `./al init`,
  `./al dev` and `./al thin` create `.secret_key.local` (git-ignored) with a
  random key for this checkout, and `dev.yml` loads it over the stub. Delete
  it to rotate. Production never reads it: `./al prod` needs the key exported.
- **`UID`/`GID`.** `dev.yml` sets the db container's user from `${UID}:${GID}`.
  Most shells export neither, and `UID` is read-only in bash, so compose warns
  and substitutes blanks. Harmless on Docker Desktop; export both if the db
  container fails to start on a Linux host.
- **`website/node_modules` is not shared with the container.** The image
  installs its own, and an anonymous volume keeps the `./website:/app` bind
  mount from covering them. This is load-bearing on any non-Linux host: parcel
  needs a per-platform native binding, so a host install would hand an Alpine
  container a Windows or macOS one. Install on the host freely; Playwright
  needs it. Anonymous volumes survive an ordinary `up`, so after changing a
  dependency run `./al init` (or `docker compose up --renew-anon-volumes`), or
  the container keeps the previous install.
- **`--reload` does not see your edits on Windows or macOS.** `./al dev` runs
  uvicorn with `--reload`, which watches with inotify, and inotify events do
  not cross a Docker bind mount from a non-Linux host. The frontend has a
  polling watcher for this, at the cost of its HMR; the API has none, so it
  silently keeps running the code it loaded at startup. The symptom is a fix
  that does not take effect; the tell is a traceback frame showing a line
  number with **no source line** beside it: Python cannot map the frame,
  because the file changed under the loaded module. Run `docker compose -f
  docker-compose.yml -f dev.yml restart api` after editing anything under
  `alfred/`.

  A syntax error is worse: the container reports `Up` while crash-looping, and
  every request answers connection-refused rather than 500. `docker logs
  alfred-api-1` names it immediately; nothing else does.

  On a Linux host `--reload` does restart the API on edits under `alfred/`, so
  a test run writing into the repo can restart the server mid-request;
  `test_e2e.yml` overrides the command to disable reload for that reason.
<!-- --8<-- [end:dev-server-notes] -->

## Conventions

- **Formatting is Black with `-S`** (single quotes preserved). CI enforces it
  through the shared `quaternionmedia/.github` workflow; run
  `./al nox -s blacken` before pushing.
- **Packaging is PDM**, not pip or poetry. Dependencies live in
  `pyproject.toml`; `pdm.lock` is committed.
- **CI is centralized**: `.github/workflows/CI.yml` calls reusable workflows in
  `quaternionmedia/.github`. Prefer extending those over adding project-local
  workflow logic.

## Known governance gaps

This project adopted the constitution with pre-existing non-compliance rather
than starting clean. The adoption-scope record in `governance/qm/adr/`
enumerates the open items and what compliance would look like for each. Read
it before adding a dependency, a datastore or a third-party service, so you
don't deepen a gap already being worked. Do not add new frontend assets loaded
from a CDN.
