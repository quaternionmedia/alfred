# Cookbook

Generated from the end-to-end suite by `website/e2e/cookbook.js`. Do not
edit by hand -- change the tests instead, and regenerate.

Every recipe below is a test that runs against a real stack: a real
database, a real render worker, and real files on disk. If a step here is
wrong, a test is failing. That is the point -- prose describing behaviour
goes stale silently, and a test describing behaviour goes red.

## appearance

Visual consistency, symmetry, and the functionality that depends on them.

Deliberately not screenshot comparison. Pixel baselines differ by platform
and font rendering, so on a Windows host and a Linux CI they disagree about
everything and the suite gets muted -- which is worse than not having it.
These measure the geometry instead: what lines up, what is the same size as
its siblings, and what stays inside the viewport. Those are the properties a
person actually notices, and they hold on any renderer.

The app claims to work "including mobile devices", so every layout assertion
runs at a phone width too.

### layout holds at every width

A page wider than its viewport is the most common and least excusable
layout failure: on a phone it means the whole interface slides
sideways under the thumb. The stage rail scrolls internally by design,
which is why this asserts on the document rather than on every child.

- **no horizontal overflow on <viewport>**
- **the stage rail stays reachable on <viewport>**
### symmetry within the stage rail

- **every stage button is the same height**
- **every stage button sits on the same baseline**
- **the stage numbers are round, not ovals**
- **stages are evenly spaced**
- **exactly one stage reads as current**

  The active stage must differ visually, not just in the DOM. Asserting
  "some colour differs" rather than a specific colour keeps this from
  breaking on a palette change while still failing if the distinction is
  removed altogether.

- **the current stage is distinguishable by more than position**

  The active stage must differ visually, not just in the DOM. Asserting
  "some colour differs" rather than a specific colour keeps this from
  breaking on a palette change while still failing if the distinction is
  removed altogether.

### consistency across controls

Measured against the CSS contract, not against each other.

Comparing buttons to their siblings looked more direct and was not
usable: the Deliver panel lists a button per undelivered render, and the
render-pipeline and flow specs create and deliver renders while this
runs. So the set being measured changed underneath it -- sometimes to
nothing, leaving one button and no comparison to make. The test passed
alone and failed in the full suite, every time, which is the shape of a
shared-state dependency rather than a layout bug.

Every single-line action button should be 2rem tall, allowing a pixel
for flex rounding. That holds whether the panel lists six renders or
none, and still catches the drift this was written for: Render and
Deliver buttons differed by two pixels before stages.scss gave them a
height.

- **panel buttons are all one height, wherever they appear**
- **panel headings share one type treatment**
- **every panel aligns to the same left edge**

  The render button is disabled with an empty timeline. It has to remain
  visible and legible -- an action that vanishes when unavailable reads as
  a broken page rather than a missing prerequisite, and the panel already
  says which step is missing.

- **the rail and the panel below it share an edge**

  The render button is disabled with an empty timeline. It has to remain
  visible and legible -- an action that vanishes when unavailable reads as
  a broken page rather than a missing prerequisite, and the panel already
  says which step is missing.

- **a disabled action still looks like an action**

  The render button is disabled with an empty timeline. It has to remain
  visible and legible -- an action that vanishes when unavailable reads as
  a broken page rather than a missing prerequisite, and the panel already
  says which step is missing.

### the rail works as navigation

- **clicking each stage shows its panel**
- **the stages are reachable by keyboard**

  The point of stages-of-one-view. Whichever stage is open, the timeline
  stays on screen and keeps its clips -- if opening the render settings
  scrolled the work out of view, these would be four routes wearing a
  shared header.

- **the rail is announced as a tablist**

  The point of stages-of-one-view. Whichever stage is open, the timeline
  stays on screen and keeps its clips -- if opening the render settings
  scrolled the work out of view, these would be four routes wearing a
  shared header.

- **the timeline is never displaced by a panel**

  The point of stages-of-one-view. Whichever stage is open, the timeline
  stays on screen and keeps its clips -- if opening the render settings
  scrolled the work out of view, these would be four routes wearing a
  shared header.

### the timeline reads as a timeline

- **clips sit on one row, in order**

  Width encodes duration -- that is what makes a timeline readable at a
  glance. The demo project's clips have different durations, so their
  widths must differ accordingly.

- **a clip is wider when it is longer**

  Width encodes duration -- that is what makes a timeline readable at a
  glance. The demo project's clips have different durations, so their
  widths must differ accordingly.

- **the media bin and the timeline agree on clip appearance**

## auth

### auth API

