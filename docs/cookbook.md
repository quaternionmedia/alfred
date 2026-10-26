# Cookbook

Generated from the end-to-end suite by `website/e2e/cookbook.js`. Do not
edit by hand -- change the tests instead, and regenerate.

Every recipe below is a test that runs against a real stack: a real
database, a real render worker, and real files on disk. If a step here is
wrong, a test is failing. That is the point -- prose describing behaviour
goes stale silently, and a test describing behaviour goes red.

`./al test` and CI run the `chromium` and `phone` projects. The
walkthroughs tagged `@recipe` run in the `docs` project, which `./al
recipes` drives against a dev stack to record them.

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

  The two below are about the phone flow, where one stage's panels are
  stacked under the rail, and run at a phone's size. In the desktop
  workspace panels sit side by side by design, and the first `.stagepanel`
  is the project list's wherever the stage is -- these would pass there
  without measuring anything they mean.

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

In the phone flow, one stage at a time: choosing one shows its panel
and not the others'. Edit shows none of theirs -- it is the timeline,
which is always there -- only the captions, which are edited with it.
The workspace brings a stage's panel forward instead
(workspace.spec.js).

- **clicking each stage shows its panel, and only its panel**
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

## assets

The interface's own assets come from the app, not from a CDN.

AGENTS.md rules out frontend assets loaded from a CDN, and the icon font was
one: its stylesheet named a file on Google's font servers, and that face
was the one the browser used, so every page view fetched it from Google.
The font is bundled from an npm package now. These hold that in place, and
check what someone using the app would notice -- that the icons are icons,
rather than the ligature names ("play_arrow") a missing font leaves on the
buttons.

- **no stylesheet or font comes from another origin**

  Every request from the first one, login screen included, so a link in
  index.html cannot slip past by loading before the session exists. And
  declared counts as well as fetched: of two faces with the same family,
  style and weight the browser downloads only the one it settles on, so a
  CDN face shadowed by a local one is never requested -- until the local
  one goes away.

- **every icon on every stage is drawn by the icon font**

  A name the font knows is one glyph, about as wide as the text is tall. A
  missing font leaves the name itself on the button, and a name the font
  does not know leaves blank space, a letter's width per letter; either
  way the text is several ems wide. So this is geometry, over the icons
  actually shown, rather than a list of names kept by hand. The text is
  measured, not the element, so padding cannot count.


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

## captions

Captions: typed, imported, transcribed, and drawn into renders.

A project's captions are text and the stretch of the timeline it is shown
for. The Captions panel -- on a wide screen a tab in the workspace, beside
Render and Deliver; on a phone the Edit stage's panel, above the viewer --
edits them by hand, reads them from a SubRip, WebVTT or JSON file -- the
server reads it, the panel shows what it found, and saving keeps it -- or
has the timeline's own sound transcribed by the server's audio engine. The
caption under the playhead shows over the viewer; renders carry the
captions once the project's style says to draw them, which it does not
until someone ticks the box.

This stack's audio engine is a stub speaking joe's media API (see
test_e2e.yml): it "hears" a segment wherever there is sound. The specs that
transcribe through it run the real worker and the real mix, and wait for
them, so they are tagged @slow.

### captions by hand

# Recipe: caption a timeline by hand

Add a caption at the playhead, type what is said, set when it starts
and ends -- in seconds, or from the playhead -- and save. The list
keeps itself in order of when captions start.

- **captions are typed, kept in order, and saved**
- **a caption that cannot be shown says why, and is not saved**

  A caption with no text, or one that ends before it starts, is marked
  with the reason, and Save waits until it is fixed.

- **a caption is deleted, and the deletion saved**

  Deleting takes a caption out of the list; saving takes it off the
  project.

### captions from a file

# Recipe: import subtitles

Import a SubRip (.srt), WebVTT (.vtt) or JSON file. The server reads it
-- forgiving the habits of the tools that wrote it -- and the panel
shows what it found before anything is kept: use them, add them to
the captions already there, or cancel.

