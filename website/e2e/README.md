# End-to-end tests

Playwright, replacing the Cypress suite that lived in `website/cypress/`.

```sh
cd website
npm install
npx playwright install --with-deps chromium

npm run e2e          # the gate: everything except @perf
npm run e2e:perf     # page-load budget, on request
npm run e2e:ui       # interactive runner
npm run e2e:report   # last HTML report
```

`E2E_BASE_URL` defaults to `http://localhost:8000`. `E2E_EMAIL`,
`E2E_PASSWORD` and `E2E_NAME` override the test account;
`E2E_LOAD_BUDGET_MS` overrides the performance budget.

## Why the conversion is not one-to-one

The Cypress suite had eight spec files. Two of them — `auth.js` (74 lines)
and `dnd.js` (150 lines) — were **entirely commented out**: zero live tests
between them. Most of `project.js` and `render.js` was commented out too.

Of the roughly thirteen live cases that remained, few could fail:

- **`window.js` tested the browser, not the app.** That `localStorage.setItem`
  followed by `getItem` returns what was set; that `document` reports a width
  and a height; and one case that set the page background to purple and
  asserted nothing. Copied from a Cypress demo repository. Dropped.
- **Its navigation assertions could not fail.** They checked `#login-link`,
  `#projects-link` and `#renders-link` were visible after history navigation.
  `src/Menu.js` renders all three unconditionally, so the assertions held on
  every route and in both auth states. Repaired here to assert the URL.
- **The login helper never checked that login worked.** `cy.loginUI` typed
  credentials, submitted, then asserted the path was still `/` — equally true
  of a failed login. Nothing registered the test user, so against a fresh
  database every "logged in" test ran logged out and still passed.
- **`project.js`'s one live test was named `adds new project`** and only
  asserted `.projects` was visible. It added nothing.
- **`render.js`'s two live tests asserted nothing at all**; every assertion in
  the file was commented out. One did not log in first.
- **Three `otto.js` selectors matched on inline style attributes**, e.g.
  `[style="width: auto;"] > :nth-child(1)`. Those break on any CSS change and
  name no control. One of them was the "reset speed" button, which has a
  `title` like every other control and is addressed by it here.

The suite also could not run as configured: `cypress.json`,
`cypress/integration/` and `cypress/plugins/` are the Cypress ≤9 layout, while
`package.json` asked for Cypress ^10.11, which requires `cypress.config.js`
and `e2e/`. `test_cy.yml` pinned a third version (`cypress/included:9.7.0`),
and its `CYPRESS_baseUrl` (`http://api/`) disagreed with `cypress.json`'s
(`http://localhost:8000/`). The CI job invoking it was commented out.

## Verification status

The suite was run against a live stack: 24 passed, 1 skipped, twice
consecutively, in about 8 seconds; the `@perf` project passes separately.

That run needed a locally patched application image, because the committed
one does not build. Three independent breaks, all from unpinned or unlocked
dependencies, none of them introduced by this conversion:

1. `FROM python` in the Dockerfile now resolves to Python 3.14, which no
   longer bundles setuptools, so `bezier` fails at `pip install` with
   `No module named 'pkg_resources'`.
2. Pinning the base to 3.11 gets past that and then fails on
   `rm /etc/ImageMagick-6/policy.xml`. The base ships ImageMagick 7, whose
   policy lives at `/etc/ImageMagick-7/`; the 6 path does not exist.
3. `parcel` floats from `^2.8.3` to 2.16.4 while `@parcel/transformer-sass`
   is pinned to exactly `2.8.3`. Parcel requires them to match, so
   `parcel build` fails and there is no `dist/` for the API to serve. Neither
   `yarn.lock` nor `package-lock.json` is committed, which is what lets this
   drift happen at all.

Until those are fixed, `./al test` cannot pass — not because of the tests.
The verification above used `FROM python:3.11`, `rm -f`, and a matching
transformer version, applied to throwaway copies outside the repository.

