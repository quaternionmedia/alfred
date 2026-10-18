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

Rendered at a time past where a fade would end. The preview builds its
clip with no fades unless the query asks for them, so t=0 would do as
well today -- but a frame from a fade is a near-identical few kilobytes
for every template, and asking for one after it keeps this asserting a
real picture whatever the fade defaults become.

- **renders a real image for every advertised template**
- **refuses a name that is not an advertised template**

  The allowlist is load-bearing, not decorative.

  otto's module namespace holds far more callables than templates --
  `ColorClip`, `rgbToDec` and the rest are imports it happens to carry.
  otto now resolves names through its own `TEMPLATES` registry, but this
  server's allowlist is what decides what it offers: `final` is in otto's
  registry and deliberately not offered here, since a clip cannot carry
  the address, website and phone it shows. Each of these must answer 404.

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
### project ownership

Any account could read, overwrite and delete any project. Somebody
else's project answers 404 now -- the same as one that does not exist,
so the answer does not confirm the id is real.

- **a project you create is yours**
- **another account can neither list nor open it**

## deliver

Following a render from queued to delivered.

# Recipe: watching a render finish

Queue a render and the Deliver stage follows it: the row moves from queued
to rendering with a progress bar, then to rendered -- or to failed, with the
reason. Nothing needs reloading. It used to be a snapshot of the moment the
stage opened, so a render looked queued for as long as you watched it.

The status and download routes are answered here rather than by a worker:
what is under test is what the page does with each answer, and a real encode
cannot be made to pause at 40% on cue. render-pipeline.spec.js drives the
real thing end to end.

### a queued render is followed until it settles

Queue from the Render stage and watch the row on Deliver: a bar and a
percentage while it renders, then "rendered" with Download and Deliver
enabled. Once it has settled nothing goes on asking about it.

- **the row moves from queued, through progress, to rendered**
- **a failed render says why, and the words stay words**

  The reason a render failed is shown under its row and in a
  notification. Notifications are HTML, and a reason is whatever the
  encoder printed, so it is escaped: angle brackets stay text.

- **without a status route, the render list is read instead**

  The status route is new. Against a server that predates it -- 404 --
  the page falls back to the render list rather than giving up, and asks
  the missing route only once.

- **a render already on the list keeps moving while the stage is open**

  Not queued from this page -- another tab, the form, before a reload --
  so nothing is watching it by id. The stage refreshes its list while
  anything on it is unfinished.

### a finished render can be downloaded

# Recipe: getting the video back

Every rendered render has a Download button. It fetches the file with the
session -- an `<a href>` cannot carry the Authorization header -- and
saves it under the name the server gives it.

- **the file arrives under its display name, fetched with the session**
- **a delivered render can still be downloaded**
- **an unfinished render offers no download yet, and says why**
- **a refused download says why**

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


## editor access

The editor from the keyboard, and read as text.

# Recipe: choosing a timeline tool without a mouse

The tools beside the timeline are buttons. Tab to one and press Enter or
Space to choose it; the chosen tool is announced as pressed. They were
icons that announced themselves as buttons and could not be reached: no tab
stop, and neither key did anything. Space is still play and pause whenever
the keyboard has not moved to a button -- choosing a tool with the mouse
does not take it away.

### the timeline tools from the keyboard

Named for the tool, not for its icon: the icon's ligature text --
"content_cut" -- is hidden from assistive technology.

- **every tool is a button with a name**
- **Tab reaches a tool, and Enter or Space chooses it**

  The page's own Space handler cancelled the press and played the
  timeline instead, so a keyboard could not have chosen a tool even had
  it reached one.

- **Space pressing a tool does not also start playback**

  The page's own Space handler cancelled the press and played the
  timeline instead, so a keyboard could not have chosen a tool even had
  it reached one.

- **after choosing a tool with the mouse, Space still plays**

  Two bare anchors side by side read "User documentationAPI reference".

### the footer

Two bare anchors side by side read "User documentationAPI reference".

- **its links are separated, to the eye and in the text**

## editor media

