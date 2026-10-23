# Configuration

alfred reads its settings from the environment. In the stacks `./al` starts,
the environment of a container is what its compose file hands it, so a setting
reaches alfred only because `dev.yml` or `production.yml` passes it on. Both
pass the settings below to the api and to the render worker, from one list per
file -- all of them, except where the table says a stack keeps one out on
purpose -- and `tests/unit/test_stack_settings.py` fails when alfred reads a
setting those lists leave out. `./al thin` composes over `dev.yml` and passes
the same.

## Setting one

Export it in the shell that starts the stack, or put it in front of the
command:

```sh
ALFRED_ALLOW_REGISTRATION=1 ./al prod
ALFRED_AUDIO_ENGINE_URL=http://host.docker.internal:8010 ./al dev
```

A container reads its environment when it starts: stop the stack and start it
again for a change to take effect.

- **Unset is the default.** The stacks pass each setting by its bare name, so
  one the shell does not set stays unset in the containers and alfred's own
  default applies -- the one in the table.
- **Empty is unset**, for every setting but one: an empty value (or one of
  spaces) gives the default in the table, as if the variable were not there.
  The exception is `ALFRED_SECRET_KEY`, where empty is a key anyone can
  reproduce: see the table.
- **Paths are inside the containers.** Both containers mount this checkout's
  `videos/` at `/app/videos`, and only the api mounts the checkout itself at
  `/app`. A directory the renderer writes and the api reads,
  `ALFRED_RENDER_DIR` above all, has to be one both can see: somewhere under
  `/app/videos`, or a volume you add to both services.
- **In Git Bash on Windows**, a value that looks like a path (`/app/videos/out`,
  `/v2/upload`) is rewritten into a Windows path before Docker sees it. Prefix
  the command: `MSYS_NO_PATHCONV=1 ALFRED_RENDER_DIR=/app/videos/out ./al dev`.
- **The browser suite takes nothing from the shell.** `test_e2e.yml` (`./al
  test`, and CI) fixes what it needs in the file -- a signing key of its own,
  the stub audio engine, and a volume for what it makes -- so a run tests the
  same stack on every machine.

## Settings

**Read by** names what acts on a setting. A stack hands the api and the
renderer the same list, so a setting reaches both even where one of them does
not use it.

