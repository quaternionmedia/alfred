# Cookbook

Generated from the end-to-end suite by `website/e2e/cookbook.js`. Do not
edit by hand -- change the tests instead, and regenerate.

Every recipe below is a test that runs against a real stack: a real
database, a real render worker, and real files on disk. If a step here is
wrong, a test is failing. That is the point -- prose describing behaviour
goes stale silently, and a test describing behaviour goes red.

## api contract

Contracts the editor depends on, asserted at the HTTP level.

# Recipe: what the API promises the editor

The browser specs check that the editor works. These check the promises it
is built on, where a change would break the editor without breaking any
assertion about the DOM: which templates exist, what a preview returns, what
a malformed request gets back, and which fields a write may touch.

All of it against the running stack with real data.

### the template preview

`Preview.js` builds this URL for every template clip on the timeline,
and it 404'd for years because the route it named -- `otto/template/...`
-- had never existed on this server.

Rendered past the fade-in: templates carry `fadeIn: 1`, so a frame at
t=0 is the faded-out first frame and every template returns a
near-identical few kilobytes. Asserting a real picture means asking for
one after the fade.

- **renders a real image for every advertised template**
- **refuses a name that is not an advertised template**

  The allowlist is load-bearing, not decorative.

  `generateEdl` resolves a template with `getattr(templates, clip.name)`
  on a name from the client, and otto's module namespace holds fourteen
  callables of which five are templates -- the rest are imports it happens
  to carry. Without the check, `ColorClip` and `rgbToDec` are reachable by
  name from a URL.

- **previewing requires a session**
- **the same request twice gives the same size image**
### malformed input is answered, not crashed on

The editor really does send `undefined`: its routes read a `project`
query parameter that is not always present, and `'/project/' + undefined`
is a string the browser will happily request. Both of these answered
500 -- through two different exception hierarchies needing two
different fixes, one in beanie and one in bson.

- **GET <path> answers <expected>**
### project writes touch only what they claim

- **the settings route saves render settings and destination**

  The guard for a defect that cost a document.

  `PUT /project/{id}` goes through the crud router's update, which
  replaces the whole record with the request body -- so a partial save
  wrote null over `name` and `logic`. The write succeeded, because writes
  are not validated; every subsequent read of that project answered 500,
  because reads are. One request turned a readable project into an
  unreadable one and nothing reported an error until the next reader
  arrived.

- **saving settings leaves the rest of the project intact**

  The guard for a defect that cost a document.

  `PUT /project/{id}` goes through the crud router's update, which
  replaces the whole record with the request body -- so a partial save
  wrote null over `name` and `logic`. The write succeeded, because writes
  are not validated; every subsequent read of that project answered 500,
  because reads are. One request turned a readable project into an
  unreadable one and nothing reported an error until the next reader
  arrived.

- **the project stays readable afterwards**

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
- **the old editor URL lands on the project stage**
- **a selected project offers its template**

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

- **the rail exposes every stage**
- **the header carries no navigation of its own**
- **choosing a stage changes the route**
- **back and forward move between routes**
- **serves the SPA shell at the root**

  This was annotated `test.fail()` as a known defect: the header rendered
  the same links twice, once as a drawer and once as a bar, emitting
  home-link, projects-link, renders-link and login-link
  twice each -- and every clip repeated clipname, inpoint and outpoint, so
  a page with 17 clips carried 52 duplicates.

  Both are fixed: the header renders one list and CSS decides whether it
  is a drawer, and per-clip labels are classes. Invalid HTML either way,
  and `#id` selectors silently address only the first match, which is a
  trap for anything written against this page later.

- **every element id is unique**

  This was annotated `test.fail()` as a known defect: the header rendered
  the same links twice, once as a drawer and once as a bar, emitting
  home-link, projects-link, renders-link and login-link
  twice each -- and every clip repeated clipname, inpoint and outpoint, so
  a page with 17 clips carried 52 duplicates.

  Both are fixed: the header renders one list and CSS decides whether it
  is a drawer, and per-clip labels are classes. Invalid HTML either way,
  and `#id` selectors silently address only the first match, which is a
  trap for anything written against this page later.


## otto

### otto editor

- **<group> are present**
- **action buttons are present**
- **the play control is present**
- **timeline slider is positionable**

## performance

### performance @perf

- **loads the shell within the budget @perf**

## projects

### the project selector

- **the old projects URL redirects into the flow**
- **one row per project, named as the API names them**
- **each row shows what is on the project, not just its name**

  The table showed a name and two icons. Whether a project had anything on
  its timeline — the thing that decides if opening it is worthwhile — was
  not visible until you opened it.

- **each row offers an edit and a create-video action**

  These used to leave for #!/editor and #!/form -- routes with no stage
  rail and no timeline, reachable from this list and unable to get back to
  it. Both now select the project and land on the stage that holds what
  they used to show.