- **a subtitle file is read by the server, reviewed, and saved**
- **a file that cannot be read says which line**

  The server's reason, naming the line it could not read, is shown where
  the review would have been, and nothing is kept.

### how captions are drawn

Size, position, colours, the box behind the text and the font are
saved with the captions. "Draw into renders" starts unticked: a
project's captions are drawn only once someone says so.

- **the style is saved with the captions, and off until someone says**
- **the caption under the playhead shows over the viewer**

  Whether or not the Captions panel is in view, the caption under the
  playhead is drawn over the viewer in its style; past it, nothing is.

- **renders carry the captions once they are drawn, and not before**

  # Recipe: burn captions into a render

  Tick "Draw into renders" and save. Every render of the timeline then
  carries the captions and their style, and the server draws them over
  the picture at the render's own size.

### transcribing the timeline

Transcribing needs an audio engine that answers and a renderer to mix
the timeline's sound. Until the server has said whether there is one,
the button waits and says it is checking; without one, it says which
is missing.

- **transcribing says why it cannot**
- **a transcription already under way is followed, and the refusal still read**

  Another tab, or an API client, started one first. The server refuses a
  second with 409 and `code: "transcription_running"` beside its
  sentence (docs/api/errors.md). The panel shows the sentence, and,
  because of the code, follows the transcription under way until its
  captions arrive -- the ones a second would have made.

### @slow transcribing through the worker

# Recipe: caption a timeline from what it says

"Transcribe timeline" sends the project's saved timeline to the
server's audio engine: the render worker mixes its sound, the engine
hears it, and what it said becomes captions, timed by the timeline.
Here the sound is two bursts of tone placed a second into the
timeline, and the stub engine hears a line of speech in each.

- **the timeline is heard by the audio engine and captioned**
- **a timeline with no sound fails, and says so**

  A timeline whose clips have no sound track -- the demo media is silent
  -- fails with that reason, and the captions it had are left alone.

### the audio engine, through the API

`audio_engine` says whether one is `configured` and `ok`, and in
`detail`, why not.

- **GET /health says whether there is one**
- **a project answers its captions, style and job**

  `PUT /project/{id}/captions` answers what it stored, in order; the
  style states `enabled`, and `GET /project/{id}` carries both.

### @slow the audio engine hears library media

`GET /media/{name}/audio` answers what the engine measured: here, the
fixture's two bursts of tone, as onsets and the silences around them.

- **a library file is analysed by the engine**

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

### when no renderer is running

# Recipe: knowing why a render is not moving

With no render worker running, a queued render stays queued. The Render
and Deliver stages say so -- "No renderer is running -- renders stay
queued" -- from the server's own health check (`GET /health`), and the
page asks about a queued render rarely until a renderer starts, then
promptly again. A server that cannot say leaves the stages as they were.

- **the Render and Deliver stages say so**
- **with a renderer running, nothing is said**
- **a server without the health check is asked once, and nothing is said**
- **a queued render is asked about rarely, and promptly once a renderer starts**
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

## editor draft

An unsaved timeline outlives the page that made it.

# Recipe: getting unsaved edits back

Edits to a project's timeline are kept in the tab until they are saved. If
the page is reloaded, or the session runs out and you log in again, opening
the project offers them back: **Restore them** puts the unsaved timeline on
screen, **Discard** keeps the saved one. Saving clears what was kept. It is
the tab's own, and goes when the tab does.

Every edit since the last save used to be lost, with no warning, whenever
the page went away.

These open the shared media project and never save it: what a test keeps
stays in its own browser, and the one test that saves brings its own
project.

### an unsaved timeline outlives a reload

- **after a reload the unsaved timeline is offered back, and restored**
- **discarded, it is gone, and the saved timeline stays**

  Opening a project, selecting clips and playing them changes nothing,
  so nothing is kept -- and a stored `start` or fade, which the editor
  would send differently, is not counted as a change.

