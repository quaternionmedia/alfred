# Core functionality tests — strategy and work plan

Scope: the backend and the render engine. Browser coverage lives in
`website/e2e/` and is out of scope here.

## Status

Phase 0 and IS-1 through IS-4 are implemented, plus the DB layer and the
stack's own configuration: **1127 tests -- 1117 passed, 2 skipped, 8
xfailed** in the `./al pytest` container, measured on integrate/wave-2 with
its `db` service up, so the database tier ran too. The two skips need a
Docker CLI, which that container does not have; where ImageMagick cannot draw
text, six more skip. The database tier IS-5 needs
exists (`integration/`, marked `needs_db`, against the `db` service
`pytest.yml` provides); its render-queueing tests are not written yet.

```sh
pdm run pytest                                       # everything
pdm run pytest -m "not needs_ffmpeg and not needs_db and not needs_docker"
pdm run pytest -m needs_ffmpeg                       # the real encode
pdm run pytest -m needs_docker                       # builds a container
```

The marked tiers skip themselves when the tool they need is absent, so the
bare `pdm run pytest` above is safe anywhere -- `conftest.py` probes for the
binary and skips on absence, never on failure. The explicit `-m` forms are for
when you want to be sure what ran.

The `needs_ffmpeg` encode is left in the default run, which deviates from the
plan's "default is the fast tier". It earns it: `imageio_ffmpeg` ships its own
binary, so it needs nothing installed, and it completes in under a second. It
is also the only test that proves the product's core function works, so
excluding it by default would waste it. The marker is there for environments
that need to opt out.

Four areas, in the order they should be built:

1. **Config validity** — does a config the editor could emit validate, and
   does an impossible one get rejected?
2. **Input selection** — how a clip resolves to a source.
3. **Output selection** — how render settings become encoder settings and a
   filename.
4. **Rendering pipeline** — clips in, video file out.

## Phase 0 — the environment, which is a hard prerequisite

**No Python test can run today, including the two that already exist.** One
missing package causes four separate failures:

| Break | Where | Symptom |
|---|---|---|
| Image build | `pip install` of `bezier` | `No module named 'pkg_resources'` |
| `import alfred` | `passlib.pwd` | same |
| `import otto.render` | `imageio_ffmpeg._utils` | same |
| Existing pytest suite | collection of `tests/test_alfred.py` | same |

`FROM python` resolves to Python 3.14, which no longer bundles setuptools, so
`pkg_resources` is gone. Only `otto.models` — pure pydantic — imports cleanly.

This is not scope creep ahead of the test work; it is the reason there is no
test work possible without it. Phase 0 fixes:

- Add `setuptools` as an explicit runtime dependency. Three separate
  installed packages import `pkg_resources` at runtime, and none of them
  declares it.
- Pin the Docker base image to a digest, at a Python version the project
  actually supports. `requires-python` says `>=3.8.1,<4.0` while CI tests
  3.11 and the image builds 3.14; narrow it to what is tested.
- `rm -f` the ImageMagick policy, or drop the line. The base now ships
  ImageMagick 7 and the hardcoded version-6 path does not exist, so this
  fails the build even once the first break is fixed.
- Commit a frontend lockfile. `parcel` floats to 2.16.4 against a
  `@parcel/transformer-sass` pinned at 2.8.3, and the bundle does not build.
  The project uses yarn (`al init`, `website/Dockerfile`), so `yarn.lock` is
  the right file — do not introduce `package-lock.json` alongside it.

Definition of done: `pdm run pytest tests/` collects and runs; `docker build .`
succeeds; `yarn parcel build` produces `dist/`.

## Layout

```
tests/
  README.md            this file
  conftest.py          shared fixtures and markers
  unit/                no DB, no network, no ffmpeg — the fast tier
    test_config_validity.py
    test_input_selection.py
    test_output_selection.py
    test_db_layer.py     the DB helpers, without a database
    test_stack_config.py compose files and Dockerfiles
  pipeline/            needs ffmpeg, no DB, no network
    test_render_pipeline.py
  integration/         needs MongoDB at DB_URL: the app in-process, real auth
    conftest.py          the app, a per-worker database, account factories
```

`integration/` runs wherever DB_URL is set -- `./al pytest` provides a
MongoDB in `pytest.yml` -- and skips where it is not. A DB_URL that is set but
does not answer fails the run instead of skipping it: the database was
promised, so its absence is a fault, not a missing tool. Each xdist worker
gets its own database (named in `conftest.py`, before the app is imported),
dropped before and after the session.

