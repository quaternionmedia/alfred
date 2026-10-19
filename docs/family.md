# The family dev loop

alfred is the control plane, but it doesn't work alone:

| Repository | Its part | Where alfred meets it |
|---|---|---|
| **otto** | the picture engine | vendored at `alfred/otto`, installed editable |
| **vox** | the sound seam: the contract and client for an audio engine | vendored at `alfred/vox`, installed editable |
| **joe** | the audio engine | over HTTP, at `ALFRED_AUDIO_ENGINE_URL` |
| **qmcp** | QM's tool server | calls alfred's API as tools and flows |
| **codecartographer** | shares the workspace's Golden Layout shell | the same shell, kept in step |
| **org-dotgithub** (quaternionmedia/.github) | the org's reusable CI workflows | alfred's CI calls them |

A change usually touches more than one repository. `./al family` runs the loop across all of them from this checkout:

```sh
./al family                 # where every repository is, and what is off
./al family test            # each one's quick suite
./al family up              # joe, then the dev stack pointed at it
./al family smoke           # a live check of the running stack
./al family down            # the dev stack, and the joe `up` started
./al family loop            # test, up, smoke, down
```

It is `scripts/family.py` and uses only Python's standard library, so it runs with any Python 3.8 or newer on the host: no environment to make first. `./al` finds that Python (`python3`, else `python`).

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

`./al family` prints each repository's branch and commit, whether it has changes, how it stands against its upstream, and where it was found. Then come the things that will bite:

- **A vendored engine whose pin differs from the checkout beside it.** alfred runs the pin: what the submodule records, not the sibling's branch.
- **A pin that is on no `origin` branch** this machine knows of. A clone cannot check it out, so push the engine before alfred. "Knows of" means as fresh as your last `git fetch`.
- **A joe without the media API** (`/api/media`), which captions and audio analysis need, and **a qmcp without alfred tools**.
- **A codecartographer without `web/node_modules`**, which its suite needs.

## Each one's quick suite

`./al family test` runs each one's own quick suite, one after another. `./al family test joe vox` runs some, and `--full` runs the whole suites. Each repository's output goes to `.family/logs/<name>.log` (git-ignored). The console gets one line per repository, plus the end of the log when it fails.

| Repository | Quick | `--full` |
|---|---|---|
| alfred | builds the test image, then `./al nox -r -s lint` and `./al nox -r -s coverage -- unit`, the unit tier, reusing nox's environments in `tests/.nox` | builds the test image, then `./al pytest` and `./al test` |
| otto | its Dockerfile's `test` target, built and run | the same |
| vox | `uv run pytest -q` | the same |
| joe | `uv run --frozen pytest -q` (set `JOE_FFMPEG` if ffmpeg isn't on PATH) | the same |
| qmcp | `uv run --locked pytest -q tests/test_alfred*.py` | `tests walkthrough` |
| codecartographer | `npm run typecheck`, `npm run test:pure` in `web/` | adds `test:state` and `build` |
| org-dotgithub | none: its workflows run in the CI that calls them | |

A repository that can't run its suite here, because it wasn't found, or uv, docker or `node_modules` is missing, is skipped with the reason, not failed. Building the test image first matters for alfred, because `./al nox` and `./al pytest` otherwise use whichever `alfred_test` image is already there, however old.

`./al pytest` and `./al nox` run as their own compose project, `<project>-pytest`. That's so a test run can't touch a running dev stack: their throwaway database is a service named `db`, as the dev stack's is.

## The stack, wired together

`./al family up`:

1. **Starts joe.**
   - It starts from its checkout with `uv run --frozen uvicorn api:app` on `ALFRED_JOE_HOST:ALFRED_JOE_PORT`. The defaults are loopback and 8010. On a Linux host, the host defaults to docker0's address, because a container can't reach the host's loopback ([Configuration](configuration.md#docker-hosts-and-joe)).
   - If joe already answers on that port, it uses it. If something else holds the port, it says what, by its OpenAPI title, and stops.
   - Its log is `.family/logs/joe.log`.
2. **Starts the dev stack** with `./al dev -d` (`--build` to rebuild), with `ALFRED_AUDIO_ENGINE_URL=http://host.docker.internal:<port>` unless you've set it. It then waits for `/healthz`.
3. **Prints where everything is,** including the `QMCP_ALFRED_URL` that points qmcp's alfred tools at it.

`./al family down` stops the dev stack, and the joe that `up` started, if it did. It leaves alone a joe that `up` found already running.

joe has no authentication: anything that can reach its port can use it. `up` binds it to loopback, or to docker0 on Linux, which only this machine's containers reach. Don't set `ALFRED_JOE_HOST=0.0.0.0` on a network you don't trust. joe's own security notes say what it exposes.

## The live check

`./al family smoke` asks the running stack, through `127.0.0.1`, everything a change across the family can break:

- alfred answers, as "Alfred API";
- its database and a render worker are up;
- the audio engine is configured and answers;
- the media library lists, and one of its files with sound is analysed by joe through vox (skipped when no file has sound);
- a template preview, and a timeline preview fetched through its signed URL;
- a one-second render, rendered, downloaded through its signed URL with a range request, then deleted;
- qmcp's `alfred_health` tool reaches it, when a qmcp with alfred tools is found.

Most of that needs a session. With the auth bypass (`ALFRED_DEV_SKIP_AUTH=1 ./al family up`), it needs nothing. Otherwise set `ALFRED_SMOKE_EMAIL` and `ALFRED_SMOKE_PASSWORD` to an account on that stack. Without either, the checks behind a session are skipped, and the output says how to run them.

## The whole loop

`./al family loop` runs the quick suites, brings the stack up, runs the live check, and takes it down again: one command after a change that crosses repositories. `--keep` leaves the stack up afterwards. It exits non-zero if any suite or check failed.

## What it never prints

The helper prints no secret, under the project's logging rule (AGENTS.md, "Logging and secrets"):
- It reads `ALFRED_SMOKE_PASSWORD` and the token a login returns, and prints neither.
- Every line it shows from a log or an answer goes through a redactor first. That covers signed URLs' `sig=`, bearer tokens, `access_token`, and any `…SECRET…`, `…PASSWORD…`, `…TOKEN…` or `…KEY…` assignment.
- The logs under `.family/logs/` are the suites' own output, kept on this machine and ignored by git.