- **a timeline that was only looked at offers nothing**

  Opening a project, selecting clips and playing them changes nothing,
  so nothing is kept -- and a stored `start` or fade, which the editor
  would send differently, is not counted as a change.

- **saving clears what was kept**
### an unsaved timeline outlives the session

The server refusing the session sends the page to log in, carrying
where it was; the timeline goes with the page. Logging in again comes
back to the project, and offers what was unsaved.

- **when the session ends, logging in again offers it back**
### storage that refuses

Private browsing and full quotas refuse storage outright. The editor
goes on working; there is simply nothing to offer back.

- **a browser that will not keep the timeline still edits it**

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

- **a stage chosen straight after a project keeps the project**

  Choosing a stage on the rail changes the stage and keeps the rest of the
  address, the project chosen a moment before included. The rail built
  the new address from the router's route, which reads a change back a
  tick after it is made; a stage chosen in that tick put back the address
  from before the project, and the project was dropped. Here the tick is
  held open, so the stage is chosen inside it every time.

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

## health

Whether the stack can do its work.

# Recipe: is a renderer running?

A render waits in `queued` until a worker takes it. On a stack with no
worker -- the thin stack runs none -- it waited for ever, and nothing could
say why. `GET /health` says how many render workers answer and how many
jobs are waiting (contract M3), and how many previews the api is drawing
and how many wait for a turn; `GET /healthz` answers container health
checks with no session and nothing behind it.

This stack runs a worker against a database that starts empty, which is
also the case where a worker used to be deaf to pings until it restarted.

### health

- **GET /healthz answers with no session**
- **GET /health needs a session**
- **GET /health has the contract fields**
- **the running worker answers, so the renderer is ok**

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

  fastapi-users answers with a code, REGISTER_USER_ALREADY_EXISTS; the
  register button says it in words, and what to do instead.

- **the address of the development login cannot be registered**

  The auth bypass acts as dev@example.com, and that account owns the
  seeded projects. It is made the first time the bypass runs, so on a
  server where it never had, whoever registered the address owned them.
  The server refuses it in any case, and says why.

### the links the server mails

# Recipe: a forgotten password

The login screen's "forgot password" asks the server to mail a reset link
to the address in the email field. The link opens an account page, which
takes the new password twice, sets it, and goes to the login screen. A
confirmation link opens the same page, which confirms the address as it
opens. Both work for somebody who is not logged in -- which is the point,
and which the session guard used to prevent, sending the page, its token
and all, to the login screen.

The server answers a reset request the same whether or not the address
has an account, so asking says nothing about who has one; a server with
no mail configured sends nothing, which only an administrator can change.

The pages' requests are answered here rather than by the server: the
token in a real link only ever reaches a mailbox, and this suite has
none. The API side, from the request to logging in with the new password,
is `tests/integration/test_password_reset_api.py`.

- **forgot password asks for a reset link for the address typed in**
- **the reset link sets the new password, then goes to log in**
- **a reset link that has expired or been used says so**
- **the new password has to be typed the same twice**
- **the confirmation link confirms the address as the page opens**
- **the account page without its link says where to get one**

## media

Media the browser fetches by itself.

# Recipe: media links that work without a session

A `<video src>`, an `<img src>` or an `<a download>` is a request the
browser makes on its own, and it carries no session. So the API hands out
signed URLs for the files those elements need -- each good for one path, for
a limited time -- and the file routes accept one in place of a session
(contract M1):

- `GET /media` lists the library with what the editor needs to place each
  file -- its kind, how long it runs, its size in pixels -- and a signed
  `url` to load it from (contract M2).
- `POST /preview/` answers with a signed URL for the frame it made.
- a render's `download_url`, in its status and in the render list.

The frames used to be served from `/data`, a static mount open to anyone;
it is gone.

### the media library

