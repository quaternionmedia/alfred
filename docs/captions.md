# Captions

A project's captions are lines of text and the stretch of the timeline each is
shown for, in timeline seconds -- the seconds the editor's playhead counts and
a render's output runs in. They are typed in the editor, imported from a
subtitle file, or transcribed from the timeline's own sound by an audio
engine, and otto draws them into renders.

Two engines cooperate under alfred's control plane, side by side: **otto**
renders the picture (vendored at `alfred/otto`), and **vox** carries the sound
(vendored at `alfred/vox`), driving an audio engine -- joe, by default -- over
HTTP. alfred owns the captions, the jobs and the routes; it does no audio or
video work itself.

## In the editor

On a wide screen, 1024 CSS pixels and up, **Captions** is a tab in the
workspace's right-hand column, beside Render and Deliver. On a phone, or
anything narrower, it is the Edit stage's panel, above the viewer and the
timeline.

- **Add at playhead** adds a two-second caption where the playhead is. Each row
  has a start and an end in seconds -- set by typing, or from the playhead with
  the buttons beside them -- the text, a button that plays from the caption's
  start, and one that deletes it. The list keeps itself in order of when
  captions start, and marks a caption that cannot be shown (no text, an end
  before its start) and why; nothing is saved while one is marked.
- **Import…** reads a SubRip (`.srt`), WebVTT (`.vtt`) or JSON file. The server
  reads it and the panel shows what it found -- how many captions, how many
  cues were left out for having no text or no length, the first few -- for
  you to use, add to the captions already there, or cancel. Accepting saves.
- **Transcribe timeline** has the project's *saved* timeline heard by the
  server's audio engine and replaces the captions with what it said, asking
  first when there are captions to replace. It is unavailable, and says why,
  when the server has no audio engine, when the engine is not answering, or
  when no renderer is running to mix the timeline's sound. The panel follows
  the job until it is done -- how many segments of speech were heard -- or has
  failed, with the reason.
- **Style**: whether the captions are drawn into renders at all, their size,
  position, line alignment, text colour, the box behind them and its colour,
  and the font. **Draw into renders** is off until you tick it: a project's
  imported or transcribed captions are often still being corrected.
- **Save** keeps the captions and the style on the project.

The caption under the playhead shows over the viewer, in its style -- faint
while the style does not draw captions into renders. It is a likeness drawn by
the page; the render is drawn by the server.

Every render of the timeline carries the captions and their style once
**Draw into renders** is ticked, exactly as they stand in the editor, saved or
not -- as the timeline itself is sent.

## Through the API

| Route | |
|---|---|
| `GET /project/{id}/captions` | `{captions, style, job}` |
| `PUT /project/{id}/captions` | `{captions, style?}`: stores those and nothing else; answers as `GET` does |
| `POST /project/{id}/captions/import` | `{format: "srt"\|"vtt"\|"json", text}` → `{captions, skipped}`; stores nothing |
| `POST /project/{id}/captions/transcribe` | `202 {job}`; `503` with the reason when there is no engine; `409` while one runs; `422` when the saved timeline has nothing to hear |
| `GET /media/{name}/audio` | the engine's analysis of a library file |
| `GET /health` | gains `audio_engine: {configured, ok, detail}` |

Each project route is scoped to the caller as every project route is: a
project that is not yours answers 404. `GET /project/{id}` carries `captions`
and `caption_style` too.

A caption is `{start, end, text}`: `start` at or after 0, `end` after it, text
that says something and at most 500 characters of it. A project carries at
most 1000, kept in order of when they start.

The style is `{enabled, fontsize, color, bg, position, align, font}` -- the
textBox template's own fields -- every one optional:

