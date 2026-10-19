# Changelog

## Unreleased — review fixes

Fixes from a review of alfred and otto, landed in five rounds of parallel
branches:

| Round | Integrated on | What it carried |
|---|---|---|
| 1 | `integrate/review-fixes` | the render pipeline, auth and ownership, the editor, CI and operations, and the engine (otto `fix/engine-contract`) |
| 2 | `integrate/wave-2` | media access and storage, the editor again, accounts and the timeline API, dependencies, and the engine (otto pinned at e050396, `fix/engine-wave2`) |
| 3 | `integrate/wave-3` | captions through an audio engine (vox vendored at `alfred/vox` beside otto, driving joe), and a Golden Layout workspace for the editor |
| 4 | `integrate/wave-4` | the review's fix round: every setting reaching the services that read it, CI installing what the image installs, the workspace's tab race and the suite's timing races, docs that describe the API as it answers, the timeline's sound written by otto (pinned at f3ceca3, `fix/engine-sound`), an api whose one event loop no longer waits on a preview, and a phone layout that keeps the whole picture on the screen |
| 5 | `integrate/wave-5` | the decisions round 4 stopped at: password hashing off the event loop behind loud safeguards, the media work moved into otto (pinned at 7ddbf10, `feat/engine-media-ops`), a code beside every refusal of the routes qmcp calls, a cap on concurrent previews, support mail sent by the worker, the render extra and the docs build tightened, and `./al family`, which runs alfred with the repositories it works with |

Read **Security** and **Changed** before deploying: several requests that were
accepted are now refused, and a production stack needs its own signing key.

### Security

- **Media names are confined to the library.** A video, image or audio clip
  names `videos/<file>` as `GET /videos` lists it, or an http(s) URL on a host
  in `ALFRED_REMOTE_MEDIA_HOSTS` (empty by default). Absolute paths, `..`,
  backslashes and other schemes are a 422 before anything is stored or queued,
  and the worker re-checks; it used to open `/etc/hostname` when asked.
- **Clients cannot pass ffmpeg options.** `ffmpeg_params` and `bitrate` are
  refused; encoding comes from server presets, `quality` = `draft` |
  `standard` | `high` (default `standard`).
- **Output files are named by render id**, not built from the client's project
  and description.
- **Render jobs travel as JSON, not pickle.** Pickled jobs still queued at
  upgrade are refused by the worker and must be queued again.
- **Renders and projects belong to their creator**, under one ownership rule
  (`alfred/core/utils/ownership.py`): another account gets 404, superusers see
  everything, records from before ownership are superuser-only. `DELETE
  /render` and `DELETE /project` are gone, `PUT /render/{id}` edits labels
  only, and an issue can be reported only about a render you may see.
- **Registration is closed under `ALFRED_PRODUCTION`** unless
  `ALFRED_ALLOW_REGISTRATION` opens it; a closed server answers 403 with a
  reason the register button shows.
- **Every stack signs with a key of its own.** Production (`production.yml`,
  `./al prod`) requires an exported `ALFRED_SECRET_KEY`, not the committed
  stub, and announces a missing or short key at boot. The `.secret_key` stub
  leaves the key empty, and an empty key still signs, so anyone could mint a
  development session: `./al init`, `./al dev` and `./al thin` create a
  git-ignored `.secret_key.local`, and the banner calls an empty key forgeable
  rather than claiming logins will fail.
- **Nothing listens beyond loopback unless asked.** Production keeps MongoDB
  private and serves without `--reload`; the dev stack, flower and `./al docs`
  listen on 127.0.0.1 unless `ALFRED_BIND` widens them, with a warning when
  that meets the auth bypass. A test holds every port every compose file
  publishes to loopback by default.
- **Media is fetched by short-lived signed links, and `/data` is gone.** `GET
  /render/{id}/download`, `GET /videos/{name}` and `GET
  /preview/frames/{name}` take a session or a signed URL
  (`ALFRED_MEDIA_URL_TTL`, 900 s) issued after the route's own checks, so
  `<video>`, `<img>` and downloads stream instead of arriving as whole-file
  blobs. The unauthenticated `/data` mount, which served deliveries and
  template previews, is removed; preview frames are private
  (`ALFRED_PREVIEW_DIR`) and expire (`ALFRED_FRAME_TTL`), and finished renders
  are not listed in the shared media library.
- **Remote media the engine fetches is never served**: it goes to a hidden
  cache (`ALFRED_REMOTE_CACHE_DIR`, passed to otto as `OTTO_DOWNLOAD_DIR`)
  pruned after `ALFRED_REMOTE_CACHE_TTL` (7 days), and a partial download is
  not reused as if whole.
- **The development login cannot be claimed**: registering
  `ALFRED_DEV_USER_EMAIL` is refused, and it gets no reset token or password.
  **An account's email cannot be changed** while ownership is keyed by it
  (422); `docs/ownership.md` plans the move to user ids.
- **Dependencies.** python-multipart 0.0.32 (was 0.0.6), Pillow 12.3 (was
  9.5.0), python-jose, ecdsa and rsa removed, and the lock refreshed within its
  ranges: open advisories in the image's dependencies go from 82 to 20. The
  icon font is served by the app, not fetched from Google.
- **Nothing alfred prints carries a secret.** Reset and verification tokens
  stay out of production logs, and out of development ones once mailed;
  support-mail failures are logged by type and SMTP code, without addresses or
  text; `./al family` redacts what it shows. AGENTS.md makes it a rule: no env
  file, resolved compose config, token, password or signature in a terminal,
  log, commit or report (`docker compose config --no-interpolate`).