| Setting | Default | What it does | Read by | Development and production |
|---|---|---|---|---|
| `ALFRED_PRODUCTION` | unset: off | Production mode: registration closed by default, single-use tokens kept out of the log, a short signing key reported, and the auth bypass refused at startup. Any non-empty value turns it on -- `false` included. | api, renderer | `production.yml` sets it on both services. `dev.yml` never passes it: production is a property of the stack file, not of the shell. |
| `ALFRED_SECRET_KEY` | none | Signs every session, password-reset and verification token, and the media URLs the api hands out. Unset, every login fails with a 500; empty, tokens are signed with a key anyone can reproduce; under production, shorter than 32 characters is reported as guessable. | api | Development: `.secret_key.local`, a random key `./al init`, `./al dev` and `./al thin` create for this checkout, loaded over the committed empty stub `.secret_key`. Exporting it does nothing in development. Production: required; export it before `./al prod`, which refuses to start without it. |
| `ALFRED_ALLOW_REGISTRATION` | open in development, closed under `ALFRED_PRODUCTION` | Whether `POST /auth/register` creates accounts. `1`, `true`, `yes` or `on` open it; any other value closes it. | api | The only way to open registration on a production stack: `ALFRED_ALLOW_REGISTRATION=1 ./al prod`. |
| `ALFRED_DEV_SKIP_AUTH` | off | Serves every request as a fixed superuser, the dev user, and skips the login screen. `1`, `true`, `yes` or `on` turn it on. See [Development auth](dev-auth.md). | api | Development only. `production.yml` does not pass it, and a process that sees it with `ALFRED_PRODUCTION` refuses to start. `./al dev` warns when it is combined with `ALFRED_BIND` beyond loopback. |
| `ALFRED_DEV_USER_EMAIL` | `dev@example.com` | The account the auth bypass acts as. It is reserved in every mode: it cannot be registered, logged into or reset. Development seeds belong to it unless `ALFRED_SEED_OWNER` says otherwise. | api | Both. |
| `ALFRED_SEED_OWNER` | the dev user in development; nobody under production | The account that owns the demo projects seeded into an empty database at startup, and by `./al seed` and `./al reseed`. With no owner they are visible to superusers only. | api | Both. |
| `ALFRED_PUBLIC_URL` | unset in development; `https://alfred.quaternion.media` in `production.yml` | The address account mail links to (password reset, confirmation), never taken from a request's Host header. An `http` or `https` URL; anything else is unset, and no mail with a link is sent. Mail also needs `EMAIL_SERVER` and `EMAIL_USERNAME`, from the `.email` env file. | api | Production: export it to deploy anywhere but the host traefik serves. |
| `ALFRED_REMOTE_MEDIA_HOSTS` | none: only the media library renders | Hosts a clip may name remote media on, comma-separated (`storage.googleapis.com`). The api refuses any other URL, and the worker refuses it rather than downloading it. | api, renderer | Both. A clip on storage.googleapis.com, or any other host, needs its host listed here. |
| `ALFRED_REMOTE_CACHE_DIR` | `/app/videos/.remote-cache` | Where fetched remote media is kept: a hidden directory, never listed or served. The stacks also pass it as `OTTO_DOWNLOAD_DIR`, the engine's name for it. | api, renderer | Both. A path both containers see. |
| `ALFRED_REMOTE_CACHE_TTL` | `604800` (a week) | Seconds fetched remote media is kept. Swept when the api starts, at most hourly by the api and the worker as they fetch, and on demand by `./al storage cache`. | api, renderer | Both. |
| `ALFRED_RENDER_DIR` | `/app/videos/renders` | Where the worker writes finished renders and the api reads them. Not listed or served by `GET /videos`. | api, renderer | Both. A path both containers see. |
| `ALFRED_DELIVERY_DIR` | `deliveries` under the working directory: the checkout's `deliveries/` | Where the `local` destination copies a delivered render. Refused if it is inside the site's directory, which is served publicly. | api | Both. |
| `ALFRED_PREVIEW_DIR` | `/tmp/alfred-previews` in the api's container | Where EDL preview frames are written and fetched from. | api | Both. |
| `ALFRED_FRAME_TTL` | `3600` | Seconds a preview frame is kept. Older ones are swept when a frame is written and when the api starts. | api | Both. |
| `ALFRED_PREVIEW_CONCURRENCY` | `4` | How many previews -- a timeline's frame or a template's -- the api draws at once. They run in the thread pool every other route shares, AnyIO's forty threads; past this many, a preview waits its turn without holding a thread. `GET /health` reports `previews: {running, waiting, limit}`. Keep it well under forty. | api | Both. |
| `ALFRED_PREVIEW_WAIT` | `10` | Seconds a preview waits for its turn before it is answered 503 with `Retry-After`, which the editor's viewer honours. | api | Both. |
| `ALFRED_MEDIA_URL_TTL` | `900` | Seconds a signed media URL works. A URL is reissued with every listing and status. | api | Both. |
| `ALFRED_SMTP_TIMEOUT` | `20` | Seconds each step of sending mail may take: connecting, and each command and reply after. Every mail alfred sends has it -- account mail from the api, and the issue reports and invoices the worker sends, which a failure that may pass is tried again for, five more times over about a quarter of an hour. | api, renderer | Both. |
| `ALFRED_BUCKET_NAME` | `tower-renders` | The Google Cloud Storage bucket the worker uploads each finished render to, and bucket delivery and cloud links use. Needs a service account key: `./cred.json` for the worker, `./cred_api.json` for the api. Without one the worker's upload fails, is logged, and the render stands. | api, renderer | Both. |
| `ALFRED_AUDIO_ENGINE_URL` | unset: no engine | The audio engine's base address, which captions are transcribed and media analysed with. Unset, captions are still typed and imported, and transcribing says why it cannot. See [Captions](captions.md). | api, renderer | Both. joe beside the stack: `http://host.docker.internal:8010`; see [Docker hosts and joe](#docker-hosts-and-joe). |
| `ALFRED_AUDIO_ENGINE_TIMEOUT` | `1800` | Seconds one request to the engine may take. | api, renderer | Both. |
| `ALFRED_AUDIO_ENGINE_CONTRACT_<FIELD>` | vox's | One field of vox's `EngineContract`, for an engine that spells its API differently from joe: `ALFRED_AUDIO_ENGINE_CONTRACT_MEDIA_UPLOAD=/v2/upload`. `none` says the engine does not offer it. A name that is not a field is reported by `GET /health`. | api, renderer | Both. The stacks pass one variable per field, listed in each file. |
| `OTTO_DOWNLOAD_DIR` | from `ALFRED_REMOTE_CACHE_DIR` | The engine's own name for the remote media cache. The stacks set it from `ALFRED_REMOTE_CACHE_DIR`, and alfred sets it from that in every process. | api, renderer | Set `ALFRED_REMOTE_CACHE_DIR` instead; exporting this does nothing in the stacks. |
| `ALFRED_PORT` | `8000` | The host port the dev stack's api is published on. | `dev.yml`, `./al` | `./al dev` and `./al thin` refuse to start when it is taken, and name what holds it. |
| `ALFRED_HMR_PORT` | `8001` | The host port of the site's live-reload server. | `dev.yml`, `./al` | Checked the same way. |
| `ALFRED_DB_PORT` | `27017` | The host port the dev database is published on, for attaching a GUI. | `dev.yml`, `./al` | Checked the same way. |
| `ALFRED_BIND` | `127.0.0.1` | The address the dev stack's api and site, `./al flower` and `./al docs` listen on. `0.0.0.0` opens them to the network, to try the app from a phone. | `dev.yml`, `flower.yml`, `./al` | Development. Production publishes nothing; traefik serves it. |
| `ALFRED_DB_BIND` | `127.0.0.1` | The address the dev database listens on. `ALFRED_BIND` does not move it. | `dev.yml` | Development. |

