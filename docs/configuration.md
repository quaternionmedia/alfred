# Configuration

alfred reads its settings from the environment. In the stacks `./al` starts,
a container's environment is what its compose file hands it. `dev.yml` and
`production.yml` each pass every setting below to the api and the render
worker from one list, except where the table says a stack keeps one out.
`./al thin` composes over `dev.yml` and passes the same.
`tests/unit/test_stack_settings.py` fails when alfred reads a setting those
lists leave out.

## Setting one

Export it in the shell that starts the stack, or put it before the command:

```sh
ALFRED_ALLOW_REGISTRATION=1 ./al prod
ALFRED_AUDIO_ENGINE_URL=http://host.docker.internal:8010 ./al dev
```

A container reads its environment when it starts: stop the stack and start it
again for a change to take effect.

- **Unset is the default.** The stacks pass each setting by its bare name, so
  one the shell leaves unset stays unset, and the table's default applies.
- **Empty is unset**, except for `ALFRED_SECRET_KEY`: an empty value, or one of
  spaces, gives the table's default. An empty `ALFRED_SECRET_KEY` is a key
  PyJWT refuses, so no token can be signed.
- **Paths are inside the containers.** Both mount this checkout's `videos/` at
  `/app/videos`; only the api mounts the checkout itself at `/app`. A directory
  the renderer writes and the api reads, `ALFRED_RENDER_DIR` above all, must be
  under `/app/videos` or on a volume you add to both services.
- **Git Bash on Windows** rewrites a value that looks like a path
  (`/app/videos/out`, `/v2/upload`) into a Windows path before Docker sees it.
  Prefix the command: `MSYS_NO_PATHCONV=1 ALFRED_RENDER_DIR=/app/videos/out ./al dev`.
- **The browser suite takes nothing from the shell.** `test_e2e.yml` (`./al
  test`, and CI) fixes what it needs in the file: its own signing key, the stub
  audio engine, and a volume for what it makes. Every machine tests the same
  stack.

## Settings

**Read by** names what acts on a setting. A stack hands the api and the
renderer the same list, so a setting reaches both even where one does not use
it.