Media in the editor: how long it runs, and how the browser fetches it.

# Recipe: adding footage at its own length

Choose a file on the Source stage (or press + beside it in the bin) and it
arrives as the whole file, from its start: as long as the file runs, which
the Source stage shows beside its name. A still image arrives as five
seconds of the picture, as does a file whose length the server could not
measure. Trimming stops at the end of the file. Every library clip used to
arrive as five seconds, because nothing reported a length.

The server's media list (`GET /media`) carries, for each file, its kind,
its length and a short-lived signed URL. The viewer plays a video from that
URL by itself -- streaming, seeking -- instead of downloading the whole file
with the session first; renders download the same way. A server without
that list still works: names come from `GET /videos`, and files are fetched
with the session as before.

The media list, the signed URLs and the render list are answered here: what
is under test is what the editor does with each answer.

### a library clip is as long as its file

- **it arrives at the length the server measured, from its start**
- **a file the server could not measure arrives as five seconds**

  It was sent as a video clip. otto draws an image clip as one picture
  for as long as the clip lasts, with no in-point to move.

- **a still image arrives as a picture: a length and no window**

  It was sent as a video clip. otto draws an image clip as one picture
  for as long as the clip lasts, with no in-point to move.

- **a server without the media list: names from /videos, five seconds each**

  Against a server from before `GET /media` -- it answers 404 -- the
  editor reads the older list of names and carries on as it did.

### a trim stops at the end of the file

The shared fixture's video clip plays the first three seconds of
demo-bars. Served here as a 3.5-second file, a long drag to the right
lengthens the clip by half a second and no more.

- **dragging past the end of the source leaves the clip as long as the file**
### media is fetched by signed URL

The element is handed the signed URL and fetches it itself -- no
Authorization header, no blob: it streams, and nothing holds the
whole file in memory. (The request is passed on here with the session
added, so that a server which does not check signatures yet still
serves it.)

- **the viewer plays a video from its signed URL, fetched by the browser**
- **a signed URL that has run out is renewed, not handed to the viewer**
- **a finished render downloads from its signed link**

  # Recipe: downloading a render

  Download hands the browser the render's signed link: the browser
  fetches the file straight to disk, under the name the server gives it,
  the way any download goes -- instead of the page fetching the whole
  file into memory with the session and handing it over afterwards.

- **a download link that has run out is asked for again**

  The list was read when the stage opened; by the time Download is
  pressed its link may have run out. A fresh one comes from the
  render's status.


## editor render

What the editor sends when it asks for a render.

The editor plays its timeline as one track, each clip starting where the
previous one ends. The renderer places clips by an explicit `start` and
layers overlaps, treating a missing `start` as 0. The editor used to send
clips with no `start` at all, so three five-second clips rendered stacked at
second 0 -- five seconds of overlap, then ten of black -- while the preview
played them one after another.

These read the request the page actually sends (intercepted and answered
here, so nothing is queued) rather than trusting the code that builds it.

### the render request places every clip

# Recipe: what "render" sends

The exact case from the bug report: three clips of one file, added one
after another. They must arrive end to end -- the second where the
first ends, the third where the second ends -- not all at 0. (How long
each is depends on what the server measured the file as; five seconds
when it measures nothing.)

- **three clips added in the editor render end to end, not stacked**
- **a start stored on a clip is replaced by its place on the timeline**

  A saved `start` records where a clip was when it was saved. Reordering,
  trimming or cutting moves it, so the request must be computed from the
  timeline as it stands and never echo the stored value. Served here with
  every stored start wrong, to prove the editor ignores them.

- **a clip fades only when a fade was chosen for it**

  The project routes store clips through otto's model, which fills in
  its one-second fades, so every clip of a saved project arrives with
  `fadeIn: 1` and `fadeOut: 1` that nobody set. Those go out as 0, like
  a clip with no fade at all; a fade of any other length was chosen,
  and is kept. Served here with one clip of each kind.