## Defects this conversion surfaced

- **Duplicate element ids.** The nav bar and the menu bar render the same
  components, so `home-link`, `projects-link`, `renders-link`,
  `documents-link` and `login-link` are each emitted twice on every page.
  This is invalid HTML and makes every `#id` selector ambiguous. Playwright's
  strict mode fails on it; Cypress did not. `navigation.spec.js` records it
  as a `test.fail()` so the suite stays green and turns red when it is fixed.
  Until then `fixtures.js` exports scoped `SELECTORS` that resolve uniquely.
- **The logo renders `src="[object Object]"`**, producing a steady stream of
  404s for `/%5Bobject%20Object%5D` in the API log.
- **`--reload` in a test run.** The image's default command runs uvicorn with
  `--reload`, and the compose file mounts the repo at `/app`. Playwright
  writing `playwright-report/` or `test-results/` under `website/` therefore
  restarts the API mid-run and drops in-flight connections. `test_e2e.yml`
  overrides the command to disable reload; this cost one spurious failure
  before it was diagnosed.
- **`test_cy.yml` mounted `./alfred/` onto `/app`**, shadowing the package
  root that `uvicorn alfred.main:app` resolves against. `test_e2e.yml` mounts
  the repo root, matching `docker-compose.yml`.

## Authentication

There is no `storageState` shortcut here, and this is a property of the app
rather than of Playwright. `src/User.js` keeps the JWT in a module-level
object; nothing is written to a cookie or to storage, so there is no
persisted credential to seed and a reload ends the session. Each test that
needs a session logs in through the form via the `authedPage` fixture.

The commented-out `auth.js` tried to shortcut this by seeding a `user` key
into `localStorage`, which the app never reads. That is consistent with the
file never having worked.

## What is covered

| Area | Where | Level |
|---|---|---|
| Login, logout, bad password | `login.spec.js` | UI |
| Token issue, `/users/me`, 401s | `auth.spec.js` | API |
| Project list authorized + anonymous | `auth.spec.js`, `projects.spec.js` | API + UI |
| Render list authorized + anonymous | `renders.spec.js` | API + UI |
| Routing, history, menu | `navigation.spec.js` | UI |
| Editor toolbar presence | `otto.spec.js` | UI |
| Page-load budget | `performance.spec.js` | UI, `@perf` |

## What is not covered

Nothing below was covered by the Cypress suite either — this is the
inherited gap, not a regression from the conversion.

1. **Rendering.** The core function of the product. Submitting a render,
   watching it progress, and verifying output is never exercised. `POST
   /render`, `POST /render/rerender/{id}`, and the Celery task in
   `alfred/core/utils/tasks.py` have no test at any level.
2. **Project mutation.** Create, update and delete all come from
   `MotorCRUDRouter`. Only the list endpoint is touched; nothing verifies a
   project can be saved or that an edit persists.
3. **Preview.** `POST /preview` is untested, and preview is how a user sees
   their edit before committing to a render.
4. **The timeline editor.** `otto.spec.js` asserts controls exist. No test
   performs a trim, cut, slip, slide or roll, or checks the resulting EDL.
   This is the most complex UI in the product and its behavior is untested.
5. **Video delivery.** `GET /videos/{video}` serves partial content with
   range headers; `alfred/core/responses/partial.py` implements the 206 path
   by hand. Untested, including the path-traversal exposure noted in the
   project's records.
6. **Authorization boundaries.** Admin (`POST /invoice`) and superuser
   routes are never called, as either an admin or a normal user. Nothing
   verifies a normal user is refused.
7. **Registration and password reset.** Registration is exercised only
   incidentally by `global-setup.js`. Reset and verification flows are
   untested.
8. **Fonts, documents, issue reporting.** `GET /fonts`, the documents view,
   and `POST /{item_id}/report` are untested.
9. **Cross-browser.** Only chromium runs. The config takes firefox and
   webkit by adding projects; the product claims mobile support, which
   nothing checks.