| Setting | Default | What it does | Read by | Development and production |
|---|---|---|---|---|
| `ALFRED_PRODUCTION` | unset: off | Production mode: registration closed by default, single-use tokens kept out of the log, a short signing key reported, and the auth bypass refused at startup. Any non-empty value turns it on, `false` included. | api, renderer | `production.yml` sets it on both services; `dev.yml` never passes it. Production is a property of the stack file, not of the shell. |
| `ALFRED_SECRET_KEY` | none | Signs every session, password-reset and verification token, and the media URLs the api hands out. Unset or empty, every login fails with a 500 (PyJWT 2.13 and later refuse an empty key); under production, shorter than 32 characters is reported as guessable. | api | Development: `.secret_key.local`, a random key for this checkout that `./al init`, `./al dev` and `./al thin` create, loaded over the committed empty stub `.secret_key`. Exporting it does nothing in development. Production: required; export it before `./al prod`, which refuses to start without it. |
| `ALFRED_ALLOW_REGISTRATION` | open in development, closed under `ALFRED_PRODUCTION` | Whether `POST /auth/register` creates accounts. `1`, `true`, `yes` or `on` open it; any other value closes it. | api | The only way to open registration on a production stack: `ALFRED_ALLOW_REGISTRATION=1 ./al prod`. |
| `ALFRED_DEV_SKIP_AUTH` | off | Serves every request as a fixed superuser, the dev user, and skips the login screen. `1`, `true`, `yes` or `on` turn it on. See [Development auth](dev-auth.md). | api | Development only: `production.yml` does not pass it, and a process that sees it with `ALFRED_PRODUCTION` refuses to start. `./al dev` warns when it meets an `ALFRED_BIND` beyond loopback. |
| `ALFRED_DEV_USER_EMAIL` | `dev@example.com` | The account the auth bypass acts as. Reserved in every mode: it cannot be registered, logged into or reset. Development seeds belong to it unless `ALFRED_SEED_OWNER` says otherwise. | api | Both. |
| `ALFRED_SEED_OWNER` | the dev user in development; nobody under production | The account that owns the demo projects seeded into an empty database at startup, and by `./al seed` and `./al reseed`. With no owner, they are visible to superusers only. | api | Both. |
| `ALFRED_PUBLIC_URL` | unset in development; `https://alfred.quaternion.media` in `production.yml` | The address account mail (password reset, confirmation) links to, never taken from a request's Host header. An `http` or `https` URL; anything else counts as unset, and no mail with a link is sent. Mail also needs `EMAIL_SERVER` and `EMAIL_USERNAME`, from the `.email` env file. | api | Production: export it to deploy anywhere but the host traefik serves. |
| `ALFRED_REMOTE_MEDIA_HOSTS` | none: only the media library renders | Hosts a clip may name remote media on, comma-separated (`storage.googleapis.com`). The api refuses any other URL, and the worker refuses it rather than download it. | api, renderer | Both. |
| `ALFRED_REMOTE_CACHE_DIR` | `/app/videos/.remote-cache` | Where fetched remote media is kept: a hidden directory, never listed or served. Passed to otto as `OTTO_DOWNLOAD_DIR`. | api, renderer | Both. A path both containers see. |
| `ALFRED_REMOTE_CACHE_TTL` | `604800` (a week) | Seconds fetched remote media is kept. Swept when the api starts, at most hourly by the api and the worker as they fetch, and on demand by `./al storage cache`. | api, renderer | Both. |
| `ALFRED_RENDER_DIR` | `/app/videos/renders` | Where the worker writes finished renders and the api reads them. Not listed or served by `GET /videos`. | api, renderer | Both. A path both containers see. |
| `ALFRED_DELIVERY_DIR` | `deliveries` under the working directory: the checkout's `deliveries/` | Where the `local` destination copies a delivered render. Refused if inside the site's directory, which is served publicly. | api | Both. |
| `ALFRED_PREVIEW_DIR` | `/tmp/alfred-previews` in the api's container | Where EDL preview frames are written and fetched from. | api | Both. |
| `ALFRED_FRAME_TTL` | `3600` | Seconds a preview frame is kept. Older ones are swept when a frame is written and when the api starts. | api | Both. |
| `ALFRED_PREVIEW_CONCURRENCY` | `4` | How many previews, of a timeline's frame or a template, the api draws at once. They share AnyIO's forty-thread pool with every other route; past this many, a preview waits its turn without holding a thread. `GET /health` reports `previews: {running, waiting, limit}`. Keep it well under forty. | api | Both. |
| `ALFRED_PREVIEW_WAIT` | `10` | Seconds a preview waits for its turn before it is answered 503 with `Retry-After`, which the editor's viewer honours. | api | Both. |
| `ALFRED_MEDIA_URL_TTL` | `900` | Seconds a signed media URL works. Every listing and status reissues the URL. | api | Both. |
| `ALFRED_SMTP_TIMEOUT` | `20` | Seconds each step of sending mail may take: connecting, then each command and reply. It applies to all of alfred's mail: account mail from the api, and the issue reports and invoices the worker sends. The worker retries a failure that may pass five more times, over about a quarter of an hour. | api, renderer | Both. |
| `ALFRED_BUCKET_NAME` | `tower-renders` | The Google Cloud Storage bucket the worker uploads each finished render to, and that bucket delivery and cloud links use. Needs a service account key: `./cred.json` for the worker, `./cred_api.json` for the api. Without one, the worker's upload fails and is logged, and the render stands. | api, renderer | Both. |
| `ALFRED_AUDIO_ENGINE_URL` | unset: no engine | The audio engine's base address, for transcribing captions and analysing media. Unset, captions can still be typed and imported, and transcribing says why it cannot. See [Captions](captions.md). | api, renderer | Both. joe beside the stack: `http://host.docker.internal:8010`; see [Docker hosts and joe](#docker-hosts-and-joe). |
| `ALFRED_AUDIO_ENGINE_TIMEOUT` | `1800` | Seconds one request to the engine may take. | api, renderer | Both. |
| `ALFRED_AUDIO_ENGINE_CONTRACT_<FIELD>` | vox's | One field of vox's `EngineContract`, for an engine that spells its API differently from joe: `ALFRED_AUDIO_ENGINE_CONTRACT_MEDIA_UPLOAD=/v2/upload`. `none` says the engine does not offer it. `GET /health` reports a name that is not a field. | api, renderer | Both. The stacks pass one variable per field, listed in each file. |
| `OTTO_DOWNLOAD_DIR` | from `ALFRED_REMOTE_CACHE_DIR` | otto's name for the remote media cache. The stacks set it from `ALFRED_REMOTE_CACHE_DIR`, and so does alfred, in every process. | api, renderer | Set `ALFRED_REMOTE_CACHE_DIR` instead; exporting this does nothing in the stacks. |
| `ALFRED_PORT` | `8000` | The host port the dev stack's api is published on. | `dev.yml`, `./al` | `./al dev` and `./al thin` refuse to start when it is taken, and name what holds it. |
| `ALFRED_HMR_PORT` | `8001` | The host port of the site's live-reload server. | `dev.yml`, `./al` | Checked the same way. |
| `ALFRED_DB_PORT` | `27017` | The host port the dev database is published on, for attaching a GUI. | `dev.yml`, `./al` | Checked the same way. |
| `ALFRED_BIND` | `127.0.0.1` | The address the dev stack's api and site, `./al flower` and `./al docs` listen on. `0.0.0.0` opens them to the network, to try the app from a phone. | `dev.yml`, `flower.yml`, `./al` | Development. Production publishes nothing; traefik serves it. |
| `ALFRED_DB_BIND` | `127.0.0.1` | The address the dev database listens on. `ALFRED_BIND` does not move it. | `dev.yml` | Development. |
| `COMPOSE_PROJECT_NAME` | the checkout's directory name, in lower case | The compose project this checkout's stacks run as. `./al test`, `./al pytest` and `./al nox` run theirs beside it, as `<project>-e2e` and `<project>-pytest`; the port guard tells that project's own containers from anyone else's; and `./al recipes` reaches the dev stack's api through it. | compose, `./al`, `./al family` | Development. Two checkouts in directories of the same name need it to keep their stacks apart. |
| `ALFRED_IMAGES` | the checkout's directory name, in lower case | What this checkout's images are called: `<prefix>_api`, `_site`, `_worker`, `_test` and `_audio_stub`. Two worktrees building at once never swap each other's dependencies under their code. | compose, `./al` | Development. `./al` sets it; compose run by hand without it builds `alfred_*`. |
| `ALFRED_DB_DIR` | `./database` | The directory the stack's database keeps its files in. | `docker-compose.yml` | Development: [`./al loop`](loop.md) gives each named run's stack one under `.loop/<name>/`, since two databases on one directory refuse to start. |
| `E2E_PROJECTS`, `E2E_ARGS`, `E2E_OUTPUT` | `--project=chromium --project=phone`; none; `website/` | The browser suite's projects, more Playwright arguments (`--grep @slow`), and a directory under `website/` for its results and report. | `test_e2e.yml`, `website/playwright.config.js` | Development and CI. `./al loop` sets them per run, so runs side by side from one checkout keep their own reports. |
| `UID`, `GID` | unset: compose warns and substitutes blanks | The user and group the dev database runs as, from `dev.yml`'s `user:`. Most shells export neither; bash sets `UID` without exporting it. | `dev.yml` | Development. Harmless unset on Docker Desktop; export both if the database fails to start on a Linux host. |