Markers, registered in `pyproject.toml` under `[tool.pytest.ini_options]`:
`needs_ffmpeg`, `needs_db`, `needs_docker`. `conftest.py` skips a marked test
when its tool is unavailable, so a bare `pdm run pytest` passes on any
checkout.

`needs_ffmpeg` resolves through `imageio_ffmpeg`'s bundled binary, not just
PATH. Probing PATH alone silently skipped the real-encode test on a machine
where it had been passing -- a skip reads like a pass, which makes it a worse
failure than the error it was meant to avoid.

## Recording defects rather than working around them

Several behaviors below are wrong. Do not fix them in a test commit, and do
not write the test to match the intended behavior and leave it failing.

Use `@pytest.mark.xfail(strict=True, reason="...")` for
behavior-that-should-be. Strict means the test fails if it ever *passes*, so
fixing the defect turns the suite red and prompts removing the marker. Pair it
with a plain test asserting what the code does today, so the current contract
is pinned and a silent change is caught. This is the same pattern as the
`test.fail()` in `website/e2e/navigation.spec.js`.

Where a fix is a behavior change to a public API — rejecting configs the API
currently accepts is the clear case — it is a decision, not a refactor. Record
it in `governance/qm/adr/` rather than deciding it inside a test.

---

# Instruction sets

Each is self-contained. Take them in order; each lands as its own commit and
must be green on its own.

## IS-1 — Config validity

**Goal.** Pin the contract between what the editor can emit and what the
backend accepts, and make the gap between them visible.

**Why this is first.** It needs only `otto.models`, the one module that
imports cleanly today, so it is the fastest feedback available and it does not
depend on Phase 0 completing perfectly.

**Background.** The editor enforces invariants in JS as the user drags
(`website/src/Clip.js`): `outpoint > inpoint`, and `inpoint >= 0`. The pydantic
models enforce none of them. Verified directly:

```
Clip(type='video', name='x.mp4', duration=3, inpoint=5, outpoint=1)  → accepted
Clip(duration=-5)                                                     → accepted
Edl(clips=[])                                                         → accepted
```

`Edl(clips=[])` is the interesting one: the model accepts it and
`generateEdl` raises `EmptyClipsException` at render time, so an invalid
config is only discovered after a job has been queued and dispatched.

**Write, in `tests/unit/test_config_validity.py`:**

1. A realistic editing session as a list of `Edl` snapshots — add a clip, trim
   the in point, trim the out point, move it, add a second clip, cut. Assert
   every intermediate snapshot validates, and the final one validates as an
   `alfred.core.models.render.Render`. Build the snapshots as plain dicts, the
   shape the API actually receives, not as pre-built model instances.
2. Round-trip stability: `Edl.parse_obj(edl.dict())` equals the original for
   each snapshot. Catches lossy or defaulted fields.
3. One test per invariant below, asserting **current** behavior (accepted),
   each paired with a strict-xfail asserting it should be rejected:
   `outpoint < inpoint`; `inpoint < 0`; `duration <= 0`; `opacity` outside
   0–1; `resize <= 0`; `Edl(clips=[])`.
4. Defaults are what the API promises: `Clip.duration == 5`,
   `fadeIn == fadeOut == 1`, `relative is True`; `Render.width/height/fps ==
   1920/1080/30.0`.
5. `alfred`'s `Render` document correctly nests otto's `Edl` — a dict payload
   with a nested `edl` validates, and a malformed nested `edl` is rejected.

**Do not** add validators to the models in this commit. Whether to reject
these configs is a decision with an API-visible consequence; the tests make
the gap legible so it can be decided.

**Done when** the file passes, and every gap has both a pinning test and a
strict-xfail.

## IS-2 — Input selection

**Goal.** Cover how a clip resolves to a source, and pin the failure modes.

**Background.** `otto.getdata.download` returns the input unchanged for
anything not starting with `http`, and otherwise HEADs the URL, enforces a
content-type allowlist and a size ceiling, and content-addresses the result as
`sha256(url).ext`. Its `except` clause **prints and returns `None`**, so a
failed download hands `None` to `VideoFileClip`.

`otto.render.generateEdl` dispatches on `clip.type` through an if/elif chain
with no else. When no branch matches, `c` is never assigned — so the first
clip raises `UnboundLocalError`, and a later clip **silently reuses the
previous clip's object**, duplicating it into the composite. The `if not c:`
guard intended to catch this cannot, because the name is either unbound or
stale.