- **rejects an unauthenticated request for the current user**
- **rejects login with a wrong password**
- **issues a bearer token for valid credentials**
- **accepts that token for the current user**
- **lists projects for an authenticated caller**
- **refuses to list projects without a token**

## demo

Getting started from nothing.

# Recipe: a first run with no projects and no media

An install that has never been used has an empty database and an empty video
directory. Both empty states offer to generate something rather than
describing what you do not have -- the media is synthesised locally with
ffmpeg's test sources, so a first run needs no network access at all.

That last point is governance, not convenience: `./al demo` downloads four
files from a Google Cloud Storage bucket, and the adoption record lists
third-party fetches as an open gap. A first-run path that needs one is a gap
anybody evaluating this project walks straight into.

These tests double as the documentation for that flow. Each `test(...)` name
is a step someone can follow; the assertions are what they should see.

### generating a demo

- **the media generator makes real clips locally**
- **generated media shows up in the media list**
- **generating media twice does not duplicate or destroy it**

  A demo project referring to video files would break the moment those
  files were cleaned up. Templates render from nothing, so the project
  works on an install that has never generated media and never will.

- **the project generator makes a project with a timeline**

  A demo project referring to video files would break the moment those
  files were cleaned up. Templates render from nothing, so the project
  works on an install that has never generated media and never will.

- **the demo project uses templates, so it needs no media on disk**

  A demo project referring to video files would break the moment those
  files were cleaned up. Templates render from nothing, so the project
  works on an install that has never generated media and never will.

- **generating the project twice returns the same one**

  These simulate an empty install rather than emptying the real one.

  Deleting every project would work exactly once and then fight every other
  spec running in parallel -- the first version did, and skipped itself
  whenever another test had created something. Intercepting the two list
  requests makes the state deterministic and tests the thing that actually
  matters here: what the panel does when the server says "nothing".

### the empty state offers a way out

These simulate an empty install rather than emptying the real one.

Deleting every project would work exactly once and then fight every other
spec running in parallel -- the first version did, and skipped itself
whenever another test had created something. Intercepting the two list
requests makes the state deterministic and tests the thing that actually
matters here: what the panel does when the server says "nothing".

- **an install with no projects offers to generate one**

  The rule this replaced two messages to establish: a panel may say you
  have nothing, but not without offering to change that. "No media on the
  server. `./al demo` downloads some." sent you to a shell, and to a
  download from a cloud bucket, before the editor would show you anything.

- **an install with no media offers to generate some**

  The rule this replaced two messages to establish: a panel may say you
  have nothing, but not without offering to change that. "No media on the
  server. `./al demo` downloads some." sent you to a shell, and to a
  download from a cloud bucket, before the editor would show you anything.

- **the empty state never dead-ends**

  The rule this replaced two messages to establish: a panel may say you
  have nothing, but not without offering to change that. "No media on the
  server. `./al demo` downloads some." sent you to a shell, and to a
  download from a cloud bucket, before the editor would show you anything.

- **the offer does not mention downloading anything**

  # Recipe: from an empty install to an editable timeline

  1. Open the Source stage.
  2. Press "Generate a demo project".
  3. Choose it.
  4. The timeline has clips on it.

  Not intercepted: this one presses the button for real, so the project it
  creates is a real one.

- **pressing generate produces a project you can open**

  # Recipe: from an empty install to an editable timeline

  1. Open the Source stage.
  2. Press "Generate a demo project".
  3. Choose it.
  4. The timeline has clips on it.

  Not intercepted: this one presses the button for real, so the project it
  creates is a real one.

- **the generated demo can be rendered**

  The whole point of generating a demo: it has to be usable, not just
  present. Queue a render of it and check the API accepts the job.


## editor

The timeline editor, with a project open.

None of this was testable before: the Project model had no `edl` field, so
every project opened an empty timeline, and there was no way to tell a
broken editor from an empty one. A seeded "Timeline demo" project is what
makes these assertions possible.

The suite finds that project through the API rather than hardcoding an id,
so it survives a reseed.

### timeline editor

- **the demo project is seeded with a timeline**
- **the timeline renders one element per clip**
- **each timeline clip is named after its template**
- **the media bin lists the templates the API offers**
- **the editor opens without a project and asks for one**

  The regression guard for this whole session's frontend work.

  Opening /otto used to produce four failures per visit: a 404 for
  /[object Object] from a broken asset import, a 401 for /videos because
  the bin used a request helper that sends no token, a 404 for
  /otto/templates which never existed, and a 500 for /project/undefined.
  None of them failed a test, because none of them threw.

