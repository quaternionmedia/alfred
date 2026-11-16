# Core functionality tests

Scope: the backend and the render engine. Browser coverage lives in
`website/e2e/` and is out of scope here. The plan these tests were built
from, their tally and the defects they pin are the project's, in
[governance/qm/project/plans/core-tests.md](../governance/qm/project/plans/core-tests.md).

```sh
pdm run pytest                                       # everything
pdm run pytest -m "not needs_ffmpeg and not needs_db and not needs_docker"
pdm run pytest -m needs_ffmpeg                       # the real encode
pdm run pytest -m needs_docker                       # builds a container
pdm run pytest -m needs_imagemagick                  # draws text
```

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
    test_stack_settings.py every setting reaches the services that read it
    test_port_allocation.py alfred's and joe's default ports are qm's
                         allocation's, read from governance/qm/ci/dashboard.py
    test_event_loop.py   the api answers while slow work is being done
    test_blocking_calls.py no coroutine in the api calls something that blocks
    test_family.py       ./al family: where each repository is, each one's suite,
                         and up, smoke and down against stand-ins
    test_cookbook.py     docs/cookbook.md is what the specs generate, linking
                         only what git tracks
    test_docs_recordings.py  each recipe's recording plays on the page that
                         places it, and only where it is on disk
    test_recipe_gifs.py  ./al recipes keeps only passing recipes, and fails a
                         GIF over its cap or an ffmpeg that fails
    test_docs_site.py    the docs build's strict checks and what it loads
    test_docs_accounted.py the docs name every setting, and give no `./al`
                         command that does not exist
    test_password_hashing.py alfred's off-the-loop copies of fastapi-users'
                         hashing, held to the release and the originals
    test_preview_slots.py  so many previews at once; the rest wait, then 503
    test_support_mail.py   support mail is queued, sent by the worker, retried
    test_refusal_codes.py every refusal code is in docs/api/errors.md and is
                         answered by a request; covered routes raise none without
                         one
  pipeline/            needs ffmpeg, no DB, no network
    test_render_pipeline.py
  integration/         needs MongoDB at DB_URL: the app in-process, real auth
    conftest.py          the app, a per-worker database, account factories
  stubs/               deterministic stand-ins for services the stack talks to
    audio_engine.py      joe's media API, hearing "speech" wherever there is
                         sound; served by test_e2e.yml, driven in-process by
                         the pipeline tier
```

## Tiers

Markers, registered in `pyproject.toml` under `[tool.pytest.ini_options]`:
`needs_ffmpeg`, `needs_db`, `needs_docker`, and `needs_imagemagick`, for a
test that draws text and so needs ImageMagick able to find a font.
`conftest.py` probes for each tool and skips a marked test on its absence,
never on its failure, so a bare `pdm run pytest` is safe on any checkout; the
`-m` forms above are for when you want to be sure what ran.

`needs_ffmpeg` resolves through `imageio_ffmpeg`'s bundled binary, not just
PATH: probing PATH alone silently skipped the real-encode test on a machine
where it had been passing, and a skip reads like a pass. That encode stays in
the default run, against the plan's "default is the fast tier": it needs
nothing installed, finishes in under a second, and is the only test that
proves the product's core function works. The marker lets an environment opt
out.

`integration/`, marked `needs_db`, runs wherever DB_URL is set (`./al pytest`
provides a MongoDB, the `db` service in `pytest.yml`) and skips where it is
not. A DB_URL that is set but does not
answer fails the run instead: the database was promised, so its absence is a
fault, not a missing tool. Each xdist worker gets its own database (named in
`conftest.py`, before the app is imported), dropped before and after the
session.

## Recording defects rather than working around them

Several behaviors the plan pins are wrong. Do not fix them in a test commit, and do
not write the test to the intended behavior and leave it failing.

Use `@pytest.mark.xfail(strict=True, reason="...")` for the behavior that
should be. Strict means the test fails if it ever *passes*, so fixing the
defect turns the suite red and prompts removing the marker. Pair it with a
plain test asserting what the code does today, so the current contract is
pinned and a silent change is caught. The browser suite's equivalent is
Playwright's `test.fail()`.

A fix that changes a public API's behavior, rejecting configs the API accepts
being the clear case, is a decision, not a refactor. Record it in
`governance/qm/adr/` rather than deciding it inside a test.