- **the size typed on the Render stage is the size requested**

  The size inputs were uncontrolled, and mithril writes `value` back on
  every redraw -- so a redraw between typing and clicking restored the
  project's size. Forcing a redraw in between is the point of this test.

### a saved timeline is the timeline a render receives

# Recipe: what "save" stores

A project stores the clips a render of it would receive (contract M4):
each placed by an explicit start, its fades explicit -- 0 unless one
was chosen -- and its window in step with its length. Anything that
renders `project.edl` as stored gets the video this editor renders.
Save sent the raw clips: no starts, so rendered as stored they stacked
at second 0, and the view's own bookkeeping went along with them.

Served here with stale starts, the one-second fades the old routes
wrote onto every clip, a chosen fade, and an out-point that disagrees
with the clip's length. The save is answered here too: the shared
fixture is not written.

- **Save sends exactly what Render sends: placed, with explicit fades**
### the toolbar Render button

It sent `?project=&width=&height=` and a body of bare clips. The route
reads only the body, so every render from this button came out at the
1920x1080 default with no project -- and with no starts, stacked.

- **sends the Render stage request, in the body**
### a form-driven project

A project with fields and logic renders from a form on the Render stage:
the logic compiles the form into clips. Those clips are layered on
purpose -- here a colour field from 0 and a title over it from 1s -- so
they keep their own starts, and a clip with none leaves with an explicit
0 rather than relying on the renderer's default.

The form also sent ffmpeg flags of its own and a quality of "web" or
"TV"; the server now picks the encoding from a named preset and refuses
client-supplied ffmpeg parameters, so this asserts neither is sent.

- **its preview frame is shown from the address the server gives**

  `POST /preview/` answers with where the frame is: a signed URL for the
  private frames route, which the image fetches by itself -- or, from a
  server before that route, a path under the public `/data` mount.

- **renders its logic layered, with a preset and no ffmpeg flags**

## editor

The timeline editor, with a project open.

None of this was testable before: the Project model had no `edl` field, so
every project opened an empty timeline, and there was no way to tell a
broken editor from an empty one. A seeded "Timeline demo" project is what
makes these assertions possible.

The suite finds that project through the API rather than hardcoding an id,
so it survives a reseed.

### timeline editor

"Timeline demo" exists and has more than one clip to edit.

- **the demo project is seeded with a timeline**
- **the timeline renders one element per clip**

  Counted against the API rather than a literal: the seed can change
  without this test needing to.

- **each timeline clip is named after its template**

  A clip on the timeline carries its template's name.

- **the media bin lists the templates the API offers**

  The bin was permanently empty: it asked for /otto/templates, which has
  never existed, and the rejection was unhandled so nothing showed.

- **the old editor URL lands on the project stage**

  #!/editor was a route with no stage rail and no timeline. Its content
  is a property of a project, so it lives beside the project you
  selected.

- **a selected project offers its template**

  The project's form logic and fields, beside the project on the Source
  stage. Collapsed by default: most visits here are to pick a project,
  not to inspect one.

- **a clip added while the project is loading is kept**

  The project's clips arrive asynchronously, and the response used to
  replace the whole timeline -- so a clip added before it landed vanished
  when it did, and Save then found nothing to save. That was the save
  test in tools.spec.js failing on most runs. The response is held back
  here so the order is certain rather than lucky.

- **a project that does not exist is asked for once, not in a loop**

  A failed load forgot the id, the answer redrew, and the redraw asked
  again: an unknown id in the URL was requested for as long as the page
  stayed open.

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
  `local` -- the one that needs no account, which is what makes "cloud
  storage optional" true of getting your video back as well as making it.
  Asserting against the endpoint rather than a literal means enabling
  a destination is a server change, and this test follows it.

- **stage 4 offers exactly what the server offers**

  Built from `GET /destinations`, not hardcoded in the editor.

  Cloud delivery is the next phase, so the server currently offers only
  `local` -- the one that needs no account, which is what makes "cloud
  storage optional" true of getting your video back as well as making it.
  Asserting against the endpoint rather than a literal means enabling
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

  The login screen carries the route to come back to, and a route with a
  query in it -- a stage, a project -- came back as nothing. mithril
  decodes the whole hash before splitting off the query, so
  `redirect=/?stage=render` split on its second `=` and the value read
  as empty; logging in landed on `/` every time.