The last five are read on the host, by compose and `./al`, not by alfred.

alfred also reads where to find its own parts, which are plumbing rather than
settings: the compose files set `VIDEO_DIR` (`/app/videos`), `DB_URL`,
`DB_NAME`, `CELERY_BROKER`, `CELERY_BACKEND` and
`GOOGLE_APPLICATION_CREDENTIALS`, and `STATIC_DIR` keeps its default, `dist`,
where the built site is mounted. The api and the renderer read `EMAIL_SERVER`,
`EMAIL_PORT`, `EMAIL_USERNAME`, `EMAIL_PASSWORD` and `EMAIL_SENDTO` from the
`.email` env file: the api for account mail, and to check that mail is set up
before it queues any; the renderer, because it sends the issue reports and
invoices.

## Docker hosts and joe

`host.docker.internal` is the machine a container runs on, as the container
sees it. Docker Desktop provides the name. A Linux host does not, so the api
and the renderer in `dev.yml` and `production.yml` map it with
`extra_hosts: host.docker.internal:host-gateway`, and
`ALFRED_AUDIO_ENGINE_URL=http://host.docker.internal:8010` resolves on a Linux
Docker host as it does on Docker Desktop. On Linux, `host-gateway` is the
address of Docker's default bridge, `docker0` -- usually `172.17.0.1`.

Resolving is half of it: joe also has to listen where a container can reach
it. `uv run uvicorn api:app --port 8010` listens on loopback, which Docker
Desktop forwards to and a Linux bridge cannot reach. On Linux, either

- listen on the bridge's address, which this machine's containers reach and
  other machines do not:

  ```sh
  uv run uvicorn api:app --host 172.17.0.1 --port 8010
  ```

  (`ip -4 addr show docker0` gives the address, if it is not that one); or

- listen on every interface, `--host 0.0.0.0`, on a network you trust.

joe asks for no login: whoever can reach its port can use what it serves.
A fresh joe serves its media API alone -- what alfred uses, and all alfred
needs, so alfred asks nothing of joe's settings. The microphone (capture and
the voice routes), the transcripts and the audio library each stay off until
joe is started with `JOE_ALLOW_MICROPHONE`, `JOE_ALLOW_TRANSCRIPTS` or
`JOE_ALLOW_LIBRARY` set to 1 (or `--allow`), and a route that is off answers
403 naming its setting. Listening on every interface offers whatever is on to
the whole network, and a host firewall is then the only thing in the way.
joe's `docs/security.md` is its threat model.

joe also answers only to a Host it knows -- loopback names, any IP address,
and `host.docker.internal` -- so `ALFRED_AUDIO_ENGINE_URL` should use one of
those. A hostname such as a compose service name or a LAN name needs joe's
`JOE_ALLOWED_HOSTS` to list it, or joe answers 400.

Then check what is answering before trusting it: `GET /health`, with a
session, reports `audio_engine: {configured, ok, detail}`.
