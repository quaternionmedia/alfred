import sys
from os import environ
from os.path import join
from tempfile import gettempdir
from urllib.parse import urlsplit

PRODUCTION = environ.get('ALFRED_PRODUCTION')

SECRET_KEY = environ.get('ALFRED_SECRET_KEY')

# HS256 keys are only as strong as they are long, and this one signs every
# session, password-reset and verification token the server issues.
MIN_SECRET_KEY_LENGTH = 32


def secret_key_problem(env):
    """What is wrong with ALFRED_SECRET_KEY for this process, or None.

    Three different failures, checked in different places:

    - **Unset**, anywhere. Nothing can be signed, so every login answers
      500 -- PyJWT is handed None -- and nothing says why. That is not a
      production-only problem: test_e2e.yml's api had no key, and its whole
      suite failed at the first login.
    - **Empty**, anywhere. The opposite failure, and the quieter one: PyJWT
      signs and verifies with an empty key without complaint, so logins work
      -- and anyone who knows the key is empty can mint a token for any
      account. The committed `.secret_key` is such a stub; `./al` gives a
      development checkout a random key of its own (`.secret_key.local`).
    - **Shorter than MIN_SECRET_KEY_LENGTH**, under ALFRED_PRODUCTION. Anyone
      holding a single token can guess HS256 keys offline until the signature
      matches, and a short key puts that within reach -- after which they can
      mint a session for any account. Development keys are stubs and allowed
      to be short.

    Reported, not enforced: the process still boots. Whether production should
    refuse to start instead is an open decision.
    """
    key = env.get('ALFRED_SECRET_KEY')
    if key is None:
        return (
            'ALFRED_SECRET_KEY is not set, so no token can be signed: every '
            'login will fail with a server error.'
        )
    if not key:
        return (
            'ALFRED_SECRET_KEY is empty. Tokens are still signed, with a key '
            'anyone can reproduce, so any session, password-reset or '
            'verification token can be forged. In development, ./al init gives '
            'this checkout a key of its own; in production, export a random one.'
        )
    if env.get('ALFRED_PRODUCTION') and len(key) < MIN_SECRET_KEY_LENGTH:
        return (
            f'ALFRED_SECRET_KEY is shorter than {MIN_SECRET_KEY_LENGTH} '
            'characters. It signs every session, password-reset and '
            'verification token, and anyone holding one of those tokens can '
            'guess keys offline until the signature matches; a short key puts '
            'that within reach, and with it a session for any account. Use a '
            f'random string of at least {MIN_SECRET_KEY_LENGTH} characters.'
        )
    return None


def _truthy(value):
    """Explicit opt-in only.

    Deliberately not `bool(environ.get(...))`, which treats `ALFRED_DEV_SKIP_AUTH=0`
    and `=false` as on -- the two spellings someone reaches for to turn a flag
    off. For a flag that disables authentication, the failure has to be in the
    direction of staying locked.
    """
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _given(value):
    """Whether a variable was actually set to something.

    Empty counts as unset. Compose passes a host variable through as
    `X=${X:-}`, which hands the container an empty string for a variable
    nobody set -- and an empty string must mean "use the default", not
    "explicitly off".
    """
    return value is not None and str(value).strip() != ''


def resolve_text(env, name, default):
    """`env[name]` without surrounding space, or `default` when unset or empty.

    For the settings an empty value would otherwise be taken literally by: an
    empty ALFRED_RENDER_DIR or ALFRED_DELIVERY_DIR is the working directory,
    an empty ALFRED_DEV_USER_EMAIL is nobody, and an empty ALFRED_BUCKET_NAME
    is no bucket -- none of which anybody means by emptying a variable. Empty
    is unset here, as it is for every other setting but the signing key.
    """
    value = env.get(name)
    return str(value).strip() if _given(value) else default


