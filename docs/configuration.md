# Configuration

alfred reads its settings from the environment. A dev stack runs with none of
them set. A production stack needs one, the signing key, and transcribing
captions needs one, the audio engine's address. This page lists every one
alfred reads, by what it is for.

## The ones you are likely to set

| To | Set |
|---|---|
| skip the login in development | `ALFRED_DEV_SKIP_AUTH=1 ./al dev` ([Skipping login](dev-auth.md)) |
| transcribe captions with joe beside the stack | `ALFRED_AUDIO_ENGINE_URL=http://host.docker.internal:1059`, or `./al family up`, which sets it |
| start clear of a port something else holds | `ALFRED_PORT=1832 ./al dev`; `ALFRED_HMR_PORT` and `ALFRED_DB_PORT` for the other two |
| try the app from a phone on the same network | `ALFRED_BIND=0.0.0.0 ./al dev` |
| run production | export `ALFRED_SECRET_KEY` before `./al prod` ([The signing key](#the-signing-key)) |
| let people register on production | `ALFRED_ALLOW_REGISTRATION=1 ./al prod` |
| render media from a bucket, not only the library | `ALFRED_REMOTE_MEDIA_HOSTS=storage.googleapis.com` |

## Setting one

Export it in the shell that starts the stack, or put it before the command, as
above. A container reads its environment when it starts: stop the stack and
start it again for a change to take effect.

- **Unset is the default**, and **empty is unset**, except for
  `ALFRED_SECRET_KEY`: an empty key is one PyJWT refuses, so no token can be
  signed.
- **Both services get every setting.** `dev.yml` and `production.yml` hand the
  api and the render worker the same list, except where a table says a stack
  keeps one out; `./al thin` composes over `dev.yml` and passes the same.
  `tests/unit/test_stack_settings.py` fails when alfred reads a setting the
  lists leave out. [Images and stacks](build.md#settings) has how.
- **Paths are inside the containers.** Both mount this checkout's `videos/` at
  `/app/videos`; only the api mounts the checkout itself at `/app`. A directory
  the renderer writes and the api reads, `ALFRED_RENDER_DIR` above all, must be
  under `/app/videos` or on a volume you add to both.
- **Git Bash on Windows** rewrites a value that looks like a path
  (`/app/videos/out`, `/v2/upload`) into a Windows path before Docker sees it.
  Prefix the command: `MSYS_NO_PATHCONV=1 ALFRED_RENDER_DIR=/app/videos/out ./al dev`.
- **The browser suite takes nothing from the shell.** `test_e2e.yml` (`./al
  test`, and CI) fixes what it needs in the file, so every machine tests the
  same stack.

## Every setting

Each is read by the api and the render worker unless its row says otherwise.

### Accounts and security

| Setting | Default | What it does |
|---|---|---|
| `ALFRED_PRODUCTION` | off | Production mode: registration closed by default, single-use tokens kept out of the log, a short signing key reported, and the auth bypass refused at startup. Any non-empty value turns it on, `false` included. `production.yml` sets it; `dev.yml` never passes it, so production is a property of the stack file, not the shell. |
| `ALFRED_SECRET_KEY` | none | Signs every session, password-reset and verification token, and the media URLs the api hands out. In development, `.secret_key.local` supplies it, and exporting it does nothing. Production needs it exported. The api reads it. [The signing key](#the-signing-key). |
| `ALFRED_ALLOW_REGISTRATION` | open in development, closed in production | Whether `POST /auth/register` creates accounts: `1`, `true`, `yes` or `on` open it, anything else closes it. The only way to open registration on production. The api reads it. |
| `ALFRED_DEV_SKIP_AUTH` | off | Serves every request as a fixed superuser, the dev user, and skips the login screen; `1`, `true`, `yes` or `on`. `production.yml` does not pass it, and a process that sees it with `ALFRED_PRODUCTION` refuses to start. The api reads it. [Skipping login](dev-auth.md). |
| `ALFRED_DEV_USER_EMAIL` | `dev@example.com` | The account the bypass acts as. Reserved in every mode: it cannot be registered, logged into or reset. The api reads it. |
| `ALFRED_SEED_OWNER` | the dev user in development; nobody in production | The account that owns the demo projects seeded into an empty database at startup and by `./al seed` and `./al reseed`. With no owner, only superusers see them. The api reads it. |
| `ALFRED_PUBLIC_URL` | unset; `https://alfred.quaternion.media` in `production.yml` | The address account mail links to, never taken from a request's Host header. Anything but an `http(s)` URL counts as unset, and then no mail with a link is sent. Mail also needs the `.email` env file. The api reads it. |
| `ALFRED_SMTP_TIMEOUT` | `20` | Seconds each step of sending mail may take. It covers account mail from the api, and the issue reports and invoices the worker sends, which retries a failure five more times over about a quarter of an hour. |

### Media, renders and delivery

| Setting | Default | What it does |
|---|---|---|
| `ALFRED_REMOTE_MEDIA_HOSTS` | none: the library only | Hosts a clip may name remote media on, comma-separated. The api refuses any other URL, and the worker refuses it rather than download it. |
| `ALFRED_REMOTE_CACHE_DIR` | `/app/videos/.remote-cache` | Where fetched remote media is kept: hidden, never listed or served. alfred hands it to otto as `OTTO_DOWNLOAD_DIR`, in every process; set this, not that. |
| `ALFRED_REMOTE_CACHE_TTL` | `604800`, a week | Seconds fetched media is kept. Swept when the api starts, at most hourly as media is fetched, and by `./al storage cache`. |
| `ALFRED_RENDER_DIR` | `/app/videos/renders` | Where the worker writes finished renders and the api reads them. Never listed or served by `GET /videos`. |
| `ALFRED_DELIVERY_DIR` | the checkout's `deliveries/` | Where the `local` destination copies a delivered render. Refused inside the site's directory, which is served publicly. The api reads it. |
| `ALFRED_MEDIA_URL_TTL` | `900` | Seconds a signed media URL works. Every listing and status issues a new one. The api reads it. |
| `ALFRED_BUCKET_NAME` | `tower-renders` | The Google Cloud Storage bucket the worker uploads each render to, and bucket delivery and cloud links use. Needs a service account key, `./cred.json` for the worker and `./cred_api.json` for the api; without one the upload fails, is logged, and the render stands. |
| `OTTO_DOWNLOAD_DIR` | from `ALFRED_REMOTE_CACHE_DIR` | otto's name for the cache above. The stacks and alfred set it; exporting it does nothing. |

### Previews

All four are read by the api.

| Setting | Default | What it does |
|---|---|---|
| `ALFRED_PREVIEW_DIR` | `/tmp/alfred-previews` | Where preview frames are written and fetched from. |
| `ALFRED_FRAME_TTL` | `3600` | Seconds a preview frame is kept; older ones are swept as frames are written and when the api starts. |
| `ALFRED_PREVIEW_CONCURRENCY` | `4` | How many previews the api draws at once. They share AnyIO's forty-thread pool with every other route, so keep it well under forty; past this many, a preview waits without holding a thread. `GET /health` reports `previews: {running, waiting, limit}`. |
| `ALFRED_PREVIEW_WAIT` | `10` | Seconds a preview waits its turn before it is answered 503 with `Retry-After`, which the viewer honours. |

### The audio engine

| Setting | Default | What it does |
|---|---|---|
| `ALFRED_AUDIO_ENGINE_URL` | unset: no engine | The engine's base address, for transcribing captions and analysing media. Unset, captions can still be typed and imported, and **Transcribe timeline** says why it cannot. [Docker hosts and joe](#docker-hosts-and-joe). |
| `ALFRED_AUDIO_ENGINE_TIMEOUT` | `1800` | Seconds one request to the engine may take. |
| `ALFRED_AUDIO_ENGINE_CONTRACT_<FIELD>` | vox's | One field of vox's `EngineContract`, for an engine that spells its API differently from joe: `ALFRED_AUDIO_ENGINE_CONTRACT_MEDIA_UPLOAD=/v2/upload`; `none` says the engine does not offer it. `GET /health` reports a name that is not a field. The stacks pass one variable per field. |

[Captions](captions.md#the-audio-engine) has what alfred asks the engine, and
vox's README the contract itself.

### The dev stack, on the host

These are read by compose and `./al`, not by alfred.

| Setting | Default | What it does |
|---|---|---|
| `ALFRED_PORT` | `1732` | The host port of the dev stack's api: root three, alfred's place in qm's port allocation. `./al dev` and `./al thin` refuse to start when anything else holds it, or the next two, and name what does. |
| `ALFRED_HMR_PORT` | `1733` | The site's live-reload port, the same number inside the container: parcel's client dials it ([The site's watcher](build.md#the-sites-watcher)). |
| `ALFRED_DB_PORT` | `27017` | The host port of the dev database, for attaching a GUI. |
| `ALFRED_BIND` | `127.0.0.1` | The address the dev stack's api and site, `./al flower` and `./al docs` listen on. `0.0.0.0` opens them to the network. Production publishes nothing; traefik serves it. |
| `ALFRED_DB_BIND` | `127.0.0.1` | The address the dev database listens on. `ALFRED_BIND` does not move it. |
| `COMPOSE_PROJECT_NAME` | the checkout's directory, in lower case | The compose project this checkout's stacks run as; `./al test`, `./al pytest` and `./al nox` run theirs beside it as `<project>-e2e` and `<project>-pytest`. Two checkouts in directories of the same name need it. |
| `ALFRED_IMAGES` | the checkout's directory, in lower case | The images' prefix, `<prefix>_api`, `_site`, `_worker`, `_test` and `_audio_stub`, so two worktrees never swap each other's dependencies. `./al` sets it. |
| `ALFRED_DB_DIR` | `./database` | Where the stack's database keeps its files. [`./al loop`](loop.md) gives each named run one under `.loop/<name>/`. |
| `E2E_PROJECTS`, `E2E_ARGS`, `E2E_OUTPUT` | `--project=chromium --project=phone`; none; `website/` | The browser suite's Playwright projects, more arguments (`--grep @slow`), and where its results go. `./al loop` sets them per run. |
| `UID`, `GID` | unset: compose warns | The user and group the dev database runs as. Harmless unset on Docker Desktop; export both if it fails to start on a Linux host. |

### Plumbing

alfred also reads what the stacks wire for it, which is not for setting:

- the compose files set `VIDEO_DIR` (`/app/videos`), `DB_URL`, `DB_NAME`,
  `CELERY_BROKER`, `CELERY_BACKEND` and `GOOGLE_APPLICATION_CREDENTIALS`;
  `STATIC_DIR` keeps its default, `dist`, where the built site is mounted;
- the `.email` env file gives the api and the renderer `EMAIL_SERVER`,
  `EMAIL_PORT`, `EMAIL_USERNAME`, `EMAIL_PASSWORD` and `EMAIL_SENDTO`;
- otto reads `LOG_DIR` on import, for log files of its own, which alfred never
  asks for: setting it changes nothing here.

## The signing key

`ALFRED_SECRET_KEY` signs every session, password-reset and verification
token (HS256), and the media URLs the api hands out. The api checks it at
startup:

- **unset or empty**, in any mode, nothing can be signed, and every login
  answers 500. The committed `.secret_key` is an empty stub, and `./al init`,
  `./al dev` and `./al thin` give a development checkout a random key of its
  own, `.secret_key.local`, which git ignores; delete it to rotate.
- **shorter than 32 characters**, under `ALFRED_PRODUCTION`, is guessable:
  anyone holding one token can try keys offline until the signature matches,
  then sign a session for any account. Development keys may be short.

Each case is reported, not enforced: the api prints `THE TOKEN SIGNING KEY IS
NOT SAFE TO USE` at startup, and still starts. Whether production should
refuse to start instead is an open decision.

## Docker hosts and joe

`host.docker.internal` is a container's name for the machine it runs on.
Docker Desktop provides it; on a Linux host, the api and the renderer in
`dev.yml` and `production.yml` map it with
`extra_hosts: host.docker.internal:host-gateway`, the address of Docker's
default bridge, `docker0`, usually `172.17.0.1`. So
`ALFRED_AUDIO_ENGINE_URL=http://host.docker.internal:1059` resolves on both.

joe must also listen where a container can reach it. On loopback, as
`uv run uvicorn api:app --port 1059` does, Docker Desktop forwards to it and a
Linux bridge cannot. On Linux, listen on the bridge's address, which this
machine's containers reach and other machines do not; `./al family up` does
this for you:

```sh
uv run uvicorn api:app --host 172.17.0.1 --port 1059
```

joe asks for no login, answers only to a Host it knows (loopback names, any IP
address and `host.docker.internal`), and serves only its media API until told
otherwise, which is all alfred uses. Its own pages decide the rest: [joe's
security](https://github.com/quaternionmedia/joe/blob/main/docs/security.md)
for what each listening address exposes and `JOE_ALLOWED_HOSTS`, and [joe's
media API](https://github.com/quaternionmedia/joe/blob/main/docs/media.md) for
running it beside alfred.

Check what is answering before trusting it: `GET /health`, with a session,
reports `audio_engine: {configured, ok, detail}`.
