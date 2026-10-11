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
- **A development auth bypass.** `ALFRED_DEV_SKIP_AUTH=1 ./al dev` serves
  every request as a fixed superuser and lets the SPA skip its login screen.
  Off unless explicitly set; refuses to start alongside `ALFRED_PRODUCTION`;
  wired only in `dev.yml`, so a production stack has no such variable to read;
  and the account it uses stores an unusable password hash, so it cannot be
  logged into once the flag is off. Prints an unmissable banner every boot.
  Documented in `docs/dev-auth.md`. Auth proper is the next phase.
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