def resolve_seconds(env, name, default):
    """A whole, positive number of seconds from `env[name]`, else `default`.

    Unset or empty is the default. Anything that is not a positive whole
    number is the default too, and says so on stderr: these are lifetimes,
    and a typo such as `15m` should neither stop the server starting nor
    quietly become something nobody asked for.
    """
    raw = env.get(name)
    if not _given(raw):
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        value = 0
    if value < 1:
        print(
            f'{name}={raw!r} is not a positive number of seconds; ' f'using {default}.',
            file=sys.stderr,
            flush=True,
        )
        return default
    return value


def resolve_count(env, name, default):
    """A whole, positive number from `env[name]`, else `default`.

    As `resolve_seconds`, for a setting that counts something other than
    seconds: unset or empty is the default, and so is anything that is not a
    positive whole number, with a line on stderr saying so.
    """
    raw = env.get(name)
    if not _given(raw):
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        value = 0
    if value < 1:
        print(
            f'{name}={raw!r} is not a positive whole number; using {default}.',
            file=sys.stderr,
            flush=True,
        )
        return default
    return value


def resolve_allow_registration(env):
    """Whether `POST /auth/register` may create accounts.

    Registration was mounted unconditionally, so anyone who could reach a
    production server could give themselves an account on it. Open by default
    in development, where registering is how you get a user at all, and closed
    by default under ALFRED_PRODUCTION, where accounts are handed out rather
    than taken.

    ALFRED_ALLOW_REGISTRATION overrides the default in either direction,
    parsed exactly like ALFRED_DEV_SKIP_AUTH: `1`, `true`, `yes` or `on` opens
    it, and any other value closes it. Unrecognised fails closed, for the same
    reason it fails towards auth staying on.
    """
    explicit = env.get('ALFRED_ALLOW_REGISTRATION')
    if _given(explicit):
        return _truthy(explicit)
    return not env.get('ALFRED_PRODUCTION')


ALLOW_REGISTRATION = resolve_allow_registration(environ)


def resolve_dev_skip_auth(env):
    """Whether to accept unauthenticated requests as a fixed dev user.

    Refuses to combine with ALFRED_PRODUCTION. Raising here means a
    misconfigured production container fails to boot instead of coming up
    wide open, which is the only acceptable direction for this mistake --
    an unauthenticated API that starts successfully looks healthy.

    Takes the environment as an argument so this is testable without
    reimporting the module; the module-level value below is the real one.
    """
    requested = _truthy(env.get('ALFRED_DEV_SKIP_AUTH', ''))
    if not requested:
        return False
    if env.get('ALFRED_PRODUCTION'):
        raise RuntimeError(
            'ALFRED_DEV_SKIP_AUTH is set together with ALFRED_PRODUCTION. '
            'The auth bypass is a local development convenience and must '
            'never run in production. Refusing to start.'
        )
    return True


# Skips login entirely and treats every caller as a fixed local user. Off
# unless explicitly asked for. See docs/dev-auth.md.
DEV_SKIP_AUTH = resolve_dev_skip_auth(environ)

# The account the bypass acts as. A real, persisted user, so routes that
# attribute a render to `user.id` behave as they will with auth on.
#
# RFC 2606 reserved, so it cannot reach anyone if a code path ever mails it.
#
# It has to be reserved *and* valid, which narrows the field more than it
# looks. dev@localhost was the first attempt: the User document stored it, so
# every gated route worked, but UserRead types email as EmailStr and rejected
# it on the way out -- /users/me alone returned 500. dev@alfred.invalid was
# the second: `.invalid` is the RFC's own "guaranteed not to resolve" TLD, but
# pydantic's validator rejects reserved TLDs outright. RFC 2606 also reserves
# the second-level domains example.com/net/org, which do validate.
DEFAULT_DEV_USER_EMAIL = 'dev@example.com'
DEV_USER_EMAIL = resolve_text(environ, 'ALFRED_DEV_USER_EMAIL', DEFAULT_DEV_USER_EMAIL)


