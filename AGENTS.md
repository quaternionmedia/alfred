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

A video editor that runs without a server dependency, built as a **small
control plane** (`alfred/`) orchestrating a **render engine** (`otto`, a
separate public QM package consumed as `al-otto` and vendored at
`alfred/otto`). The seam owns auth, project and render lifecycle state,
and orchestration; it does not own video handling. Keep it that way — see
the control-plane record in `governance/qm/adr/`.

- `alfred/core/routes/` — API surface (FastAPI routers)
- `alfred/core/models/` — Beanie/Pydantic documents
- `alfred/core/utils/` — DB, Celery tasks, storage, email
- `website/` — mithril SPA, built with parcel
- `governance/qm/` — the constitution and this project's `adr/`

## Clone and setup

```sh
git clone --recurse-submodules git@github.com:quaternionmedia/alfred.git
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
| `./al prod` | Production stack (expects a running traefik) |

Tests can also run directly: `nox -f tests/noxfile.py -s coverage`.

### Dev server notes

These bite on a first run, none obvious from the error:

- **Port 8000, and this one fails silently.** 27017 below is the loud version
  of this problem; 8000 is the quiet one, and it is worse. If something else
  already holds 8000, Docker still starts the stack and reports it healthy —
  but every request from your machine reaches the other application, because
  the host port belongs to whoever bound it first. Nothing errors. It happened
  during this project's 0.3.0 work: another QM service defaults to 8000 too,
  and `curl localhost:8000/openapi.json` answered `Apothecary API` for a full
  session while Alfred was up and serving correctly on its own network.

  `./al dev` now refuses to start when 8000 is already answering, and names
  the occupant from its OpenAPI title. Override rather than kill whatever has
  it: `ALFRED_PORT=8100 ./al dev`. `ALFRED_DB_PORT` and `ALFRED_HMR_PORT` do
  the same for the other two.

  The general rule, worth more than the specific fix: **a test result is only
  as good as your knowledge of what served it.** Before trusting a number,
  confirm the identity of the server — `curl localhost:$PORT/openapi.json`
  names it. See [docs/retrospective-verification-discipline.md](docs/retrospective-verification-discipline.md).
- **Port 27017.** `dev.yml` publishes MongoDB on the host. If anything else is
  already bound there — a standalone `mongod`, another project's container —
  the stack fails with `Bind for 0.0.0.0:27017 failed: port is already
  allocated`, and the message names the port but not the culprit. Find it with
  `docker ps`, or run with an override that remaps or drops the publish.
  Nothing in the app needs 27017 exposed on the host; it is published for
  attaching a GUI, and not publishing it is the better default.
- **`UID`/`GID`.** `dev.yml` sets the db container's user from `${UID}:${GID}`.
  Neither is exported by default in most shells, and `UID` is read-only in
  bash, so compose warns and substitutes blanks. Harmless on Docker Desktop;
  export both if the db container fails to start on a Linux host.

- **`website/node_modules` is not shared with the container.** The image
  installs its own, and an anonymous volume keeps the `./website:/app` bind
  mount from covering them. This is load-bearing on any non-Linux host: parcel
  needs a per-platform native binding, so a host install would otherwise hand
  an Alpine container a Windows or macOS one. Install on the host freely --
  you need to, for Playwright. One consequence: anonymous volumes survive an
  ordinary `up`, so after changing a dependency run `./al init` (or
  `docker compose up --renew-anon-volumes`) or the container keeps the
  previous install.

- **`--reload` does not see your edits on Windows or macOS.** `./al dev` runs
  uvicorn with `--reload`, which watches with inotify — and inotify events do
  not cross a Docker bind mount from a non-Linux host. This is the same
  limitation that costs the frontend its HMR, but the frontend has a polling
  watcher and the API does not, so the API silently keeps running the code it
  loaded at startup.

  The symptom is a fix that does not take effect, and the tell is a traceback
  whose frame shows a line number with **no source line** beside it — Python
  cannot map the frame because the file changed under the loaded module. Run
  `docker compose -f docker-compose.yml -f dev.yml restart api` after editing
  anything under `alfred/`.

  A syntax error is worse: the container reports `Up` while crash-looping, and
  every request answers connection-refused rather than 500. `docker logs
  alfred-api-1` names it immediately; nothing else does.

`./al dev` runs with `--reload`, so on a Linux host edits under `alfred/`
restart the API. That also means a test run writing into the repo can restart
the server mid-request — `test_e2e.yml` overrides the command to disable
reload for exactly that reason.

## Conventions

- **Formatting is Black with `-S`** (single quotes preserved). CI enforces
  it via the shared `quaternionmedia/.github` workflow; run
  `./al nox -s blacken` before pushing.
- **Packaging is PDM**, not pip or poetry. Dependencies live in
  `pyproject.toml`; `pdm.lock` is committed.
- **CI is centralized**: `.github/workflows/CI.yml` calls reusable
  workflows in `quaternionmedia/.github`. Prefer extending those over
  adding project-local workflow logic.

## Known governance gaps

This project adopted the constitution with pre-existing non-compliance
rather than starting clean. The open items — and what compliance would
look like for each — are enumerated in the adoption-scope record in
`governance/qm/adr/`. Read it before adding a dependency, a datastore, or
a third-party service, so you don't deepen a gap that is already being
worked. Do not add new frontend assets loaded from a CDN.
