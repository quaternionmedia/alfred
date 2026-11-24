# Images and stacks

How the image is built, what each compose file adds, how the suites' stacks
are kept apart from the dev stack, and what CI runs. The files themselves keep
a line per decision and point here.

## The image

`Dockerfile` builds one image for the api and the render worker, with a `test`
stage over it for the API suite.

- **The base is pinned by digest**, at Python 3.11. Unpinned, `python`
  reached 3.14, which no longer bundles setuptools. Bump the digest on
  purpose, and run the suites on the new one.
- **The lockfiles, exactly.** The three `requirements*.lock` exports, then
  otto, vox and alfred editable, all with `--no-deps`, so pip resolves nothing
  ([Dependencies](dependencies.md#lockfiles)). `pip check` in the image
  reports only vox's speech and CLI dependencies, which alfred never loads. A
  dependency added to `pyproject.toml` and never locked would be left out
  without a word, so `tests/unit/test_stack_config.py` checks that
  `requirements.lock` holds every one.
- **uvicorn floats.** `pyproject.toml` lists it as a development dependency,
  so no export holds it, and the image installs the newest release.
- **The default command reloads** on file changes, for the dev stack. The
  other stacks start uvicorn without `--reload`: see [the production
  stack](#the-production-stack) and [the browser suite's
  stack](#the-browser-suites-stack).
- **The `test` stage** is the api image of the same commit, plus nox.
  `pytest.yml` builds it, so `./al pytest` and `./al nox` run on the api's own
  system: its Python, its ImageMagick policy and its fonts. The plain `api`
  stage comes last, because a build that names no target, as every compose
  file's api and renderer do, gets the last stage.

### ImageMagick's policy

The image deletes ImageMagick's `policy.xml`, at the version-6 and the
version-7 path both (the base ships 7). moviepy's text rendering needs some of
what the policy forbids.

This is open. The policy is what limits ImageMagick's handling of untrusted
input, and alfred accepts media from its users. The fix is a policy that
relaxes only the rules moviepy's text needs.

### Fonts

moviepy's `TextClip` asks for Courier unless told otherwise, and the base
ships only DejaVu. Without Courier, ImageMagick cannot read the font, and
every template that draws text (`title`, `textBox`, `bullets`, `initial`,
`final`) fails. `fonts-urw-base35` is the PostScript set that ImageMagick's
`type-urw-base35.xml` already describes. It takes the image from 8 fonts to
105, and Courier, Helvetica and Times resolve.

The stacks mount `alfred/otto/fonts` at `/usr/share/fonts/truetype/otto`, a
subdirectory. A bind mount over `/usr/share/fonts/truetype/` itself replaces
the image's fonts with the host directory, empty or not, and then no template
with text draws. The api and the renderer mount the same directory, so a
preview draws with the fonts its render will.

## The compose files

| File | What it is | Run by |
|---|---|---|
| `docker-compose.yml` | the base: the site, the api and the database | under each of the next three |
| `dev.yml` | the dev stack: ports, the render worker, every setting | `./al dev` |
| `thin.yml` | over `dev.yml`, the render worker left out | `./al thin` |
| `production.yml` | the production stack, behind traefik | `./al prod` |
| `flower.yml` | Celery monitoring, beside the dev stack | `./al flower` |
| `pytest.yml` | the API suite and a throwaway database | `./al pytest`, `./al nox` |
| `test_e2e.yml` | the browser suite and everything it runs against | `./al test`, CI |

`./al` names the images after the checkout (`ALFRED_IMAGES`), so two
worktrees never build over each other's ([Configuration](configuration.md)).

### Settings

`dev.yml` and `production.yml` hand every setting alfred reads to the api and
the renderer from one list, `x-alfred-settings`, merged into both, so the two
services cannot drift apart. A setting exported and not listed would reach
neither; `tests/unit/test_stack_settings.py` fails when alfred reads one the
lists leave out.

Each is passed by its bare name, so a setting the shell leaves unset stays
unset, and the code's default holds. Empty is not the same as unset to a
container: `ALFRED_RENDER_DIR` or `ALFRED_DELIVERY_DIR` set to nothing would
name the working directory, the checkout itself. alfred reads an empty value
as unset for that reason ([Setting one](configuration.md#setting-one)).

`ALFRED_SECRET_KEY` is on neither list. In development the env files supply
it, `.secret_key` and then `.secret_key.local` over it, and a bare name in the
list would erase their key whenever the shell had none. Production takes it
from the deploying shell ([below](#the-production-stack)).

The audio engine's contract is a second list: one
`ALFRED_AUDIO_ENGINE_CONTRACT_<FIELD>` per field of vox's `EngineContract`
(`alfred/vox/vox/contract.py`), in its order. Compose passes names, not
patterns, and the settings test holds the list to the contract's fields.

### Paths

- **`VIDEO_DIR` is `/app/videos`**, absolute, in the api and the renderer. The
  renderer writes there and the api delivers from there, so both must name the
  same file; a relative path would depend on a working directory nobody sets
  on purpose. Both mount the checkout's `videos/` there.
- **The worker runs from the image's `WORKDIR`**, `/app`, with no
  `--workdir`. It resolves library clips against `VIDEO_DIR`, so the working
  directory decides nothing.
- **Media fetched from a URL** goes to `OTTO_DOWNLOAD_DIR`, which the stacks
  set from `ALFRED_REMOTE_CACHE_DIR`: a hidden directory in the shared
  library. A file fetched for a preview is not fetched again to render, and is
  never listed or served (contract M6).
- **The renderer loads `.email`**, as the api does: the worker is what sends
  issue reports and invoices.
- **`website/node_modules`** is an anonymous volume in each container that
  mounts `website/`, so the image's install is not covered by the host's; see
  the [dev server notes](dev-server.md).

### The site's watcher

`dev.yml`'s site runs `yarn run dev`, which polls (`website/dev-watch.js`).
`@parcel/watcher` subscribes to inotify, and inotify events do not cross a
Docker Desktop bind mount from Windows or macOS: the container sees the edited
file but is never told, so `parcel watch` sits idle and `dist/` goes stale.
Parcel's own polling backend, `--watch-backend brute-force`, aborts on
startup, and parcel does not read `PARCEL_WATCHER_BACKEND`.

Polling costs the HMR: `dist/` is current within a second, and the browser
does not refresh itself. On a Linux host, `yarn run dev:hmr` runs parcel's own
watcher.

parcel builds its HMR port into the bundle, and the browser dials that port on
the page's own host. So the port has one number on both sides of the
container: `dev.yml` publishes `ALFRED_HMR_PORT` (1733) as itself and hands it
to the site, and `dev:hmr` listens on it. A port mapped to a different one
inside would leave the browser dialling a port nothing on the host publishes.

### Ports

- **The dev stack** publishes on loopback unless `ALFRED_BIND` says otherwise,
  and the database only through `ALFRED_DB_BIND`: `ALFRED_BIND` is for trying
  the app from a phone, which never needs an unauthenticated database on the
  network too. See the [dev server notes](dev-server.md).
- **Flower** publishes on loopback for the same reason. It asks for no login
  unless one is configured, and its API revokes tasks and shuts workers down.
  `ALFRED_BIND=0.0.0.0 ./al flower` opens it, for a network you trust.
- **Production** publishes no database port. Nothing outside the stack needs
  it; attach a GUI through `docker compose exec db mongo`, or a tunnel.
- **`host.docker.internal`** is mapped in the api and the renderer of both
  stacks, for an audio engine beside them; see [Docker hosts and
  joe](configuration.md#docker-hosts-and-joe).

### The production stack

`production.yml` composes over `docker-compose.yml`, behind a traefik already
running on the external `web` network. `./al prod` builds the docs into
`alfred/site/` first, with `squidfunk/mkdocs-material` at the release
`pdm.docs.lock` holds (`tests/unit/test_docs_site.py` checks the tag).

- **`ALFRED_PRODUCTION` is set in the file**, so production is a property of
  the stack, not of the shell that starts it.
- **`ALFRED_SECRET_KEY` comes from the deploying shell**, and compose refuses
  to start without it. It overrides the committed development stub that
  `docker-compose.yml` loads. `./al prod` checks for it before it stops
  anything, so a missing key never leaves production down.
- **There is no `ALFRED_DEV_SKIP_AUTH`** on its list: the auth bypass has no
  way into this stack.
- **`ALFRED_PUBLIC_URL`** defaults to the host traefik serves; export it to
  deploy elsewhere.
- **The api runs without `--reload`.** The repository is bind-mounted at
  `/app`, so with it any write under the checkout, a `git pull` included,
  would restart the server mid-request on code nobody deployed. Deploying is a
  restart.
- **The renderer** is `dev.yml`'s, with `ALFRED_PRODUCTION`.

### Without the render worker

`./al thin` composes `thin.yml` last, over `dev.yml`, and scales the renderer
to nothing: a merge cannot remove a service, but it can keep one from
starting. The renderer carries moviepy, ImageMagick, ffmpeg and the fonts, and
nothing else needs them. Projects load, media lists, clips go on the timeline
and previews draw through the api without it.

What waits: a queued render sits in the queue and never reaches `rendered`,
and the Deliver stage shows it as queued. Transcribing captions, an issue
report and an invoice's mail are the worker's jobs too, and wait the same way.

## The suites' stacks

`./al pytest` and `./al nox` run as the compose project `<project>-pytest`,
and `./al test` as `<project>-e2e`. Their services share names with the dev
stack's (`db`; `api`, `renderer` and `db`), so under the checkout's own project
a test run would recreate a running dev stack's containers with its own.

### The API suite's stack

`pytest.yml` builds the image's `test` stage, and runs nox's default sessions:
formatting, lint, and the suite ([nox](#nox)). Its database is a throwaway: no
ports, no mounts, and each test worker drops its own database before and after
the run. `depends_on` only orders the start, so the `needs_db` tier's fixture
waits for MongoDB to answer, and fails rather than skips if it never does: the
database was promised.

### The browser suite's stack

`test_e2e.yml` needs nothing beforehand: no `./al init`, no dev stack, no
built site, no secrets. CI runs it as it is, and `./al test` runs it after
`down --volumes`, which removes what the last run left. A run's containers and
volumes stay until the next one, for its logs:
`docker compose -p <project>-e2e -f test_e2e.yml logs api`.

- **`--build` and `--renew-anon-volumes`**, so a run tests this checkout's
  images and dependencies. The site's `node_modules` and the database are
  anonymous volumes, which compose hands back to a recreated container.
- **The site builds, then stays up.** `--exit-code-from e2e` stops every
  container as soon as one exits, so a build that exits would end the run.
  Its healthcheck reads a marker of its own, `/tmp/built`, so a `dist/` left
  by an earlier run cannot pass it early. The api waits for the site, and the
  runner for a healthy api: global-setup's first request is `/openapi.json`.
- **The api runs without `--reload`.** Playwright writes its reports under
  `website/`, inside the mount at `/app`, and a reload would drop requests in
  flight.
- **Outputs go to the `e2e-outputs` volume**, at `/outputs` in the api and the
  renderer: renders, deliveries, preview frames and fetched media. In the
  checkout, the dev stack would list them as orphans. Inputs stay in the
  checkout's `videos/`: the demo clips the suite makes, and the stub's speech.
- **The runner installs outside the checkout**, in `/tmp/deps`, from copies of
  `package.json` and `yarn.lock`. Installed in place, npm rewrites
  `website/yarn.lock` through the mount. The runner is called by its path, so
  it is the release just installed.
- **Its signing key is written in the file.** It signs this stack's tokens and
  nothing else, and it says it is not a secret.
- **The audio engine is a stub** of joe's media API, with no model and no
  download (`tests/stubs/audio_engine.py`); the api and the renderer reach it
  through vox, as they would joe. It writes `videos/e2e-speech.wav`, four
  seconds holding two bursts of tone, the one clip with sound the captions
  specs need.
- **Reports stay with the run:** `website/playwright-report/`, which CI
  uploads. Nothing is sent to a hosted test service.

### nox

`tests/noxfile.py` is what `./al pytest` and `./al nox` run in the test
container.

- **The default sessions check and change nothing:** `formatting`
  (`black --check`), `lint` and `coverage`. `blacken`, which formats in place,
  runs only by name: `./al nox -s blacken`.
- **The tools' ranges are pinned** (black 26, ruff below 1), so the gate
  fails when the code changes, not when a tool ships. CI's shared format and
  lint jobs install the newest black and ruff, so black's range is its newest
  major.
- **Every session runs from the repository root**, as CI does. From `tests/`,
  black and ruff covered only the tests. ruff finds `pyproject.toml` there and
  matches `extend-exclude` against the root it reports from; `..` with
  `--config` leaves the excludes unmatched, and lints the submodules.
- **`coverage` installs what the image does**: the three locks, alfred, and
  otto and vox from their submodules, all with `--no-deps`. Arguments after
  `--` narrow the run: `./al nox -s coverage -- unit` is the unit tier,
  alfred's quick suite in `./al family test`.

## CI

| Workflow | Runs on | What it does |
|---|---|---|
| `CI.yml` | every push and pull request | the API suite, black, ruff, and the browser suite through `playwright.yml` |
| `playwright.yml` | called by `CI.yml` | `docker compose -f test_e2e.yml up --build --exit-code-from e2e`; reports uploaded |
| `docs.yml` | pull requests; pushes to `main`, `dev`, `docs` | `mkdocs build --strict`; on a push, then `mike deploy` |
| `CD.yml` | pushes and pull requests to `main`; releases | the org's image build, with the submodules |
| `publish.yml` | a `v*` tag | checks the tag, runs the API suite, builds and publishes to PyPI |
| `license-report.yml` | pushes to `main`; pull requests | license reports, never failing |

- **The API suite runs as the image installs**, through the org's `pytest.yml`:
  Python 3.11, the submodules, and `pip_args` installing the three locks and
  both engines with `--no-deps`. The org workflow's defaults are a floating
  3.x (3.14, where `reportlab<4` has no wheel), no submodules and no lockfile.
  The runner has no ImageMagick, so the `needs_imagemagick` tests skip there
  and run in `./al pytest`. `publish.yml` runs the same job as its release
  gate: keep the two in step.
- **The docs deploy waits on the strict build.** mike has no `--strict` of
  its own, and builds the same commit with the same configuration.
- **`CD.yml` passes `submodules: recursive` as a string**, as the org
  workflow's input is typed: the image builds the engines into itself, from
  the tree the suites tested.
- **A release publishes from a tag that names it.** A version tag is a claim
  (`governance/qm/records/DRAFT-version-tags-are-claims.md`): the tag must be
  `v` followed by `alfred/_version.py`'s version exactly, and
  `website/package.json` must agree. A manual dispatch has to start from the
  tag too. The package builds on 3.11 with `pdm build`, which isolates its own
  environment, only after the API suite passes.
- `adr-lint.yml`, `reuse-lint.yml` and `submodule-check.yml` are copied from
  `governance/qm`'s project seed, and keep its versions.

### License report

`license-report.yml` reports the licenses along each of alfred's three
runtime paths, a Python package, an npm frontend and a container image, as the
org's open-license record asks. It never fails a build. Three things would
have to exist before it could:

1. **An allowlist of license identifiers, with normalisation ahead of it.**
   License metadata is too messy to compare raw: alfred's Python packages
   declare about six licenses in more than twenty spellings, and at least one
   npm dependency declares its license only in the deprecated `licenses`
   array. A gate comparing raw strings fails honest packages and passes
   unreadable ones.
2. **Coverage of the runtime path, not only the manifests.** The manifest
   scans come back clean while the deployed stack runs a database image under
   a source-available license. A gate wired to the scans alone would report
   compliance the stack does not have. Closing it takes an SBOM per built
   image, and a reviewed inventory of hosted services and assets loaded from
   elsewhere.
3. **A decision on license compatibility**, a separate question: every
   component can comply on its own while the combination is not
   distributable as declared.

These are prerequisites, not a schedule. Ordering them is a human decision,
recorded in `governance/qm/adr/`.
