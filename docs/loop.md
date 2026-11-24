# The test loop

`./al loop` runs alfred's suites side by side, as one named run. Start as many runs as you like: each has its own compose projects, stack ports, database, logs and browser results, so two runs never test each other's containers.

```text
$ ./al loop
loop main: quick, pytest, e2e, docs   (logs: .loop/main/)
.. quick    host tests
.. pytest   ./al pytest, down
.. e2e      ./al test
.. docs     mkdocs build --strict

ok quick        23s  141 passed
ok docs         41s  built, strict
ok pytest     6m10s  1892 passed, 8 skipped, 8 xfailed
ok e2e        9m02s  402 passed

quick: ok  pytest: ok  e2e: ok  docs: ok
```

## Runs

```sh
./al loop                            # quick, pytest, e2e and docs, at once
./al loop --stack --keep             # ... then joe and the dev stack, checked live, left up
./al loop fast --only quick,docs     # the ones that take seconds
./al loop slow --only e2e --grep @slow
./al loop b --stack --port 8100      # a second stack beside the first
./al loop shots --only recipes       # the docs' screenshots and the recipes' recordings
./al loop main --down                # take a run's stack down
./al loop --list                     # the runs this checkout has made, and which stacks are up
./al loop b --stack --dry-run        # what a run would start, and nothing else
```

A run is named by its first argument, `main` when there is none: lower case, digits, `-` and `_`. Two runs of the same name at once are refused, since they would share everything; `.loop/<name>/running` marks a run that is going.

## The suites

| Suite | What it runs | Needs |
|---|---|---|
| `quick` | the host's own tests of the scripts and the docs (`tests/unit/test_loop.py`, `test_family.py`, `test_task_runner.py`, the docs and cookbook tests), in seconds | `uv` |
| `pytest` | the API suite in Docker, with formatting and lint, as CI runs it (`./al pytest`) | Docker, a POSIX shell |
| `e2e` | the browser suite in Docker, desktop and phone (`./al test`) | Docker, a POSIX shell |
| `docs` | the docs site, built `--strict` into `.loop/<name>/site` | `uvx` |
| `family` | the quick suites of otto, vox, joe, qmcp and the rest (`--family`) | each one's own tools ([Family dev loop](family.md)) |
| `stack` | joe, then the dev stack pointed at it, then the live check (`--stack`) | Docker, `uv` for joe |
| `recipes` | against the stack: the docs' screenshots, the recipes' recordings and the cookbook (`--recipes`) | the host's `website/node_modules` |

A run's suites start together and report as each one finishes. Each writes its whole output to `.loop/<name>/<suite>.log`; the console gets one line per suite with what it counted, and the end of the log when it fails. A suite that cannot run here is skipped with the reason, not failed. The run exits non-zero if any suite failed.

## Flags

| Flag | What it does |
|---|---|
| `--only quick,docs` | these suites and no others |
| `--skip e2e` | the default suites but these |
| `--stack` | add the stack: joe, the dev stack, the live check |
| `--keep` | leave the stack up afterwards (implies `--stack`) |
| `--recipes` | retake the screenshots and recordings against the stack (implies `--stack`) |
| `--family` | add the other repositories' quick suites |
| `--port 8100` | the stack's api port; the live-reload and database ports follow it |
| `--joe ../../joe.worktrees/media` | joe's checkout, as `ALFRED_FAMILY_JOE` |
| `--grep @slow` | only the browser tests matching this, as Playwright's `--grep` (no spaces) |
| `--projects chromium,docs` | the browser projects to run, in place of `chromium,phone` |
| `--down` | take this run's stack down, and stop the joe it started |
| `--list` | the runs made here, and whether each stack answers |
| `--dry-run` | print each step with what it is given, and start nothing |

Environment set in the shell, `ALFRED_DEV_SKIP_AUTH=1` for one, reaches every step as it does `./al dev`.

## What a run is called

| | `main` | any other name, `b` |
|---|---|---|
| API suite | compose project `<checkout>-main-pytest` | `<checkout>-b-pytest` |
| Browser suite | `<checkout>-main-e2e`, results under `website/.loop/main/` | `<checkout>-b-e2e`, `website/.loop/b/` |
| Stack | `<checkout>`, the ordinary dev stack, on 8000, 8001 and 27017, with `./database` | `<checkout>-b`, on `--port` or the first free block of 8100, 8200 and so on, with its database under `.loop/b/` |
| joe | the joe on `ALFRED_JOE_PORT` (8010), started by this run if none answers | the same joe, shared |
| Logs | `.loop/main/` | `.loop/b/` |

`main`'s stack is the dev stack, so `./al stop` and `./al family down` work on it too, and a run replaces the stack that was up: it takes it down and brings it up again from the checkout as it is now. Every stack shares one joe. `--down` stops only the joe its own run started.

Images are named after the checkout (`ALFRED_IMAGES`, which `./al` sets): every run from one checkout builds the same images from the same files, and two checkouts never swap each other's. Before this, every checkout built `alfred_api`, and a worktree's test run could start on another worktree's dependencies.

## Checking a change in the app

```sh
ALFRED_DEV_SKIP_AUTH=1 ./al loop --stack --keep --joe ../../joe.worktrees/tighten
```

That runs every suite, and leaves joe and the dev stack up at <http://127.0.0.1:8000> to try by hand. `./al loop --down` takes them down. While it is up, a second run can test something else beside it, on its own ports:

```sh
./al loop slow --only e2e --grep @slow
```

## Interrupting a run

Ctrl-C stops every process the run started. Containers it brought up may stay: `./al loop <name> --down` takes its stack down, and the next `./al test` or `./al pytest` under that name starts from nothing anyway.

## What it never prints

The steps are handed ports, project names and paths and nothing else, and `--dry-run` shows exactly those. The end of a failed suite's log goes through the same redaction as [`./al family`](family.md#what-it-never-prints) before it is shown. The logs themselves stay under `.loop/`, which git ignores.

## The loop and CI

The loop is local. CI (`.github/workflows/CI.yml`, through the org's shared workflows) runs the same API and browser suites on GitHub's machines when a branch is pushed; nothing in `./al loop` starts it. Run the loop first, and push when it is green.