The last ten are read on the host, by compose and `./al`, not by alfred.

alfred also reads plumbing, which is not settings:

- the compose files set `VIDEO_DIR` (`/app/videos`), `DB_URL`, `DB_NAME`,
  `CELERY_BROKER`, `CELERY_BACKEND` and `GOOGLE_APPLICATION_CREDENTIALS`;
  `STATIC_DIR` keeps its default, `dist`, where the built site is mounted;
- the api and the renderer read `EMAIL_SERVER`, `EMAIL_PORT`, `EMAIL_USERNAME`,
  `EMAIL_PASSWORD` and `EMAIL_SENDTO` from the `.email` env file. The api uses
  them for account mail, and to check mail is set up before it queues any; the
  renderer sends the issue reports and invoices;
- otto reads `LOG_DIR` when it is imported, as the directory for log files of
  its own (`otto.log.configure`). alfred never asks otto for them, so setting
  it changes nothing here.

## Docker hosts and joe

`host.docker.internal` is a container's name for the machine it runs on.
Docker Desktop provides it. A Linux host does not, so the api and the renderer
in `dev.yml` and `production.yml` map it with
`extra_hosts: host.docker.internal:host-gateway`, and
`ALFRED_AUDIO_ENGINE_URL=http://host.docker.internal:8010` resolves on both.
On Linux, `host-gateway` is the address of Docker's default bridge, `docker0`,
usually `172.17.0.1`.

joe must also listen where a container can reach it.
`uv run uvicorn api:app --port 8010` listens on loopback, which Docker Desktop
forwards to and a Linux bridge cannot reach. On Linux, either

- listen on the bridge's address, which this machine's containers reach and
  other machines do not:

  ```sh
  uv run uvicorn api:app --host 172.17.0.1 --port 8010
  ```

  (`ip -4 addr show docker0` gives the address, if it is not that one); or

- listen on every interface, `--host 0.0.0.0`, on a network you trust.

joe asks for no login: whoever reaches its port can use what it serves. A
fresh joe serves only its media API, which is all alfred uses, so alfred needs
none of joe's settings. The microphone (capture and the voice routes), the
transcripts and the audio library stay off until joe starts with
`JOE_ALLOW_MICROPHONE`, `JOE_ALLOW_TRANSCRIPTS` or `JOE_ALLOW_LIBRARY` set to 1
(or `--allow`); a route that is off answers 403 naming its setting. On every
interface, whatever is on is offered to the whole network, with only a host
firewall in the way. joe's `docs/security.md` is its threat model.

joe answers only to a Host it knows: loopback names, any IP address, and
`host.docker.internal`. Use one of those in `ALFRED_AUDIO_ENGINE_URL`. Any
other hostname, such as a compose service name or a LAN name, must be listed in
joe's `JOE_ALLOWED_HOSTS`, or joe answers 400.

Check what is answering before trusting it: `GET /health`, with a session,
reports `audio_engine: {configured, ok, detail}`.