- **the editor loads a project when given one**

  The regression guard for this whole session's frontend work.

  Opening /otto used to produce four failures per visit: a 404 for
  /[object Object] from a broken asset import, a 401 for /videos because
  the bin used a request helper that sends no token, a 404 for
  /otto/templates which never existed, and a 500 for /project/undefined.
  None of them failed a test, because none of them threw.

- **opening the editor makes no failing requests**

  The regression guard for this whole session's frontend work.

  Opening /otto used to produce four failures per visit: a 404 for
  /[object Object] from a broken asset import, a 401 for /videos because
  the bin used a request helper that sends no token, a 404 for
  /otto/templates which never existed, and a 500 for /project/undefined.
  None of them failed a test, because none of them threw.


## flow

The four-stage flow, end to end, against real data.

Source -> Edit -> Render -> Deliver, driven through the UI, asserted against
the API. Nothing here is stubbed: the projects come from the seeded database,
the templates from the engine's own allowlist, and the delivery moves real
bytes to a real path.

The render stage is the one place this stops short of the whole loop. Queuing
a render hands the job to a Celery worker and an actual encode, which takes
longer than a browser test should wait; these assert that the job is accepted
and recorded, and `test_render_pipeline.py` covers the encode itself with a
real 320x240 file.

### the four-stage flow

- **the timeline is the entry point**
- **the rail names all four stages in order**
- **edit is the stage you land on**
- **the stage survives a reload, because it lives in the URL**
- **stage 1 lists every project the API returns**

  The regression guard for the bug that making `/` the timeline exposed.

  The timeline loaded its project in `oninit` only. Once the timeline was
  mounted at `/`, picking a project became a same-document navigation that
  changed ?project= without remounting anything -- so the first project
  opened was the only one that ever appeared, and no request was made.

- **choosing a project on stage 1 loads its timeline on stage 2**

  The regression guard for the bug that making `/` the timeline exposed.

  The timeline loaded its project in `oninit` only. Once the timeline was
  mounted at `/`, picking a project became a same-document navigation that
  changed ?project= without remounting anything -- so the first project
  opened was the only one that ever appeared, and no request was made.

- **the timeline stays mounted across every stage**
- **stage 3 refuses to render an empty timeline**
- **stage 3 offers the render when there is something to render**

  Built from `GET /destinations`, not hardcoded in the editor.

  Cloud delivery is the next phase, so the server currently offers only
  `local` -- the one that needs no account, which is what makes "works
  even without a server" true of getting your video back as well as making
  it. Asserting against the endpoint rather than a literal means enabling
  a destination is a server change, and this test follows it.

- **stage 4 offers exactly what the server offers**

  Built from `GET /destinations`, not hardcoded in the editor.

  Cloud delivery is the next phase, so the server currently offers only
  `local` -- the one that needs no account, which is what makes "works
  even without a server" true of getting your video back as well as making
  it. Asserting against the endpoint rather than a literal means enabling
  a destination is a server change, and this test follows it.

- **opening the flow makes no failing requests**
### delivery, with real bytes

Driven through the API rather than the UI, because the UI can only
deliver a render a worker has already produced.

This asserted 409-or-502 at first, on the assumption that a freshly
queued render has no file yet. That was true only while renders were
failing: a one-second solid colour now encodes in about a second, so the
file often exists by the time this runs and delivery succeeds. Asserting
the race made the test fail whenever the pipeline got faster, which is
the wrong direction for a test to point.

What is true either way: the answer is a considered one. 200 when the
file is there, 409 when it is not yet, 502 if a destination refuses it --
and never a 500, which would mean the server broke rather than declined.
render-pipeline.spec.js covers the successful path deliberately, after
waiting for the encode.

- **delivering a render always answers sensibly, never a 500**
- **a malformed render id is refused, not crashed on**
- **an unknown destination is refused**
- **delivery requires authentication**

## login

### login UI

- **shows an error for an invalid password**
- **logs in with valid credentials**
- **logs back out**
- **leaves a protected view anonymous for a visitor**

## navigation

### navigation

- **menu exposes the primary sections**
- **menu links change the route**
- **back and forward move between routes**
- **serves the SPA shell at the root**

  This was annotated `test.fail()` as a known defect: the header rendered
  the same links twice, once as a drawer and once as a bar, emitting
  home-link, projects-link, renders-link, documents-link and login-link
  twice each -- and every clip repeated clipname, inpoint and outpoint, so
  a page with 17 clips carried 52 duplicates.

  Both are fixed: the header renders one list and CSS decides whether it
  is a drawer, and per-clip labels are classes. Invalid HTML either way,
  and `#id` selectors silently address only the first match, which is a
  trap for anything written against this page later.