### Changed

- **The engine is otto 7ddbf10**, by way of `fix/engine-contract`,
  `fix/engine-wave2` and `fix/engine-sound`. Renders come out at the requested
  size with media fitted inside and centred; `outpoint` trims; `fps` is
  honoured; a clip's own `fadeIn`/`fadeOut` are its only fades (`0` means
  none), and a video clip's sound fades with its picture; `opacity: 0` is
  invisible; audio clips are mixed into the sound instead of crashing the
  render. Each video is probed once per version of its file, and otto installs
  without bezier.
- **A clip the engine cannot render is refused when it is built**, a position
  it cannot place a clip at among them, with a message naming the clip
  (counted from 1): a 422 from the preview, the render's `error` otherwise.
- **The media work is otto's**: preview frames (`renderFrame`), library probes
  (`otto.media.probe`), demo clips (`otto.demo.demoClip`) and encoding
  (`renderMultitrack(preset=...)`, `draft`, `standard` and `high` carrying
  alfred's x264 and AAC settings unchanged). alfred imports no media library
  and runs no ffmpeg; HTTP is unchanged, except that `POST /demo/media`
  answers 503, not an unhandled 500, when the engine cannot start ffmpeg.
- **otto writes a transcription's sound**: `renderSound` mixes the timeline's
  video and audio clips, as long as the whole timeline, into a 16 kHz mono
  16-bit WAV. alfred names only the rate: no codec, ffmpeg option or moviepy
  call is left in the transcription path. A clip otto cannot play is named
  by its place in the whole timeline, its refusal reaching the Captions panel
  in otto's words, without an exception's name in front.
- **The editor renders what it plays.** Every clip goes out with an explicit
  `start` and without fades nobody chose, so three 5-second clips render as 15
  seconds of hard cuts, not 5 seconds of all three overlapping and 10 of black.
- **A saved timeline holds what the editor sent.** Projects store and serve
  their EDL with `exclude_unset`, the editor saves exactly the clips it renders
  (explicit starts and fades), settings and timeline saves write only their own
  fields, and a template's preview is built at the clip's length, as its
  render is.
- **`POST /render` refuses an `fps` outside 1–120 and a frame outside
  16–7680**, with a 422.
- **Renders are written to `ALFRED_RENDER_DIR`** (default `videos/renders`;
  point it at the library to make renders reusable as media) and local
  deliveries to `ALFRED_DELIVERY_DIR` (default `deliveries`, never inside
  DATA_DIR).
- **An empty setting is an unset one**, the signing key aside.
  `ALFRED_RENDER_DIR`, `ALFRED_DELIVERY_DIR`, `ALFRED_DEV_USER_EMAIL` and
  `ALFRED_BUCKET_NAME` took it literally: the working directory, nobody, no
  bucket.
- **Seeds and demos have owners.** `ALFRED_SEED_OWNER` names theirs (in
  development, the dev user), and each account gets one demo project, even
  under simultaneous requests (a partial unique index; projects carry `demo`).
- **Deleting a render removes its files.** Bucket deliveries store a `gs://`
  reference and are signed when asked for; media and byte ranges go out
  uncompressed; workers poll the broker every 0.5 s.
- **Issue reports and invoices are mailed by the worker.** `POST
  /render/{id}/report` and `POST /invoice` answer 202 `{state, job}` once the
  mail is queued, 503 when mail is not set up or the queue is down. The worker
  sends with `ALFRED_SMTP_TIMEOUT` (20 s) and retries a failure that may pass,
  five times over about fifteen minutes; account mail stays on the api's thread
  with the same timeout, and the renderer loads `.email`.
- **A render the broker will not take is a 503 that says so, and is failed.**
  `POST /render` and `POST /render/rerender/{id}` answered a plain-text 500 and
  left the render `queued` for good; they answer 503 `render_not_queued` and
  record the render `failed` with the reason, as transcription does.
- **`GET /health` gains `audio_engine: {configured, ok, detail}`**, `POST
  /render` accepts `captions` and `caption_style`, and httpx is a runtime
  dependency (vox's client).
- **The viewer's frame takes the output's shape at any size**, the transport is
  two rows, and on a phone a stage's panels scroll inside themselves.
- **Python 3.11 only.** numpy 1.26.4; fastapi 0.125 with starlette 0.50;
  beanie 1.30; celery 5.6; imageio-ffmpeg 0.6. Installs use `--no-deps` from
  the lockfiles, because python-multipart overrides fastapi-users' exact pin;
  `requirements-test.lock` pins the test tools.
- **`al[render]` is the engine's own extra** (`al-otto[render]`), and pdm
  resolves al-otto from the submodule, not PyPI, whose 0.2.2 still brought
  bezier: `pdm.lock` and its exports describe the engine the image runs,
  bezier is not locked, and no other locked version changed.
- **Front-end dependencies are current**: golden-layout 2.6.0, mithril 2.3.8,
  parcel 2.16.4, sass 1.105, jwt-decode 4, Playwright 1.64.1 and its runner
  image. golden-layout, mithril and Playwright, which codecartographer also
  uses, match its unmerged `chore/deps-current` (its main has mithril 2.2 and
  Playwright 1.61). json-logic-engine stays at 1.3.9, as 2.x changes how stored
  project logic evaluates; unused babel and cssnano packages are gone.
- **vox moves to faa81a2** (by way of 771c154); nothing alfred calls changes.
  Its stand-in engine judges media requests in joe's order, with joe's
  statuses and sentences, its README says which of joe's refusals the offline
  engine holds a caller to, and its HANDOFF is restamped.
- **production.yml maps `host.docker.internal` to the host**, as dev.yml does,
  so an audio engine beside the stack is reached at the documented address on
  a Linux host too.
- **Test runs use compose projects of their own.** `./al pytest` and `./al nox`
  run as `<project>-pytest`: their throwaway database is a service named `db`,
  like the dev stack's, which a test run recreated. `./al test` runs as
  `<project>-e2e`: it removes its last run's containers and volumes, renews its
  anonymous volumes after a dependency change, and keeps renders, deliveries
  and preview frames on a volume, not in the working tree, so it neither takes
  over a running dev stack nor leaves anonymous volumes behind.
- **The docs site loads nothing from another host** (system fonts, no emoji
  extension), and **the cookbook links only what git tracks**, so each recipe
  shows its committed GIF.

### Fixed

- **Library video clips render.** The worker resolved `videos/x.mp4` against
  its own working directory, which held no videos; it resolves against
  VIDEO_DIR, and the Celery task is registered once.
- **Files are served as asked**: a file over 4 MB whole, a Range request
  exactly its range, a `Range: bytes=-N` longer than the file as the whole
  file, and a missing file as a 404, not a 500.
- **The toolbar Render button renders the project at its size**; it sent query
  parameters the API ignored.
- **A clip added while a project is loading stays on the timeline**, and Save
  saves it.
- **Templates can be added from the bin and the Source stage** and dragged onto
  the timeline, and template clips show their own text, not "Hello, world".
- **Sessions no longer end an hour after login**, logout calls the real route,
  and a login redirect returns to the stage and project it came from.
- **Template backgrounds are drawn in their colour** instead of black,
  textBox's background is drawn at all, and the demo text is readable.
- **Bucket delivery** signs the object it uploaded, and `DELETE /project/{id}`
  no longer answers 500 after deleting.
- **Trim and seek work by touch**; the page has a doctype and can be zoomed on
  a phone.
- **`./al` reports its real version**, and `seed`, `reseed`, `dump` and
  `restore` work; seeding assigns the same owner as startup.
- **A worker started on a fresh database answers pings**, `POST /auth/verify`
  answers 200 (it answered 500 after confirming), and logging in as the
  development login is a 400, not a 500.
- **`./al pytest` tests the locked versions** (it resolved from PyPI), and its
  test image is a stage of the root Dockerfile instead of `FROM alfred_api`,
  whatever that tag held. `./al init` creates the `videos/`
  directory the stacks mount.
- **Scrubbing and zooming land under the pointer**, the timeline keeps its
  clips on one row, and a Deliver-stage reload no longer sends an
  unauthenticated request.
- **The api answers while a preview is drawn.** `POST /preview/`, `GET
  /preview/template/{name}`, `POST /demo/media`, `POST /invoice`, `GET
  /videos`, queueing a render or a transcription, mailing an issue report,
  reading a subtitle file, and the startup font probe and frame sweep run in
  FastAPI's thread pool. Each held the api's one event loop, `/healthz` and
  `/health` included, for as long as it took: thirty seconds for a send to a
  broker that does not answer.
- **A login no longer holds the api.** fastapi-users 10.4 hashed and checked
  passwords on the event loop, about 0.3 s each, so every login, registration
  and reset held every other request; alfred's copies of its five
  password-hashing methods (`utils/passwords.py`) run in the thread pool, and
  with eight logins at once `/healthz` answers in under 10 ms where it took
  1.1-1.6 s. The api refuses to start on a fastapi-users other than 10.4.2, or
  an original whose fingerprint differs, naming what to re-check, and each boot
  logs one `Password hashing:` line naming the override.
- **Demo media is made once, and listed only when whole**: two presses at once
  make each clip once, written under a hidden name and moved into place when
  ffmpeg finishes.
- **A tab chosen in the workspace stays chosen.** It sometimes went behind
  again (Render back over Captions, the rail on Edit) because the workspace
  compared the stage it wrote into the address with the router's copy, a tick
  behind. Both read the address itself; a second tab chosen in that tick is
  written too, and a stage chosen on the rail keeps a project opened a moment
  before.
- **The Captions panel says it is checking the audio engine** until the
  server's health answer arrives, with Transcribe disabled, and follows a
  transcription already under way when the server refuses a second, by its
  code, still showing the server's sentence.
- **Every setting alfred reads reaches the api and the renderer.** dev.yml and
  production.yml pass them by bare name from one list per file
  (`ALFRED_ALLOW_REGISTRATION`, the only way to open registration in
  production, was among those ignored), and `test_stack_settings.py` fails when
  the code reads one a stack does not pass.
- **`./al` lists every command it runs**, and its port guard checks
  `ALFRED_HMR_PORT` and `ALFRED_DB_PORT` as well as `ALFRED_PORT`, names the
  container in the way, and runs for `./al thin` too.
- **The API docs describe the API as it answers.** Render settings go in the
  request body; status is `GET /render/{id}/status`, downloads use the signed
  `download_url`, the preview is `POST /preview/` (with its slash), issues go to
  `POST /render/{id}/report`, `final` is not offered, and a clip's `data`
  carries only otto's `TemplateData` fields. Examples name library media and
  say what a URL needs, preview images are frames the server makes, every
  relative link names its page, and docs/ownership.md no longer names an
  `./al owners` command, which does not exist.
- **On a phone the whole picture is on the screen in every stage**, where it
  showed 41 of 203 pixels at 390x844 and none at 375x667. The viewer keeps the
  frame's room (a quarter of an upright screen, two-fifths of one held
  sideways), the panels and the timeline give way down to floors of their own,
  the stage rail is no longer squeezed, and a screen too short for the floors
  (375x667, or held sideways) scrolls rather than cutting off the column's
  bottom.

### Added

- **`GET /render/{id}/status`** (state, progress and failure reason) and
  **`GET /render/{id}/download`** (Range support, named attachment). The
  Render and Deliver stages follow a render live and offer a Download button.
- **A settings editor for template clips**: text, duration, colours, font,
  size, alignment and position, with the server's reason when a setting cannot
  render. `GET /templates` describes otto's registry; `final` is not offered.
- **Timeline tools**: cut (S splits at the playhead), and slip, slide and dual
  roller, by mouse and touch. Trims stop at the end of the source, and a cut
  template's second half continues its animation.
- **Unsaved timeline edits are offered back** after a reload or a new login;
  the timeline tools are reachable from the keyboard; a notice says when no
  renderer is running.
- **A MongoDB-backed API test tier** (`tests/integration`, `needs_db`) on a `db`
  service in `pytest.yml`.
- **The browser suite runs in CI**, `chromium` and `phone` (390x844), on a
  stack `test_e2e.yml` builds from a clean checkout: site, api, render worker,
  database and a deterministic stub audio engine. `./al test` runs the same
  thing, and does not rewrite `website/yarn.lock`.
- **A `LICENSE` file** stating the MIT licence the package metadata declares.
- **`GET /media`** (duration, size, kind and a signed URL per library file;
  the editor's library clips take their length and kind from it), **`GET
  /health`** (database, renderer workers, queue), **`GET /healthz`**,
  `download_url` on render status and list items, and **`./al storage
  migrate|orphans|cache`** (dry runs unless `--apply`).
- **Password reset by mail** when `EMAIL_SERVER`, `EMAIL_USERNAME` and the new
  `ALFRED_PUBLIC_URL` are set, with a reset page; production passes
  `ALFRED_PUBLIC_URL` through.
- **Captions**, typed in the Captions panel, imported from SubRip, WebVTT or
  JSON with a review step, or transcribed from the timeline's sound by an audio
  engine, and drawn over the viewer under the playhead. Renders draw them as
  textBox clips once the project's caption style enables them (it starts
  disabled). Routes: `GET`/`PUT /project/{id}/captions`, `POST
  .../captions/import`, `POST .../captions/transcribe` (a worker job; 503 with
  no engine, 409 while one runs).
- **vox, vendored at `alfred/vox` beside otto, is the client for the sound**:
  the audio engine's contract (`EngineContract`, which names no engine) and a
  typed client (`vox.media.MediaEngine`), installed editable wherever otto is
  and held to the vendored copy by the stack-config checks.
  `ALFRED_AUDIO_ENGINE_URL`, `ALFRED_AUDIO_ENGINE_TIMEOUT` and
  `ALFRED_AUDIO_ENGINE_CONTRACT_*` configure it; `docs/captions.md` says how to
  point it at joe.
- **`GET /media/{name}/audio`**: the audio engine's analysis of a library file
  (tempo, beats, onsets, loudness, silences, waveform peaks), cached per file
  version.
- **A desktop workspace.** At 1024 px and wider the editor's panels dock in
  Golden Layout 2.6, after codecartographer's shell: moved, resized,
  maximised, closed, kept per browser (a broken arrangement falls back to the
  default), reopened from a Panels menu, reset, and reached from the keyboard.
  `?stage=` links and the rail bring a stage's panel forward; narrower screens
  keep the stage flow, built from the same panels.
- **qmcp can drive alfred over its HTTP API.** qmcp's `feat/alfred-tools` adds
  tools that list projects and templates, queue a render and follow it, and a
  flow that puts a finished render to a person for approval. Its
  `feat/alfred-captions`, built on that, adds tools that transcribe a project's
  captions, read and correct them, burn them into a render and deliver it, and
  a flow that puts the transcript to a person before the captioned render, and
  the render before it is delivered.
- **A code beside every refusal of the project, captions and render routes**:
  `{"detail": "<the same sentence>", "code": "<a word>"}`. The preview cap
  (`previews_busy`), mail to support (`mail_not_configured`,
  `mail_not_queued`), deliveries (`destination_unknown` for an unknown
  destination, `delivery_failed` for a failed one, both still 502) and `GET
  /media/{name}/audio` (`unknown_feature`, `media_silent`,
  `audio_engine_refused`, `audio_engine_failed`) carry codes too.
  docs/api/errors.md lists them
  and what is not covered yet; `tests/unit/test_refusal_codes.py` holds the
  table to the routes and the routes to raising nothing without one.
- **A cap on concurrent previews.** At most `ALFRED_PREVIEW_CONCURRENCY` (4)
  are drawn at once; the rest wait without holding a thread, up to
  `ALFRED_PREVIEW_WAIT` (10 s), then get 503 with `Retry-After`, which the
  viewer waits out before asking once more. `GET /health` reports
  `previews: {running, waiting, limit}`.
- **`./al family`**: alfred with otto, vox, joe, qmcp, codecartographer and
  the org's workflows, from this checkout. `status` says where each repository
  is and whether a vendored pin differs from the checkout beside it or is on
  no origin branch; `test` runs each one's quick suite; `up` starts joe, then
  the dev stack pointed at it; `smoke` checks the running stack live, through
  to a render downloaded by its signed URL and qmcp's alfred tools; then `down`
  and `loop` (docs/family.md).
- **Guards against drift.** `test_blocking_calls.py` fails when a coroutine in
  the api calls something that blocks; `test_event_loop.py` shows `/healthz`
  answering while a preview and demo media are made. Four browser tests no
  longer depend on timing, and the stub audio engine takes what joe takes: its
  twenty content types, its limits, its refusals.
- **The docs are held to what the code offers.** `docs/configuration.md` gives
  every setting, its default, what reads it and how to set it, and what a
  Linux Docker host needs to reach joe; `test_docs_accounted.py` fails when it
  misses a setting alfred reads, docs/family.md one `./al family` reads, or a
  document gives an `./al` command that does not exist.
- **Docs that show first.** `./al recipes` records each recipe as a GIF in
  `docs/recipes/` and takes the screenshots in `docs/assets/screens/`, from
  demo data it builds; the README and the main docs pages open with them, and
  `test_docs_images.py` holds every image to a page that uses it.

### CI and release

- **CI tests on Python 3.11, against the vendored engine and the lockfile.** It
  needs quaternionmedia/.github's `fix/ruff-check-and-python-input` merged
  first, for `ruff check` and the pytest workflow's `python_version` and
  `submodules` inputs; that branch also adds a `requirements` input alfred
  does not use.
- **The api test jobs install the lockfiles `--no-deps`** through the pytest
  workflow's `pip_args`: `requirements.lock`, `requirements-test.lock` and
  `requirements-render.lock`, then the project and both vendored engines,
  `alfred/vox` editable beside otto.
- **The engine's render extra is pinned.** `requirements-render.lock` (gizeh
  0.1.12, cairocffi 1.7.1), exported from pdm.lock's `render` group, is
  installed `--no-deps` by CI.yml and publish.yml, the image and nox, with the
  engine itself `--no-deps -e alfred/otto`, so nothing resolves the engine's
  dependencies on the day and CI can import the text templates. The runner has
  no ImageMagick, so the text-drawing tests skip there and run in the image.
- **Publishing needs a `v*` tag that names the version** in
  `alfred/_version.py`, and the backend suite passing at that commit.
- **Every workflow but three runs on actions that target Node 24**, CI's and
  CD's through the org workflows once `fix/ruff-check-and-python-input` is
  merged. `adr-lint.yml`, `reuse-lint.yml` and `submodule-check.yml`, copied
  verbatim from governance, keep the checkout v4 and setup-python v5 it ships,
  which target Node 20.
- **The deploy workflow passes `submodules: recursive`**, the string
  `build.yml` takes, not the boolean `true`; haiku.yml checks out with
  `actions/checkout@v7`.
- **The docs workflow builds with `--strict`** on pull requests and before each
  deploy, which runs from pushes only; mkdocs.yml's `validation:` warns on
  every page, link and anchor check, and MkDocs is held below 2.

### Measured

| Round | On | `./al pytest` | `./al test` | Also |
|---|---|---|---|---|
| 1 | f0e8cb3 | 699 passed, 2 skipped, 8 xfailed | 212 passed, 1 skipped | |
| 2 | `integrate/wave-2` | 1118 passed, 2 skipped, 8 xfailed | 281 passed, 1 skipped | |
| 3 | `integrate/wave-3` | 1464 passed, 2 skipped, 8 xfailed | 381 passed, 1 skipped, across `chromium` and `phone`, including the `@slow` specs that encode on otto and transcribe through vox and the stub engine | Live, against joe on the host: a synthesised spoken line was transcribed into three timed captions and rendered with them drawn in |
| 4 | `integrate/wave-4` | 1567 passed, 2 skipped, 8 xfailed, from a fresh clone | 389 passed, 1 skipped on the final commit; none passed only on retry in any of three full runs from a fresh clone | CI's install, emulated in a clean container: 1378 passed, 191 skipped (the database tier and the text-drawing tests), none failed. `mkdocs build --strict` without a warning. Live, against joe on the host: the 28 checks of the API pass, and qmcp's tools queued a render with the project's captions and were handed its signed download |
| 5 | `integrate/wave-5` | 1810 passed, 2 skipped, 8 xfailed, from a fresh clone | 391 passed, 1 skipped; none passed only on retry | CI's install, emulated: 1619 passed, 193 skipped, none failed. `mkdocs build --strict` without a warning. `./al family loop` against the round's branches of joe, qmcp and vox: every repository's quick suite green, and the live check's nine checks passing against a joe with nothing but its media API turned on |

## 0.3.0 — breaking

The release that made the project buildable, testable and governed. Nothing
in it is a feature; a good deal of it is removal.

Read the **Breaking** section before upgrading. Several changes alter runtime
behavior rather than only the developer experience.

### Breaking

- **The database is seeded on startup, for real.** `count_documents` on a
  motor handle returns a `Future`, which is always truthy, so the guard
  `if not db.Project.count_documents({})` never fired and the seeding block
  had never run. Awaiting it means an **empty `Project` collection now
  receives the three demo projects**. Any deployment relying on an empty
  collection staying empty is affected.
- **`get_client()` lost its `database` parameter.** It never did anything.
  Callers passing it must drop it.
- **`deOid` is gone** from `alfred.core.utils`. It was defined, exported, and
  referenced only by a commented-out import.
- **`alfred.core.utils.__all__` holds names rather than function objects.**
  `from alfred.core.utils import *` previously raised `TypeError`; it now
  works, which changes what that import binds.
- **Cypress is removed** — suite, config, `test_cy.yml`, the `.cypress` key
  file, and the Cypress Cloud recording step. `./al test` now runs Playwright
  via `test_e2e.yml`.
- **`./al bats` is removed.** It invoked `test_bats.yml`, which has never
  existed in this repository.
- **Base images are pinned by digest.** Builds no longer track upstream
  `latest`; bumping is now a deliberate commit.

### Fixed

- **The application image did not build.** `FROM python` had reached Python
  3.14, where setuptools is not bundled, so `bezier` failed at `pip install`
  with `No module named 'pkg_resources'`. Pinning the base exposed a second
  failure underneath it: `rm /etc/ImageMagick-6/policy.xml` on a base that now
  ships ImageMagick 7. Both fixed; `setuptools` is an explicit dependency
  because three installed packages import `pkg_resources` at runtime without
  declaring it.
- **No fonts in the API image, so no template could draw text.** `dev.yml`
  mounted `./alfred/otto/fonts` over `/usr/share/fonts/truetype/`, and that
  host directory is empty -- so the mount replaced the image's eight fonts
  with nothing. fontconfig reported 0 fonts, ImageMagick reported 0, and
  `TextClip` failed, which otto catches and turns into a `None` return.
  `generateEdl` reports that as "A clip did not get made properly", naming
  neither fonts nor ImageMagick. Five of the six templates are TextClip. The
  mount is now a subdirectory, so project fonts are additive, and the image
  installs `fonts-urw-base35` because moviepy defaults to `Courier`, which the
  base does not ship.
- **`alfred.core.models.__all__` held classes rather than names**, so
  `from alfred.core.models import *` raised TypeError. The identical defect
  was fixed in `alfred.core.utils` earlier in this release; it was in two
  modules and the test written for the first did not cover the second.
- **The logo was broken on every page.** `import LOGO from './assets/...png'`
  yielded an object rather than a URL, so the img src was literally
  `[object Object]` and the browser requested `/[object%20Object]` -- eleven
  404s per session in the API log. The favicon had the same fault in dark
  mode. Both now use `new URL(..., import.meta.url)`.
- **The media bin never loaded videos.** `Bin.js` used `m.request` rather than
  the `auth` helper, so `/videos` was called with no Authorization header and
  answered 401 on every open. The rejection was unhandled, so the bin simply
  rendered nothing.
- **`/project/undefined` and `/render/undefined` returned 500.** The editor
  really does send that -- its routes read a `project` query parameter that is
  not always present. The two failed through different exception hierarchies
  and needed separate fixes; both now answer 422, and the frontend no longer
  makes the request at all.
- **`/users/me` returned an unusable id** -- `{}` under real authentication,
  `null` under the dev bypass, while the stored user had a real ObjectId in
  both cases. Three things were wrong in sequence. Subscripting the generic
  base left `UserRead.id` typed `typing.Any`. Typing it correctly exposed the
  next: FastAPI serialises through `jsonable_encoder`, which has no rule for a
  `bson.ObjectId` subclass and falls back to `vars(value)` -- and an
  ObjectId's `vars()` is `{}`. Adding `json_encoders` to Config fixed the
  model in isolation and changed nothing on the route, because FastAPI clones
  a response model into a fresh class and the clone does not carry Config. The
  fix is a pre-validator, which belongs to the field and survives the cloning.
- **The dev stack's website container took its dependencies from the host.**
  `docker-compose.yml` mounts `./website` over `/app`, and the image shipped no
  `node_modules` at all, so every dependency the container used came from
  whatever the host had installed. parcel resolves a native binding per
  platform: an Alpine container needs `@parcel/rust-linux-x64-musl`, and a
  Windows or macOS host installs a binding for itself and nothing else. The
  container exited 1 on startup with `Cannot find module
  '@parcel/rust-linux-x64-musl'`. Following the documented setup -- a host
  install, which the README asks for to get Playwright -- broke the documented
  dev command. The image now installs its own dependencies with
  `--frozen-lockfile`, and an anonymous volume keeps the host's out of the
  container. Host installs are now harmless.
- **The frontend bundle did not build.** `parcel` floated to 2.16.4 against
  `@parcel/transformer-sass` pinned at exactly 2.8.3, which parcel requires to
  match. `yarn.lock` is now committed so the two cannot drift apart again.
- **`./al init` did not work.** `website/Dockerfile` tracked
  `node:current-alpine`, now Node 26, where yarn is not bundled; the image fell
  through to `node yarn install`.
- **The Python test suite could not even be collected**, by the same
  `pkg_resources` absence, via `passlib`.
- **A new MongoDB client and connection pool per call.** `get_db()` is called
  per request in the fonts route. Clients are now reused, keyed on the running
  event loop — a motor client bound to one loop raises `Event loop is closed`
  on another, so a global singleton would have worked in the server and broken
  every test.
- **`get_client(db_url=...)` and `get_db(database=...)` ignored their
  arguments** and used module constants. `get_sync_db` gained the `db_url`
  parameter it lacked.
- `test_login_fail` posted to `/auth/login`, which has never been a route, and
  asserted the 405 that the catch-all SPA mount returns for any non-GET. It
  tested nothing about authentication and has been replaced.
- **The video routes named one directory two ways** -- a relative `videos`
  in one route and `/app/videos` in the next -- and listing a missing
  directory answered 500. Both read `VIDEO_DIR`, which is created if absent.
- **The browser suite dropped connections under its own load.** Each of eight
  parallel workers logged in for every test against one `uvicorn --reload`
  process, which surfaced as `socket hang up` on `POST /auth/jwt/login` in
  whichever test was logging in. The token fixture is worker-scoped.
- **`/auth/jwt/refresh` answered 500 for every caller.** It called a method
  fastapi-users no longer has, so the one path that keeps a session alive
  could not work. Refresh and logout are covered.
- **Concurrent template previews overwrote each other's frames**, written to
  `data/<timestr>.jpg` at one-second resolution. Frames get unique names.
- **The stage panels stayed empty after a reload**: the flow loaded before the
  session was restored and never retried. It retries, and the Source stage
  re-reads on entry.
- **Logging in returned to the login form** when the redirect parameter was
  empty or absent. It lands on the application.
- **The Source stage could render nothing at all.** A keyed vnode among
  unkeyed siblings made mithril reject the fragment during render.
  `views.spec.js` walks every stage with a project selected, and with an id
  that matches nothing.
- **A request failing with anything but 401 never settled**, so a 500 left a
  button spinning; and a deep link redrew before its data was stored.
- **Play, pause and the speed controls never worked.** The transport called
  into a `Monitor` that was never mounted. Playback drives the timeline, so a
  project of template stills plays.
- **Nothing could be added to a timeline without a project.** A guard compared
  `undefined` with `null` and cleared the clip list on every redraw.
- **Trim resized clips it was not dragging, Save had never saved, and Render
  posted the wrong shape.** `PUT /project/{id}/timeline` writes the clips and
  nothing else; Render sends `{edl: {clips: [...]}}` with its token.
- **A template missing a field answered 500.** `GET /preview/template/{name}`
  answers 422 with the reason, and the viewer prints it.
- **The lint and format gates checked nothing.** `ruff -v .` is a usage error
  on current ruff, and both sessions ran from `tests/`, so `alfred/` was never
  read. Both gates run over the application at pinned versions with an
  explicit rule set, and what they surfaced is fixed, among it a mutable
  default that carried one mail's attachments into the next.
- **Every module touching authentication failed to import** under setuptools
  81, which removed the `pkg_resources` that `passlib` imports. setuptools is
  capped below 81 until fastapi-users moves to pwdlib.
- **A local browser run against the dev stack is capped at four workers**, so
  the single reloading server is not driven past what it serves.

### Added

- **Backend test suite**: config validity, input selection, output selection,
  the render pipeline, and the DB layer. 236 tests plus 19 strict `xfail`s
  that pin known defects, so fixing one turns the suite red rather than
  passing silently. Includes one real 320×240 encode — the only test that
  proves the product does what it exists to do.
- **Playwright end-to-end suite** replacing Cypress, with an authenticated
  fixture that actually asserts the login took effect. The Cypress helper did
  not, and nothing registered the test user, so every "logged in" test had been
  running logged out and passing.
- **Governance**: the QM constitution vendored at `governance/qm`, `AGENTS.md`
  with tool pointers as real symlinks, the ADR lint, and a report-only license
  workflow covering all three runtime paths.
- **The timeline editor works.** It never had data to open: `OttoTimeline`
  reads `project.edl` and the `Project` model had no `edl` field, so the value
  was always undefined. `Project.edl` is now an optional `Edl` -- the same type
  `Render` already uses -- and a "Timeline demo" project is seeded with three
  template clips that need no media files on disk.
- **`GET /templates`.** The editor's media bin has always requested a template
  list on init and no such route existed, so the bin was permanently empty and
  the 404 went unremarked because the rejection was unhandled. Backed by an
  explicit allowlist rather than `dir(otto.templates)`: the module namespace
  holds fourteen callables of which six are templates, the rest being imports
  it happens to carry.
- **`GET /preview/template/{name}`.** Renders one template to a frame, so the
  editor can show what a template clip looks like. `Preview.js` has built this
  URL since before it existed. The name is validated against the allowlist --
  which matters, because `generateEdl` resolves templates with
  `getattr(templates, clip.name)` on a client-supplied name.
- **The session survives a reload.** The JWT lived in a module-level object,
  so refreshing any page logged you out. It is kept in `sessionStorage` now
  and restored before routing, so no guarded view flashes the login screen
  first. sessionStorage rather than localStorage: it is scoped to one tab and
  cleared when the tab closes, and the token already passed through
  localStorage momentarily for cross-tab sharing, so this adds no new class of
  exposure. Expired tokens are discarded on restore rather than presented,
  since a UI that renders as logged in and then 401s on every request is worse
  than one that asks you to log in.
- **The timeline is the entry point.** `/` rendered a marketing homepage --
  four screenshots and a Hitchcock quote -- so the first thing the app showed
  was a description of itself rather than the thing it does. It is gone, and
  with it four images loaded from `images.squarespace-cdn.com`, which
  `AGENTS.md` forbids and the adoption record lists as an open gap.
- **The render pipeline produces a video.** It could not before: the renderer
  container had no `videos/` mount, so every encode died on "Error opening
  output videos/....mp4: No such file or directory" -- recorded as a failed
  render and nowhere else. The path is now absolute and configured
  (`VIDEO_DIR`), which is what the delivery endpoint reads too; it had been
  looking in `DATA_DIR` and would have reported every render missing.
- **A render is marked `RENDERED` when the encode finishes.** The task ran the
  encode and the cloud upload inside one `try`, so a missing credentials file
  marked a perfectly good video as a failed render -- which on a checkout
  without GCS credentials is every render. `status` is also modelled on
  `Render` now; the logger had always written it and the API had always dropped
  it, so a caller could watch progress reach 100 and still not know whether the
  render succeeded.
- **Render filenames include the render's id.** Everything else in the name can
  repeat, so two renders of the same project in the same second produced the
  same filename and the second silently overwrote the first's output. Three
  concurrent renders in the e2e suite collided on exactly that, shared one
  file, and each reported success.
- **`aria-selected` carries a value.** Mithril rendered the boolean as a bare
  `aria-selected=""`, the HTML boolean form, which conveys no state to a screen
  reader at all.
- **`PUT /project/{id}/settings`.** A project remembers the size it renders at
  and where its output goes, which is what makes the flow reusable rather than
  a wizard re-run from scratch. A separate route from the project's own PUT:
  the crud router's update replaces the whole document, so a partial body
  writes null over every field it omits. That is not theoretical -- doing it
  wiped a project's `name` and `logic`, and every subsequent `GET` of that
  project answered 500, because writes are not validated and reads are. The
  settings route names the two fields it may write and touches nothing else.
- **A four-stage flow, as one view.** Source, Edit, Render and Deliver are
  stages of the timeline page rather than separate routes, so the thing being
  worked on stays on screen while its settings are adjusted. The stage lives in
  the URL, so a reload or a shared link lands where the person left off. A
  saved project carries what each stage needs, which is what makes the flow
  reusable rather than a wizard you re-run from scratch.
- **A destination seam, with local delivery.** `POST /render/{id}/deliver`
  sends a finished render somewhere and records where it went.
  `LocalDestination` is implemented fully; the existing Google Cloud Storage
  path becomes `BucketDestination` behind the same interface. Local is the
  default, so a server with no cloud account can still get a video back; until
  now the only finished-render path went to a Google bucket. This begins
  paying down the vendor-SDK gap the adoption record flags.
- **A development auth bypass.** `ALFRED_DEV_SKIP_AUTH=1 ./al dev` serves
  every request as a fixed superuser and lets the SPA skip its login screen.
  Off unless explicitly set; refuses to start alongside `ALFRED_PRODUCTION`;
  wired only in `dev.yml`, so a production stack has no such variable to read;
  and the account it uses stores an unusable password hash, so it cannot be
  logged into once the flag is off. Prints an unmissable banner every boot.
  Documented in `docs/dev-auth.md`. Auth proper is the next phase.
- **Demo media and a demo project, generated rather than downloaded.** Both
  empty states of the Source stage offer to generate. `POST /demo/media`
  synthesises three clips from ffmpeg's own test sources and skips any that
  exist; `POST /demo/project` creates a template-only project with an upsert,
  so pressing it twice makes one project. Nothing is fetched from a third
  party.
- **`docs/cookbook.md` is generated from the end-to-end specs** by
  `website/e2e/cookbook.js`, and `tests/unit/test_cookbook.py` fails when the
  committed page differs from what regenerating it produces.
- **Governance current with `project/alfred`.** `governance/qm` moves to the
  project branch's propagated head, which brings the seed's
  `submodule-check.yml`, `reuse-lint.yml` in the reporting mode its header
  prescribes, and the current `adr-lint.yml`, which runs the ADR lint from
  the submodule. `docs/retrospective-0.3.0.md` hands this release to
  governance triage.
- **`./al dev` says which server owns its port.** Every published port is
  overridable (`ALFRED_PORT`, `ALFRED_DB_PORT`, `ALFRED_HMR_PORT`). `./al dev`
  refuses to start on a port that already answers and names the occupant by
  its OpenAPI title, recognising its own stack; the browser suite refuses to
  run against anything but Alfred.
- **Recipe recordings.** A `docs` Playwright project records the tests tagged
  `@recipe`, and `./al recipes` regenerates the recordings. They stay local
  (`docs/recipes/*.webm` is gitignored); the collector writes an SVG stub per
  passing recipe into `docs/recipes/` to be committed in their place, and none
  is committed yet.
- **Material entries add to the timeline**, as buttons that say what clicking
  does, and controls that cannot act name the missing precondition.
- `CONTRIBUTING.md` and a pull request template. `./al nox` runs in the
  container.
- **`./al thin`**: the dev stack without the renderer, the Celery worker that
  carries moviepy, ImageMagick, ffmpeg and a font set. `thin.yml` composes
  after `docker-compose.yml` and `dev.yml` and leaves it out; a queued render
  waits and never reaches `RENDERED`.
- `CHANGELOG.md`, and dev-server notes in `AGENTS.md` for the two things that
  bite on a first run.

### Removed

- `.github/workflows/bats.yml` and `nox.yml` — reusable workflows nothing
  called; `bats.yml` invoked a compose file that does not exist.
- `website/src/logic.js`, `resizable.js`, `sortable.js` — zero import or
  require sites, so parcel could not reach them from the entry point.
  Confirmed by rebuilding: the JS bundle's content hash is unchanged either
  side of the removal (`website.5e1ea2fd.js`, 279.86 kB), so the three files
  contributed nothing to the artifact. `logic.js` was also the source of a
  false claim that the frontend loaded media from a Google Cloud Storage URL —
  the string was in the sources and never reached the bundle.
- The obsolete `version:` key from every compose file, which warned on every
  invocation.
- The standalone routes `#!/editor`, `#!/form`, `#!/documents`,
  `#!/projects` and `#!/renders`, retired into the four-stage flow; their URLs
  redirect. The header's PROJECTS and RENDERS links, which duplicated the
  stage rail.

### Known, unresolved

Enumerated with reproductions in the adoption record under `governance/qm/adr/`
and in `tests/README.md`. The largest: MongoDB is SSPL-licensed and fills
three roles at once; object storage is reached through a vendor SDK rather
than a protocol seam; the frontend loads a font and two images from third-party
CDNs; and `renderMultitrack` ignores its own `fps` argument, so a caller asking
for 60 silently gets 30. And `final` is
advertised by no allowlist: it requires `address`, `website` and `phone`, and
`TemplateData` -- the only shape a clip's `data` can take -- models none of
them, so it cannot be driven through this API at all.
