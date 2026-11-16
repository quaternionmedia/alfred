# The tour

The editor's user journeys, a stage at a time, in a box over the editor: the way
a person finds their way through it, and the way they say how each part of it is.

## What it takes, and in what order

The tour is the [user journeys](journeys.md) that go through the editor's four
stages, in that page's order: A first video, Your own footage, Arrange and title,
Render and deliver, From a form, and Captions and cutting by words. A first video
goes the whole way, Source to Deliver; each after it takes the stages its part of
the way needs. On a phone, Coming back and Saving are the same stages seen another
way, An account comes before the editor, and With an assistant is outside it, so
none of them is in the tour.

The box has no words of its own. A stage's line is the one the rail shows for it,
and what there is to try on it is the journey's own steps on that stage, each a
link to the journey on User journeys (`alfred/tour.py` reads them from
`docs/journeys.md`, so they are the page's words).

## Saying how a stage is

- **✓ Works**: the stage does what it says.
- **✗ Off**: something is not right, with what is off typed in the field beside
  the buttons; Enter in the field is ✗ Off. Off with the field empty is refused.

Either is kept, and the box goes to the next stage. A stage with a word on it
wears it among the journey's stages, and the box says what was said, by whom and
when.

**A word is kept under a name.** The field above the buttons holds it: asked once
and kept by this browser. A word with no name is refused. The name is what was
typed, and nothing checks it.

**A word is of the build it was said of.** Once the server runs another commit,
what was said is still shown, marked as said of an earlier build, and the stage
waits for a word again: the box's count is of words on this build, and it opens
on the first stage without one.

## Where the words are kept

In the database, one document per word in the `TourWord` collection, never
rewritten: the stage (`first-video/edit`), `works` or `off`, what is off, who
said it, the moment, and the commit the server ran with whether its tree had
changes beside it. The latest word on a stage is its feedback.

**Only a server started with `ALFRED_TOUR_WORDS` keeps them**
([configuration](configuration.md)), because a name typed into a browser is not a
login: a word is taken only by a server that answers its own machine. The dev
stack publishes on loopback unless `ALFRED_BIND` says otherwise, so
`ALFRED_TOUR_WORDS=1 ./al dev` is a server that keeps them. A process that sees
it with `ALFRED_PRODUCTION` refuses to start. Without it the tour still shows
every journey and takes the editor to every stage, and keeps nothing.

The commit is read with git from the checkout the server runs, which the dev
stack mounts at `/app`. Where git cannot read it, the commit is null, and every
word counts for whatever build is running.

## The routes

- `GET /tour`: the journeys in their order, each stage with its line, what to
  try on it, what takes the editor there (`puts`), and its latest word with
  whether that is `current`, said of the commit now running; the commit the
  server runs; and `words`, whether this server keeps them. It answers without a
  session, as the docs do.
- `POST /tour/feedback`: one word, `{stage, verdict, note, by}`. A stage no
  journey has is refused (404), and so is a verdict that is neither, Off with
  nothing said, or a word with no name (422).
- `GET /tour/feedback`: every word kept, oldest first.

The two `GET` documents have the shape the governance corpus's
`project-seed/tour-schema.json` states, which an application serves and the
harness reads.

What alfred plans, and what was found of each thing it claims, is not kept in
this repository. Its roadmap is `project/ROADMAP.md` on alfred's branch of the
governance corpus, at `governance/qm/project/ROADMAP.md` in a clone, and
`qmcp tour` reads it beside the two `GET` routes: each claim, the journey that
shows it, and what was said of each stage.

## What it does not do

- It makes, renders, transcribes, sends and deletes nothing: Generate a demo
  project, New project, Queue render, Deliver, Download, Transcribe timeline,
  Save and every delete are a person's.
- It stands in for nothing a person brings: their own footage in the library, an
  audio engine for captions, an account.
- Nothing leaves the server: the words are in its own database.
