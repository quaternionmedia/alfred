# The family dev loop

```text
$ ./al family loop
ok alfred            240s
ok otto              26s
ok vox               28s
ok joe               43s
ok qmcp              33s
ok codecartographer  2s
-  org-dotgithub     skipped: no suite of its own here: its workflows run in the CI that calls them
…
PASS  alfred answers -- "Alfred API" at http://127.0.0.1:8000
PASS  database and a render worker -- db ok, 1 worker(s)
PASS  audio engine -- answers
PASS  media library -- 5 files
PASS  sound analysed by the audio engine -- videos/e2e-speech.wav: 4.0 s
PASS  template preview -- 200
PASS  timeline preview -- a signed frame, fetched
PASS  render -- rendered in 2 s, downloaded through a signed URL
PASS  qmcp's alfred tools reach it -- alfred_health answered
9 pass
```

*One `./al family loop` against branches of joe, qmcp and vox: each repository's quick suite, then joe and the dev stack, checked live (abridged; about seven minutes).*

alfred is the control plane, but it doesn't work alone:

| Repository | Its part | Where alfred meets it |
|---|---|---|
| **otto** | the picture engine | vendored at `alfred/otto`, installed editable |
| **vox** | the sound seam: the contract and client for an audio engine | vendored at `alfred/vox`, installed editable |
| **joe** | the audio engine | over HTTP, at `ALFRED_AUDIO_ENGINE_URL` |
| **qmcp** | QM's tool server | calls alfred's API as tools and flows |
| **codecartographer** | shares the workspace's Golden Layout shell | the same shell, kept in step |
| **org-dotgithub** (quaternionmedia/.github) | the org's reusable CI workflows | alfred's CI calls them |

A change usually touches more than one. `./al family` runs the loop across all of them from this checkout:

```sh
./al family                 # where every repository is, and what is off
./al family test            # each one's quick suite
./al family up              # joe, then the dev stack pointed at it
./al family smoke           # a live check of the running stack
./al family down            # the dev stack, and the joe `up` started
./al family loop            # test, up, smoke, down
```

It is `scripts/family.py`, on Python's standard library alone, so any Python 3.8 or newer on the host runs it with no environment to make first. `./al` finds that Python (`python3`, else `python`).

## Where each repository is

For each one, the first answer wins:

1. **`ALFRED_FAMILY_<NAME>`**, if you set it: `ALFRED_FAMILY_JOE`, `ALFRED_FAMILY_QMCP`, `ALFRED_FAMILY_VOX`, `ALFRED_FAMILY_OTTO`, `ALFRED_FAMILY_CODECARTOGRAPHER`, `ALFRED_FAMILY_ORG_DOTGITHUB`. It may name any git checkout or worktree, absolute or relative to this checkout. A setting that names no checkout is reported, not passed over: you asked for that one.
2. **A git checkout named after it** in this checkout's parent, grandparent or great-grandparent, nearest first. So `~/src/qm/alfred` finds `~/src/qm/qmcp` and `~/src/joe`. A worktree under `alfred.worktrees/` finds the same siblings.
3. **For otto and vox, the copy vendored here.**

To point the loop at a branch without disturbing a checkout, make a worktree and name it:

```sh
git -C ../../joe worktree add ../joe.worktrees/media feat/video-audio-engine
ALFRED_FAMILY_JOE=../../joe.worktrees/media ./al family up
```

## Status

`./al family` prints each repository's branch and commit, whether it has changes, how it stands against its upstream, and where it was found. Then it flags what will bite:

- **A vendored engine whose pin differs from the checkout beside it.** alfred runs the pin, what the submodule records, not the sibling's branch.
- **A pin on no `origin` branch** this machine knows of. A clone cannot check it out, so push the engine before alfred. "Knows of" is as fresh as your last `git fetch`.
- **A joe without the media API** (`/api/media`), which captions and audio analysis need, and **a qmcp without alfred tools**.
- **A codecartographer without `web/node_modules`**, which its suite needs.

## Each one's quick suite

`./al family test` runs each one's quick suite in turn; `./al family test joe vox` runs some, and `--full` runs the whole suites. Each repository's output goes to `.family/logs/<name>.log` (git-ignored). The console gets one line per repository, plus the end of the log when it fails.

