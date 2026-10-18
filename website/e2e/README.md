# End-to-end tests

Playwright, replacing the Cypress suite that lived in `website/cypress/`.

The whole suite, on a stack built from the checkout -- the site, the api, a
render worker for the `@slow` specs, and the database -- in Docker:

```sh
./al test
```

Or from the host, against a stack you are already running:

```sh
cd website
yarn install
npx playwright install --with-deps chromium

yarn e2e             # the gate: everything except @perf and @recipe
yarn e2e:perf        # page-load budget, on request
yarn e2e:ui          # interactive runner
yarn e2e:report      # last HTML report
```

`E2E_BASE_URL` defaults to `http://localhost:8000`. Before the first test,
`global-setup.js` fetches `/openapi.json` from it and fails the run unless the
title is `Alfred API` -- a published port belongs to whoever bound it first,
and this suite has been run against a different QM service that also defaults
to 8000, producing real measurements of the wrong program. If that guard
fires, start Alfred elsewhere (`ALFRED_PORT=8100 ./al dev`) and point the
suite at it. `E2E_EMAIL`,
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

`./al test` on `integrate/review-fixes`: **212 passed, 1 skipped, in 3.3
minutes**, including the `@slow` specs that wait on a real encode. The skip is
data-dependent: the project filter test needs more than three projects.

The three image breaks recorded when this suite replaced Cypress -- `FROM
python` reaching 3.14, the ImageMagick 6 policy path on an ImageMagick 7 base,
and `parcel` drifting with no lockfile -- are fixed: the base is pinned by
digest, the policy is edited where ImageMagick 7 keeps it, and `yarn.lock` is
committed. The run installs its npm dependencies outside the checkout, so it
no longer rewrites `website/yarn.lock`.

## Defects this conversion surfaced

All four are fixed; `navigation.spec.js` now asserts there are no duplicate
ids, and the logo, reload and mount problems are gone with their causes.

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

There is no `storageState` shortcut here. `src/User.js` keeps the session in
`sessionStorage`, so it survives a reload in the same tab and ends with the
tab, and it renews the token while the editor is in use. Each test that needs
a session logs in through the form via the `authedPage` fixture, which also
proves the login took effect. `session.spec.js` covers renewal, staying logged
in and logout; `views.spec.js` that a reload keeps the session.

## What is covered

| Area | Where | Level |
|---|---|---|
| Login, registration (incl. closed registration), password reset and confirmation pages | `login.spec.js` | UI |
| Token issue, `/users/me`, 401s, project ownership | `auth.spec.js` | API |
| Token renewal, staying logged in, logout | `session.spec.js` | UI |
| Project selector and its filter | `projects.spec.js` | UI + API |
| Demo project and media, empty states | `demo.spec.js` | UI + API |
| The four-stage flow, delivery with real bytes | `flow.spec.js` | UI + API |
| Timeline editor, transport, saving | `editor.spec.js`, `tools.spec.js`, `otto.spec.js` | UI |
| Trim, cut, slip, slide and roll, by mouse and touch | `timeline-tools.spec.js` | UI |
| Adding and editing template clips, fonts and placement | `templates.spec.js` | UI |
| The timeline tools from the keyboard, the footer | `editor-access.spec.js` | UI |
| Media lengths and kinds, signed media and download URLs, the `/videos` fallback | `editor-media.spec.js` | UI |
| Unsaved timelines kept across a reload or a new login | `editor-draft.spec.js` | UI |
| The render request: clip starts, fades, toolbar, form | `editor-render.spec.js` | UI |
| Render checks before queueing, status, another user | `render-api.spec.js` | API |
| Render pipeline end to end, downloads, ranges | `render-pipeline.spec.js` | API, `@slow` |
| Following a render, downloading it, no renderer running | `deliver.spec.js` | UI |
| Render list | `renders.spec.js` | API + UI |
| Preview contract, malformed input, partial writes | `api-contract.spec.js` | API |
| Routing, history, menu, unique ids | `navigation.spec.js` | UI |
| Views render, no uncaught page errors, reload | `views.spec.js` | UI |
| Layout at every width | `appearance.spec.js` | UI |
| Recipe walkthroughs (the cookbook) | `recipes.spec.js` | UI, `@recipe` |
| Page-load budget | `performance.spec.js` | UI, `@perf` |

The project assertions read the expected set from `GET /project` rather than
hardcoding names, so they survive a different seed.

The uncaught-page-error check is worth more than it looks: a mithril view that
raises during render leaves the page half-drawn without failing any request,
so no other test in this suite would notice.

## What is not covered

1. **Password reset and confirmation, end to end in a browser.** The token
   only ever reaches a mailbox, so `login.spec.js` answers the account pages'
   requests itself; the API side, from the request to logging in with the new
   password, runs in `tests/integration/test_password_reset_api.py`.
2. **Fonts and documents.** The template fields' font list is served by the
   specs, not read from the fonts the server found; the documents view is
   exercised only by the views rendering.
3. **Editing gestures from the keyboard.** The timeline tools are chosen from
   the keyboard, but trim, slip, slide and roll are pointer drags.
4. **Cross-browser and real devices.** Only chromium runs. Touch is covered
   through pointer events, not on a phone; the config takes firefox and webkit
   by adding projects.
5. **Cloud delivery.** The server offers only `local`; a bucket destination is
   tested at the unit level, never against a real bucket.