- **GET /media describes exactly the files GET /videos lists**
- **a clip says how long it runs and how big its picture is**
- **its url plays in a video element, in a page with no session**
- **a url opens its own file and no other**
### a preview frame

- **the EDL preview answers with a signed URL for its frame**
- **the URL fetches the frame with no session**
- **an image element shows it, in a page with no session at all**
- **the frame without its signature is refused**
- **a signature moved to another frame is refused**
### nothing is served from /data

- **the public mount the frames came from is gone**

## navigation

### navigation

Below 1026 pixels the header had a menu button, which opened its links
as a drawer over the editor -- and once the rail had taken every link,
it opened an empty one. The only control in a phone's header did
nothing.

- **the rail exposes every stage**
- **the header carries no navigation of its own**
- **the header holds the logo and no control that does nothing**
- **the session link is in the footer, at the size of the links beside it**

  Styled as the header link it once was: 28 pixels, and below 1026 pixels
  lifted out of the footer to the page's top right corner, where on a
  phone it ran into the logo.

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
others -- and then did nothing to any clip, so for a while they were
shown disabled. They work now (timeline-tools.spec.js drives each), and
each says in its title how it is used.

- **edit tools are present**
- **every tool can be chosen, and is the only one chosen**
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
- **the filter narrows the list without losing anything**

  A filter rather than pagination: the list is small enough to render
  whole, and typing a name beats scrolling for one. It appears only when
  there are enough projects to be worth filtering, so the test makes four
  of its own, named with a mark no other project carries.

  Other workers add and remove projects while this runs, so the counts
  asserted are of this test's own rows, never of the whole list.

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

- **recipe: import captions and show them over the picture**

  The Captions panel reads a subtitle file and shows what it found before
  anything is kept. Use them, tick **Draw into renders** and save, and
  the caption under the playhead is drawn over the picture.


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
- `GET /render/{id}/status` answers for one render (C2), with a signed
  `download_url` once there is a file to download (M1).
- A render is its owner's: another user gets 404 for it everywhere (C6).
- The download takes a session or a signature for exactly its own path,
  and nothing else (M1).

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
- **a made-up signature opens nothing**
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
- **the download_url fetches it with no session, as a link would**

  What an `<a download>` or a `<video src>` can use: the status hands
  out a signed URL, and a request carrying no Authorization header at all
  gets the file -- whole, or a range at a time.

- **a browser plays the download_url in a video element**

  Streamed by the browser itself, with no session in the page at all:
  the element asks for the file by URL and plays it, which is the point
  of a signed URL. The editor used to fetch each file whole with the
  session token and hand the bytes to the element instead.

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

  The snapshot is taken once the list has arrived, with a render of the
  test's own on it -- queued, rendering or done by then; the rule holds
  for each. Taken at a fixed 300 ms, a list slower than that read as
  nothing rendered, and the test skipped itself.

- **a delivered render says where it went**

## screens

The screenshots the docs open with, taken from the running app.

# Screens

Tagged `@screens` and run by the `docs` project beside the recipes:
`./al recipes` takes each one and saves it as
`docs/assets/screens/<name>.png`, which the README and the docs pages show
under their titles. Like a recipe's recording, a screenshot made this way
shows the app as it is: when a screen cannot be reached, its test fails and
its file is gone rather than stale.

The state they show is built here, through the API, so they need no audio
engine and none of anyone's data: the demo media, a project made from it,
captions imported from a SubRip file and turned on, and one finished
render to deliver. The page's lists are narrowed to those, so a screen
taken on someone's own stack shows none of their projects, files or
renders.

Desktop screens are 1280x800 and phone screens 390x844. Excluded from the
`chromium` and `phone` projects, like the recipes.

### @screens

- **screen: the workspace at Edit**
- **screen: captions over the picture**
- **screen: Render**
- **screen: Deliver**
- **screen: the Panels menu**
### on a phone

- **screen: Edit on a phone**
- **screen: Render on a phone**

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

## stacked