def resolve_seed_owner(env):
    """Who owns the projects seeded into an empty database at startup.

    Every project has an owner now, and the seeded ones are created by the
    server rather than by anybody, so somebody has to be named.

    ALFRED_SEED_OWNER names an account outright. Unset, development seeds
    belong to the dev user -- the account ALFRED_DEV_SKIP_AUTH acts as -- so
    the bypass opens onto the same projects it always did, and would keep
    them even if that account stopped being a superuser. In production they
    get no owner, which makes them superuser-only: a production server
    should not hand its demo projects to an account named in a development
    default.
    """
    explicit = env.get('ALFRED_SEED_OWNER')
    if _given(explicit):
        return explicit.strip()
    if env.get('ALFRED_PRODUCTION'):
        return None
    return resolve_text(env, 'ALFRED_DEV_USER_EMAIL', DEFAULT_DEV_USER_EMAIL)


SEED_OWNER = resolve_seed_owner(environ)


def resolve_public_url(env):
    """Where people reach this server, for the links in account mail.

    A password-reset mail carries a link into the app, and the link needs the
    app's address. It comes from ALFRED_PUBLIC_URL (`https://alfred.example`),
    never from the request that asked for the reset: its Host header is
    whatever the asker sent, and a reset link built on it would carry somebody
    else's token to the asker's own host.

    An `http` or `https` URL with a host, without a trailing slash; anything
    else is treated as unset, and no mail with a link is sent.
    """
    value = (env.get('ALFRED_PUBLIC_URL') or '').strip().rstrip('/')
    parts = urlsplit(value)
    if parts.scheme not in ('http', 'https') or not parts.netloc:
        return None
    return value


PUBLIC_URL = resolve_public_url(environ)

# The media library: what `GET /videos` lists and clips name as
# `videos/<file>`. It was a bare 'videos' literal inside the Celery task, so
# nothing else could agree with it without repeating the string -- and the
# delivery endpoint duly looked in DATA_DIR instead and found nothing.
VIDEO_DIR = environ.get('VIDEO_DIR', 'videos')
STATIC_DIR = environ.get('STATIC_DIR', 'dist')

# Where the worker writes finished renders, and the download route reads them.
# Inside the media library by default, so the ./videos mount the api and the
# worker already share covers it -- but in a subdirectory, which neither
# `GET /videos` nor `GET /videos/{file}` reaches into. Renders used to be
# written beside the media, so every user's output was listed to everyone
# signed in and served to anyone who asked for it by name.
RENDER_DIR = resolve_text(environ, 'ALFRED_RENDER_DIR', join(VIDEO_DIR, 'renders'))

# Where the `local` destination copies a delivered render. Not anywhere a
# static mount serves: a local delivery used to land under the public /data
# mount, which made it a link to somebody's video for anyone who had it. A
# delivered render's `link` is the download route instead.
DELIVERY_DIR = resolve_text(environ, 'ALFRED_DELIVERY_DIR', 'deliveries')

# Where EDL preview frames are written, and `GET /preview/frames/{name}` reads
# them from. Outside every directory the app serves statically: frames used to
# be written to DATA_DIR and fetched from its unauthenticated /data mount, so
# the only thing between a frame and anyone was its name. They are fetched
# with a session or a signed URL now (contract M1). The api is the only
# process that writes or reads them, so a directory private to its container
# is the right default.
PREVIEW_DIR = environ.get('ALFRED_PREVIEW_DIR') or join(gettempdir(), 'alfred-previews')

# How long a preview frame is kept, in seconds. Frames were never removed, so
# every playhead move in the editor left a file behind for good. Older ones
# are swept when a frame is written and when the api starts.
FRAME_TTL = resolve_seconds(environ, 'ALFRED_FRAME_TTL', 3600)