- **every element id is unique**

  This was annotated `test.fail()` as a known defect: the header rendered
  the same links twice, once as a drawer and once as a bar, emitting
  home-link, projects-link, renders-link, documents-link and login-link
  twice each -- and every clip repeated clipname, inpoint and outpoint, so
  a page with 17 clips carried 52 duplicates.

  Both are fixed: the header renders one list and CSS decides whether it
  is a drawer, and per-clip labels are classes. Invalid HTML either way,
  and `#id` selectors silently address only the first match, which is a
  trap for anything written against this page later.


## otto

### otto editor

- **<group> are present**
- **timeline slider is positionable**

## performance

### performance @perf

- **loads the shell within the budget @perf**

## projects

### projects

- **renders the projects list for an authenticated user**
- **table header names the three columns**
- **one row per project, named as the API names them**
- **each row offers an edit and a create-video action**
- **the edit action routes to the template editor for that project**
- **the create-video action routes to the form for that project**
- **an anonymous visitor is sent to login, not to the project list**

## render pipeline

The whole loop, with a video at the end of it.

Queue a render from the browser, wait for the Celery worker to encode it with
ffmpeg, then deliver the result and check the bytes arrived. Nothing here is
stubbed: a real worker, a real encode, a real file.

This is the only test in the suite that waits on an encode, so it is tagged
@slow and given its own timeout. Everything is deliberately small -- 320x180,
one second, a solid colour -- because the point is that the pipeline runs end
to end, not that it can handle a long edit.

It also needs a worker. Where none is running the render never leaves
`queued`, so the wait below reports that plainly rather than timing out on an
assertion that says nothing.

### @slow render pipeline, end to end

- **a render queued from the API becomes a real video file**
- **the finished render can be delivered, and the bytes arrive**
- **delivery is recorded on the render, so it is not repeated blindly**

  The same loop, driven through the UI rather than the API.

  Queue from the Render stage, then watch the Deliver stage list it. This
  is what "generate a video from the browser" means: no direct API call
  for the part a person would do.

- **the browser can drive a render and see it appear**

  The same loop, driven through the UI rather than the API.

  Queue from the Render stage, then watch the Deliver stage list it. This
  is what "generate a video from the browser" means: no direct API call
  for the part a person would do.


## renders

### renders

- **renders view loads for an authenticated user**
- **render list is available from the API**
- **refuses renders to an anonymous caller**

## tools

The timeline tools, and the media they act on.

# Recipe: editing with the timeline tools

The editor is three regions in the order you work: a **viewer** showing the
selected clip with the output settings beside it, a **transport** carrying
everything that moves the playhead, and an **editor** with the timeline
flanked by the tools that change it and the bin that feeds it.

All media here is the generated demo footage -- `POST /demo/media`
synthesises it locally with ffmpeg, so these tests need no downloads and no
cloud account.

### selected media renders

The preview was blank for every video clip.

`<video src="videos/x.mp4">` is a browser-issued request with no
Authorization header, and /videos requires a session -- so it 401'd and
showed nothing. Selecting media in the bin looked like a click that did
not register. The element is handed an object URL fetched with the token
instead.

- **a video clip previews from generated demo footage**
- **a template clip previews as a rendered frame**
- **previewing makes no unauthorised requests**
### the tools pass their events

- **choosing a timeline tool marks it active**
- **only one timeline tool is active at a time**
- **the transport controls are present and clickable**
- **clicking transport controls raises no page errors**

  These call into `Edl.jump`, which indexes the clip list. With an empty
  or short timeline that is where an off-by-one would surface, and a
  thrown handler leaves the toolbar looking fine and doing nothing.

### the editor layout groups its tools

Viewer, transport, editor. The arrangement used to be a stack of bars
with related controls apart and unrelated controls together -- aspect
and resolution floating above the preview, speed buried inside the
timeline's grid, zoom stranded below it.

- **the three regions are present and in order**
- **every region starts on the same left edge**
- **the timeline is the widest thing in the editor**
- **related tools sit in one group, not scattered**
### async actions say they are working

Every action on these panels talks to the server and none of them said
so, so a slow request looked like a click that missed. Buttons carry a
spinner and `aria-busy` while their request is in flight.

- **the render button reports itself busy**
- **a busy button is disabled, so it cannot be double-fired**

## views

### views

- **renders view loads with its heading**
- **documents view loads with its heading**
- **home view loads**
- **each view renders without an uncaught page error**
- **an unknown route does not leave a blank page**
- **a reload keeps the session**
- **logging out survives a reload too**
- **a session does not leak into a fresh browser context**

---

Regenerate with `node website/e2e/cookbook.js`.