The phone flow: the editor's panels stacked one stage at a time.

Below 1024 pixels the editor is not a workspace. The rail chooses a stage,
the stage's panels sit under it, and the viewer and the timeline are always
below them -- built from the same panel modules the workspace docks
(workspace.spec.js). Run by the `phone` project, at 390x844, with the
flow, editor, timeline-tools and deliver specs; the picture's room is also
checked on a smaller phone, and on one held sideways.

### the phone flow

Below 1024 pixels there is no dock and no Panels menu: the rail, and the
regions under it.

- **is a stack, not a dock**
- **a notice lets a tap through to what is under it**

  Choosing Source puts the project list and the library under the rail,
  and the viewer and the timeline under them.

- **a stage's panels sit between the rail and the viewer**

  Choosing Source puts the project list and the library under the rail,
  and the viewer and the timeline under them.

- **a long project list scrolls inside its panel, and the timeline stays on screen**

  The stage's panels keep their height up to a share of the screen and
  scroll inside themselves past it. Unbounded, a long list took the whole
  column and squeezed the viewer and the timeline out of it.

- **the viewer and the transport fit the screen**

  The frame is the output's shape and no wider than the screen, and the
  playback and speed buttons wrap rather than run past its edges. Both
  did: every `section` is a column, which sized the frame's room by the
  frame, and the two button groups could not wrap.

- **the selected template clip's settings are beside the output settings**

  Not a panel of their own on a phone: beside the aspect and the
  resolution, where they always were, and nothing at all while no template
  clip is selected.

### the phone flow fits the width of the phone

At the rail's desktop spacing the four stages came to 459 pixels, so on
a 375-pixel phone Deliver was cut off at its number and the rail
scrolled sideways: the last stage of the flow, out of sight.

Mutation: drop the rail's narrow-screen spacing (stages.scss) and this
fails.

- **all four stages sit across the rail**
- **no stage scrolls sideways**

  The scrubber was the whole row plus its margins, and the transport
  scrolled sideways by 32 pixels to show them; a generated clip's long
  file name ran the Material panel past the screen. A phone held upright
  scrolls one way.

### on a narrower phone

Choosing is the work on Source, so the viewer and the timeline give way
first, to their floors. Shared in proportion as on the other stages,
the timeline took 207 pixels at 375x812 and the project list 78: its
heading, its filter, and not one whole project.

Mutation: drop the Source stage's `flex-shrink` (flow.scss) and the
timeline keeps more than its floor, and this fails.

- **the rail and every stage still fit**
### the Source stage

Choosing is the work on Source, so the viewer and the timeline give way
first, to their floors. Shared in proportion as on the other stages,
the timeline took 207 pixels at 375x812 and the project list 78: its
heading, its filter, and not one whole project.

Mutation: drop the Source stage's `flex-shrink` (flow.scss) and the
timeline keeps more than its floor, and this fails.

- **gives its panels the room the timeline can spare**
### the Render stage

Width and height took a row each at the inputs' own width, and shared
in proportion the stage had 114 pixels at 375x812: Width, the top of
Height, and Queue render below them, out of sight.

Mutation: drop the Render stage's rules (flow.scss) and the form
scrolls inside its panel; drop the fields' row (stages.scss) and width
and height stack again. Either fails this.

- **shows its whole form, Queue render included**
### the picture keeps its room

In every stage the whole picture is on the screen, and the stage's own
panels and the timeline give way to it, scrolling inside themselves --
at 390x844 all on one screen, the page itself not scrolling. The
viewer's region was a scroller the column could squeeze like any other,
and it was squeezed, under the stage's panels at their full share: to a
few dozen pixels of a 203-pixel picture at 390x844, and to none of it
at 375x667.

- **every stage shows the whole picture on one screen at a phone's size**
### on a smaller phone

At 375x667 the stage's panels and the timeline would share about 100
pixels, which holds a heading of the one and a row of tools of the
other. They keep a floor instead, and the page scrolls past it -- by
the window, from anywhere that does not scroll itself.