| Field | Default | |
|---|---|---|
| `enabled` | false, on a project | whether renders draw the captions |
| `fontsize` | 54 | pixels in a 1080-line frame, scaled with the render: 36 at 720 |
| `color` | `#ffffff` | `#rgb` or `#rrggbb` |
| `bg` | `#000000` | the box behind the text, drawn at 40% opacity; `""` for none |
| `position` | `bottom` | `bottom`, `top`, `center`, or `[across, down]` -- `left`/`center`/`right`, `top`/`center`/`bottom` |
| `align` | `center` | how lines line up: `center`, `west`, `east` (`left`, `right` are taken too) |
| `font` | `DejaVu-Sans` | a font name as ImageMagick lists it |

**`enabled` on a project and on a render.** A project's style always states
`enabled` once it has captions -- as sent, else as it was, else false -- so a
client reading the project knows whether its renders draw them. A render
request is different: `POST /render` takes optional `captions` and
`caption_style`, and a request that carries captions means them -- they are
drawn unless its style says `enabled: false`.

The job is `{state, error, engine, segments, updated_at}`: `state` is
`queued`, `transcribing`, `done` or `failed`; `error` says why it failed, in a
line; `engine` is the address it was sent to, without credentials; `segments`
is how many stretches of speech the engine heard. A job not heard from for
the engine's timeout and a quarter of an hour is taken as abandoned -- a
worker that died -- and another may start.

## Importing subtitles

The readers forgive what is unambiguous and name the line they could not
read when it is not:

- a byte-order mark; CRLF, LF or CR line ends;
- `,` or `.` before the milliseconds, one to nine digits of them, hours past
  99 or no hours at all (`01:02.500`);
- SubRip index numbers or none, and coordinates after the timing;
- WebVTT's header, cue identifiers, cue settings (`align:start`), and its
  `NOTE`, `STYLE` and `REGION` blocks;
- markup inside a cue -- `<i>`, `<font>`, `<c.yellow>`, `<v Speaker>`, inline
  timestamps, `{\an8}` -- which a render does not draw, and HTML entities;
- cues with no text or no length, which are left out and counted.

JSON is a list of `{start, end, text}`, or an object holding one under
`captions` (as alfred answers), `segments` (as a speech engine answers) or
`cues`. Times are seconds, or timestamps such as `"00:00:01,500"`.

## How captions render

Each caption becomes one `textBox` template clip, appended after the
timeline's own clips -- so drawn over them -- with an explicit `start`, a
`duration` of `end - start`, and no fades. A caption past the end of the
timeline is left out, and one running over it is cut there, so captions never
lengthen a render.

The clips are made from the style when the render is queued, for the render's
own frame: the font size scales with the frame's height; the caption sits
inside a safe area inset 5% from the top and bottom; the box behind it is
sized to the text -- estimated from DejaVu Sans's own glyph widths -- and the
text wraps at 90% of the frame's width. A render keeps its captions beside its
timeline rather than written into it, so a rerender makes the clips again and
draws them as the first render did.

## Transcribing a timeline

`POST /project/{id}/captions/transcribe` queues a job on the render queue: the
worker that renders is the one that transcribes, so `GET /health`'s renderer
count says whether anything will pick it up.

1. otto builds the project's saved timeline -- its video and audio clips, as
   long as the whole timeline, so silence stands where the rest were and
   times do not move -- and the mix is written as a 16 kHz mono WAV in a
   directory private to the job, removed afterwards.
2. The audio engine hears it, through vox, with word timings.
3. What it heard becomes captions a person can read in the time they are
   shown: a stretch of speech is cut at word boundaries into captions of at
   most two lines (84 characters) and seven seconds, ending at sentences where
   one ends; times are clamped to the timeline; empty text is dropped.
4. The captions replace the project's own, and the job says `done`. A project
   that had no style gets one that does not draw them into renders until
   someone ticks the box.

A failure -- no sound in the timeline, a media name the library does not
hold, an engine that is missing, refuses or does not answer -- leaves the
captions as they were and the job `failed`, with the reason in a line.

## The audio engine