| Repository | Quick | `--full` |
|---|---|---|
| alfred | builds the test image, then `./al nox -r -s lint` and `./al nox -r -s coverage -- unit`, the unit tier, reusing nox's environments in `tests/.nox`; then takes the test project down, pass or fail | builds the test image, then `./al pytest` and `./al test` |
| otto | its Dockerfile's `test` target, built and run | the same |
| vox | `uv run pytest -q` | the same |
| joe | `uv run --frozen pytest -q` (set `JOE_FFMPEG` if ffmpeg isn't on PATH) | the same |
| qmcp | `uv run --locked pytest -q tests/test_alfred*.py` | `tests walkthrough` |
| codecartographer | `npm run typecheck`, `npm run test:pure` in `web/` | adds `test:state` and `build` |
| org-dotgithub | none: its workflows run in the CI that calls them | |

A repository that can't run its suite here (not found, or uv, docker or `node_modules` missing) is skipped with the reason, not failed. alfred's test image is built first because `./al nox` and `./al pytest` otherwise use whatever `alfred_test` image is there, however old.

`./al pytest` and `./al nox` run as their own compose project, `<project>-pytest`, so a test run can't touch a running dev stack: their throwaway database is a service named `db`, as the dev stack's is.

## The stack, wired together

`./al family up`:

1. **Starts joe.**
   - It runs `uv run --frozen uvicorn api:app` from joe's checkout on `ALFRED_JOE_HOST:ALFRED_JOE_PORT`, by default loopback and 8010. On a Linux host, the host defaults to docker0's address, because a container can't reach the host's loopback ([Configuration](configuration.md#docker-hosts-and-joe)).
   - If joe already answers on that port, it uses that joe. If something else holds the port, it names it by its OpenAPI title and stops.
   - Its log is `.family/logs/joe.log`.
2. **Starts the dev stack** with `./al dev -d` (`--build` to rebuild), with `ALFRED_AUDIO_ENGINE_URL=http://host.docker.internal:<port>` unless you've set it, then waits for `/healthz`.
3. **Prints where everything is,** including the `QMCP_ALFRED_URL` that points qmcp's alfred tools at it.

`./al family down` stops the dev stack, and the joe `up` started, if it did. A joe that `up` found already running is left alone.

joe has no authentication: anything that reaches its port can use what it serves. `up` binds it to loopback, or on Linux to docker0, which only this machine's containers reach. Don't set `ALFRED_JOE_HOST=0.0.0.0` on a network you don't trust.

A fresh joe serves only its media API, all alfred uses, so `up` sets nothing on it. Its microphone, transcripts and audio library stay off unless you start the loop with `JOE_ALLOW_MICROPHONE`, `JOE_ALLOW_TRANSCRIPTS` or `JOE_ALLOW_LIBRARY` set to 1; qmcp's and vox's voice loops need the microphone. Each one turned on is announced with a warning in `.family/logs/joe.log`. joe's `docs/security.md` says what each exposes.

## The live check

`./al family smoke` asks the running stack, through `127.0.0.1`, everything a change across the family can break:

- alfred answers, as "Alfred API";
- its database and a render worker are up;
- the audio engine is configured and answers;
- the media library lists, and joe analyses one of its files with sound through vox (skipped when no file has sound);
- a template preview, and a timeline preview fetched through its signed URL;
- a one-second render: rendered, downloaded through its signed URL with a range request, then deleted;
- qmcp's `alfred_health` tool reaches it, when a qmcp with alfred tools is found.

Most of that needs a session. With the auth bypass (`ALFRED_DEV_SKIP_AUTH=1 ./al family up`), it needs nothing; otherwise set `ALFRED_SMOKE_EMAIL` and `ALFRED_SMOKE_PASSWORD` to an account on that stack. Without either, the checks behind a session are skipped, and the output says how to run them.

## The whole loop

`./al family loop` runs the quick suites, brings the stack up, runs the live check, and takes it down: one command after a change that crosses repositories. `--keep` leaves the stack up. It exits non-zero if any suite or check failed.

## What it never prints

The helper prints no secret, under the project's logging rule (AGENTS.md, "Logging and secrets"):
- It reads `ALFRED_SMOKE_PASSWORD` and the token a login returns, and prints neither.
- Every line it shows from a log or an answer goes through a redactor first, which covers signed URLs' `sig=`, bearer tokens, `access_token`, and any `…SECRET…`, `…PASSWORD…`, `…TOKEN…` or `…KEY…` assignment.
- The logs under `.family/logs/` are the suites' own output, kept on this machine and ignored by git. `ALFRED_FAMILY_STATE` moves them, with the record of the joe `up` started: each run of [`./al loop`](loop.md) but `main` keeps its own under `.loop/<name>/family/`, so taking its stack down never stops a joe another run started.
