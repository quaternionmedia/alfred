# Running on the host

The dev stack runs alfred in containers ([Get started](start.md)). The same
code runs as processes on this machine, against a MongoDB it can reach, with
joe beside it: for iterating without Docker, or on a machine that has none.
This page is that run. It gives what `./al dev` gives, the editor, the api, a
render worker and the site's watcher; it does not give the suites' stacks
(`./al pytest`, `./al test`), production, or fontconfig, which the api image
has and most hosts do not.

## What you need

| What | Why |
|---|---|
| Python 3.11 and pdm 2.29 or newer | the api and the worker. `pdm.lock` keeps the `docs` group in a lock of its own, which pdm before 2.29 cannot leave out of an install |
| A MongoDB you can reach | projects, renders and the render queue. Any edition; the Community zip, run from a folder, is enough |
| Node.js and yarn | the site, from `website/node_modules`, installed on the host as [Commands](commands.md) says |
| uv | joe, for captions and the Audio lane |
| ImageMagick, on `PATH` | text templates: moviepy draws their text with it, as the api image does ([ImageMagick's policy](build.md#imagemagicks-policy)) |

## Install

```sh
pdm install -G dev -G test -G render
pdm run pip install --no-deps -e alfred/otto -e alfred/vox
cd website && yarn install --frozen-lockfile && cd ..
```

The second line makes the vendored engines editable, as the contributor
guide says: `pdm install` takes a copy of otto and no vox at all.

The api signs its tokens with `ALFRED_SECRET_KEY`, which `./al init` writes
to `.secret_key.local` for a checkout; without Docker, write it yourself:

```sh
python -c "import secrets; print('ALFRED_SECRET_KEY=' + secrets.token_hex(32))" > .secret_key.local
```

## Run

```sh
ALFRED_DEV_SKIP_AUTH=1 ./al host up
```

`up` starts joe as `./al family up` does, then the api, a render worker and
the site's watcher from this checkout's own environment, and says where
each answers. `./al host` says what answers on each port and what `up`
started; `./al host down` stops what it started, and leaves alone a joe or
a database it found running. Each process logs to `.host/logs/<name>.log`,
which git ignores.

Before it starts anything, `up` refuses and says why: the api's port already
answering, the site's port in use, no environment of the checkout's own
(`pdm install` above), no `website/node_modules`, or nothing answering
where `ALFRED_HOST_DB` points.

| Setting | Default | What it does |
|---|---|---|
| `ALFRED_HOST_DB` | `mongodb://127.0.0.1:27018` | The MongoDB the api and the worker use; `up` checks that something answers there. On a port the dev stack does not publish, so both can be started without moving either. |
| `ALFRED_PORT`, `ALFRED_HMR_PORT` | `1732`, `1733` | The api's port and the site's reload port, as for the stack. |
| `ALFRED_JOE_HOST`, `ALFRED_JOE_PORT` | `127.0.0.1`, `1059` | Where joe listens, as for [the family](family.md). |
| `ALFRED_HOST_STATE` | `.host` | Where the logs and the record of what `up` started are kept. |
| `ALFRED_DEV_SKIP_AUTH`, and every setting alfred reads | | Pass through to the api and the worker, as the stack's lists pass them ([Configuration](configuration.md)). |

### What `up` runs

Each as a process, for running one by hand from the root of the checkout.
**The database** `up` does not start: any MongoDB, on a port the dev stack
does not publish, so the two can be started without moving either:

```sh
mongod --dbpath <a folder of its own> --port 27018 --bind_ip 127.0.0.1
```

**The site.** parcel's own watcher builds `website/dist` and reloads the
browser as sources change, over a port it binds to loopback only when
told the host, as the stack publishes it. It sees edits on a host; in the container the
bind mount hides them, so the stack polls with `yarn run dev` instead, and
that poller spawns `npx` without a shell, which Windows refuses.

```sh
cd website && npx parcel watch src/index.html --hmr-host 127.0.0.1 --hmr-port 1733
```

**The api.** The settings the stacks wire ([Plumbing](configuration.md#plumbing))
pointed at loopback, then uvicorn with its reloader on `alfred/`:

```sh
set -a; . ./.secret_key.local; set +a
export ALFRED_DEV_SKIP_AUTH=1
export DB_URL=mongodb://127.0.0.1:27018
export DB_NAME=alfred
export CELERY_BROKER=mongodb://127.0.0.1:27018/celery
export CELERY_BACKEND=mongodb://127.0.0.1:27018/celery
export STATIC_DIR=website/dist
export VIDEO_DIR=videos
export ALFRED_AUDIO_ENGINE_URL=http://127.0.0.1:1059
pdm run uvicorn alfred.main:app --host 127.0.0.1 --port 1732 --reload --reload-dir alfred
```

**The render worker.** The same environment, celery's solo pool, which is
the one Windows has, and the root of the checkout as its working directory,
so clips resolve against `VIDEO_DIR` as the api's do:

```sh
pdm run celery -A alfred.core.utils.tasks:renderer -b "$CELERY_BROKER" --result-backend "$CELERY_BACKEND" worker --loglevel=info --pool=solo
```

**joe**, from its own checkout, with `JOE_FFMPEG` naming ffmpeg where it is
not on `PATH`:

```sh
uv run --frozen uvicorn api:app --host 127.0.0.1 --port 1059
```

## Check what answers

`curl 127.0.0.1:1732/openapi.json` names what holds the port, and alfred
says `Alfred API`. `GET /health` reports the database, the worker and the
audio engine. `./al family smoke` asks the running stack everything a
change across the family can break, through `127.0.0.1`, whatever started
it.

## What differs from the stack

- **Text templates.** Without ImageMagick a text template's preview is
  refused as though its fields were missing, and a render of one fails
  building the template; the colour, bars and testcard templates draw
  without it. `./al family smoke` shows exactly that: its template preview,
  timeline preview and render checks fail, and the other six pass.
- **Fonts.** `fc-list` lists the fonts a text template can be drawn in; the
  api image has fontconfig and a host may not. Without it the api says so at
  start and leaves the font list as it was, which on a fresh database is
  empty: a text template's font choice offers nothing.
- **Ports.** The api holds 1732 as the stack's would, so `./al dev` refuses
  to start beside it and names it. Run one or the other, or move one with
  `ALFRED_PORT`.
- **`./al`.** Its stack commands, `./al stop`, `./al logs`, `./al sh` and
  `./al docker`, address compose and do nothing for these processes: stop
  each in its terminal. An edit under `alfred/` restarts the api by itself;
  `./al docker restart api` is for the bind mount, which there is none of.
- **The data.** The stack's database lives in `database/`, in its own
  container's format. The host's MongoDB starts empty, and the api seeds its
  demo projects on first start.