**Write, in `tests/unit/test_input_selection.py`:** monkeypatch
`otto.getdata.head` and `otto.getdata.download_url`; no network, no files.

1. Non-http input is returned unchanged.
2. Each allowed content type maps to its extension:
   `image/jpeg→jpg`, `video/mp4→mp4`, `image/png→png`, `audio/mpeg→mp3`.
3. Rejected: a `text/*` type, an `html` type, a type outside the allowlist,
   and `content-length` above `1e10`. Assert `download` returns `None` today;
   strict-xfail that it should raise.
4. Content addressing is deterministic and distinct: same URL twice gives the
   same filename, two URLs give different ones.
5. An existing file is not re-downloaded — `download_url` is not called.
6. **Unknown clip type.** `Clip(type='bogus')` as the only clip raises
   `UnboundLocalError`; strict-xfail that it should raise `EdlException`.
7. **The silent-duplication bug**, which matters more than 6: an EDL of
   `[valid_clip, Clip(type='bogus')]` produces a composite of two clips where
   the second is the same object as the first. Assert that today. Strict-xfail
   the correct behavior. This is the highest-value test in this instruction
   set — it is silent, it corrupts output, and nothing else would catch it.
8. Template resolution: a nonexistent template name raises `AttributeError`
   from `getattr(templates, name)`; a name that resolves to a non-template
   module attribute is called anyway. Pin both.

## IS-3 — Output selection

**Goal.** Cover how render settings become encoder settings and a filename.

**Background.** `RenderAPI.queueRender` builds the output filename by
f-string from `project`, `description`, `width`, `height`, `quality` and
`edl.duration`, with no sanitisation and no null handling. All of those are
`Optional`. `renderMultitrack` accepts `fps` and then **hardcodes `fps=30.0`**
in the `write_videofile` call, so the parameter is dead.

**Write, in `tests/unit/test_output_selection.py`:** monkeypatch
`write_videofile` to capture kwargs; assert on what the encoder is asked for,
never by encoding.

1. Filename shape for a fully populated render.
2. `project=None` puts the string `None` into the filename; `description=None`
   omits its segment; `edl.duration=None` yields `Nones`. Pin all three,
   strict-xfail the sane behavior.
3. **Filename injection.** A `description` of `../../etc/passwd` or containing
   a path separator flows unsanitised into the name that `upload()` joins with
   `videos/`. Assert no sanitisation today; strict-xfail that separators and
   `..` are stripped. Flag in the commit message that this has a security
   consequence and belongs in the security branch, not here.
4. **`fps` is ignored.** `renderMultitrack(edl, fps=60)` still calls
   `write_videofile(fps=30.0)`. Pin, strict-xfail.
5. `moviesize=(width, height)` reaches `generateEdl`.
6. `ffmpeg_params` reaches `write_videofile` unchanged. The control-plane
   record names this as an accepted leak that must not widen, so pin it: any
   future filtering becomes a visible test change.
7. `bitrate` is typed `Optional[List]` on alfred's `Render` while
   `write_videofile` expects a string. Pin what a list does today.

## IS-4 — Rendering pipeline

**Goal.** Cover clip-graph construction, and prove end to end that the
product renders a file.

**Write, in `tests/pipeline/test_render_pipeline.py`.** Split into a mocked
group (fast, default tier) and one real render marked `needs_ffmpeg`.

Mocked:

1. `EmptyClipsException` for an empty EDL.
2. N clips produce a composite of N layers, in order.
3. `start` and positive `offset` set the start time; negative `offset`
   subclips instead.
4. `duration` sets clip duration; `edl.duration` sets composite duration.
5. **`outpoint` is ignored** — the handling is commented out in `render.py`.
   Pin, strict-xfail.
6. `fadeIn`/`fadeOut` default to `1`, so every clip is crossfaded whether or
   not the caller asked. `0` disables it, because the guard is truthiness.
   Pin: this is surprising and worth being deliberate about.
7. An `audio` clip sets the composite audio *and* is appended to the video
   clip list. Pin; flag as suspect.

Real render, `@pytest.mark.needs_ffmpeg`:

8. Two template clips, 320×240, ~2s total, rendered to a temp path. Assert the
   file exists, is non-empty, and probes to the expected duration (±1 frame)
   and resolution. Keep it small; this must stay seconds, not minutes.

**This is the single most valuable test in the plan.** Nothing currently
proves the product's core function works at all.