# How many previews -- a timeline's frame or a template's -- the api draws at
# once. Previews run in the thread pool, which they share with file responses,
# the other routes' offloaded work and `/health`'s broker ping: AnyIO's forty
# threads, all of which a burst of previews could take. Past this many, a
# preview waits for one to finish (`utils.concurrency`). Keep it well under
# forty.
PREVIEW_CONCURRENCY = resolve_count(environ, 'ALFRED_PREVIEW_CONCURRENCY', 4)

# How long a preview waits for its turn, in seconds, before it is answered 503
# with a Retry-After header rather than queueing for as long as the others
# take.
PREVIEW_WAIT = resolve_seconds(environ, 'ALFRED_PREVIEW_WAIT', 10)


# Where the engine keeps media it fetched from a URL (contract M6). Inside the
# library directory, so the api's previews and the worker's renders share one
# copy through the mount they both have -- but in a hidden subdirectory, which
# neither `GET /videos` nor `GET /media` lists and `/videos/{file}` never
# serves. The engine wrote downloads to `data/` under its working directory,
# which the api served publicly at /data.
#
# The engine reads OTTO_DOWNLOAD_DIR. The compose files set it outright; for
# anything started another way it is set from here, at import -- before the
# engine is imported, since the `alfred` package imports this module first --
# so one value decides where downloads go in every process.
def resolve_remote_cache_dir(env, video_dir):
    """ALFRED_REMOTE_CACHE_DIR, else OTTO_DOWNLOAD_DIR, else in the library.

    An explicit ALFRED_REMOTE_CACHE_DIR wins over an OTTO_DOWNLOAD_DIR that
    disagrees; empty counts as unset.
    """
    for name in ('ALFRED_REMOTE_CACHE_DIR', 'OTTO_DOWNLOAD_DIR'):
        if _given(env.get(name)):
            return env[name].strip()
    return join(video_dir, '.remote-cache')


REMOTE_CACHE_DIR = resolve_remote_cache_dir(environ, VIDEO_DIR)
environ['OTTO_DOWNLOAD_DIR'] = REMOTE_CACHE_DIR

# How long fetched remote media is kept, in seconds; a week by default. The
# engine keeps every file it fetches and never removed one. Swept when the api
# starts, and at most hourly by the api and the worker as they fetch; `./al
# storage cache` does it on demand.
REMOTE_CACHE_TTL = resolve_seconds(environ, 'ALFRED_REMOTE_CACHE_TTL', 7 * 24 * 3600)

# How long a signed media URL works, in seconds (contract M1). Long enough to
# watch a preview or finish a download that started; a URL is reissued with
# every listing and status, so nothing needs one to last.
MEDIA_URL_TTL = resolve_seconds(environ, 'ALFRED_MEDIA_URL_TTL', 900)


def parse_hosts(value):
    """A comma-separated host list, normalised for comparison.

    Lowercased and stripped, empty entries dropped. A frozenset so the
    setting cannot be mutated by whatever imports it.
    """
    return frozenset(
        host.strip().lower() for host in (value or '').split(',') if host.strip()
    )


# Hosts a clip may name as remote media (`https://<host>/...`). Empty unless
# configured, so by default only the media library can be rendered.
#
# The engine downloads any http(s) URL a clip names, from the worker and from
# the api when previewing, so without a list this is a request to anywhere
# those processes can reach -- including addresses on their own network.
REMOTE_MEDIA_HOSTS = parse_hosts(environ.get('ALFRED_REMOTE_MEDIA_HOSTS', ''))

# The audio engine: what transcribes a timeline's sound into captions, and
# analyses a library file's. Reached through vox (vendored at alfred/vox) and
# `utils.audio_engine`, the only module that knows how; nothing else in alfred
# names an engine, a path or a key of one.
#
# ALFRED_AUDIO_ENGINE_URL is the engine's base address. Unset or empty, there
# is no engine: captions are still typed and imported, and transcribing says
# why it cannot. joe's own CLI binds 8000, this server's port; run it as
# `uv run uvicorn api:app --port 8010` and point this at
# http://host.docker.internal:8010 (docs/captions.md).
AUDIO_ENGINE_URL = (environ.get('ALFRED_AUDIO_ENGINE_URL') or '').strip() or None