- **logs back out**

  The login screen carries the route to come back to, and a route with a
  query in it -- a stage, a project -- came back as nothing. mithril
  decodes the whole hash before splitting off the query, so
  `redirect=/?stage=render` split on its second `=` and the value read
  as empty; logging in landed on `/` every time.

- **leaves a protected view anonymous for a visitor**

  The login screen carries the route to come back to, and a route with a
  query in it -- a stage, a project -- came back as nothing. mithril
  decodes the whole hash before splitting off the query, so
  `redirect=/?stage=render` split on its second `=` and the value read
  as empty; logging in landed on `/` every time.

- **a deep link survives logging in**

  The login screen carries the route to come back to, and a route with a
  query in it -- a stage, a project -- came back as nothing. mithril
  decodes the whole hash before splitting off the query, so
  `redirect=/?stage=render` split on its second `=` and the value read
  as empty; logging in landed on `/` every time.

### registering

Registration is closed by default in production. Every refusal used to
read "error regestering", which invites somebody to keep trying a thing
nothing they type can fix. The server's own reason is shown instead.

Answered here rather than by a closed server, because this suite
registers its own user and needs registration open to do it.

- **a server that does not take registrations says so**
- **an address that already has an account says so**

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

Slip, slide and dual roller could be chosen -- they lit up like the
others -- and then did nothing to any clip. They are visibly disabled
now, with a title saying why, and choosing one says so too.

- **edit tools are present**
- **tools that are not built yet say so, and do not pretend**
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


## render api

What a render request may ask for, and whose renders a caller can reach.

# Recipe: the render API's promises

Asserted at the HTTP level against the running stack. None of this waits on
an encode, so it needs no worker: every request here is refused, or answered,
before the worker would be involved.

- Media is named as `GET /videos` lists it, or by URL on an allowed host;
  anything else is a 422 before anything is stored (contract C4).
- Encoding comes from a named quality preset; client ffmpeg options are a
  422 (C5).
- `GET /render/{id}/status` answers for one render (C2).
- A render is its owner's: another user gets 404 for it everywhere (C6).

### a render request is checked before it is queued

- **media named by <what> is a 422**
- **media named as the library lists it is accepted**
- **a template outside the allowlist is a 422**
- **the EDL preview checks the same things**
- **encoder options are not the client's: <JSON>**
### a render answers for itself

- **its status has exactly the contract fields**
- **a malformed id is a 422 and a missing one a 404**
- **none of it is open to an anonymous caller**
### another user's render

- **is not listed, and answers 404 everywhere**
- **there is no way to delete every render at once**

## render pipeline

The whole loop, with a video at the end of it.

Queue a render from the browser, wait for the Celery worker to encode it with
ffmpeg, then download and deliver the result and check the bytes arrived.
Nothing here is stubbed: a real worker, a real encode, a real file.

This is the only spec in the suite that waits on an encode, so it is tagged
@slow and given its own timeout. Everything is deliberately small -- 320x180,
one second -- because the point is that the pipeline runs end to end, not
that it can handle a long edit.

It also needs a worker. Where none is running the render never leaves
`queued`, so the wait below reports that plainly rather than timing out on an
assertion that says nothing.

### @slow render pipeline, end to end

The defect this guards: a clip dragged from the media bin is named
`videos/<file>`, and the worker opened that against its own working
directory, where there is no `videos/`. Every render with a media clip
failed, and the only render test used a template, which needs no file.

- **a render queued from the API becomes a real video file**
- **a clip from the media library renders**
- **a finished render downloads, whole or in ranges**
- **the finished render can be delivered, and the link works**
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

The session lifecycle: renewal, expiry, logout, and what a token is worth.

# Recipe: staying logged in, and stopping