- **the edit action stays inside the flow**

  These used to leave for #!/editor and #!/form -- routes with no stage
  rail and no timeline, reachable from this list and unable to get back to
  it. Both now select the project and land on the stage that holds what
  they used to show.

- **the create-video action stays inside the flow**
- **a project id naming nothing says so and offers a way out**
- **choosing a project opens it on the timeline**

  A filter rather than pagination: the list is small enough to render
  whole, and typing a name beats scrolling for one. It appears only when
  there are enough projects to be worth filtering.

- **the filter narrows the list without losing anything**

  A filter rather than pagination: the list is small enough to render
  whole, and typing a name beats scrolling for one. It appears only when
  there are enough projects to be worth filtering.

- **choosing material puts it on the timeline**

  # Recipe: putting footage on the timeline

  The Material list named every file on the server and offered no way to
  use any of them -- each entry was an `<li>` with text in it. The only
  route from "I have footage" to "it is on the timeline" was to find the
  bin on the editor stage and drag, an affordance with no visible cue,
  unreachable from the keyboard, and on a different stage from the list
  that told you the footage existed.

- **material added without a project survives the next redraw**

  The timeline reloaded its project on every redraw, and the guard meant
  to stop that compared a raw `undefined` against a normalised `null`. So
  with no project selected the comparison never matched, the branch that
  clears the clip list ran about sixty times a second, and anything added
  to the timeline was erased before it could be drawn.

  A count taken immediately would have passed throughout. This one waits.

- **a chosen clip is what the viewer shows**
- **an anonymous visitor is sent to login**

## recipes

The recipes, written to be watched.

# Recipes

These are tagged `@recipe` and are the source of both halves of the
documentation: `docs/cookbook.md` is generated from their titles and
comments, and `./al recipes` records them as video through the `docs`
Playwright project. A demonstration made this way cannot drift from the
behaviour, because it is the behaviour -- and when a recipe breaks there is
no video rather than a misleading one.

They are deliberately unhurried. Every other spec asserts as fast as it can;
these pause between steps so a person watching can follow, which is the one
place in this suite where a `waitForTimeout` is the point rather than a
smell.

Excluded from the `chromium` project, so the gate on every pull request does
not pay for the pauses.

### @recipe walkthroughs

The editor is the first thing the app shows. Three regions, in the order
you work: the **viewer** with the output settings beside it, the
**transport** that moves the playhead, and the **editor** where the
timeline sits with its tools and the media bin beneath.

- **recipe: open the editor and look around**
- **recipe: generate a demo from an empty install**

  A first run needs no downloads. The Source stage offers to generate both
  a project and its media, synthesised locally with ffmpeg's test sources.

- **recipe: choose a project and edit its timeline**

  Choosing a project on the Source stage loads its timeline. The clips are
  laid out left to right, and each one is as wide as it is long.

- **recipe: pick a tool and move the playhead**

  The tools that change clips sit beside the timeline; the ones that move
  the playhead sit above it, in the transport.

- **recipe: render the timeline and deliver the result**

  The Render stage turns the timeline into a video; the Deliver stage
  sends it somewhere. Delivery is local by default, so this works on a
  machine with no cloud account.


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

### the render list

Status and progress lived only in the retired table, and they are what
tells you whether a render can be delivered at all. A row without them
makes the Deliver button a guess.

- **the old renders URL redirects into the flow**
- **render list is available from the API**
- **refuses renders to an anonymous caller**
- **each row shows the state of its render**
- **an unfinished render cannot be delivered**

  There is no file to send until the worker has finished, and a button
  that fails is worse than one that explains itself. The row disables it
  and says why in the title.

  Asserted as a rule over one DOM snapshot, not by picking an unfinished
  render from the API and then looking for its row. That version raced
  the worker: other specs queue renders, so a render chosen as unfinished
  could complete between the API read and the assertion, and the test
  failed for having been right a moment earlier.

- **a delivered render says where it went**

## session

The session lifecycle: refresh, logout, and what a token is worth.

# Recipe: staying logged in, and stopping

The editor keeps a JWT in sessionStorage and sends it as a bearer token. When
a request comes back 401 the app tries `/auth/jwt/refresh` before giving up
and redirecting to the login screen -- so refresh is the only mechanism that
keeps anybody logged in past a token's lifetime, and it is worth testing at
the HTTP level rather than only through the UI.

These are deliberately API-level. The browser path is covered in
views.spec.js ("a reload keeps the session"); what is checked here is the
contract the browser depends on.

### token refresh

This answered 500 for every caller.

The route called `auth_backend.get_login_response(...)`, which has not
existed on fastapi-users' AuthenticationBackend for several major
versions -- it carries `login` and `logout` and nothing else. So the one
path that exists to keep somebody logged in was the one path that could
not work, and a session reaching its expiry failed with a server error
rather than renewing.

