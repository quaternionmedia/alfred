import sys
from os import environ
from os.path import join
from tempfile import gettempdir
from urllib.parse import urlsplit

PRODUCTION = environ.get('ALFRED_PRODUCTION')

SECRET_KEY = environ.get('ALFRED_SECRET_KEY')

# Under ALFRED_PRODUCTION, a shorter key is reported as guessable.
MIN_SECRET_KEY_LENGTH = 32


def secret_key_problem(env):
    """What is wrong with ALFRED_SECRET_KEY for this process, or None.

    Unset or empty, anywhere: PyJWT signs nothing, so every login answers 500.
    Shorter than MIN_SECRET_KEY_LENGTH, under ALFRED_PRODUCTION: one token is
    enough to guess it offline. Reported at startup, not enforced; see
    docs/configuration.md#the-signing-key.
    """
    key = env.get('ALFRED_SECRET_KEY')
    if key is None:
        return (
            'ALFRED_SECRET_KEY is not set, so no token can be signed: every '
            'login will fail with a server error.'
        )
    if not key:
        return (
            'ALFRED_SECRET_KEY is empty, and an empty key signs nothing: every '
            'login will fail with a server error. In development, ./al init '
            'gives this checkout a key of its own; in production, export a '
            'random one.'
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
    """`1`, `true`, `yes` or `on`. Anything else is off, `0` and `false`
    included: not `bool(...)`, which reads both as on."""
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _given(value):
    """Set to something: empty or blank counts as unset, the default."""
    return value is not None and str(value).strip() != ''


def resolve_text(env, name, default):
    """`env[name]` stripped, or `default` when unset or empty: an empty path
    is the working directory, which nobody means by emptying a variable."""
    value = env.get(name)
    return str(value).strip() if _given(value) else default


def resolve_seconds(env, name, default):
    """A positive whole number of seconds from `env[name]`, else `default`.

    Anything else (`15m`) is the default too, with a line on stderr: a typo
    neither stops the server nor becomes something nobody asked for.
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
    """As `resolve_seconds`, for a count."""
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
    """Whether `POST /auth/register` creates accounts: open in development,
    closed under ALFRED_PRODUCTION. ALFRED_ALLOW_REGISTRATION overrides either
    way, read as `_truthy`, so an unrecognised value closes it."""
    explicit = env.get('ALFRED_ALLOW_REGISTRATION')
    if _given(explicit):
        return _truthy(explicit)
    return not env.get('ALFRED_PRODUCTION')


ALLOW_REGISTRATION = resolve_allow_registration(environ)


def resolve_dev_skip_auth(env):
    """Whether to serve every request as the dev user.

    Raises with ALFRED_PRODUCTION: a misconfigured production process fails to
    boot rather than come up open (docs/dev-auth.md).
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


# Every caller served as the dev user; off unless asked for.
DEV_SKIP_AUTH = resolve_dev_skip_auth(environ)

# The account the bypass acts as. Reserved, and valid to EmailStr, which few
# reserved addresses are: see docs/dev-auth.md#the-dev-accounts-address.
DEFAULT_DEV_USER_EMAIL = 'dev@example.com'
DEV_USER_EMAIL = resolve_text(environ, 'ALFRED_DEV_USER_EMAIL', DEFAULT_DEV_USER_EMAIL)


def resolve_seed_owner(env):
    """Who owns the projects seeded into an empty database: ALFRED_SEED_OWNER;
    unset, the dev user in development and nobody (superusers only) under
    ALFRED_PRODUCTION."""
    explicit = env.get('ALFRED_SEED_OWNER')
    if _given(explicit):
        return explicit.strip()
    if env.get('ALFRED_PRODUCTION'):
        return None
    return resolve_text(env, 'ALFRED_DEV_USER_EMAIL', DEFAULT_DEV_USER_EMAIL)


SEED_OWNER = resolve_seed_owner(environ)


def resolve_public_url(env):
    """ALFRED_PUBLIC_URL, which account mail links to; never a request's Host
    header, which the asker controls. An http(s) URL with a host, trailing
    slash dropped; anything else is None, and no mail with a link is sent."""
    value = (env.get('ALFRED_PUBLIC_URL') or '').strip().rstrip('/')
    parts = urlsplit(value)
    if parts.scheme not in ('http', 'https') or not parts.netloc:
        return None
    return value


PUBLIC_URL = resolve_public_url(environ)

# The media library: what `GET /videos` lists, and clips name `videos/<file>`.
VIDEO_DIR = environ.get('VIDEO_DIR', 'videos')
STATIC_DIR = environ.get('STATIC_DIR', 'dist')

# Finished renders: in the library mount both containers share, in a
# subdirectory no library route lists or serves.
RENDER_DIR = resolve_text(environ, 'ALFRED_RENDER_DIR', join(VIDEO_DIR, 'renders'))

# Where the `local` destination copies a render. Never under a static mount;
# its link is the download route.
DELIVERY_DIR = resolve_text(environ, 'ALFRED_DELIVERY_DIR', 'deliveries')

# Preview frames, for `GET /preview/frames/{name}` with a session or a signed
# URL (contract M1). Outside every static mount; only the api uses it.
PREVIEW_DIR = environ.get('ALFRED_PREVIEW_DIR') or join(gettempdir(), 'alfred-previews')

# Seconds a preview frame is kept; swept when one is written and at startup.
FRAME_TTL = resolve_seconds(environ, 'ALFRED_FRAME_TTL', 3600)

# Previews drawn at once (`utils.concurrency`). They share AnyIO's forty
# threads with every other route: keep it well under forty.
PREVIEW_CONCURRENCY = resolve_count(environ, 'ALFRED_PREVIEW_CONCURRENCY', 4)

# Seconds a preview waits for a slot before a 503 with Retry-After.
PREVIEW_WAIT = resolve_seconds(environ, 'ALFRED_PREVIEW_WAIT', 10)


# Media otto fetched from a URL (contract M6): hidden in the shared library,
# never listed or served. Set as OTTO_DOWNLOAD_DIR here, before otto is
# imported, so every process agrees.
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

# Seconds fetched media is kept: swept at startup, at most hourly while
# fetching, and by `./al storage cache`.
REMOTE_CACHE_TTL = resolve_seconds(environ, 'ALFRED_REMOTE_CACHE_TTL', 7 * 24 * 3600)

# Seconds a signed media URL works (contract M1); every listing reissues one.
MEDIA_URL_TTL = resolve_seconds(environ, 'ALFRED_MEDIA_URL_TTL', 900)


def parse_hosts(value):
    """A comma-separated host list, normalised for comparison.

    Lowercased and stripped, empty entries dropped. A frozenset so the
    setting cannot be mutated by whatever imports it.
    """
    return frozenset(
        host.strip().lower() for host in (value or '').split(',') if host.strip()
    )


# Hosts a clip may fetch media from; empty, the library only. otto fetches any
# URL it is given, the api's and the worker's own network included.
REMOTE_MEDIA_HOSTS = parse_hosts(environ.get('ALFRED_REMOTE_MEDIA_HOSTS', ''))

# The audio engine's base URL, reached only through `utils.audio_engine`.
# Unset: no engine, and transcribing says so. See docs/captions.md.
AUDIO_ENGINE_URL = (environ.get('ALFRED_AUDIO_ENGINE_URL') or '').strip() or None

# Seconds one engine request may take. Transcribing, on the worker, runs about
# as long as the speech on a CPU: minutes for a long timeline.
AUDIO_ENGINE_TIMEOUT = resolve_seconds(environ, 'ALFRED_AUDIO_ENGINE_TIMEOUT', 1800)

# A field of vox's EngineContract per variable. `none` is None (not offered),
# empty is unset, and a name that is no field is reported by /health.
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

# Seconds each step of sending mail may take; smtplib waits forever without.
SMTP_TIMEOUT = resolve_seconds(environ, 'ALFRED_SMTP_TIMEOUT', 20)

INVOICE_EMAIL_BODY = '''Please find attached an invoice for this week's renders. 

If you have any questions, feel free to contact us.

Thanks!

~Alfred
alfred.quaternion.media
'''


class CeleryConfig:
    """JSON in both directions, nothing else accepted (contract C7): unpickling
    runs code, and anyone who can write the MongoDB broker could send some.
    Task arguments are plain data; the worker rebuilds its models from them.
    """

    task_serializer = 'json'
    result_serializer = 'json'
    event_serializer = 'json'
    accept_content = ['json']
    result_accept_content = ['json']

    # Inside /health's one-second ping timeout; at kombu's default of 1 s a
    # running renderer could read as missing.
    broker_transport_options = {'polling_interval': 0.5}
