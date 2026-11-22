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
| `label` | score | a title for each candidate: the topic the language engine has live over it, the strongest of those it read within the candidate ([Who spoke, and what about](editing-by-text.md#who-spoke-and-what-about)); a category, the one of `categories` (separated by commas) a labeller sorts what is said in the candidate into; and, with `score`, how well the labeller says it stands alone, 0 to 1, under `label` ([The labeller](#the-labeller)); each skipped, with a note in the job, where there is none | `title` true, `categories`, `score` false |
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

### The labeller

A `label` step with `categories`, or with `score`, asks a labeller: a chat
model behind an OpenAI-style route at `ALFRED_LABELLER_URL`, serving the
model `ALFRED_LABELLER_MODEL` names
([Configuration](configuration.md#the-labeller)). It is asked a candidate at
a time, over the candidates standing where the step is in the recipe: after
`top`, as the built-in recipes place it, a run asks about as many candidates
as it keeps drafts, and before it, about every window. Of each, it is asked
which one of the categories fits what is said in the candidate, answered with the category alone, and how well the stretch
stands alone as a clip, answered with a whole number from 0 to 10, which the
step scales to 0 to 1. The words sent are cut to a fixed length; the answer
is read for the longest category it names, and for the first number it
holds. A labeller that does not answer ends the asking at the first failure,
with a note in the job: the candidates asked before it keep what they were
given, the rest are made uncategorised, and the drafts are made all the
same.
alfred names no model: the route and the model are the operator's, and `GET
/health` reports whether the labeller answers and serves the model named.
No built-in recipe asks it; a copy of one with `categories` on its `label`
step does.

## The built-in recipes

Every account has these, read by name; an account that wants one changed
stores a copy under a name of its own.

| Recipe | Leaves | Knobs |
|---|---|---|
| `highlights` | the windows where the most is said, and where the talking gets loud while the picture moves, each a short of its own: `windows`, `dialogue`, `spikes`, `top`, `label`, `compose each` | shortest 8, longest 12, count 25 |
| `teaser` | the best windows, in order, as one piece of a chosen length: `compose together` | shortest 8, longest 12, target 60 |
| `chapters` | one draft per stretch between long pauses, titled: `chapters`, `label` | pause 4 |
| `excerpts` | the excerpt flow's stretches, each a draft: `spans`, `label` | pause 1, shortest 10, longest 90 |
| `tight-cut` | the whole source, its long pauses shortened and its filler words dropped: `fillers`, `tighten`, `compose whole` | longer_than 1.5, to 0.5, the fillers |
| `quotes` | each sentence that stands alone, as a tall short with its words drawn in: `sentences`, `keep`, `dialogue`, `top`, `label`, `render` 1080 by 1920 with captions | shortest 3, longest 20, count 25 |

The first values are a collaborator's advice for an evening's recording:
clips of eight to twelve seconds, about twenty-five of them. They hold until
they are measured.

## In the editor

The **Sculpt** stage, between Source and Edit, has two panels. **Recipes**
lists the built-in recipes and yours, each with a tick and, once ticked, its
knobs drawn as a form project's fields are; **Sculpt** starts the run over
the open project, and a line under the button follows it to done or failed,
with the run's notes. The button waits, and says why, while the project has
no transcript. **Drafts** lists what the runs left, each with its length, its
recipe, its category where a labeller gave one, and its scores; opening one takes it to Edit as any
project, and ticking several then **Drop** lets go of them with their cues.
On a phone the stage shows one panel at a time, chosen by a switch. The line
under the rail offers **Next: Sculpt** from Source once a project is
transcribed, and the Projects panel lists a source's drafts under it,
collapsed. [From a long recording](journeys.md#from-a-long-recording) walks
it.

## Drafts

`POST /project/{id}/drafts` with `{recipes: [{recipe, values}]}` queues a run
the render worker makes, as a transcription is made: the source's timeline
is measured, each recipe runs over its words, its sound and its motion, and
each draft it leaves is a project of the source's owner, named
`<source> – <title> <n>`: the title the topic the language engine had live
over it where the recipe's `label` step found one, the recipe's label where
not; numbered in timeline order, with where it came from as its
`description`, its captions and its words moved into it, the source's render
settings, and `source`:

``` json title="A draft's source"
{
  "project": "66f1a0…",
  "recipe": "highlights",
  "values": {"shortest": "8", "longest": "12", "count": "25"},
  "spans": [[1832.4, 1841.9]],
  "scores": {"dialogue": 0.84, "spikes": 1.0, "label": 0.8},
  "category": "story",
  "made_at": "2026-11-21T15:02:11Z"
}
```

`category` is the one a labeller sorted the draft into, empty where none was
asked or the answer named none; `scores.label` is how well the labeller said
it stands alone, where that was asked.

The source keeps the run as its `drafts_job`, `queued`, `running`, then
`done` with how many were `made` and the run's `notes` (a step skipped, a
file not measured), or `failed` with the reason; and a cue per span each
draft took, under the source `alfred-drafts`, kind `draft`, its `ref` the
draft's id, which the Cues lane draws. `GET /project` carries `source` and
`description`, so a list groups drafts under their source.

A run refuses, by code, a source with no words (`no_words`: transcribe it
first), a recipe that is neither built in nor yours (`unknown_recipe`), a
source whose run is under way (`drafts_running`) and a broker that will not
take the job (`drafts_not_queued`). `DELETE /project/{id}/drafts` with
`{drafts: [id]}` drops the drafts named, with their cues; it drops nothing
unless every id is one of this source's drafts of yours (`not_a_draft`), and
a project that is not a draft keeps having no delete here.

## Through the API

| Route | |
|---|---|
| `GET /recipes` | the built-in recipes, each with `builtin: true` and its name as its `id`, then the caller's own |
| `POST /recipes` | `{name, label, description, fields, steps}`, owned by the caller; answers it with its `id` |
| `GET /recipes/{id}` | a built-in recipe by its name, or one of the caller's by its id; 404 `unknown_recipe` otherwise |
| `PUT /recipes/{id}` | replaces one of the caller's whole; a built-in cannot be replaced |
| `POST /project/{id}/drafts` | `{recipes: [{recipe, values}]}` → `202 {job}`; the worker makes the drafts |
| `GET /project/{id}/drafts` | `{job, drafts}`, each draft `{id, name, description, duration, source}` |
| `DELETE /project/{id}/drafts` | `{drafts: [id]}` → `{dropped}`: those drafts and their cues |

A recipe is scoped to its owner as a project is: another account's answers
404, exactly as one that does not exist.