- **a valid token can be exchanged for a new one**
- **the refreshed token actually authenticates**
- **refresh refuses an anonymous caller**

  Pinned as a property, not filed as a defect.

  These are stateless JWTs with no server-side revocation list, so logging
  out clears the browser's copy and cannot invalidate a token somebody
  already holds. That is how the mechanism works and it is a real
  consequence: a leaked token stays valid until it expires, and "log out
  everywhere" is not something this design can offer.

  If revocation is ever added this test goes red, which is the moment to
  decide deliberately rather than discover it.

- **refresh refuses a malformed token**

  Pinned as a property, not filed as a defect.

  These are stateless JWTs with no server-side revocation list, so logging
  out clears the browser's copy and cannot invalidate a token somebody
  already holds. That is how the mechanism works and it is a real
  consequence: a leaked token stays valid until it expires, and "log out
  everywhere" is not something this design can offer.

  If revocation is ever added this test goes red, which is the moment to
  decide deliberately rather than discover it.

### logout

Pinned as a property, not filed as a defect.

These are stateless JWTs with no server-side revocation list, so logging
out clears the browser's copy and cannot invalidate a token somebody
already holds. That is how the mechanism works and it is a real
consequence: a leaked token stays valid until it expires, and "log out
everywhere" is not something this design can offer.

If revocation is ever added this test goes red, which is the moment to
decide deliberately rather than discover it.

- **logout succeeds for an authenticated caller**
- **a bearer token still works after logout**
### what a token gets you

The e2e user is not a superuser, so the admin router must refuse it.
A 200 here would mean any registered account can reach the admin
surface, which is the kind of thing that is only noticed deliberately.

- **every gated route refuses an anonymous caller**
- **a token from one login works across every gated route**
- **the admin surface needs more than an ordinary session**

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

- **play advances the playhead, and pause stops it**

  # Recipe: playing the timeline

  The play button had never worked. It called into a component that was
  imported but never rendered, so the element reference it needed was
  always null and the click threw before anything moved.

  What it drives now is the timeline, not a file. That distinction is
  load-bearing rather than pedantic: `POST /demo/project` builds its
  timeline from template clips, so the first project anyone generates is
  entirely stills, and a transport bound to a video element would leave
  it inert -- on exactly the project a new user presses play on first.

- **the transport says so when there is nothing to play**
### the project actions

# Recipe: saving a timeline

The save button posted to `/edl`, which is not a route on this server
and never has been, with a bare `m.request` that would not have carried
a token if it were. The rejection was handled nowhere, so the button
reported nothing. Timelines could not be saved at all.

The name assertion is the point of the second half. The obvious way to
write a timeline back is `PUT /project/{id}`, which replaces the whole
document -- a partial body arrives with `logic` unset, `logic` is
required, and every later GET of that project answers 500. This checks
that saving clips did not take the name with it.

- **saving a timeline persists it, and keeps the rest of the project**
- **the actions say why they are unavailable**

  Viewer, transport, editor. The arrangement used to be a stack of bars
  with related controls apart and unrelated controls together -- aspect
  and resolution floating above the preview, speed buried inside the
  timeline's grid, zoom stranded below it.

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

- **the renders view is now the deliver stage**
- **the documentation links are always to hand**

  This test existed and passed while the Source stage threw on every
  render. It walked the routes that take no parameters, and the throw was
  in the branch that only runs once a project is selected -- so the panel
  produced no DOM at all, and nothing here went near it. Four other specs
  failed on the symptoms (an empty timeline, a missing disclosure, a
  missing warning) and none named the cause.

  So the walk now includes the states a parameter puts the app into: a
  real project, and an id matching nothing.

- **home view loads**

  This test existed and passed while the Source stage threw on every
  render. It walked the routes that take no parameters, and the throw was
  in the branch that only runs once a project is selected -- so the panel
  produced no DOM at all, and nothing here went near it. Four other specs
  failed on the symptoms (an empty timeline, a missing disclosure, a
  missing warning) and none named the cause.

  So the walk now includes the states a parameter puts the app into: a
  real project, and an id matching nothing.

- **each view renders without an uncaught page error**

  This test existed and passed while the Source stage threw on every
  render. It walked the routes that take no parameters, and the throw was
  in the branch that only runs once a project is selected -- so the panel
  produced no DOM at all, and nothing here went near it. Four other specs
  failed on the symptoms (an empty timeline, a missing disclosure, a
  missing warning) and none named the cause.

  So the walk now includes the states a parameter puts the app into: a
  real project, and an id matching nothing.

- **an unknown route does not leave a blank page**
- **a reload keeps the session**
- **logging out survives a reload too**
- **a session does not leak into a fresh browser context**

---

Regenerate with `node website/e2e/cookbook.js`.