- **every stage shows the whole picture, and the page scrolls to the rest**
### held sideways

The frame's room is two-fifths of the screen held sideways, and the
header, the rail, the room, the transport and the footer are taller
than the screen on their own, so this page has to scroll. The column
used to run on past the window's edge instead, out of reach.

- **every stage shows the whole picture, and the page scrolls to the rest**

## templates

Template clips: adding them, and changing what they say.

# Recipe: a title card

Templates are made, not uploaded -- a title, a text box, a colour field.
Add one from the bin under the timeline (its + button, or drag it into
place) or from the Source stage's Templates list. Its settings appear beside
the viewer: text, length, font and size, how the text is aligned, where the
template sits in the frame, and colours -- whichever of those the template
takes. The server renders every change, and if a setting cannot be rendered
it says why, next to the settings.

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

- **every template is offered by the server's label, not otto's name**

  `textBox` and `makeColor` are otto's identifiers, and the editor showed
  them on its buttons as they are. The server sends a label with each
  template now, and every place that names one -- the Source stage's
  list, the bin, the clip on the timeline and its settings -- says that.

  Mutation: show `t.name` in the Material panel again and this fails.

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

### a template's type and placement

# Recipe: setting a title's font, size and position

A text template is offered a font -- from the fonts this server can draw
-- a size, and where it sits in the frame; a text box also how its text
is aligned in the box. Each is the template's own until chosen, and
"Template default" puts it back.

- **font, size, alignment and position change the frame and the render**
- **each template is offered only what it takes**

  A title takes a font and a position but aligns nothing; a colour field
  takes a position, and nothing about text.

- **a font that cannot be drawn says why, and the default puts it right**

  Validation is the server's, as for every setting: the frame is
  rendered with the font, and a refusal's reason is shown beside the
  fields. Served here so the reason is known.

- **a placement written by a project's logic is kept, not replaced**

  A project can place a template by coordinates, which the form offers
  no field for. It is shown as set, and goes on to the render untouched
  when other settings change.

### a server busy with other previews

The server draws only so many previews at once
(ALFRED_PREVIEW_CONCURRENCY). One that has waited its turn too long is
answered 503 with a Retry-After header. The viewer says it is waiting,
keeps quiet for as long as the header asks -- it does not ask again and
again -- and then asks once more, and shows the frame it gets.

- **the viewer waits as long as the server asks, then asks once more**

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

### slip

# Recipe: choosing which part of a clip plays

Choose **Slip** and drag a clip: it keeps its length and its place, and
the part of its file it shows moves under it. The picture follows the
pointer, as in other editors -- drag right to bring in earlier material,
left for later -- stopping at the start and the end of the file.

- **by mouse, the window moves along the file and nothing else does**
- **it stops at the start and at the end of the file**

  A template is drawn on demand from its own second 0, so it can show
  any stretch of its animation -- but nothing before its start.

- **a template slips through its animation**

  A template is drawn on demand from its own second 0, so it can show
  any stretch of its animation -- but nothing before its start.

- **a clip showing the whole of its file says there is nothing to slip**

  # Recipe: moving a clip between its neighbours

  Choose **Slide** and drag a clip along the timeline. It keeps what it
  shows; its neighbours give and take the time -- the clip before it ends
  later or sooner, the clip after it starts later or sooner in its file --
  so the timeline keeps its length.

### slide

# Recipe: moving a clip between its neighbours

Choose **Slide** and drag a clip along the timeline. It keeps what it
shows; its neighbours give and take the time -- the clip before it ends
later or sooner, the clip after it starts later or sooner in its file --
so the timeline keeps its length.

- **by mouse, the neighbours give and take the time**
- **the first clip has nothing before it to slide against, and says so**

  # Recipe: moving a cut

  Choose the **dual roller** and drag near a cut: the cut moves, the clip
  before it ending where the clip after it now starts in its file. Pressed
  on a clip's first half, the roller takes the cut at its start; on its
  second half, the cut at its end.

