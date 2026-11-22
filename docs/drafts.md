# Recipes and drafts

A long recording is cut into drafts by a recipe: a chain of algorithms over
the recording's timeline, its words and what was measured of it, configured
by a few knobs. A recipe is data a person chooses and sets, not code a person
writes; a draft is a project of its own, cut from the source, that the editor
opens as it opens any project. The editor runs recipes on its Sculpt stage;
a program runs them through the API.

## Three nouns

- **A source** is a project whose timeline is long: a recording of a show, a
  talk, a session. alfred holds it as any project, with its transcript as
  captions and as words timed one by one ([Captions](captions.md)), and the
  engines' measures of its timeline, the level of the sound and the motion
  of the picture over time ([What is measured](measures.md)).
- **A recipe** is `{name, label, description, fields, steps}`. `fields` are
  knobs, declared as a form project declares its fields
  ([Project](about/project.md#fields)): each has a `type` the editor draws, a
  `name`, a `text` for the person, and a `defaultValue`. `steps` is a list of
  operations from the table below, each `{op, ...parameters}`; a parameter is
  a value, or `{"var": <field name>}`, which reads the knob.
- **A draft** is what a recipe leaves: a project carrying `source`, the
  project it was cut from, the spans it took, the recipe and the values it
  ran with, and the scores it was chosen by, with its captions and its words
  moved into it.

## The operations

The steps run in order over one state: the *candidates* a segment step
found, each with the scores the score steps gave it, thinned by the filter
steps; the ranges the edit steps cut out of whatever is kept; and how the
compose steps make the drafts. Every parameter has a first value, held until
it is measured against what people keep and drop.

| Operation | Kind | What it does | Parameters |
|---|---|---|---|
| `windows` | segment | candidate windows between `shortest` and `longest` seconds, laid `every` so many seconds along the source, each beginning at a word's start and ending at a word's end, a sentence's end preferred | `shortest` 8, `longest` 12, `every` 2 |
| `chapters` | segment | the stretches between pauses of at least `pause` seconds, numbered | `pause` 4 |
| `sentences` | segment | each sentence, captions joined until one ends a sentence | |
| `spans` | segment | stretches cut at pauses and at the ends of sentences, between `shortest` and `longest` seconds, each in its chapter: the excerpt flow's proposal | `pause` 1, `chapter_pause` 4, `shortest` 10, `longest` 90 |
| `silences` | segment | the stretches the audio engine heard as silence, longer than `longer_than` seconds | `longer_than` 2 |
| `dialogue` | score | how much is said in a candidate, words a second over its whole length, so a stretch with a break in it scores by what is said around the break; scaled so the most talkative is 1 | `weight` 1 |
| `spikes` | score | the share of a candidate's seconds in which the level rises above `level_above` times its usual and the picture moves above `motion_above` times its usual at once, each usual a baseline over the whole source; with `where_words`, only seconds in which a word is said; scaled so the spikiest is 1 | `weight` 1, `level_above` 1.5, `motion_above` 1.5, `where_words` true |
| `label` | score | a title and a category from a labeller; skipped, with a note in the job, where there is none | `title` true, `categories` |
| `top` | filter | the highest-scored candidates that do not overlap, by the weighted sum of their scores: `count` of them, or `per_hour` for each hour of the source when that is set | `count` 25, `per_hour` 0 |
| `keep` | filter | the candidates between `shortest` and `longest` seconds | `shortest` 0, `longest` a day |
| `fillers` | filter | cuts each of the `words`, separated by commas, out of what is kept | `words` um, uh, er, ah, erm, hmm |
| `tighten` | edit | cuts every pause between words longer than `longer_than` seconds down to `to` seconds | `longer_than` 1.5, `to` 0.5 |
| `excerpt` | edit | each candidate as a draft of its own: `compose` with `how` `each` | |
| `compose` | compose | `how` the drafts are made: `each` candidate its own draft; the candidates `together`, in order, the best first up to `target` seconds when that is set; or the `whole` source with the edits applied | `how` each, `target` 0 |
| `render` | compose | each draft's render size, and whether its captions are drawn into its renders | `width` 1920, `height` 1080, `captions` false |

A recipe with no compose step makes one draft per candidate. A step naming
no operation, a parameter the operation lacks or a value out of its range is
refused when the recipe is written ([Refusals](api/errors.md),
`unknown_operation` and `recipe_refused`), the sentence naming the step.

## The built-in recipes

Every account has these, read by name; an account that wants one changed
stores a copy under a name of its own.

| Recipe | Leaves | Knobs |
|---|---|---|
| `highlights` | the windows where the most is said, and where the talking gets loud while the picture moves, each a short of its own: `windows`, `dialogue`, `spikes`, `top`, `compose each` | shortest 8, longest 12, count 25 |
| `teaser` | the best windows, in order, as one piece of a chosen length: `compose together` | shortest 8, longest 12, target 60 |
| `chapters` | one draft per stretch between long pauses | pause 4 |
| `excerpts` | the excerpt flow's stretches, each a draft: `spans` | pause 1, shortest 10, longest 90 |
| `tight-cut` | the whole source, its long pauses shortened and its filler words dropped: `fillers`, `tighten`, `compose whole` | longer_than 1.5, to 0.5, the fillers |
| `quotes` | each sentence that stands alone, as a tall short with its words drawn in: `sentences`, `keep`, `dialogue`, `top`, `render` 1080 by 1920 with captions | shortest 3, longest 20, count 25 |

The first values are a collaborator's advice for an evening's recording:
clips of eight to twelve seconds, about twenty-five of them. They hold until
they are measured.

## Through the API

| Route | |
|---|---|
| `GET /recipes` | the built-in recipes, each with `builtin: true` and its name as its `id`, then the caller's own |
| `POST /recipes` | `{name, label, description, fields, steps}`, owned by the caller; answers it with its `id` |
| `GET /recipes/{id}` | a built-in recipe by its name, or one of the caller's by its id; 404 `unknown_recipe` otherwise |
| `PUT /recipes/{id}` | replaces one of the caller's whole; a built-in cannot be replaced |

A recipe is scoped to its owner as a project is: another account's answers
404, exactly as one that does not exist.
