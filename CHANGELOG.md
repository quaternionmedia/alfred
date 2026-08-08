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
for 60 silently gets 30.
