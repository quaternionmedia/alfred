# Retrospective: release/0.3.0

**Status:** input for governance triage. Not a decision record.
**Scope:** the `release/0.3.0` branch, from adopting the constitution to the
four-stage editor
**Tools:** drafted with an AI coding agent; every claim below was verified by
running the thing it describes, and the ones that were not are marked

## Why this is not in `governance/qm/adr/`

Two reasons, both worth stating so nobody files the next one wrongly. It
records no decision -- it is material *for* deciding, and the ADR template is
explicit that one ADR carries one decision. And `adr/` lives in the governance
submodule, so putting it there would mean a second unpushed submodule commit
alongside the `otto` one below; a handoff document should not add to the thing
it is handing off.

Triage may well produce ADRs from the questions at the end. Those belong in
`governance/qm/adr/`, one decision each.

---

## What this branch turned out to be

It began as "make the test suite runnable" and became a repair of the entire
development loop. That is the single most useful finding for triage: **for most
of this project's recent history the application did not build, did not start,
and could not render a video — and nothing reported any of it.** Not one of
those failures was a bug in the application's own logic.

The pattern repeated often enough to be worth naming:

| Symptom | Where the cause was |
|---|---|
| API image would not build | unpinned base image reached Python 3.14 |
| Frontend bundle would not build | floating `parcel` against a pinned transformer |
| `./al init` failed | unpinned node base reached Node 26, no yarn |
| Website container exited on start | host `node_modules` bind-mounted over the image's |
| No template could draw text | empty host directory mounted over the image's fonts |
| Every render failed | no `videos/` mount, and a cwd-relative path |
| Text templates failed in renders only | the renderer image was never rebuilt |
| The timeline was always empty | the model had no `edl` field |

Seven of those eight are **configuration shadowing or drift**, not code. Five
involve a bind mount or an unpinned version replacing something that worked
with something that did not.

## Governance-relevant outcomes

Things this branch closed, partially closed, or newly exposed. Triage should
decide which of the "opened" items become their own records.

### Closed

- **Reproducible builds.** All base images pinned by digest. The API image
  installs from `requirements.lock`, exported from `pdm.lock`. Without that it
  re-resolves loose ranges on every build, which had the application running
  different versions of `beanie`, `fastapi` and `motor` than the test suite.
  Local and container now match exactly.
- **Two CDN dependencies removed.** The deprecated homepage loaded four images
  from `images.squarespace-cdn.com`. `AGENTS.md` forbids new CDN assets and the
  adoption record lists the existing ones as a gap; deleting that page removed
  four of them.
- **First run needs no network.** Demo projects and demo media are generated
  locally with ffmpeg's synthetic sources. `./al demo` — which downloads from a
  Google Cloud Storage bucket — is no longer on the path to a working editor.
- **Human-only contributorship.** 31 commits, no co-author trailers, verified.

### Partially closed

- **Object storage behind a vendor SDK.** There is now a `Destination`
  protocol; `LocalDestination` is implemented fully and is the default, and the
  existing Google Cloud Storage path sits behind the same interface as
  `BucketDestination`. The SDK is still the only remote implementation, so the
  gap is narrowed rather than closed: the seam exists and one side of it no
  longer requires a cloud account.

### Opened, or newly visible

- **The `otto` submodule now carries a local commit.** `alfred/otto` points at
  `888093a`, which fixes a defect that made five of six templates unrenderable.
  **It has not been pushed.** Until it reaches `quaternionmedia/otto`, this
  branch references a commit no other clone can resolve. This is the one item
  that blocks merge.
- **A `PUT` to a project replaces the whole document.** `fastapi-crudrouter`'s
  update writes the request body over the record, so a partial body nulls
  every field it omits. Observed: a partial save wiped a project's `name` and
  `logic`, the write succeeded because writes are not validated, and every
  subsequent read of that project returned 500. A purpose-built
  `/project/{id}/settings` route avoids it for the one case this branch needed;
  the general defect remains.
