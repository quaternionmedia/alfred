# Changelog

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
  the render pipeline, and the DB layer. 95 tests plus 19 strict `xfail`s that
  pin known defects, so fixing one turns the suite red rather than passing
  silently. Includes one real 320×240 encode — the only test that proves the
  product does what it exists to do.
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
  default, so a server with no cloud account can still get a video back -- the
  README calls this "a video editor that works even without a server", and
  until now the only finished-render path went to a Google bucket. This begins
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
  `@recipe`; `docs/recipes/` carries an SVG stub per recipe, and
  `./al recipes` regenerates the recordings.
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