## IS-5 — Render queueing (integration, optional)

**Goal.** Cover the API path that accepts a render and dispatches it.

Needs MongoDB; mark `needs_db` and use `test_e2e.yml`'s db service or a
throwaway container. Celery must be eager or its `.delay` monkeypatched — do
not require a broker.

1. `POST /render` persists the document and returns its id.
2. The dispatched task receives the same `edl`, `filename`, `moviesize`, `fps`
   and `ffmpeg_params` the request implied.
3. `POST /render/rerender/{id}` requires a superuser; a normal user is
   refused. Nothing currently tests any authorization boundary.
4. `GET /render` requires authentication.

---

# Known defects this plan pins

Carried here so they are not rediscovered. None are fixed by these tests.

| # | Defect | Where |
|---|---|---|
| 1 | Unknown clip type silently emits a duplicate layer: the dispatch chain has no `else`, so `c` is unbound on the first clip and stale on a later one. The stale clip is re-processed with the bad clip's timing, producing a second layer with the previous clip's picture. | `otto/render.py` if/elif chain |
| 2 | `download()` returns `None` on any failure | `otto/getdata.py` |
| 3 | `fps` argument ignored; `30.0` hardcoded | `otto/render.py` `renderMultitrack` |
| 4 | `outpoint` silently ignored | `otto/render.py`, commented out |
| 5 | Render filename unsanitised and null-unsafe | `routes/render.py` `queueRender` |
| 6 | Models accept configs the editor cannot produce | `otto/models.py` |
| 7 | `Edl(clips=[])` fails only at render time | model vs `generateEdl` |
| 8 | `bitrate` typed as a list, encoder wants a string | `models/render.py` |
| 9 | Seeding never runs: `count_documents` on a motor handle returns a `Future`, which is always truthy, so `if not ...` never fires and the block is skipped. Verified by inspecting the returned type against a live handle. | `alfred/main.py` |
| 10 | `test_login_fail` posts to `/auth/login`, which is not a route; it asserts the static-file mount's 405 | `tests/test_alfred.py` |

Defect 10 was rewritten while implementing IS-1: the file now asserts that
`/auth/jwt/login` is mounted and `/auth/login` is not, which is the check that
would actually have caught a typo'd route.

## Found while implementing

Not in the original plan; surfaced by writing the tests.

| # | Defect | Where |
|---|---|---|
| 11 | Request validation requires a database. `Render` is a beanie `Document`, and `Document.__init__` calls `get_motor_collection()`, so deciding whether an incoming payload is well-formed needs a live MongoDB connection. This is why filename-construction coverage had to move to IS-5. | `alfred/core/models/render.py` |
| 12 | Fades cannot be switched off on a template clip. `makeColor` hardcodes `.crossfadein(1).crossfadeout(1)` before the engine consults `fadeIn`/`fadeOut`, so `fadeIn=0` only removes the *second* fade. | `otto/templates.py` |
| 13 | Requesting a fade stacks it on the template's. Asking for a 2s fade in yields the template's 1s crossfade *and* a 2s one. | `otto/templates.py` + `otto/render.py` |
| 14 | The template lookup reaches any module attribute. `getattr(templates, clip.name)` resolves imported helpers such as `concatenate_videoclips` and `rgbToDec`, which were never meant to be reachable as templates. | `otto/render.py` |

Defect 1's description was corrected against measured behavior: the duplicate
layer is not the same object as its predecessor, because the effects chain
rebinds `c` at each step. It is a re-processed derivative carrying the
previous clip's pixels — verified identical frame data — with the bad clip's
duration. The corruption is the same; the mechanism is not object identity.

## Fixed in the engine

Defects 1–4 and 12–14 are fixed in otto, which this repository pins at
`a387666`. Their pairs -- a test pinning the defect and a strict xfail for the
fix -- became single tests of the fixed behaviour when the pin moved: an
unknown or missing clip type, a refused download and a template name outside
otto's registry (`otto.templates.TEMPLATES`) each raise `EdlException`
naming the clip; `fps` reaches the encoder; `outpoint` trims; a clip's own
`fadeIn` and `fadeOut` are its only fades. The audio clip IS-4 pinned as
suspect is mixed into the sound and never drawn. Defect 6 stands -- the models
still accept those configs -- but the engine now refuses each of them at
render time with an `EdlException` naming the clip and the field, as it
already refused defect 7's empty EDL, rather than rendering nonsense.