### dual roller

# Recipe: moving a cut

Choose the **dual roller** and drag near a cut: the cut moves, the clip
before it ending where the clip after it now starts in its file. Pressed
on a clip's first half, the roller takes the cut at its start; on its
second half, the cut at its end.

- **by mouse, one clip ends where the next now starts**

  Rolled right, the second clip gives up all but a tenth of a second:
  the shortest a clip may be. Rolled left, the second clip can start no
  earlier than its file does.

- **the cut moves only as far as both clips allow**

  Rolled right, the second clip gives up all but a tenth of a second:
  the shortest a clip may be. Rolled left, the second clip can start no
  earlier than its file does.

- **a single clip has no cut to roll, and says so**
### slip, slide and roll by touch

- **a finger slips a clip**
- **a finger slides a clip**
- **a finger rolls a cut**

  There was no doctype, so every browser laid the page out in quirks
  mode; and the viewport carried `maximum-scale=1`, which stops a phone
  from zooming -- the one tool someone who needs larger controls has.

### on a phone

There was no doctype, so every browser laid the page out in quirks
mode; and the viewport carried `maximum-scale=1`, which stops a phone
from zooming -- the one tool someone who needs larger controls has.

- **the page is laid out to standard, and can be zoomed**
### zoom

Zoom in was placed `absolute` at the right of whatever box held it: in
the workspace's tools column it was drawn over the bar, whose end ran on
under the bin beside the column; on a phone it sat at the far end of the
row, away from its bar. The workspace's column has no room for a bar
between two buttons, so there the buttons zoom alone (editor.scss).

Mutation: put back `position: absolute; right: 0` on zoom in (Scale.js)
and on a phone it leaves the bar's box, and this fails.

- **its buttons and its bar sit side by side, none drawn over another**

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

## workspace

The desktop workspace: the editor's panels docked with Golden Layout.

# Recipe: arranging the workspace

On a screen 1024 pixels wide or more the editor is a workspace of panels:
projects and the library on the left, the viewer above the timeline in the
middle, the selected clip's settings and the Render, Deliver and Captions
tabs on the right. Drag a tab to move a panel, drag the gaps to resize
them, close what you do not need. The arrangement is kept in this browser
and comes back on the next visit. The Panels menu brings back a closed
panel, in its place, and Reset layout restores the arrangement above.

Every panel here is the panel the phone flow stacks (stacked.spec.js);
these are about the dock around them.

### the default workspace

`findFirstComponentItemById` is how a panel is brought forward, or
known to be open rather than opened a second time. A default-layout
entry without its id is invisible to it -- in codecartographer that
made bringing the canvas forward a no-op and reopening it add a
second. Read from what Golden Layout itself saves of the layout it
loaded, so it is the layout in use, not a file that could disagree.

- **every panel is in it, once, under its registry id**
- **the material is on the left, the work in the middle, the rest on the right**

  Where each panel opens on a first visit: the default layout's columns
  and stacks, measured on the page, not read from the configuration.

- **the workspace loads without an error in the console**

  Counted from the first load with a session: before it, the page asks
  the server whether auth is disabled (`GET /users/me`, a 401 when it is
  not), and the browser reports that refusal in the console whatever the
  layout. Then a deep link to each stage, and a reload -- a full load of
  the workspace, saved arrangement and all.

### ?stage= in the workspace

The stage flow's links -- bookmarks, the rail, the old #!/renders --
still land: in the workspace a stage is a panel brought forward, with
`Stack.setActiveComponentItem`. (`ComponentItem.focus()` marks an item
focused and leaves its stack showing whichever tab it showed.)

- **each stage brings its panel to the front**
- **the rail brings a stage forward again, even the stage already chosen**

  Choosing the stage already in the address changes nothing in it, and
  still brings its panel to the front: it may have been put behind another
  since.