alfred reaches the engine through vox's `EngineContract`: the paths, parameter
names and response keys an engine must answer with, as a value whose defaults
are joe's spelling. `alfred/core/utils/audio_engine.py` builds it from the
settings below and is the only module in alfred that imports vox; nothing in
alfred spells a path or key of the engine's. vox's media client
(`vox.media.MediaEngine`) uploads the sound and asks for a transcript or an
analysis -- joe's media API by default: `POST /api/media`, then
`/api/media/{id}/transcribe` or `/analyze`.

| Setting | Default | |
|---|---|---|
| `ALFRED_AUDIO_ENGINE_URL` | unset | the engine's base address; unset is no engine |
| `ALFRED_AUDIO_ENGINE_TIMEOUT` | `1800` | seconds one request may take. Transcribing runs on the render worker, so nothing else waits on it; joe takes about 18 s for its first transcription after it starts, then roughly as long as the speech on a CPU |
| `ALFRED_AUDIO_ENGINE_CONTRACT_<FIELD>` | vox's | any field of vox's `EngineContract`, for an engine that spells it differently; `none` says it does not offer it |

A `CONTRACT_` name that is not a field of the contract is reported by
`GET /health` rather than ignored. Both settings go to the api and to the
renderer: the api asks the engine for `/health` and for analyses, and the
renderer transcribes.

**vox's media client** is `vox.media`, which the vendored vox carries. A build
with an older vox, without it, says so in `GET /health`'s
`audio_engine.detail`, answers 503 with the same reason to a transcription,
and sends nothing to the engine.

### Pointing alfred at joe

joe's own CLI binds 8000, which is alfred's port. In joe's checkout, run its
API on another one:

```sh
uv run uvicorn api:app --port 8010
```

and start alfred with the address its containers reach the host by:

```sh
ALFRED_AUDIO_ENGINE_URL=http://host.docker.internal:8010 ./al dev
```

Docker Desktop resolves `host.docker.internal` itself; on a Linux host,
`dev.yml` maps it to the host's gateway, and joe has to listen on an address
the containers can reach: see [Configuration](configuration.md). Then
`GET /health` should answer `audio_engine: {configured: true, ok: true}`. It
needs a session: send a token, or start the stack with
`ALFRED_DEV_SKIP_AUTH=1`. `GET /healthz` needs none, and says only that the
api is up. And, as with any port, check what is answering there before
trusting it.

### Analysing library media

`GET /media/{name}/audio` -- `name` as `GET /media` lists it, `videos/<file>`,
or the bare file name -- hands the file to the engine and answers its
analysis: `duration`, `tempo` (beats a minute), `beats` and `onsets` (seconds),
`loudness` (`rms_db`, `peak_db`, `lufs`), `silences` (`[{start, end}]`) and
`peaks` (`{rate, values}`, 0 to 1). `features` asks for some of `tempo`,
`beats`, `onsets`, `loudness`, `silences` and `peaks`; all by default. The
answer is kept until the file changes. 404 for what the library does not hold,
422 for an image or a file the engine will not read, 502 when the engine
fails, 503 when there is none.

## Testing

No test needs joe, a speech model or a download.

- `tests/unit/test_audio_engine.py` drives the adapter against a fake of
  vox's media client, with an alien contract that shares no path, parameter
  or key with the default, and greps alfred's own source for any of joe's
  spellings.
- `tests/stubs/audio_engine.py` is a deterministic engine speaking joe's media
  API: it hears a segment of "speech" wherever the sound it is sent is louder
  than a whisper, timed where the sound is. The pipeline tier mixes real
  timelines through it in-process; `test_e2e.yml` runs it as the browser
  suite's engine, and has it write `videos/e2e-speech.wav` -- two bursts of
  tone -- into the library for a timeline to transcribe.
- `tests/pipeline/test_caption_pipeline.py` encodes captions and reads the
  frames back: text and its box where the style puts them, while they are
  shown and not otherwise.