The editor keeps a JWT in sessionStorage and sends it as a bearer token.
Tokens live an hour, and `/auth/jwt/refresh` only exchanges one that still
works -- so the editor renews its token a few minutes before it expires, for
as long as somebody is using it, and again whenever the window comes back
into focus with more than half the token spent. A tab left alone for a whole
token lifetime is not renewed, and lapses.

When the session does end -- the token ran out, or the server refused it --
the editor sends you to the login screen, and back to where you were once
you have logged in.

It used to try to refresh *after* a request came back 401, by which time the
token it refreshed with had already been refused: that retry never renewed
anything, and every session simply ended an hour after login.

The browser tests here move the page's clock rather than waiting an hour.
The server's clock does not move, which is the point: a token the page
believes is nearly spent is still good at the server, so renewing it works.

### token refresh

This answered 500 for every caller.

The route called `auth_backend.get_login_response(...)`, which has not
existed on fastapi-users' AuthenticationBackend for several major
versions -- it carries `login` and `logout` and nothing else.

- **a valid token can be exchanged for a new one**
- **the refreshed token actually authenticates**

  `iat` beside `exp`, so the editor can count a token's lifetime down on
  its own clock. Judged against `exp` alone, a browser running a few
  minutes slow would renew a token that had already died.

- **a token says how long it lives, in server time**

  `iat` beside `exp`, so the editor can count a token's lifetime down on
  its own clock. Judged against `exp` alone, a browser running a few
  minutes slow would renew a token that had already died.

- **refresh refuses an anonymous caller**
- **refresh refuses a malformed token**
### staying logged in

- **an editor in use renews its token before it expires**
- **coming back to the window renews a token more than half spent**
- **a tab nobody uses is not renewed a second time**
- **a session that ran out while the machine slept goes to log in, and back**

  Any 401: the token expired, or the server no longer accepts it -- a
  restart with a new signing key, a disabled account. Renewal cannot
  help, so the editor does not try; it keeps the route to come back to.

- **a session the server refuses goes to log in, and back**

  Any 401: the token expired, or the server no longer accepts it -- a
  restart with a new signing key, a disabled account. Renewal cannot
  help, so the editor does not try; it keeps the route to come back to.

### logout

It posted to `/logout`, which is not a route; the static mount answered
405 and nobody read it. It calls fastapi-users' own logout now, with the
token it is ending, and forgets the token whatever the answer.

- **logout succeeds for an authenticated caller**
- **the editor logs out at the server, not at a route that does not exist**
- **a bearer token still works after logout**

  Pinned as a property, not filed as a defect.

  These are stateless JWTs with no server-side revocation list, so logging
  out clears the browser's copy and cannot invalidate a token somebody
  already holds. That is how the mechanism works and it is a real
  consequence: a leaked token stays valid until it expires, and "log out
  everywhere" is not something this design can offer.

  If revocation is ever added this test goes red, which is the moment to
  decide deliberately rather than discover it.

### what a token gets you

The e2e user is not a superuser, so the admin router must refuse it.
A 200 here would mean any registered account can reach the admin
surface, which is the kind of thing that is only noticed deliberately.

- **every gated route refuses an anonymous caller**
- **a token from one login works across every gated route**
- **the admin surface needs more than an ordinary session**

## templates

Template clips: adding them, and changing what they say.

# Recipe: a title card

Templates are made, not uploaded -- a title, a text box, a colour field.
Add one from the bin under the timeline (its + button, or drag it into
place) or from the Source stage's Templates list. Its settings appear beside
the viewer: text, length and colours. The server renders every change, and
if a setting cannot be rendered it says why, next to the settings.

None of this worked before. The timeline refused drops from the bin, the
drop handler threw on the shape of a template entry when one got through,
and there was nowhere to change a template clip once it existed. Template
clips only reached a timeline through demo and seed projects.

### adding a template

Press + on a template in the bin. It lands on the end of the timeline
as five seconds of "Your text here", its settings open beside the
viewer, and that is exactly what a render receives.

- **the bin adds a template as a clip with text and five seconds**
- **a template that takes no text is not given any**

  makeColor's parameters are a colour and a position. Offering it a
  text field would invite an edit that changes nothing.