- **choosing a tab says which stage you are on**

  A tab chosen writes its panel's stage into the address, replacing the
  entry rather than adding one, so the rail follows and Back does not walk
  through every tab chosen.

- **a tab chosen stays in front while the address catches up**

  Choosing a tab writes its stage into the address, which the router reads
  back a moment later. A redraw in that moment brought the stage from
  before back over the tab just chosen: Render in front again, the rail on
  Edit, until something else was chosen. On a loaded machine the rail
  test above did this in one run of ten to twenty; here the moment is
  held open and a redraw put in it, so it would happen every time.

- **the address follows the last tab chosen, however quick**

  Two tabs chosen before the router has read the first back: the address
  names the second one's stage, as the rail does. Render chosen after
  Captions was taken for the stage the route still said -- Render, from
  before -- and never written, so the address and the rail stayed on
  Captions' Edit while Render was in front.

- **Back and Forward bring the stage forward**

  A stage chosen on the rail is a page visited: Back returns to the stage
  before, with its panel in front, and Forward to the one after. (A tab
  chosen replaces the address rather than adding to it.)

### the arrangement is kept

Closing a panel and choosing a tab are kept in this browser
(localStorage, `alfred.layout.v1`), and are what the next visit opens
with.

- **a closed panel and a chosen tab survive a reload**
- **a panel dragged by its tab to another stack stays there**

  Golden Layout's own move: the Captions tab dragged onto the Projects
  stack's tab strip joins it, comes to the front there, draws, and is
  there after a reload.

- **a resized panel keeps its size across a reload**

  Dragging the gap between two panels resizes them, and the sizes are kept
  with the arrangement.

- **a saved arrangement holding <name> gives way to the default**

  Golden Layout throws on a panel nobody registered, and a panel without
  its id, or shown twice, breaks finding a panel by id. Each is caught
  before Golden Layout sees it: the default loads instead, and the
  viewer is told why.

- **a saved arrangement naming only its own panels is loaded as saved**

  The check refuses only what cannot be used: a valid arrangement, however
  unlike the default, is the one that opens.

### the Panels menu

The Panels menu says which panels are closed. Choosing one brings it
back beside the panels it shares a stack with by default; choosing it
again, or its stage, brings it forward -- found by its id -- and never
adds a second.

- **a closed panel comes back once, in its place**
- **a stage whose panel was closed opens it again**

  A rail click or a stage link whose panel is closed reopens it in its
  place: the project list over the library, though closing it had folded
  their column away.

- **Reset layout restores the default, and keeps the work**

  Golden Layout builds every panel again when it loads a layout. The
  panels are drawn in boxes the layout moves, so the timeline is not
  fetched again: a clip added and not saved is still there afterwards,
  and no draft is offered back.

- **the menu and the tabs work from the keyboard**

  The Panels menu is a menu button: Enter or the arrow keys open it on an
  item, the arrow keys move along it, Escape closes it and returns the
  focus. Golden Layout's tabs are given roles: a tablist per stack, tabs
  named for their panels, one tab stop per strip, the arrow keys along it,
  Enter to show a panel and Delete to close it.

### the viewer keeps its shape

The frame is the largest rectangle of the output's aspect that fits its
panel: a larger window makes it larger and the same shape, and an
upright output makes it upright.

- **resizing the panel resizes the picture, never reshapes it**
### the frame takes overlays

What is drawn over the picture -- the caption under the playhead -- is
placed against the frame (`viewerOverlays`, panels/Viewer.js), so the
frame is positioned and the preview fills it, with nothing else in
between.

- **the frame is positioned, and the picture fills it**
### the workspace and the phone flow

Below 1024 pixels the workspace gives way to the phone flow, and comes
back above it, with the same panels: an unsaved clip is still on the
timeline either way, and nothing is offered back as a draft.

- **narrowing the window swaps one for the other, and the work stays**

---

Regenerate with `node website/e2e/cookbook.js`.