# How long one request to the engine may take, in seconds. Transcribing is the
# slow one, and it runs on the render worker, where no request is waiting on
# it: joe takes about eighteen seconds for its first transcription after it
# starts, then about as long as the speech lasts on a CPU, so a long timeline
# takes minutes. Half an hour, by default, before a job is given up on.
AUDIO_ENGINE_TIMEOUT = resolve_seconds(environ, 'ALFRED_AUDIO_ENGINE_TIMEOUT', 1800)

# Where an engine spells things differently from vox's defaults: any field of
# vox's `EngineContract`, as ALFRED_AUDIO_ENGINE_CONTRACT_<FIELD> -- for
# instance ALFRED_AUDIO_ENGINE_CONTRACT_MEDIA_UPLOAD=/v2/upload. `none` sets a
# field to None ("this engine does not offer it"); empty is unset. A name
# that is not a field is reported by /health rather than ignored.
AUDIO_ENGINE_CONTRACT_PREFIX = 'ALFRED_AUDIO_ENGINE_CONTRACT_'


def resolve_audio_engine_contract(env):
    """{field: value} for every ALFRED_AUDIO_ENGINE_CONTRACT_<FIELD> set."""
    overrides = {}
    for name, value in env.items():
        if not name.startswith(AUDIO_ENGINE_CONTRACT_PREFIX) or not _given(value):
            continue
        field = name[len(AUDIO_ENGINE_CONTRACT_PREFIX) :].lower()
        value = value.strip()
        overrides[field] = None if value.lower() == 'none' else value
    return overrides


AUDIO_ENGINE_CONTRACT = resolve_audio_engine_contract(environ)

DB_URL = environ.get('DB_URL')
DB_NAME = environ.get('DB_NAME', 'db')

CELERY_BROKER = environ.get('CELERY_BROKER')
CELERY_BACKEND = environ.get('CELERY_BACKEND')

BUCKET_NAME = resolve_text(environ, 'ALFRED_BUCKET_NAME', 'tower-renders')
DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024  # 5MB

EMAIL_USERNAME = environ.get('EMAIL_USERNAME')
EMAIL_PASSWORD = environ.get('EMAIL_PASSWORD')
EMAIL_SERVER = environ.get('EMAIL_SERVER')
EMAIL_PORT = environ.get('EMAIL_PORT')
EMAIL_SENDTO = environ.get('EMAIL_SENDTO')
if EMAIL_SENDTO:
    EMAIL_SENDTO = EMAIL_SENDTO.split(',')

INVOICE_EMAIL_BODY = '''Please find attached an invoice for this week's renders. 

If you have any questions, feel free to contact us.

Thanks!

~Alfred
alfred.quaternion.media
'''


class CeleryConfig:
    """JSON in both directions, and nothing else accepted (contract C7).

    This was pickle, and unpickling a message runs whatever code it names.
    The broker and the result backend are MongoDB collections, so anyone able
    to write to that database could run code in the worker, and in the api
    through task results. Task arguments are plain data now -- the EDL as a
    dict, ids as strings -- and the worker rebuilds its models from them.

    A task queued as pickle before this change is refused by the worker
    rather than run; re-queue it.
    """

    task_serializer = 'json'
    result_serializer = 'json'
    event_serializer = 'json'
    accept_content = ['json']
    result_accept_content = ['json']

    # How often a process waiting on the MongoDB broker looks for a message,
    # in seconds; kombu's default is 1. `GET /health` counts workers with a
    # Celery ping, and a worker hears a ping the next time it looks -- so at
    # 1 s a reply could take longer than the ping's own one-second timeout,
    # and a running renderer would intermittently be reported missing. Half a
    # second answers well inside it, for one cheap query a second per queue
    # on an idle worker. Queued renders are picked up sooner as well.
    broker_transport_options = {'polling_interval': 0.5}