- **the Source stage lists every template, and adds one**

  Templates are material too, so the Source stage lists them beside the
  media, and says where an added one landed.

- **a template dragged from the bin lands on the timeline**

  The bin and the timeline are two Sortable lists, and the timeline's
  group accepted only itself -- so a drag from the bin was refused before
  the drop handler ever ran. And the handler, had it run, read fields
  from the dragged element that template entries do not have.

### changing a template clip's settings

Each field changes the clip itself: the label on the timeline, its
width, the frame the server renders for the viewer, and the clip a
render receives. A colour can be typed or picked; the swatch follows.

- **text, length and colour change the clip, its frame, and its render**
- **typing a duration is not interrupted halfway**

  The field is controlled; without a draft, "1." would be rewritten to
  the clip's duration before the next digit arrived.

- **a setting that cannot render says why, beside the settings**

  Validation is the server's: the frame is rendered from the clip's data,
  and a template that cannot render what it was given answers 422 with
  the reason. That reason was read from a blob response with
  `responseText`, which throws, so it never reached the screen. Served
  here so the reason is known.


## timeline tools

The timeline tools, by mouse and by touch.

# Recipe: trimming and cutting

Choose a tool beside the timeline. **Trim** (`[ ]`) drags a clip's end to
make it longer or shorter. **Time** (`|`) moves the playhead to where you
press. The README promises editing on mobile devices, and these work by
touch as well as by mouse: they listen for pointer events, which are one
stream for both. They listened for mouse events, which a finger does not
send while it moves, so on a phone trimming did nothing at all.

### trim, by mouse

Grab a clip near its end and drag. The pointer is captured, so the
drag keeps arriving at the clip after leaving its edge -- the whole
gesture -- and the clips after it move along. (Its file is served as a
minute long, so the end of the file is not what stops it.)

- **dragging a clip past its own edge lengthens it, and its out-point**
### by touch

A real touch drag, sent through the browser's input pipeline rather
than as synthetic events -- the kind a phone sends.

- **a finger can trim a clip**
- **a tap on a clip moves the playhead to that point of it**

  With the time tool, a tap half way along the second clip puts the
  playhead half way through it.

- **a swipe across the timeline is a scroll, not a seek**

  The press that starts a scroll is not a choice of position: seeking on
  press would jump the playhead every time someone scrolled.

### cut

# Recipe: cutting a clip in two

Choose the scissors and press a clip where it should split: the playhead
goes there and the clip becomes two. Or put the playhead anywhere and
press S. Either half can then be trimmed, moved or deleted on its own.

- **a media clip becomes two windows onto its file that meet**

  The first half keeps the clip's in-point and ends where the cut is;
  the second starts in the file where the first ends and finishes where
  the original did. Back to back they show what the original showed.

- **a template clip becomes two halves of one animation, edited separately**

  Two clips of the same template, each with its own copy of the
  settings. The second carries on where the first stopped: it starts in
  the template where the cut was (its in-point) and ends where the
  original did (its out-point), so its animation continues rather than
  starting over -- in the viewer, and in the render.

- **a continuing half keeps its window when its length changes**

  otto plays a clip with an out-point from its in-point to its out-point
  and does not read `duration`. So a length typed beside the viewer has
  to move the out-point too, or the render would ignore it.

- **S splits the clip under the playhead, whatever the tool**

  Put the playhead anywhere -- here with the time tool, half way through
  the first clip -- and press S.

- **a cut at the very edge of a clip says why it did nothing**

  At 0 the playhead is at the very start of the first clip, so a cut
  there would leave nothing on one side. It is refused, and says so.

### on a phone

There was no doctype, so every browser laid the page out in quirks
mode; and the viewport carried `maximum-scale=1`, which stops a phone
from zooming -- the one tool someone who needs larger controls has.

- **the page is laid out to standard, and can be zoomed**

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
not register. The element is handed the signed URL the server issued
for the file, or -- from a server that issues none -- an object URL for
the file fetched with the token.

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