- **Unvalidated attribute lookup on user input.** `generateEdl` resolves a
  template with `getattr(templates, clip.name)` on a name from the client. The
  module namespace holds fourteen callables of which five are templates. The
  control plane now validates against an explicit allowlist before the value
  reaches the engine, but `otto` itself is unchanged and would still resolve
  anything in its namespace for a caller that reaches it directly.
- **Hot reload does not work on non-Linux hosts.** inotify events do not cross
  a Docker bind mount from Windows or macOS. Worked around with a polling
  watcher; the underlying constraint is unchanged, and anyone adding tooling
  that assumes filesystem events should know.
- **The e2e suite shares one database with itself.** Tests run fully parallel
  against one stack, so specs that create renders and specs that measure
  render-dependent UI interfere. Handled case by case; a fixture-level answer
  (per-worker data namespaces) would be better and is not written.

## Docs, tests and recipes as one object

`docs/cookbook.md` is generated from the end-to-end specs by
`website/e2e/cookbook.js`, and `tests/unit/test_cookbook.py` fails if the
committed file drifts from them. The suite is the source; the prose is a build
artefact.

The reasoning, for the record: prose describing behaviour goes stale silently,
and a test describing behaviour goes red. Making the documentation a rendering
of the tests means the only way to change what the project claims is to change
something that runs. It is deliberately a parser rather than a Playwright
reporter — a reporter documents the tests that *ran on one machine*, so the
cookbook would quietly shrink whenever something was skipped, and the question
the cookbook answers is "what does this project claim to do".

**Not yet true:** videos are not part of this object. The pipeline renders
video and the suite drives it, but nothing generates demonstration footage from
the recipes. That is the obvious next step and is not built.

## On the tests themselves

The suite grew from 0 to 225 backend tests and 100 end-to-end tests. More
useful for triage than the count: **a review pass found six tests that could
not fail**, and three of those were written during this branch, including one
that compared an element to itself and one that counted renders to decide a
render had succeeded — it passed while the render it queued was failing.

Two habits came out of that and are worth keeping:

1. **Prove a guard fails.** Every tightened assertion in
   `test_stack_config.py` was mutation-tested — comment out the volume, add
   `--production`, reintroduce `version:` — and confirmed to go red.
2. **A skipped test is not a passing test.** Two tests here skipped themselves
   under normal conditions and were rewritten to run.

19 defects are pinned as strict `xfail`, so fixing one turns the suite red and
forces the marker to be removed. That mechanism worked in practice: fixing
`otto`'s `title` template turned the suite red the moment it started passing.

## A second retrospective

[retrospective-verification-discipline.md](retrospective-verification-discipline.md)
covers a method failure rather than a code one: every test number in this
branch was measured against a server whose identity was never established, on a
default port, with a bypass flag I had set myself and left set. The functional
findings here stand; the evidence behind them is weaker than the numbers imply,
and that document says how much.

## What triage should decide

1. **Push `alfred/otto` or revert the pointer.** Blocking.
2. Whether the crudrouter full-replace defect gets its own record, or the
   routers get replaced.
3. Whether `final` — a template that cannot be driven through this API because
   `TemplateData` models none of its required parameters — should be made
   drivable or removed from `otto`.
4. Whether the videos in "docs, videos, tests and cookbook are one object"
   should be generated from the recipes, and if so by what.
5. Whether the remaining CDN assets (a font and two images outside the deleted
   homepage) are in scope for this release or the next.

## Unverified claims in this document

Everything above was checked by running it, with two exceptions, stated plainly:

- The **production** stack has not been started. Every claim here concerns the
  dev stack and the test suites. `production.yml` was edited only to remove the
  obsolete `version:` key.
- **CI has not run.** `.github/workflows/CI.yml` still has its
  `integration_tests` job commented out, so the e2e suite has never executed in
  CI. The comment says the app image would not build, which is no longer true —
  re-enabling it is a decision for triage rather than something to switch on
  unasked.
